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
    render_template, request, url_for,
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
    """Estado congelado de uma partida num dado turno/fase."""
    def __init__(self, game: GameState, turn: int, phase: str):
        self.turn = turn
        self.phase = phase
        self.players = []
        for p in game.players:
            self.players.append({
                'id': p.id,
                'name': p.name,
                'victory_points': p.victory_points,
                'hand': [_card_info(c) for c in p.hand],
                'pack_home': [_card_info(c) for c in p.pack_home],
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
        # Hunting Grounds global
        self.hunting_grounds_cards = [
            _card_info(c) for c in game.hunting_grounds_cards
        ]
        # Combat
        self.combat = {
            'is_active': game.combat.is_active,
            'step': game.combat.step,
            'attackers': game.combat.attackers,
            'defenders': game.combat.defenders,
            'declarations': dict(game.combat.declarations),
            'last_to_declare': game.combat.last_to_declare,
        }
        # Log entries since last snapshot
        self.log = list(game.log) if hasattr(game, 'log') else []


def _card_info(c) -> dict:
    """Serializa uma CardInstance para o template."""
    return {
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
    }


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
    return render_template('analysis/new.html', decks=decks)


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
    logs_collected = []

    # Cria bots
    bots = {}
    for p in game.players:
        bots[p.id] = PriorityBot(game, p.id, difficulty='hard')

    # Snapshots iniciais: cada fase do turno 1
    _capture_state(game, states, logs_collected)

    # Loop principal para avançar a partida
    stale = 0
    last_turn = game.turn_number
    last_phase = game.phase
    max_steps = max_turns * 50
    step = 0
    _alpha_order = []
    _alpha_index = 0
    _alpha_map = {}
    _alpha_phase = False

    while step < max_steps:
        # Salva log atual
        logs_collected = list(game.log)

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
            _capture_state(game, states, logs_collected)
        else:
            stale += 1
        last_phase = game.phase

        if stale > 200:
            break

        # Verifica condições de fim
        from rage_web.game_engine.combat_queue import (
            _tem_character, _eliminar_jogador
        )
        if game.turn_number > 1:
            for p in game.players:
                if not _tem_character(p) and not getattr(p, 'eliminado', False):
                    _eliminar_jogador(game, p)

        jogadores_ativos = [p for p in game.players
                            if not getattr(p, 'eliminado', False)]
        if len(jogadores_ativos) <= 1:
            _capture_state(game, states, logs_collected)
            break

        for p in jogadores_ativos:
            if p.victory_points >= p.renown_level:
                _capture_state(game, states, logs_collected)
                break
        else:
            step += 1
            continue
        break

        # Verifica limite de turnos
        if game.turn_number > max_turns:
            _capture_state(game, states, logs_collected)
            break

        step += 1

    # Armazena
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
    }

    return redirect(url_for('analysis.view_state',
                            game_id=game_id, state_index=0))


def _capture_state(game, states, logs):
    """Cria um snapshot do estado atual e adiciona à lista."""
    snap = Snapshot(game, game.turn_number, game.phase)
    states.append(snap)


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

    return render_template('analysis/view.html',
                           game_id=game_id,
                           state=snap,
                           state_index=state_index,
                           total_states=len(states),
                           meta=meta,
                           deck1_name=deck1.name if deck1 else '?',
                           deck2_name=deck2.name if deck2 else '?',
                           player_count=len(snap.players),
                           get_card_image_url=_get_card_img_url)


def _get_card_img_url(card_id):
    """Retorna URL da imagem da carta."""
    from rage_web.ext.repository import get_card_image_url_by_id
    return get_card_image_url_by_id(card_id)


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
