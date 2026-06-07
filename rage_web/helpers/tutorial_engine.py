"""Motor de tutorial: captura o estado do jogo turno a turno para exibir em pagina web."""

from __future__ import annotations
import copy
from dataclasses import dataclass, field
from typing import Any, Optional

from rage_web.game_engine.state import GameState, Zone
from rage_web.game_engine.match import build_game_from_decks_n
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.combat_queue import verificar_vitoria, _tem_character
from rage_web.game_engine.action_descriptions import describe_action


@dataclass
class PhaseSnapshot:
    """Captura de uma fase do jogo."""
    turno: int
    fase: str
    descricao_fase: str
    board_state: dict[str, Any]
    acoes: list[dict[str, str]]
    narrativa: str
    eventos_especiais: list[str] = field(default_factory=list)


@dataclass
class TutorialData:
    """Dados completos do tutorial."""
    jogadores: list[dict[str, Any]]
    turnos: list[list[PhaseSnapshot]]
    resumo_final: dict[str, Any]
    regras_demonstradas: list[str]


FASE_DESCRICOES = {
    'redraw': '🔄 Redraw — Comprar cartas',
    'regeneration': '💚 Regeneration — Regeneração',
    'resource': '🛠️ Resource — Jogar recursos',
    'umbra': '🌙 Umbra — Step Sideways',
    'moot': '🗳️ Moot — Juntas e votação',
    'combate': '⚔️ Combate — Lutar!',
}

JOGADOR_CORES = {
    0: {'nome': 'Azul', 'classe': 'is-info', 'emoji': '🔵'},
    1: {'nome': 'Amarelo', 'classe': 'is-warning', 'emoji': '🟡'},
    2: {'nome': 'Roxo', 'classe': 'is-link', 'emoji': '🟣'},
}

NARRATIVAS = {
    'redraw': [
        "Sua mão se enche de cartas. É hora de se preparar para o que vem pela frente.",
        "Novas oportunidades surgem a cada compra. O que o destino reserva?",
        "As cartas fluem. Cada uma pode ser a diferença entre a glória e a derrota.",
    ],
    'regeneration': [
        "Seus personagens se curam. A vitalidade retorna aos seus corpos.",
        "A regeneração é um presente dos ancestrais. Seus personagens se fortalecem.",
        "Feridas cicatrizam. Seus guerreiros estão prontos para o próximo desafio.",
    ],
    'resource': [
        "É hora de jogar suas cartas de recurso. Cada carta colocada na mesa é um passo rumo à vitória.",
        "Territórios, aliados, equipamentos — o tabuleiro se enriquece com suas ações.",
        "Você joga suas cartas com estratégia. Cada recurso conta.",
    ],
    'umbra': [
        "A Umbra chama. Seus personagens podem atravessar para o mundo espiritual.",
        "Step sideways — seus guerreiros entram na Umbra, fora do alcance dos inimigos.",
        "A fronteira entre mundos se dissolve. Seus personagens se movem entre dimensões.",
    ],
    'moot': [
        "As Juntas são convocadas! É hora de votar. Seus votos podem mudar o destino da partida.",
        "A democracia dos Garou. Cada voto conta. Cada decisão importa.",
        "Juntas são o coração político do jogo. Use seus votos com sabedoria.",
    ],
    'combate': [
        "O combate começa! Seus personagens enfrentam os inimigos. Que os ancestrais os protejam.",
        "Garras e presas se chocam. O campo de batalha é um lugar de glória e sacrifício.",
        "A fúria da batalha toma conta. Cada personagem luta por sua tribo.",
    ],
}


def _formatar_zona(cartas: list) -> list[dict]:
    resultado = []
    for c in cartas:
        tipo = c.card_type or 'Unknown'
        nome = c.name
        vida = f"{c.health_current}/{c.health}" if c.health > 0 else "-"
        resultado.append({
            'nome': nome,
            'tipo': tipo,
            'vida': vida,
            'tapada': c.is_tapped,
            'display': f"{nome} ({vida}){' 🔒' if c.is_tapped else ''}",
        })
    return resultado


def _capturar_board(game: GameState) -> dict[str, Any]:
    jogadores = []
    for idx, p in enumerate(game.players):
        cor = JOGADOR_CORES.get(idx, {'nome': 'Cinza', 'classe': '', 'emoji': '⚪'})
        jogadores.append({
            'id': p.id,
            'nome': p.name,
            'cor': cor,
            'vp': p.victory_points,
            'vp_necessario': p.renown_level,
            'vp_barra': min(100, int(p.victory_points / max(p.renown_level, 1) * 100)),
            'mao': len(p.hand),
            'deck_combat': len(p.deck_combat),
            'deck_sept': len(p.deck_sept),
            'pack_home': _formatar_zona(p.pack_home),
            'hunting_grounds': _formatar_zona(p.hunting_grounds),
            'umbra': _formatar_zona(p.umbra),
            'discard_combat': len(p.discard_combat),
            'discard_sept': len(p.discard_sept),
            'victory_pile': len(p.victory_pile),
            'eliminado': getattr(p, 'eliminado', False),
        })

    hg_global = []
    for c in getattr(game, 'hunting_grounds_cards', []):
        hg_global.append({
            'nome': c.name,
            'tipo': c.card_type or 'Unknown',
            'vida': f"{c.health_current}/{c.health}" if c.health > 0 else "-",
        })

    combate = None
    if game.combat.is_active:
        combate = {
            'step': game.combat.step,
            'attackers': game.combat.attackers,
            'defenders': game.combat.defenders,
        }

    return {
        'jogadores': jogadores,
        'hg_global': hg_global,
        'combate': combate,
        'turno': game.turn_number,
        'fase': game.phase,
    }


def _detectar_eventos(game: GameState, prev_board: Optional[dict]) -> list[str]:
    eventos = []
    if prev_board is None:
        return eventos
    for j_atual in game.players:
        j_prev = None
        for pj in prev_board.get('jogadores', []):
            if pj['id'] == j_atual.id:
                j_prev = pj
                break
        if j_prev is None:
            continue
        vp_diff = j_atual.victory_points - j_prev['vp']
        if vp_diff > 0:
            eventos.append(f"{j_atual.name} ganhou {vp_diff} VP!")
        if getattr(j_atual, 'eliminado', False) and not j_prev.get('eliminado', False):
            eventos.append(f"💀 {j_atual.name} foi eliminado!")
    return eventos


def _classificar_acao(acao: str) -> str:
    if acao.startswith('moot_'):
        return 'moot'
    elif acao.startswith('combat') or acao.startswith('attack') or acao.startswith('eliminate') or acao.startswith('declare') or acao.startswith('feint'):
        return 'combate'
    elif acao.startswith('umbra_'):
        return 'umbra'
    elif acao.startswith('play_') or acao.startswith('use_'):
        return 'resource'
    elif acao.startswith('redraw_') or acao.startswith('draw'):
        return 'redraw'
    elif acao.startswith('pass'):
        return 'pass'
    return 'outro'


def _gerar_narrativa(fase: str, turno: int) -> str:
    import random
    opcoes = NARRATIVAS.get(fase, ["A partida continua..."])
    return random.choice(opcoes)


def run_tutorial(deck_ids: list[int], seed: int = 42, max_turns: int = 5,
                 vp_to_win: int | None = None) -> TutorialData:
    """Executa uma partida de tutorial capturando todos os estados do jogo."""
    game = build_game_from_decks_n(*deck_ids, seed=seed)

    if vp_to_win is not None:
        for p in game.players:
            p.renown_level = vp_to_win

    bots = {}
    for idx, p in enumerate(game.players):
        bots[p.id] = PriorityBot(game, p.id, difficulty='hard')

    jogadores_info = []
    for idx, p in enumerate(game.players):
        cor = JOGADOR_CORES.get(idx, {'nome': 'Cinza', 'classe': '', 'emoji': '⚪'})
        num_chars = len([c for c in p.pack_home if 'Character' in (c.card_type or '')])
        jogadores_info.append({
            'id': p.id,
            'nome': p.name,
            'cor': cor,
            'deck_id': deck_ids[idx] if idx < len(deck_ids) else 0,
            'num_personagens': num_chars,
            'renome_level': p.renown_level,
        })

    prev_board = None
    regras_demonstradas = set()

    # Estrutura: turnos[turno_idx][fase_idx] = PhaseSnapshot
    turnos_snapshots = []  # lista de turnos, cada turno é lista de fases
    turno_atual_fases = []  # fases do turno atual
    fase_atual_acoes = []  # ações da fase atual
    fase_atual_raw = []  # ações raw da fase atual

    max_steps = max_turns * 50
    step = 0
    last_turn = game.turn_number
    last_phase = game.phase

    while step < max_steps:
        # Detectar mudança de fase
        if game.phase != last_phase or game.turn_number != last_turn:
            # Salvar snapshot da fase que acabou
            if fase_atual_acoes or True:  # Salvar mesmo sem ações
                board = _capturar_board(game)
                eventos = _detectar_eventos(game, prev_board)
                prev_board = copy.deepcopy(board)

                for acao_raw in fase_atual_raw:
                    tipo = _classificar_acao(acao_raw)
                    if tipo != 'outro' and tipo != 'pass':
                        regras_demonstradas.add(tipo)

                snapshot = PhaseSnapshot(
                    turno=last_turn,
                    fase=last_phase,
                    descricao_fase=FASE_DESCRICOES.get(last_phase, last_phase),
                    board_state=board,
                    acoes=list(fase_atual_acoes),  # cópia
                    narrativa=_gerar_narrativa(last_phase, last_turn),
                    eventos_especiais=eventos,
                )
                turno_atual_fases.append(snapshot)

            # Se mudou de turno, salvar turno anterior
            if game.turn_number != last_turn and turno_atual_fases:
                turnos_snapshots.append(turno_atual_fases)
                turno_atual_fases = []

            # Reset para nova fase
            fase_atual_acoes = []
            fase_atual_raw = []
            last_turn = game.turn_number
            last_phase = game.phase

        # Alpha actions no combate
        if game.phase == 'combat' and game.combat.alpha_order:
            if game.combat.current_alpha_index < len(game.combat.alpha_order):
                cid_atual = game.combat.current_alpha
                dono_id = None
                for pid, cid in game.combat.alphas.items():
                    if cid == cid_atual:
                        dono_id = pid
                        break
                if dono_id:
                    cp = next(p for p in game.players if p.id == dono_id)
                    game.current_player_index = game.players.index(cp)
                else:
                    cp = game.current_player
            else:
                cp = game.current_player
        else:
            cp = game.current_player

        bot = bots[cp.id]
        action = bot.decide()

        # Capturar ação para a fase atual
        if action and not action.startswith('wait'):
            descricao = describe_action(action, game)
            acao_formatada = {
                'jogador': cp.name,
                'jogador_id': cp.id,
                'acao': action,
                'descricao': descricao,
                'tipo': _classificar_acao(action),
            }
            fase_atual_acoes.append(acao_formatada)
            fase_atual_raw.append(action)

        # Verificar condições de fim
        if game.turn_number > max_turns:
            break

        # Verificar vitória
        for p in game.players:
            if p.victory_points >= p.renown_level:
                # Salvar última fase
                board = _capturar_board(game)
                eventos = _detectar_eventos(game, prev_board)
                snapshot = PhaseSnapshot(
                    turno=game.turn_number,
                    fase=game.phase,
                    descricao_fase=FASE_DESCRICOES.get(game.phase, game.phase),
                    board_state=board,
                    acoes=list(fase_atual_acoes),
                    narrativa=f"🏆 {p.name} atingiu {p.victory_points} VP e venceu!",
                    eventos_especiais=eventos + [f"🏆 {p.name} VENCEU!"],
                )
                turno_atual_fases.append(snapshot)
                turnos_snapshots.append(turno_atual_fases)
                break

        # Regra 2.3: eliminação
        if game.turn_number > 1:
            for p in game.players:
                if not _tem_character(p) and not getattr(p, 'eliminado', False):
                    from rage_web.game_engine.combat_queue import _eliminar_jogador
                    _eliminar_jogador(game, p)
                    regras_demonstradas.add('eliminacao')

        step += 1

    # Salvar último turno se não foi salvo
    if turno_atual_fases:
        turnos_snapshots.append(turno_atual_fases)

    # Resumo final
    vencedor = None
    for p in game.players:
        if p.victory_points >= p.renown_level:
            vencedor = p
            break
    if vencedor is None:
        ativos = [p for p in game.players if not getattr(p, 'eliminado', False)]
        if len(ativos) == 1:
            vencedor = ativos[0]

    resumo = {
        'vencedor': vencedor.name if vencedor else 'Empate',
        'vencedor_id': vencedor.id if vencedor else None,
        'turnos_jogados': len(turnos_snapshots),
        'jogadores': [
            {
                'nome': p.name,
                'vp_final': p.victory_points,
                'eliminado': getattr(p, 'eliminado', False),
            }
            for p in game.players
        ],
    }

    return TutorialData(
        jogadores=jogadores_info,
        turnos=turnos_snapshots,
        resumo_final=resumo,
        regras_demonstradas=sorted(regras_demonstradas),
    )


def tutorial_to_dict(data: TutorialData) -> dict:
    """Converte TutorialData para dicionário serializável."""
    return {
        'jogadores': data.jogadores,
        'turnos': [
            [
                {
                    'turno': s.turno,
                    'fase': s.fase,
                    'descricao_fase': s.descricao_fase,
                    'board': s.board_state,
                    'acoes': s.acoes,
                    'narrativa': s.narrativa,
                    'eventos': s.eventos_especiais,
                }
                for s in turno
            ]
            for turno in data.turnos
        ],
        'resumo': data.resumo_final,
        'regras': data.regras_demonstradas,
    }
