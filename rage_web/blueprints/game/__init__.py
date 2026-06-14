"""Blueprint do frontend web da partida."""

from __future__ import annotations

import os
import uuid

from flask import (
    Blueprint, Response, current_app, jsonify, redirect,
    render_template, request, url_for,
)

import rage_web.ext.repository as rep
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.combat_queue import (
    COMBAT_ACTIONS, declare_action, end_combat,
    feint_action, get_combatants, get_declaration_summary,
    reveal_all, resolve_combat, start_combat,
)
from rage_web.game_engine.state import GameState, Zone

bp = Blueprint('game', __name__, template_folder='templates',
               url_prefix='/game')

# Partidas ativas em memoria
# Tanto partidas criadas pelo web quanto pelo bot
_games: dict[str, GameState] = {}


def _get_bot_game(game_id: str) -> GameState | None:
    """Tenta buscar partida do bot Telegram."""
    try:
        from rage_web.telegram_bot.handlers import game_manager
        return game_manager.get_game(game_id)
    except Exception:
        return None


def _get_bot_games_for_player(telegram_id: int) -> list:
    """Retorna partidas ativas de um jogador no bot Telegram."""
    try:
        from rage_web.telegram_bot.handlers import game_manager
        session = game_manager.get_player_session(telegram_id)
        if session:
            game = game_manager.get_game(session.game_id)
            if game:
                from rage_web.game_engine.state import GameState as GS
                return [game]
    except Exception:
        pass
    return []


# ── Serializacao para templates ──

def _card_for_template(card) -> dict:
    from rage_web.ext.repository import get_card_image_url_by_id
    return {
        'card_id': card.card_id,
        'name': card.name,
        'card_type': card.card_type,
        'rage': card.rage,
        'gnosis': card.gnosis,
        'health': card.health,
        'health_current': card.health_current,
        'renown': card.renown,
        'image_url': get_card_image_url_by_id(card.card_id),
        'keywords': card.keywords,
        'text': card.text,
    }


def _player_for_template(p) -> dict:
    return {
        'id': p.id,
        'name': p.name,
        'victory_points': p.victory_points,
        'has_passed': p.has_passed,
        'hand': [_card_for_template(c) for c in p.hand],
        'pack_home': [_card_for_template(c) for c in p.pack_home],
        'umbra': [_card_for_template(c) for c in p.umbra],
        'hunting_grounds': [_card_for_template(c) for c in p.hunting_grounds],
        'victory_pile': [_card_for_template(c) for c in p.victory_pile],
        'deck_combat_count': len(p.deck_combat),
        'deck_sept_count': len(p.deck_sept),
        'discard_combat_count': len(p.discard_combat),
        'discard_sept_count': len(p.discard_sept),
    }


def _game_for_template(g: GameState) -> dict:
    combat = {}
    if g.combat.is_active:
        combat = {
            'is_active': True,
            'step': g.combat.step,
            'attackers': g.combat.attackers,
            'defenders': g.combat.defenders,
            'declarations': dict(g.combat.declarations),
            'last_to_declare': g.combat.last_to_declare,
            'current_alpha': g.combat.current_alpha,
            'alpha_order': g.combat.alpha_order,
        }
    else:
        combat = {'is_active': False}

    return {
        'id': g.id,
        'turn_number': g.turn_number,
        'phase': g.phase,
        'current_player_index': g.current_player_index,
        'current_player_name': g.current_player.name,
        'players': [_player_for_template(p) for p in g.players],
        'combat': combat,
        'log': g.log[-15:],
        'winner': g.winner,  # player_id string
        'hunting_grounds_cards': [_card_for_template(c) for c in g.hunting_grounds_cards],
    }

    # Se tem vencedor, enriquece com nome
    if g.winner:
        winner_p = next((p for p in g.players if p.id == g.winner), None)
        if winner_p:
            data['winner_name'] = winner_p.name
            data['winner_vp'] = winner_p.victory_points


# ── Rotas ──

@bp.route('/new')
def new_game():
    """Formulario para iniciar nova partida."""
    decks = rep.find_all_decks()
    return render_template('game/new.html', decks=decks)


@bp.route('/create', methods=['POST'])
def create_game():
    """Cria partida a partir do formulario."""
    deck1_id = request.form.get('deck1', type=int)
    deck2_id = request.form.get('deck2', type=int)
    seed = request.form.get('seed', 42, type=int)
    p1_name = request.form.get('p1_name', 'Jogador 1')
    p2_name = request.form.get('p2_name', 'Jogador 2')

    # Cria partida
    if deck1_id and deck2_id:
        from rage_web.game_engine.match import build_game_from_decks
        g = build_game_from_decks(deck1_id, deck2_id, seed=seed)
        # Renomeia jogadores
        if g.players:
            g.players[0].name = p1_name
        if len(g.players) > 1:
            g.players[1].name = p2_name
    else:
        g = create_sample_game(seed=seed)
        if g.players:
            g.players[0].name = p1_name
        if len(g.players) > 1:
            g.players[1].name = p2_name

    _games[g.id] = g
    return redirect(url_for('game.view_game', game_id=g.id))


@bp.route('/<game_id>')
def view_game(game_id: str):
    """Tela principal da partida."""
    g = _games.get(game_id)
    if not g:
        # Tenta buscar partida do bot
        g = _get_bot_game(game_id)
        if not g:
            return render_template('errors/404.html',
                                   message='Partida nao encontrada'), 404

    data = _game_for_template(g)
    return render_template('game/board.html', game=data)


@bp.route('/<game_id>/board')
def game_board_partial(game_id: str):
    """Partial do tabuleiro para refresh HTMX."""
    g = _games.get(game_id)
    if not g:
        g = _get_bot_game(game_id)
        if not g:
            return 'Partida nao encontrada', 404

    data = _game_for_template(g)
    return render_template('game/_game_board.html', game=data)


@bp.route('/<game_id>/action', methods=['POST'])
def game_action(game_id: str):
    """Executa uma acao na partida via HTMX.

    Body: action=<nome>&params...
    """
    g = _games.get(game_id)
    if not g:
        g = _get_bot_game(game_id)
        if not g:
            return 'Partida nao encontrada', 404

    # Suporta form-urlencoded e JSON (hx-vals)
    if request.is_json:
        body = request.get_json(silent=True) or {}
    else:
        body = {k: v for k, v in request.form.items()}

    action = body.get('action', '')
    result = _executar_acao(g, action, body)
    if result.startswith('ERRO:'):
        return f'<div class="notification is-danger is-light">{result[5:]}</div>', 400

    data = _game_for_template(g)
    return render_template('game/_game_board.html', game=data)


@bp.route('/<game_id>/log')
def game_log_partial(game_id: str):
    """Partial do log para refresh HTMX."""
    g = _games.get(game_id)
    if not g:
        return 'Partida nao encontrada', 404
    logs = g.log[-15:]
    return render_template('game/_log.html', logs=logs)


def _executar_acao(g: GameState, action: str, params: dict) -> str:
    """Executa uma acao na partida.

    Args:
        g: Estado da partida.
        action: Nome da acao.
        params: Dict de parametros (pode ser de form ou JSON).
    """
    cp = g.current_player

    def _int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    if action == 'pass':
        cp.pass_turn()
        all_passed = all(p.has_passed for p in g.players)
        if all_passed:
            g.next_phase()
            for p in g.players:
                p.reset_pass()
            g.add_log(f'Todos passaram. Avancando para {g.phase}')
        else:
            g.next_player()
            g.add_log(f'{cp.name} passou. Vez de {g.current_player.name}')
        return 'OK'

    elif action == 'next':
        old = g.phase
        g.next_phase()
        g.add_log(f'Avancou: {old} -> {g.phase}')
        return 'OK'

    elif action == 'draw_combat':
        count = _int(params.get('count', 1))
        drawn = cp.draw_combat(count)
        if drawn:
            g.add_log(f'{cp.name} comprou {len(drawn)} carta(s) de combate')
        return 'OK'

    elif action == 'draw_sept':
        count = _int(params.get('count', 1))
        drawn = cp.draw_sept(count)
        if drawn:
            g.add_log(f'{cp.name} comprou {len(drawn)} carta(s) de sept')
        return 'OK'

    elif action == 'play':
        idx = _int(params.get('hand_index', -1))
        if idx < 0 or idx >= len(cp.hand):
            return 'ERRO:Indice de mao invalido'
        from rage_web.game_engine.rules import zona_da_carta
        card = cp.hand.pop(idx)
        zona = zona_da_carta(card.card_type or '')
        if zona == 'hunting_grounds':
            card.zone = Zone.HUNTING_GROUNDS
            cp.hunting_grounds.append(card)
            g.add_log(f'{cp.name} jogou {card.name} no Hunting Grounds')
        else:
            card.zone = Zone.PACK_HOME
            card.health_current = card.health
            cp.pack_home.append(card)
            g.add_log(f'{cp.name} jogou {card.name}')
        return 'OK'

    elif action == 'use_card':
        idx = _int(params.get('hand_index', -1))
        modo_idx = _int(params.get('modo_idx', 0))
        if idx < 0 or idx >= len(cp.hand):
            return 'ERRO:Indice de mao invalido'
        card = cp.hand[idx]
        if not card.modelo_id:
            return 'ERRO:Carta sem modelo de efeitos'

        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        from rage_web.game_engine.rules import parse_custo_rage

        modelo = CARTAS_EXEMPLO.get(card.modelo_id)
        if not modelo:
            return 'ERRO:Modelo nao encontrado'

        # Pagar custo Rage
        custo_rage = parse_custo_rage(card.damage)
        if custo_rage is not None and custo_rage > 0:
            pagador = cp.pagar_custo_rage(custo_rage)
            if not pagador:
                return f'ERRO:Custo Rage {custo_rage} nao pode ser pago'

        # Pagar custo Gnosis
        if card.gnosis and card.gnosis > 0:
            pagador = cp.pagar_custo_gnosis(card.gnosis)
            if not pagador:
                return f'ERRO:Custo Gnosis {card.gnosis} nao pode ser pago'

        cp.hand.pop(idx)
        aplicar_carta(g, modelo, cp.id, modo_idx=modo_idx)
        return 'OK'

    elif action == 'attack':
        attacker_id = params.get('attacker_id', '')
        defender_id = params.get('defender_id', 'hg')
        if not attacker_id:
            return 'ERRO:attacker_id obrigatorio'
        if not start_combat(g, [attacker_id], [defender_id]):
            return 'ERRO:Nao foi possivel iniciar combate'
        g.add_log(f'{cp.name} atacou {defender_id} com {attacker_id}')
        return 'OK'

    elif action == 'declare':
        card_id = params.get('card_id', '')
        combat_action = params.get('combat_action', 'strike')
        if not declare_action(g, card_id, combat_action):
            return 'ERRO:Nao foi possivel declarar'
        g.add_log(f'{card_id} declarou {combat_action}')
        return 'OK'

    elif action == 'reveal':
        if not reveal_all(g):
            return 'ERRO:Nao foi possivel revelar'
        return 'OK'

    elif action == 'feint':
        card_id = params.get('card_id', '')
        new_action = params.get('new_action', 'strike')
        if not feint_action(g, card_id, new_action):
            return 'ERRO:Nao foi possivel usar Feint'
        return 'OK'

    elif action == 'resolve':
        if not resolve_combat(g):
            return 'ERRO:Nao foi possivel resolver'
        return 'OK'

    elif action == 'end_combat':
        end_combat(g)
        return 'OK'

    elif action == 'step_umbra':
        # Step sideways manual
        from rage_web.game_engine.rules import pode_step_sideways, \
            encontrar_caern, GAUNTLET_DEFAULT
        card_id = params.get('card_id', '')
        personagem = None
        for c in cp.pack_home:
            if str(c.card_id) == card_id:
                personagem = c
                break
        if not personagem:
            return 'ERRO:Criatura nao encontrada no Pack Home'
        caern = encontrar_caern(cp)
        gauntlet = int(caern.damage) if caern and caern.damage else GAUNTLET_DEFAULT
        if not pode_step_sideways(personagem, caern, gauntlet):
            return 'ERRO:Criatura nao pode stepping sideways'
        cp.step_sideways(personagem)
        g.add_log(f'{personagem.name} foi para a Umbra')
        return 'OK'

    elif action == 'step_back':
        card_id = params.get('card_id', '')
        personagem = None
        for c in cp.umbra:
            if str(c.card_id) == card_id:
                personagem = c
                break
        if not personagem:
            return 'ERRO:Criatura nao encontrada na Umbra'
        cp.step_back(personagem)
        g.add_log(f'{personagem.name} voltou da Umbra')
        return 'OK'

    elif action == 'select_alpha':
        card_id = params.get('card_id', '')
        from rage_web.game_engine.combat_queue import selecionar_alfa
        if not selecionar_alfa(g, cp.id, card_id):
            return 'ERRO:Nao foi possivel selecionar alpha'
        from rage_web.game_engine.combat_queue import calcular_ordem_alfa
        calcular_ordem_alfa(g)
        g.add_log(f'{cp.name} selecionou alpha {card_id}')
        return 'OK'

    elif action == 'restart':
        # Volta pro formulario
        return 'RESTART'

    else:
        return f'ERRO:Acao desconhecida: {action}'
