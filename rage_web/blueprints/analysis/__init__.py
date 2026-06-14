"""Blueprint de análise de partidas.

Permite configurar uma partida (decks, seed, turnos máximos) e
navegar turno a turno, fase a fase, inspecionando o estado completo
do jogo em cada ponto.
"""

from __future__ import annotations

import os
import uuid
import copy
from dataclasses import dataclass, field
from typing import Optional

from flask import (
    Blueprint, current_app, jsonify, redirect,
    render_template, request, session, url_for,
)

from rage_web.ext.database import db
from rage_web.ext.repository import find_all_decks
from rage_web.models.card import Card
from rage_web.models.deck import Deck
from rage_web.game_engine.cli import build_game_from_decks
from rage_web.game_engine.state import GameState, Zone
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.combat_queue import (
    get_declaration_summary,
)
from sqlalchemy import text


bp = Blueprint('analysis', __name__, template_folder='templates',
               url_prefix='/analysis')

# ── Estados de partida armazenados ──
# game_id -> { 'states': [...], 'meta': {...} }


class Snapshot:
    """Estado congelado de uma partida num dado turno/fase.

    O log contém APENAS as entradas desde o snapshot anterior
    (log_offset controla o ponto de corte).
    """
    def __init__(self, game: GameState, turn: int, phase: str,
                 log_offset: int = 0):
        self.turn = turn
        self.phase = phase
        self.players = []
        for p in game.players:
            self.players.append({
                'id': p.id,
                'name': p.name,
                'victory_points': p.victory_points,
                'hand': [_card_info(c) for c in p.hand],
                # Separa Events e Gifts como efeitos ativos
                'active_effects': [
                    _card_info(c) for c in p.pack_home
                    if (c.card_type or '') == 'Event'
                ],
                'active_gifts': [
                    _card_info(c) for c in p.pack_home
                    if (c.card_type or '') == 'Gift'
                ],
                'pack_home': [
                    _card_info(c) for c in p.pack_home
                    if (c.card_type or '') not in ('Event', 'Gift')
                ],
                'umbra': [_card_info(c) for c in p.umbra],
                'hunting_grounds': [_card_info(c) for c in p.hunting_grounds],
                'victory_pile': [_card_info(c) for c in p.victory_pile],
                'discard_combat': [_card_info(c) for c in p.discard_combat],
                'discard_sept': [_card_info(c) for c in p.discard_sept],
                'out_of_play': [_card_info(c) for c in p.out_of_play],
                'deck_combat_count': len(p.deck_combat),
                'deck_sept_count': len(p.deck_sept),
                'rage_pool': p.rage_pool,
                'gnosis_pool': p.gnosis_pool,
            })
        # Hunting Grounds unificado: neutro + todos os jogadores
        todas_hg = list(game.hunting_grounds_cards)
        for p in game.players:
            todas_hg.extend(p.hunting_grounds)
        self.hunting_grounds_cards = [_card_info(c) for c in todas_hg]
        # Combat
        self.combat = {
            'is_active': game.combat.is_active,
            'step': game.combat.step,
            'attackers': game.combat.attackers,
            'defenders': game.combat.defenders,
            'declarations': dict(game.combat.declarations),
            'last_to_declare': game.combat.last_to_declare,
            'alphas': dict(game.combat.alphas),
            # player_id -> alpha card_id
            'alpha_order': list(game.combat.alpha_order),
            # order by renown
            'current_alpha_index': game.combat.current_alpha_index,
        }
        # Log entries APENAS desde o snapshot anterior
        log_full = list(game.log) if hasattr(game, 'log') else []
        self.log = log_full[log_offset:]


def _card_info(c) -> dict:
    """Serializa uma CardInstance para o template."""
    info = {
        'card_id': getattr(c, 'card_id', 0),
        'name': getattr(c, 'name', '?'),
        'card_type': getattr(c, 'card_type', ''),
        'rage': getattr(c, 'rage', 0),
        'gnosis': getattr(c, 'gnosis', 0),
        'health': getattr(c, 'health', 0),
        'health_current': getattr(c, 'health_current', getattr(c, 'health', 0)),
        'renown': getattr(c, 'renown', 0),
        'tapped': getattr(c, 'tapped', False),
        'face_down': getattr(c, 'face_down', False),
        'damage': getattr(c, 'damage', ''),
        'requires': getattr(c, 'requires', ''),
        'keywords': getattr(c, 'keywords', []),
        'text': getattr(c, 'text', ''),
        # Estatísticas efetivas (com buffs)
        'rage_efetivo': getattr(c, 'rage_efetivo', getattr(c, 'rage', 0)),
        'gnosis_efetivo': getattr(c, 'gnosis_efetivo', getattr(c, 'gnosis', 0)),
        'health_max_efetivo': getattr(c, 'health_max_efetivo', getattr(c, 'health', 0)),
        # Buffs (só se > 0)
        'buff_rage': getattr(c, 'buff_rage', 0),
        'buff_gnosis': getattr(c, 'buff_gnosis', 0),
        'buff_health': getattr(c, 'buff_health', 0),
        'buff_reducao_dano': getattr(c, 'buff_reducao_dano', 0),
        'buff_dano_proximo_ataque': getattr(c, 'buff_dano_proximo_ataque', 0),
        'buff_dano_agravado': getattr(c, 'buff_dano_agravado', 0),
        # Modificadores
        'modifiers': getattr(c, 'modifiers', {}),
        # Dano anexado
        'total_dano_anexado': getattr(c, 'total_dano', 0),
        'damage_cards_count': len(getattr(c, 'damage_cards', [])),
        # Equipamentos anexados
        'attached_equipment': [
            {
                'card_id': getattr(eq, 'card_id', 0),
                'name': getattr(eq, 'name', '?'),
                'card_type': getattr(eq, 'card_type', ''),
                'keywords': getattr(eq, 'keywords', []),
            }
            for eq in getattr(c, 'attached_equipment', [])
        ],
        # Gifts permanentes anexados
        'attached_gifts': [
            {
                'card_id': getattr(g, 'card_id', 0),
                'name': getattr(g, 'name', '?'),
                'card_type': getattr(g, 'card_type', ''),
                'keywords': getattr(g, 'keywords', []),
            }
            for g in getattr(c, 'attached_gifts', [])
        ],
    }
    return info


# ── Cache de partidas analisadas ──
_analyses: dict[str, dict] = {}


def _calc_deck_renown(deck_id: int) -> int:
    """Calcula o renome total de personagens de um deck."""
    result = db.session.execute(text('''
        SELECT COALESCE(SUM(c.renown * dc.quantity), 0)
        FROM deck_cards dc
        JOIN card c ON c.id = dc.card_id
        WHERE dc.deck_id = :did AND c.tipo LIKE '%Character%'
    '''), {'did': deck_id}).scalar()
    return result or 0


def _get_decks_with_renown() -> list[dict]:
    """Retorna lista de decks com nome + renome total formatado."""
    decks = find_all_decks()
    result = []
    for d in decks:
        renown = _calc_deck_renown(d.id)
        result.append({
            'id': d.id,
            'name': d.name,
            'renown': renown,
            'label': f'{d.name} [{renown} ren]',
        })
    return sorted(result, key=lambda x: x['name'])


# ── Rotas ──

@bp.route('/')
def new_analysis():
    """Formulário para configurar a análise."""
    decks = _get_decks_with_renown()
    ultimos = {
        'deck1': session.get('ultimos_deck1'),
        'deck2': session.get('ultimos_deck2'),
    }
    return render_template('analysis/new.html',
                           decks=decks,
                           ultimos=ultimos)


@bp.route('/run', methods=['POST'])
def run_analysis():
    """Executa a partida programaticamente e captura snapshots."""
    deck1_id = request.form.get('deck1', type=int)
    deck2_id = request.form.get('deck2', type=int)
    seed = request.form.get('seed', 42, type=int)
    max_turns = request.form.get('max_turns', 30, type=int)
    p1_name = request.form.get('p1_name', 'Jogador 1')
    p2_name = request.form.get('p2_name', 'Jogador 2')

    # Cria partida
    try:
        game = build_game_from_decks(deck1_id, deck2_id, seed=seed)
    except Exception as e:
        return f'Erro ao criar partida: {e}', 400

    if len(game.players) >= 1:
        game.players[0].name = p1_name
    if len(game.players) >= 2:
        game.players[1].name = p2_name

    game_id = str(uuid.uuid4())[:8]
    states = []
    log_offset = 0

    # Cria bots
    bots = {}
    for p in game.players:
        bots[p.id] = PriorityBot(game, p.id, difficulty='hard')

    # Snapshots iniciais: cada fase do turno 1
    log_offset = _capture_state(game, states, log_offset)

    # Loop principal para avançar a partida
    stale = 0
    last_turn = game.turn_number
    last_phase = game.phase
    max_steps = max_turns * 200  # Margem segura para ações por turno
    step = 0
    _alpha_order = []
    _alpha_index = 0
    _alpha_map = {}
    _alpha_phase = False

    from rage_web.game_engine.combat_queue import (
        _tem_character, _eliminar_jogador
    )

    while step < max_steps:
        # Gerenciamento de alphas (mesma lógica do match.py)
        if game.phase == 'combat' and game.combat.alpha_order and not _alpha_order:
            _alpha_order = list(game.combat.alpha_order)
            _alpha_index = 0
            _alpha_map = {cid: pid for pid, cid in game.combat.alphas.items()}
            _alpha_phase = True

        if _alpha_phase and _alpha_order and _alpha_index < len(_alpha_order):
            if not game.combat.is_active:
                cid_atual = _alpha_order[_alpha_index]
                dono_id = _alpha_map.get(cid_atual)
                if dono_id:
                    cp = next(p for p in game.players if p.id == dono_id)
                    game.current_player_index = game.players.index(cp)
                else:
                    cp = game.current_player
            else:
                cp = game.current_player
        else:
            _alpha_phase = False
            cp = game.current_player

        bot = bots.get(cp.id)
        if not bot:
            break

        try:
            action = bot.decide()
        except Exception:
            break

        if _alpha_phase and action and not action.startswith('wait'):
            _alpha_index += 1

        # Detecta mudança de fase/turno
        if game.turn_number != last_turn or game.phase != last_phase:
            stale = 0
            if game.phase != 'combat':
                _alpha_order.clear()
                _alpha_index = 0
                _alpha_map.clear()
                _alpha_phase = False
            # Captura snapshot ao mudar de fase
            log_offset = _capture_state(game, states, log_offset)
        else:
            stale += 1
        last_phase = game.phase

        # Se ficou muito tempo sem mudar de fase (ex: combate longo),
        # aumenta o limite em vez de abortar
        if stale > 500:
            stale = 0  # Reseta para permitir mais ações

        # Verifica condições de fim
        if game.turn_number > 1:
            for p in game.players:
                if not _tem_character(p) and not getattr(p, 'eliminado', False):
                    _eliminar_jogador(game, p)

        jogadores_ativos = [p for p in game.players
                            if not getattr(p, 'eliminado', False)]
        if len(jogadores_ativos) <= 1:
            _capture_state(game, states, log_offset)
            break

        # Verifica vitoria
        venceu = False
        for p in jogadores_ativos:
            if p.victory_points >= p.renown_level:
                _capture_state(game, states, log_offset)
                venceu = True
                break
        if venceu:
            break

        # Verifica limite de turnos (USANDO max_turns corretamente)
        if game.turn_number > max_turns:
            _capture_state(game, states, log_offset)
            break

        step += 1

    # Armazena (inclui log completo para export)
    full_log = list(game.log)
    _analyses[game_id] = {
        'meta': {
            'deck1_id': deck1_id,
            'deck2_id': deck2_id,
            'p1_name': p1_name,
            'p2_name': p2_name,
            'seed': seed,
            'max_turns': max_turns,
        },
        'states': states,
        'total_states': len(states),
        'full_log': full_log,
    }
    # Salva decks da última análise na sessão (persiste entre requests)
    session['ultimos_deck1'] = deck1_id
    session['ultimos_deck2'] = deck2_id

    return redirect(url_for('analysis.view_state',
                            game_id=game_id, state_index=0))


def _capture_state(game, states, log_offset: int) -> int:
    """Cria um snapshot do estado atual e retorna o novo offset do log."""
    snap = Snapshot(game, game.turn_number, game.phase, log_offset)
    states.append(snap)
    return len(game.log)


@bp.route('/<game_id>/<int:state_index>')
def view_state(game_id: str, state_index: int):
    """Exibe um snapshot específico da partida."""
    analysis = _analyses.get(game_id)
    if not analysis:
        return render_template('errors/404.html',
                               message='Análise não encontrada'), 404

    states = analysis['states']
    if state_index < 0 or state_index >= len(states):
        return render_template('errors/404.html',
                               message='Estado não encontrado'), 404

    snap = states[state_index]
    meta = analysis['meta']

    # Deck names
    deck1 = Deck.query.get(meta['deck1_id'])
    deck2 = Deck.query.get(meta['deck2_id'])

    # --- Turn-based navigation ---
    # Constroi indice: primeiro snapshot de cada turno
    turn_starts = {}  # turn_number -> state_index
    for i, s in enumerate(states):
        tn = s.turn
        if tn not in turn_starts:
            turn_starts[tn] = i
    sorted_turns = sorted(turn_starts.keys())
    current_turn = snap.turn
    current_turn_idx = sorted_turns.index(current_turn) if current_turn in sorted_turns else 0
    total_turns = len(sorted_turns)
    first_of_current_turn = turn_starts.get(current_turn, 0)
    last_of_current_turn = next(
        (turn_starts[t] for t in sorted_turns if t > current_turn),
        len(states)
    ) - 1
    # Indices dos turnos adjacentes
    prev_turn_idx = sorted_turns[current_turn_idx - 1] if current_turn_idx > 0 else None
    next_turn_idx = sorted_turns[current_turn_idx + 1] if current_turn_idx < total_turns - 1 else None

    # ── State comparison (diff com snapshot anterior) ──
    prev_snap = states[state_index - 1] if state_index > 0 else None
    diff = _compute_diff(prev_snap, snap) if prev_snap else None

    return render_template('analysis/view.html',
                           game_id=game_id,
                           state=snap,
                           state_index=state_index,
                           total_states=len(states),
                           turn_starts=turn_starts,
                           current_turn=current_turn,
                           total_turns=total_turns,
                           first_of_current_turn=first_of_current_turn,
                           last_of_current_turn=last_of_current_turn,
                           prev_turn_idx=prev_turn_idx,
                           next_turn_idx=next_turn_idx,
                           diff=diff,
                           meta=meta,
                           deck1_name=deck1.name if deck1 else '?',
                           deck2_name=deck2.name if deck2 else '?',
                           player_count=len(snap.players),
                           get_card_image_url=_get_card_img_url)


def _compute_diff(prev: Snapshot, cur: Snapshot) -> dict:
    """Compara dois snapshots e retorna mudancas visuais.

    Returns dict com:
    - 'victory_points': {player_id: (antes, depois)}
    - 'novas_cartas': {player_id: [lista de nomes]} (cartas que apareceram)
    - 'cartas_removidas': {player_id: [lista de nomes]}
    - 'dano_tomado': {player_id: [(nome, antes_hp, depois_hp)]}
    - 'nova_fase': (antes, depois)
    - 'combate_iniciado': bool
    - 'combate_terminou': bool
    """
    diff = {
        'victory_points': {},
        'novas_cartas': {},
        'cartas_removidas': {},
        'dano_tomado': {},
        'fase': (prev.phase, cur.phase),
        'turno': (prev.turn, cur.turn),
        'combate_iniciado': False,
        'combate_terminou': False,
    }

    if not prev.combat.get('is_active') and cur.combat.get('is_active'):
        diff['combate_iniciado'] = True
    if prev.combat.get('is_active') and not cur.combat.get('is_active'):
        diff['combate_terminou'] = True

    # Compara jogadores
    prev_players = {p['id']: p for p in prev.players}
    cur_players = {p['id']: p for p in cur.players}

    for pid, cp in cur_players.items():
        pp = prev_players.get(pid)
        if not pp:
            continue

        # VP
        if cp['victory_points'] != pp['victory_points']:
            diff['victory_points'][pid] = (
                pp['victory_points'], cp['victory_points'])

        # Novas cartas no pack_home
        prev_names = {c['name'] + str(c['card_id']) for c in pp.get('pack_home', [])}
        cur_names = {c['name'] + str(c['card_id']) for c in cp.get('pack_home', [])}
        novas = cur_names - prev_names
        removidas = prev_names - cur_names
        if novas:
            diff['novas_cartas'][pid] = list(novas)
        if removidas:
            diff['cartas_removidas'][pid] = list(removidas)

        # Dano tomado (health_current mudou)
        dano = []
        prev_cards = {c['name'] + str(c['card_id']): c for c in pp.get('pack_home', [])}
        for c in cp.get('pack_home', []):
            key = c['name'] + str(c['card_id'])
            pc = prev_cards.get(key)
            if pc and pc['health_current'] != c['health_current']:
                dano.append((c['name'], pc['health_current'], c['health_current']))
        if dano:
            diff['dano_tomado'][pid] = dano

    return diff


def _get_card_img_url(card_id):
    """Retorna URL da imagem da carta."""
    from rage_web.ext.repository import get_card_image_url_by_id
    return get_card_image_url_by_id(card_id)


# ── Export Log ──

@bp.route('/<game_id>/export-log')
def export_log(game_id: str):
    """Exporta o log completo da partida como .txt"""
    analysis = _analyses.get(game_id)
    if not analysis:
        return 'Análise não encontrada', 404

    full_log = analysis.get('full_log', [])
    meta = analysis['meta']

    lines = []
    lines.append(f'Rage CCG — Log de Partida')
    lines.append(f'Deck 1: {meta["p1_name"]}')
    lines.append(f'Deck 2: {meta["p2_name"]}')
    lines.append(f'Seed: {meta["seed"]}')
    lines.append(f'Max Turns: {meta["max_turns"]}')
    lines.append('=' * 60)
    lines.append('')
    for entry in full_log:
        lines.append(entry)
    lines.append('')
    lines.append('=' * 60)
    lines.append(f'Total de snapshots: {len(analysis.get("states", []))}')

    text = '\n'.join(lines)

    from flask import Response
    return Response(
        text,
        mimetype='text/plain',
        headers={
            'Content-Disposition':
            f'attachment; filename="rage-match-{game_id}.txt"'
        }
    )


# ── Simulation (headless) ──

_simulations: dict[str, dict] = {}


@bp.route('/simulation', methods=['GET', 'POST'])
def simulation():
    """Configura e roda simulacao headless de N partidas."""
    decks = _get_decks_with_renown()

    if request.method == 'GET':
        ultimos = {
            'sim_deck1': session.get('ultimos_sim_deck1'),
            'sim_deck2': session.get('ultimos_sim_deck2'),
        }
        return render_template('analysis/simulation.html',
                               decks=decks,
                               results=None,
                               ultimos=ultimos)

    # POST: roda a simulacao
    deck1_id = request.form.get('deck1', type=int)
    deck2_id = request.form.get('deck2', type=int)
    num_games = request.form.get('num_games', 10, type=int)
    max_turns_sim = request.form.get('max_turns', 30, type=int)
    seed = request.form.get('seed', 0, type=int)
    dif1 = request.form.get('difficulty1', 'hard')
    dif2 = request.form.get('difficulty2', 'hard')
    p1_name = request.form.get('p1_name', 'Jogador 1')
    p2_name = request.form.get('p2_name', 'Jogador 2')

    if num_games < 1:
        num_games = 1
    if num_games > 1000:
        num_games = 1000

    # Roda as partidas
    wins_p1 = 0
    wins_p2 = 0
    draws = 0
    timeouts = 0
    total_steps = 0
    results = []

    from rage_web.game_engine.match import run_match

    for i in range(num_games):
        s = seed + i if seed else 0
        try:
            result = run_match(
                seed=s,
                max_turns=max_turns_sim,
                deck_ids=[deck1_id, deck2_id],
                difficulties=[dif1, dif2],
                verbose=0,
                vp_to_win=50,
                max_steps_override=500
            )
        except Exception as e:
            result = f'error:{e}'

        results.append(result)
        if result == 0:
            wins_p1 += 1
        elif result == 1:
            wins_p2 += 1
        elif result == 'draw':
            draws += 1
        else:
            timeouts += 1

    # Salva decks da última simulação na sessão
    session['ultimos_sim_deck1'] = deck1_id
    session['ultimos_sim_deck2'] = deck2_id

    return render_template('analysis/simulation.html',
                           decks=decks,
                           ultimos={
                               'sim_deck1': deck1_id,
                               'sim_deck2': deck2_id,
                           },
                           results={
                               'deck1_name': p1_name,
                               'deck2_name': p2_name,
                               'num_games': num_games,
                               'wins_p1': wins_p1,
                               'wins_p2': wins_p2,
                               'draws': draws,
                               'timeouts': timeouts,
                               'winrate_p1': round(wins_p1 / num_games * 100, 1) if num_games else 0,
                               'winrate_p2': round(wins_p2 / num_games * 100, 1) if num_games else 0,
                           })


@bp.route('/<game_id>/next/<int:state_index>')
def next_state(game_id: str, state_index: int):
    """Avança para o próximo estado."""
    return redirect(url_for('analysis.view_state',
                            game_id=game_id, state_index=state_index + 1))


@bp.route('/<game_id>/prev/<int:state_index>')
def prev_state(game_id: str, state_index: int):
    """Volta para o estado anterior."""
    return redirect(url_for('analysis.view_state',
                            game_id=game_id,
                            state_index=max(0, state_index - 1)))


@bp.route('/<game_id>/jump-turn/<int:turn>')
def jump_to_turn(game_id: str, turn: int):
    """Pula para o primeiro snapshot do turno especificado."""
    analysis = _analyses.get(game_id)
    if not analysis:
        return 'Análise não encontrada', 404
    states = analysis['states']
    for i, s in enumerate(states):
        if s.turn == turn:
            return redirect(url_for('analysis.view_state',
                                    game_id=game_id, state_index=i))
    return redirect(url_for('analysis.view_state',
                            game_id=game_id, state_index=0))
