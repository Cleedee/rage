"""API REST para debug do motor de jogo.

Uso:
    from rage_web.game_engine.api import api_bp
    app.register_blueprint(api_bp)
"""

from __future__ import annotations

import json
import uuid

from flask import Blueprint, Response, current_app, jsonify, request

from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.combat_queue import (
    COMBAT_ACTIONS, can_feint, declare_action, end_combat,
    feint_action, get_combatants, get_declaration_summary,
    reveal_all, resolve_combat, start_combat,
)
from rage_web.game_engine.state import GameState, Zone


api_bp = Blueprint('game_api', __name__, url_prefix='/api/game')

# Armazenamento em memoria (futuro: Redis/banco)
_games: dict[str, GameState] = {}


# -----------------------------------------------------------------------
# Serializacao
# -----------------------------------------------------------------------

def _serialize_card(card) -> dict:
    return {
        'card_id': card.card_id,
        'name': card.name,
        'card_type': card.card_type,
        'zone': card.zone.value,
        'owner_id': card.owner_id,
        'controller_id': card.controller_id,
        'rage': card.rage,
        'gnosis': card.gnosis,
        'health': card.health,
        'health_current': card.health_current,
        'renown': card.renown,
        'is_tapped': card.is_tapped,
        'is_face_down': card.is_face_down,
    }


def _serialize_player(p) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'victory_points': p.victory_points,
        'renown_level': p.renown_level,
        'rage_pool': p.rage_pool,
        'gnosis_pool': p.gnosis_pool,
        'has_passed': p.has_passed,
        'hand': [_serialize_card(c) for c in p.hand],
        'pack_home': [_serialize_card(c) for c in p.pack_home],
        'hunting_grounds': [_serialize_card(c) for c in p.hunting_grounds],
        'umbra': [_serialize_card(c) for c in p.umbra],
        'deck_combat_count': len(p.deck_combat),
        'deck_sept_count': len(p.deck_sept),
        'discard_combat_count': len(p.discard_combat),
        'discard_sept_count': len(p.discard_sept),
        'victory_pile': [_serialize_card(c) for c in p.victory_pile],
    }


def _serialize_game(g: GameState) -> dict:
    """Serializa o estado da partida para JSON."""
    combat_summary = {}
    if g.combat.is_active:
        cs = g.combat
        combat_summary = {
            'is_active': True,
            'step': cs.step,
            'attackers': cs.attackers,
            'defenders': cs.defenders,
            'last_to_declare': cs.last_to_declare,
        }
        summary = get_declaration_summary(g)
        if 'declarations' in summary:
            combat_summary['declarations'] = summary['declarations']
        if 'declared_count' in summary:
            combat_summary['declared_count'] = summary['declared_count']
    else:
        combat_summary = {'is_active': False}

    return {
        'id': g.id,
        'turn_number': g.turn_number,
        'phase': g.phase,
        'current_player_index': g.current_player_index,
        'current_player_id': g.current_player.id,
        'players': [_serialize_player(p) for p in g.players],
        'combat': combat_summary,
        'log': g.log[-20:],
    }


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------

@api_bp.route('/new', methods=['POST'])
def new_game():
    """Cria uma nova partida de exemplo.

    Body (opcional):
        seed: int (default 42)
    """
    data = request.get_json(silent=True) or {}
    seed = data.get('seed', 42)
    game = create_sample_game(seed=seed)
    _games[game.id] = game
    return jsonify({'game_id': game.id, 'state': _serialize_game(game)}), 201


@api_bp.route('/<game_id>', methods=['GET'])
def get_game(game_id: str):
    """Retorna o estado completo da partida."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404
    return jsonify({'game_id': game.id, 'state': _serialize_game(game)})


@api_bp.route('/<game_id>/players', methods=['GET'])
def list_players(game_id: str):
    """Retorna a lista de jogadores da partida."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404
    players = [{'id': p.id, 'name': p.name, 'index': i}
               for i, p in enumerate(game.players)]
    return jsonify({'game_id': game.id, 'players': players})


@api_bp.route('/<game_id>/legal-actions', methods=['GET'])
def legal_actions(game_id: str):
    """Retorna as acoes validas no momento atual."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    actions = {'phase': game.phase, 'available': []}

    cp = game.current_player

    if game.combat.is_active:
        actions['combat_active'] = True
        actions['available'].extend([
            {'action': 'declare', 'params': {'card_id': '<id>',
                                              'action': list(COMBAT_ACTIONS)}},
            {'action': 'reveal'},
        ])
        if game.combat.step == 'reveal':
            actions['available'].append(
                {'action': 'feint',
                 'params': {'card_id': '<id>', 'new_action': list(COMBAT_ACTIONS)}}
            )
        if game.combat.step in ('reveal', 'resolve'):
            actions['available'].extend([
                {'action': 'resolve'},
                {'action': 'end_combat'},
            ])
    else:
        actions['available'].extend([
            {'action': 'draw', 'params': {'deck': 'combat|sept', 'count': 1}},
            {'action': 'play', 'params': {'hand_index': 0}},
            {'action': 'attack',
             'params': {'attacker_id': '<id>', 'defender_id': '<id> (opcional)'}},
            {'action': 'pass'},
            {'action': 'next'},
        ])

    return jsonify(actions)


# -----------------------------------------------------------------------
# Acoes do jogador
# -----------------------------------------------------------------------

@api_bp.route('/<game_id>/draw', methods=['POST'])
def api_draw(game_id: str):
    """Compra cartas do deck.

    Body:
        deck: 'combat' | 'sept' (default 'combat')
        count: int (default 1)
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    deck = data.get('deck', 'combat')
    count = data.get('count', 1)
    cp = game.current_player

    if deck == 'combat':
        drawn = cp.draw_combat(count)
    else:
        drawn = cp.draw_sept(count)

    return jsonify({
        'drawn': [_serialize_card(c) for c in drawn],
        'hand_count': len(cp.hand),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/play', methods=['POST'])
def api_play(game_id: str):
    """Joga uma carta da mao para o Pack Home.

    Body:
        hand_index: int (indice na mao)
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    idx = data.get('hand_index', -1)
    cp = game.current_player

    if idx < 0 or idx >= len(cp.hand):
        return jsonify({'error': f'Indice invalido. Mao tem {len(cp.hand)} cartas.'}), 400

    from rage_web.game_engine.rules import zona_da_carta, pode_recrutar_ally
    card = cp.hand[idx]

    # Verifica requisito de recrutamento para Allies (4.4.1)
    if 'Ally' in (card.card_type or ''):
        if not pode_recrutar_ally(cp, card):
            return jsonify({
                'error': f'Nao pode recrutar {card.name}: '
                         f'nenhum personagem atende o requisito'
                         f' ("{card.requires}")'
            }), 400

    cp.hand.pop(idx)
    zona = zona_da_carta(card.card_type or '')
    if zona == 'hunting_grounds':
        card.zone = Zone.HUNTING_GROUNDS
        cp.hunting_grounds.append(card)
        game.add_log(f'{cp.name} jogou {card.name} no Hunting Grounds')
    else:
        card.zone = Zone.PACK_HOME
        card.health_current = card.health
        cp.pack_home.append(card)
        game.add_log(f'{cp.name} jogou {card.name}')

    return jsonify({
        'played': _serialize_card(card),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/use-card', methods=['POST'])
def api_use_card(game_id: str):
    """Usa uma carta de efeito da mao.

    Body:
        hand_index: int
        modo_idx: int (opcional, default 0)
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    idx = data.get('hand_index', -1)
    modo_idx = data.get('modo_idx', 0)
    cp = game.current_player

    if idx < 0 or idx >= len(cp.hand):
        return jsonify({'error': f'Indice invalido. Mao tem {len(cp.hand)} cartas.'}), 400

    card = cp.hand[idx]
    if not card.modelo_id:
        return jsonify({'error': f'Carta {card.name} nao tem modelo de efeitos.'}), 400

    # Verifica requisitos de Gift (Rage FOO Rule)
    if card.card_type == 'Gift':
        from rage_web.game_engine.rules import pode_usar_gift
        if not pode_usar_gift(cp, card):
            return jsonify({
                'error': f'Nao pode usar {card.name}: '
                         f'nenhum personagem atende os requisitos'
                         f' ("{card.requires}")'
            }), 400

    from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
    if not modelo:
        return jsonify({'error': f'Modelo {card.modelo_id} nao encontrado.'}), 500

    if modo_idx < 0 or modo_idx >= len(modelo.modos):
        return jsonify({'error': f'Modo invalido. Modos: {len(modelo.modos)}'}), 400

    # Valida custo de Rage e Gnosis
    from rage_web.game_engine.rules import parse_custo_rage
    custo_rage = parse_custo_rage(card.damage)
    if custo_rage is not None and custo_rage > 0:
        pagador = cp.pagar_custo_rage(custo_rage)
        if pagador is None:
            return jsonify({
                'error': f'Custo de Rage {custo_rage} nao pode ser pago. '
                         f'Nenhum personagem destapped com Rage >= {custo_rage}.'
            }), 400
        game.add_log(f'{cp.name} pagou Rage {custo_rage} com {pagador}')
    custo_gnosis = card.gnosis
    if custo_gnosis and custo_gnosis > 0:
        pagador = cp.pagar_custo_gnosis(custo_gnosis)
        if pagador is None:
            return jsonify({
                'error': f'Custo de Gnosis {custo_gnosis} nao pode ser pago. '
                         f'Nenhum personagem destapped com Gnosis >= {custo_gnosis}.'
            }), 400
        game.add_log(f'{cp.name} pagou Gnosis {custo_gnosis} com {pagador}')

    # Remove da mao
    cp.hand.pop(idx)

    # Aplica os efeitos
    logs = aplicar_carta(game, modelo, cp.id, modo_idx=modo_idx)

    return jsonify({
        'used': {'name': card.name, 'modo': modelo.modos[modo_idx].descricao},
        'logs': logs,
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/attack', methods=['POST'])
def api_attack(game_id: str):
    """Inicia combate.

    Body:
        attacker_id: str
        defender_id: str (opcional, default 'hg')
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    attacker_id = data.get('attacker_id', '')
    defender_id = data.get('defender_id', 'hg')

    if not attacker_id:
        return jsonify({'error': 'attacker_id é obrigatorio'}), 400

    # Verifica se o atacante existe
    cp = game.current_player
    atacante = _find_card_in_player(attacker_id, cp)
    if not atacante and attacker_id not in get_combatants(game):
        # Permite ID de criatura em combate
        pass

    # Resolve 'hg' para uma presa especifica no Hunting Grounds
    if defender_id == 'hg':
        alvo_hg = _melhor_alvo_hg(game)
        if alvo_hg:
            defensores = [str(alvo_hg.card_id)]
        else:
            return jsonify({'error': 'Nenhum alvo no Hunting Grounds'}), 400
    else:
        defensores = [defender_id]

    if not start_combat(game, [attacker_id], defensores):
        return jsonify({'error': 'Nao foi possivel iniciar combate (ja existe um ativo?).'}), 409

    game.add_log(f'{cp.name} iniciou combate: {attacker_id} vs {defender_id}')

    return jsonify({
        'combat': get_declaration_summary(game),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/declare', methods=['POST'])
def api_declare(game_id: str):
    """Declara acao de combate.

    Body:
        card_id: str
        action: str (strike, block, dodge, etc.)
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    card_id = data.get('card_id', '')
    action = data.get('action', '').lower()

    if not card_id or not action:
        return jsonify({'error': 'card_id e action sao obrigatorios'}), 400

    if action not in COMBAT_ACTIONS:
        return jsonify({'error': f'Acão invalida: {action}',
                         'valid_actions': sorted(COMBAT_ACTIONS)}), 400

    if not declare_action(game, card_id, action):
        return jsonify({'error': 'Nao foi possivel declarar. Combate ativo?'}), 409

    return jsonify({
        'declared': {'card_id': card_id, 'action': action},
        'combat': get_declaration_summary(game),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/reveal', methods=['POST'])
def api_reveal(game_id: str):
    """Revela todas as acoes de combate."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    if not reveal_all(game):
        return jsonify({'error': 'Nao foi possivel revelar.'}), 409

    return jsonify({
        'combat': get_declaration_summary(game),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/feint', methods=['POST'])
def api_feint(game_id: str):
    """Usa Feint para trocar acao de combate.

    Body:
        card_id: str
        new_action: str
    """
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    data = request.get_json(silent=True) or {}
    card_id = data.get('card_id', '')
    new_action = data.get('new_action', '').lower()

    if not card_id or not new_action:
        return jsonify({'error': 'card_id e new_action sao obrigatorios'}), 400

    if not feint_action(game, card_id, new_action):
        return jsonify({'error': 'Nao foi possivel usar Feint.'}), 409

    return jsonify({
        'feinted': {'card_id': card_id, 'new_action': new_action},
        'combat': get_declaration_summary(game),
        'state': _serialize_game(game),
    })


@api_bp.route('/<game_id>/resolve', methods=['POST'])
def api_resolve(game_id: str):
    """Resolve o combate atual."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    if not resolve_combat(game):
        return jsonify({'error': 'Nao foi possivel resolver o combate.'}), 409

    return jsonify({'state': _serialize_game(game)})


@api_bp.route('/<game_id>/end-combat', methods=['POST'])
def api_end_combat(game_id: str):
    """Encerra o combate forcadamente."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    end_combat(game)
    return jsonify({'state': _serialize_game(game)})


@api_bp.route('/<game_id>/pass', methods=['POST'])
def api_pass(game_id: str):
    """Passa a vez para o proximo jogador."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    cp = game.current_player
    cp.pass_turn()

    all_passed = all(p.has_passed for p in game.players)
    if all_passed:
        game.next_phase()
        for p in game.players:
            p.reset_pass()
        game.add_log(f'Todos passaram. Avancando para {game.phase}')
    else:
        game.next_player()
        game.add_log(f'{cp.name} passou. Vez de {game.current_player.name}')

    return jsonify({'state': _serialize_game(game)})


@api_bp.route('/<game_id>/next', methods=['POST'])
def api_next(game_id: str):
    """Avança forcadamente para a proxima fase."""
    game = _games.get(game_id)
    if not game:
        return jsonify({'error': 'Partida nao encontrada'}), 404

    old_phase = game.phase
    game.next_phase()
    game.add_log(f'Avancou: {old_phase} -> {game.phase}')

    return jsonify({'state': _serialize_game(game)})


# -----------------------------------------------------------------------
# Util
# -----------------------------------------------------------------------

def _find_card_in_player(card_id_str: str, player) -> object | None:
    """Busca carta por ID nas zonas do jogador."""
    for c in player.pack_home:
        if str(c.card_id) == card_id_str:
            return c
    for c in player.hunting_grounds:
        if str(c.card_id) == card_id_str:
            return c
    return None


def _melhor_alvo_hg(game) -> object | None:
    """Encontra o melhor alvo Victim/Enemy/Battlefield no Hunting Grounds."""
    TIPOS_HG = {'victim', 'enemy', 'battlefield'}
    candidatos = []
    for c in game.hunting_grounds_cards:
        ct = (c.card_type or '').lower()
        if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
            candidatos.append(c)
    for p in game.players:
        for c in p.hunting_grounds:
            ct = (c.card_type or '').lower()
            if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                candidatos.append(c)
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c.renown or 1) / max(c.health_current, 1),
                    reverse=True)
    return candidatos[0]
