#!/usr/bin/env python3
"""Simulador de partida entre dois bots Rage CCG.

Modos de verbosidade:
    verbose=0: só resultado final (quem venceu)
    verbose=1: narrativa (turnos, jogadas importantes, dano, mortes, VP)
    verbose=2: debug completo (tudo, inclusive passes e passos de combate)

Uso:
    python3 match.py                          # hard vs hard, verbose=1
    python3 match.py --p1 easy --p2 easy
    python3 match.py --seed 123 --max-turns 10
    python3 match.py --verbose 2               # debug
    python3 match.py --quiet                   # só resultado
"""

import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rage_web.game_engine.cli import create_sample_game, build_game_from_decks
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.combat_queue import get_declaration_summary, get_combatants
from rage_web.game_engine.state import GameState


# ── Sistema de verbosidade narrativa ──
# verbose=0: só resultado
# verbose=1: narrativa (turnos, jogadas importantes, dano, mortes, VP)
# verbose=2: debug completo (tudo)
_VERBOSE = 1

def vlog(level: int, *args, **kwargs):
    """Log condicional conforme nivel de verbosidade."""
    if level <= _VERBOSE:
        print(*args, **kwargs)

def vsep(level: int, char='━', width=60):
    if level <= _VERBOSE:
        print(char * width)

def set_verbosity(level: int):
    """Altera o nivel de verbosidade global."""
    global _VERBOSE
    _VERBOSE = level


FASE_NOMES = {
    'redraw': 'REDRAW (Compra)',
    'regeneration': 'REGENERACAO',
    'resource': 'RECURSO (Jogar cartas)',
    'umbra': 'UMBRA (Step Sideways)',
    'moot': 'MOOT (Junta)',
    'combat': 'COMBATE',
}

def _log_fase(game, turno, fase):
    """Loga mudanca de fase com destaque e lista HG."""
    nome = FASE_NOMES.get(fase, fase.upper())
    vlog(1, f'\n  ── [{turno}] {nome} ──\n')
    hg_cards = []
    for p in game.players:
        for c in p.hunting_grounds:
            hg_cards.append(f'{c.name}(dono:{p.name})')
    hg_global = getattr(game, 'hunting_grounds_cards', [])
    for c in hg_global:
        hg_cards.append(f'{c.name}(global)')
    if hg_cards and _VERBOSE >= 2:
        vlog(2, f'    🎯 Hunting Grounds: {", ".join(hg_cards)}')


def print_separator(char='━', width=60):
    vlog(1, char * width)


def print_board(game: GameState):
    """Exibe o estado de forma compacta (sempre visivel em verbose>=1)."""
    if _VERBOSE < 1:
        return
    fase_icone = {
        'redraw': '🔄', 'regeneration': '💚', 'resource': '🛠️',
        'umbra': '🌙', 'moot': '🗳️', 'combat': '⚔️',
    }
    icone = fase_icone.get(game.phase, '?')
    vlog(1, f'  ═══ Turno {game.turn_number} {icone} {game.phase.upper()} ═══')
    for p in game.players:
        pack = ', '.join(
            f'{c.name}({c.health_current}/{c.health})'
            for c in p.pack_home
        ) or '—'
        hand = len(p.hand)
        deck_c = len(p.deck_combat)
        deck_s = len(p.deck_sept)
        hg_local = ', '.join(f'{c.name}({c.health_current}/{c.health})' if hasattr(c,'health') and c.health else c.name[:15] for c in p.hunting_grounds) or '—'
        vlog(1, f'  {p.name:20s} 🃏{hand:2d} 📚C{deck_c:2d} S{deck_s:2d} '
              f'🏆{p.victory_points}')
        vlog(1, f'  {" "*20} 🏠 {pack}')
        vlog(1, f'  {" "*20} 🎯 {hg_local}')
    hg_global = getattr(game, 'hunting_grounds_cards', [])
    if hg_global:
        hg_names = ', '.join(
            f'{c.name}({c.health_current}/{c.health})' if hasattr(c,'health') and c.health
            else c.name[:15] for c in hg_global
        )
        vlog(2, f'  {" "*20} 🌍 HG Global: {hg_names}')
    if game.combat.is_active:
        atk = ', '.join(game.combat.attackers)
        dfd = ', '.join(game.combat.defenders)
        vlog(1, f'  ⚔️  COMBATE [{game.combat.step}] {atk} vs {dfd}')
        if _VERBOSE >= 2:
            summary = get_declaration_summary(game)
            if 'declarations' in summary:
                for cid, action in summary['declarations'].items():
                    vlog(2, f'     {cid}: {action}')


def build_game_from_decks_n(*deck_ids: int, seed: int = 42):
    """Converte N decks do banco SQLite em uma partida."""
    from rage_web.game_engine.cli import build_game_from_decks_n as _build_n
    return _build_n(*deck_ids, seed=seed)


def run_match(seed: int = 42, max_turns: int = 30,
              max_steps_override: int | None = None,
              difficulty_p1: str = 'hard',
              difficulty_p2: str = 'hard',
              deck1_id: int | None = None,
              deck2_id: int | None = None,
              delay: float = 0.3,
              # Novos parametros N-player
              deck_ids: list[int] | None = None,
              difficulties: list[str] | None = None,
              vp_to_win: int | None = None,
              verbose: int | None = None) -> str:
    """Roda uma partida entre bots (2 ou mais jogadores).

    Args:
        verbose: 0=só resultado, 1=narrativa, 2=debug.
                 None = usa o nivel global _VERBOSE.
        Demais parametros: vide match.py original.
    """
    global _VERBOSE
    if verbose is not None:
        old_verbose = _VERBOSE
        _VERBOSE = verbose
    else:
        old_verbose = None

    try:
        return _run_match_impl(seed, max_turns, max_steps_override,
                               difficulty_p1, difficulty_p2,
                               deck1_id, deck2_id, delay,
                               deck_ids, difficulties, vp_to_win)
    finally:
        if old_verbose is not None:
            _VERBOSE = old_verbose


def _run_match_impl(seed, max_turns, max_steps_override,
                    difficulty_p1, difficulty_p2,
                    deck1_id, deck2_id, delay,
                    deck_ids, difficulties, vp_to_win):
    """Implementacao interna do loop de partida."""
    # ── Setup ──
    if deck_ids and len(deck_ids) >= 2:
        n_players = len(deck_ids)
        diffs = difficulties or ['hard'] * n_players
        if len(diffs) < n_players:
            diffs = diffs + ['hard'] * (n_players - len(diffs))
        try:
            game = build_game_from_decks_n(*deck_ids, seed=seed)
        except ValueError as e:
            vlog(0, f'Erro ao carregar decks: {e}')
            return 'error'
    elif deck1_id and deck2_id:
        n_players = 2
        diffs = [difficulty_p1, difficulty_p2]
        try:
            game = build_game_from_decks(deck1_id, deck2_id, seed=seed)
        except ValueError as e:
            vlog(0, f'Erro ao carregar decks: {e}')
            return 'error'
    else:
        n_players = 2
        diffs = [difficulty_p1, difficulty_p2]
        game = create_sample_game(seed=seed)

    if vp_to_win is not None:
        for p in game.players:
            p.renown_level = vp_to_win

    bots = {}
    for p in game.players:
        idx = game.players.index(p)
        diff = diffs[idx] if idx < len(diffs) else 'hard'
        bots[p.id] = PriorityBot(game, p.id, difficulty=diff)

    colors = ['\033[1;36m', '\033[1;33m', '\033[1;35m',
              '\033[1;32m', '\033[1;31m', '\033[1;34m']
    reset = '\033[0m'

    # ── Header ──
    vsep(1)
    vlog(1, f'  🎮 RAGE CCG — PARTIDA ENTRE BOTS')
    if deck_ids:
        deck_info = ' | Decks: ' + ', '.join(str(d) for d in deck_ids)
    elif deck1_id and deck2_id:
        deck_info = f' | Decks: {deck1_id} vs {deck2_id}'
    else:
        deck_info = ' | Deck: Sample'
    diffs_str = ', '.join(d.upper() for d in diffs)
    vp_info = ''
    strategy_info = ''
    if game.players:
        vp_strs = [f'J{p.id[-1]}: {p.renown_level}' for p in game.players]
        vp_info = ' | VP: ' + ', '.join(vp_strs)
        strat_strs = [f'{p.name.split(" (")[0]}:{p.deck_strategy}'
                      for p in game.players]
        strategy_info = ' | Estrat: ' + ', '.join(strat_strs)
    vlog(1, f'  {diffs_str}{deck_info} | {n_players} jogadores | '
          f'Max: {max_turns}t{vp_info}{strategy_info}')
    vsep(1)
    if _VERBOSE >= 1:
        print_board(game)

    # ── Variaveis de estado ──
    step = 0
    action_count = 0
    stale_steps = 0
    last_turn = game.turn_number
    last_phase = game.phase
    _displayed_phase = game.phase  # para log de mudanca de fase
    _displayed_turn = game.turn_number
    last_log_len = 0
    max_steps = max_steps_override if max_steps_override else max_turns * 50
    if max_steps_override and _VERBOSE >= 2:
        vlog(2, f'  (max-steps: {max_steps})')
    if _VERBOSE >= 1:
        _log_fase(game, last_turn, last_phase)

    _alpha_order = []
    _alpha_index = 0
    _alpha_map = {}
    _alpha_phase = False

    # ── Loop principal ──
    while step < max_steps:
        if game.phase == 'combat' and game.combat.alpha_order and not _alpha_order:
            _alpha_order = list(game.combat.alpha_order)
            _alpha_index = 0
            _alpha_map = {cid: pid for pid, cid in game.combat.alphas.items()}
            _alpha_phase = True

        # Se o combate acabou, limpa alpha order e deixa o sistema
        # normal de passes resolver a transicao de fase
        if not game.combat.is_active:
            _alpha_order.clear()
            _alpha_index = 0
            _alpha_map.clear()
            _alpha_phase = False

        if _alpha_phase and _alpha_order and _alpha_index < len(_alpha_order):
            # Alpha phase: SEMPRE avanca para o proximo alpha da ordem,
            # independente de combate estar ativo ou nao.
            # Isto garante que ambos os jogadores tenham oportunidade
            # de agir com seus alfas, mesmo se o primeiro ja iniciou combate.
            cid_atual = _alpha_order[_alpha_index]
            dono_id = _alpha_map.get(cid_atual)
            if dono_id:
                cp = next(p for p in game.players if p.id == dono_id)
                game.current_player_index = game.players.index(cp)
            else:
                cp = game.current_player
        else:
            _alpha_phase = False
            cp = game.current_player

        bot = bots[cp.id]
        idx = game.players.index(cp)
        color = colors[idx % len(colors)]

        action = bot.decide()
        action_count += 1

        if _alpha_phase and action and not action.startswith('wait'):
            _alpha_index += 1

        if game.turn_number != last_turn or game.phase != last_phase:
            stale_steps = 0
            if game.phase != 'combat':
                _alpha_order.clear()
                _alpha_index = 0
                _alpha_map.clear()
                _alpha_phase = False
        else:
            stale_steps += 1
        last_phase = game.phase

        if stale_steps > 200:
            vlog(0, f'  ⚠️  TRAVOU ({stale_steps} steps sem progresso)')
            vsep(0)
            if _VERBOSE >= 1:
                print_board(game)
            return 'stuck'

        # ── Exibir acao ──
        if action and not action.startswith('wait'):
            from rage_web.game_engine.action_descriptions import describe_action
            descricao = describe_action(action, game)

            is_pass = action.startswith('pass')
            is_combat_transition = action.startswith('combat_to_')
            is_combat_wait = action == 'combat_wait'
            is_targeting = action.startswith('target_')
            is_reveal = action == 'reveal'
            is_combat_end = action in ('end_combat', 'combat_end')
            is_draw = action == 'draw'

            if _VERBOSE == 1:
                # Modo narrativo: mostra ações relevantes, silencia passes/detalhes de combate
                if not (is_pass or is_combat_transition or is_combat_wait
                        or is_targeting or is_reveal or is_combat_end):
                    print(f'  {color}{cp.name}: {descricao}{reset}')
            elif _VERBOSE >= 2:
                # Modo debug: mostra tudo
                if action.startswith('combat'):
                    print(f'  {color}{cp.name}: ⚔️  {descricao}{reset}')
                elif action.startswith('play_'):
                    print(f'  {color}{cp.name}: 🃏 {descricao}{reset}')
                elif action.startswith('use_'):
                    print(f'  {color}{cp.name}: 🎴 {descricao}{reset}')
                elif action.startswith('attack_') or action.startswith('eliminate_'):
                    print(f'  {color}{cp.name}: ⚔️  {descricao}{reset}')
                elif action.startswith('declare_'):
                    print(f'  {color}{cp.name}: 🗣️  {descricao}{reset}')
                elif action.startswith('feint_'):
                    print(f'  {color}{cp.name}: 🎭 {descricao}{reset}')
                elif action.startswith('umbra_'):
                    print(f'  {color}{cp.name}: 🌙 {descricao}{reset}')
                elif action.startswith('alpha_'):
                    print(f'  {color}{cp.name}: 👑 {descricao}{reset}')
                elif action.startswith('redraw_'):
                    print(f'  {color}{cp.name}: 🔄 {descricao}{reset}')
                elif action.startswith('moot_'):
                    print(f'  {color}{cp.name}: 🗳️  {descricao}{reset}')
                elif action == 'reveal':
                    print(f'  {color}{cp.name}: 👁️  {descricao}{reset}')
                elif action in ('end_combat', 'combat_end'):
                    print(f'  {color}{cp.name}: 🏁 {descricao}{reset}')
                elif action.startswith('target_'):
                    print(f'  {color}{cp.name}: 🎯 {descricao}{reset}')
                elif action == 'combat_wait':
                    print(f'  {color}{cp.name}: ⏳ {descricao}{reset}')
                elif action == 'draw':
                    print(f'  {color}{cp.name}: 📥 COMPRAR{reset}')
                elif action.startswith('pass'):
                    if delay:
                        fase_alvo = action.replace('pass_', '').upper() if action != 'pass' else ''
                        label = f'⏭️  PASSAR {fase_alvo}' if fase_alvo else '⏭️  PASSAR'
                        print(f'  {color}{cp.name}: {label}{reset}')

        # ── Mostrar resultados do game.log ──
        while last_log_len < len(game.log):
            entry = game.log[last_log_len]
            last_log_len += 1
            entry_stripped = entry.strip()
            entry_body = entry_stripped
            if entry_body.startswith('[') and '] ' in entry_body:
                entry_body = entry_body.split('] ', 1)[1]

            if _VERBOSE == 1:
                # Modo narrativo: só resultados críticos
                if 'foi destruido' in entry_body or 'foi eliminado' in entry_body:
                    vlog(1, f'    💀 {entry_stripped}')
                elif 'VP' in entry_body and any(kw in entry_body for kw in ['ganhou', 'recebeu', 'perdeu', 'conquistou']):
                    vlog(1, f'    🏆 {entry_stripped}')
                elif 'regenerou' in entry_body:
                    vlog(1, f'    💚 {entry_stripped}')
                elif 'sofreu' in entry_body and 'dano' in entry_body:
                    vlog(1, f'    💥 {entry_stripped}')
                elif 'causou' in entry_body and 'dano' in entry_body:
                    vlog(1, f'    💥 {entry_stripped}')
                elif 'VENCEU' in entry_body:
                    vlog(0, f'    🏆 {entry_stripped}')
                elif 'anulou' in entry_body:
                    vlog(1, f'    🛡️  {entry_stripped}')
                continue

            # verbose>=2: log completo (comportamento legado)
            if entry_body.startswith('[BOT]'):
                body = entry_body[5:].strip()
                if not body.startswith(('pagou', 'passou', 'selecionou', 'comprou')):
                    if not (('(Rage ' in body or '(Gnosis ' in body) and '):' in body):
                        vlog(2, f'    🤖 {body}')
                continue
            if ' passou' in entry_body or entry_body.startswith('Todos passaram'):
                continue
            if ' selecionou ' in entry_body and ' como alpha' in entry_body:
                continue
            if 'comprou ' in entry_body and 'carta' in entry_body:
                continue
            if ('(Rage ' in entry_body or '(Gnosis ' in entry_body) and '):' in entry_body:
                continue
            if 'pagou' in entry_body and ('Rage' in entry_body or 'Gnosis' in entry_body):
                continue
            if 'usou ' in entry_body and ('(' in entry_body or ')' in entry_body):
                continue
            if ' jogou ' in entry_body:
                continue
            if entry_body.startswith('(') and entry_body.endswith(')'):
                continue
            if not entry_body or entry_body.startswith('━'):
                continue
            if 'foi destruido' in entry_body or 'foi eliminado' in entry_body:
                vlog(1, f'    💀 {entry_stripped}')
            elif 'causou' in entry_body and 'dano' in entry_body:
                vlog(1, f'    💥 {entry_stripped}')
            elif 'usou ' in entry_body and '(dano:' in entry_body:
                vlog(2, f'    ⚔️  {entry_stripped}')
            elif 'atacou Hunting Grounds' in entry_body:
                vlog(2, f'    🎯 {entry_stripped}')
            elif 'sofreu' in entry_body and 'dano' in entry_body:
                vlog(1, f'    💥 {entry_stripped}')
            elif 'VP' in entry_body:
                vlog(1, f'    🏆 {entry_stripped}')
            elif 'regenerou' in entry_body:
                vlog(1, f'    💚 {entry_stripped}')
            elif 'Quest' in entry_body or 'quest' in entry_body:
                vlog(2, f'    📜 {entry_stripped}')
            elif entry_body.startswith('('):
                vlog(2, f'    📝 {entry_stripped}')
            elif 'anulou' in entry_body:
                vlog(1, f'    🛡️  {entry_stripped}')
            elif 'Gauntlet' in entry_body:
                vlog(2, f'    🌐 {entry_stripped}')
            elif 'passiva' in entry_body.lower() or 'registrado' in entry_body:
                continue
            elif 'rage' in entry_body.lower() or 'gnosis' in entry_body.lower():
                if '+' in entry_body or '-' in entry_body:
                    vlog(2, f'    📊 {entry_stripped}')
            elif 'Feint' in entry_body:
                continue
            elif 'Acoes reveladas' in entry_body:
                continue
            elif 'Resolvendo combate' in entry_body:
                continue
            elif entry_body.startswith('Resolucao por velocidade'):
                vlog(2, f'    ⚡ {entry_stripped}')
            elif entry_body.startswith('[Fim'):
                vlog(2, f'    ⚡ {entry_stripped}')
            else:
                if any(kw in entry_body for kw in ['regenera', 'imune', 'ataque', 'dano', 'cura', 'morte', 'Wyldstorm', 'Frenar', 'Combate iniciado']):
                    vlog(2, f'    📋 {entry_stripped}')

        # Tabuleiro periodico (só verbose>=2)
        if _VERBOSE >= 2 and action_count % 4 == 0 and not game.combat.is_active and delay:
            vsep(2, '-')
            print_board(game)
            time.sleep(delay * 2)

        # ── Verificar fim ──
        if game.turn_number > max_turns:
            vsep(0)
            vlog(0, f'⏰ LIMITE DE TURNOS ({max_turns}) ATINGIDO')
            return 'timeout'

        from rage_web.game_engine.combat_queue import _tem_character, _eliminar_jogador
        if game.turn_number > 1:
            for p in game.players:
                if not _tem_character(p) and not getattr(p, 'eliminado', False):
                    _eliminar_jogador(game, p)
                    vsep(0)
                    vlog(0, f'💀 {p.name} foi eliminado! (sem Characters em jogo)')

        jogadores_ativos = [p for p in game.players if not getattr(p, 'eliminado', False)]
        if len(jogadores_ativos) == 1:
            p = jogadores_ativos[0]
            vsep(0)
            vlog(0, f'🏆 {p.name} VENCEU! (unico jogador com Characters em jogo)')
            return p.id
        if len(jogadores_ativos) == 0:
            vsep(0)
            vlog(0, '💀 Todos os jogadores foram eliminados! Empate.')
            return 'draw'

        for p in jogadores_ativos:
            if p.victory_points >= p.renown_level:
                vsep(0)
                vlog(0, f'🏆 {p.name} VENCEU! ({p.victory_points}/{p.renown_level} VP)')
                return p.id

        # Tabuleiro na mudanca de fase/turno
        if game.phase != _displayed_phase or game.turn_number != _displayed_turn:
            if game.turn_number != _displayed_turn and _VERBOSE >= 1:
                vlog(1, f'\n  ════ TURNO {game.turn_number} ════\n')
            if _VERBOSE >= 1:
                _log_fase(game, game.turn_number, game.phase)
                vsep(1, '-', 40)
                print_board(game)
            time.sleep(delay)
            _displayed_turn = game.turn_number
            _displayed_phase = game.phase

        step += 1

    vsep(0)
    vlog(0, f'⏰ STEPS EXCEDIDOS ({max_steps})')
    return 'timeout'


def main():
    parser = argparse.ArgumentParser(
        description='Simulador de partida Rage CCG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Exemplos:
  rage-match --deck 416 --deck 7                    # 2 jogadores
  rage-match --deck 416 --deck 90 --deck 7           # 3 jogadores
  rage-match --verbose 2                             # debug completo
  rage-match --quiet                                 # só resultado
''')
    parser.add_argument('--p1', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--p2', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-turns', type=int, default=30)
    parser.add_argument('--max-steps', type=int, default=0)
    parser.add_argument('--deck1', type=int, default=None)
    parser.add_argument('--deck2', type=int, default=None)
    parser.add_argument('--delay', type=float, default=0.3)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--deck', type=int, action='append')
    parser.add_argument('--diff', type=str, action='append',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--vp', type=int, default=None)
    parser.add_argument('--verbose', type=int, default=1, choices=[0, 1, 2],
                        help='0=só resultado, 1=narrativa, 2=debug')
    parser.add_argument('--quiet', action='store_true',
                        help='Equivalente a --verbose 0')
    args = parser.parse_args()

    if args.quiet:
        verbosity = 0
    else:
        verbosity = args.verbose

    max_steps_override = args.max_steps if args.max_steps > 0 else None
    delay = args.delay if args.watch else 0

    if args.deck and len(args.deck) >= 2:
        result = run_match(
            seed=args.seed, max_turns=args.max_turns,
            max_steps_override=max_steps_override, delay=delay,
            deck_ids=args.deck, difficulties=args.diff,
            vp_to_win=args.vp, verbose=verbosity,
        )
    else:
        result = run_match(
            seed=args.seed, max_turns=args.max_turns,
            max_steps_override=max_steps_override,
            difficulty_p1=args.p1, difficulty_p2=args.p2,
            deck1_id=args.deck1, deck2_id=args.deck2,
            delay=delay, vp_to_win=args.vp, verbose=verbosity,
        )

    vlog(0, f'Resultado: {result}')


if __name__ == '__main__':
    main()
