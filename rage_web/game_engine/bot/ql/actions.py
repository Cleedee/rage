"""Macro-ações do agente Q-Learning.

O agente escolhe entre categorias de ação (ex: 'res_character',
'combat_act', 'redraw_discard'). Cada executor delega a escolha
concreta (qual carta, qual alvo) para heurísticas do PriorityBot,
retornando a string de ação técnica do motor (ou None se não há
nada válido a fazer — o agente então usa um fallback seguro).
"""

from __future__ import annotations

import logging

import numpy as np

from rage_web.game_engine.combat_queue import advance_combat_step, end_combat
from rage_web.game_engine.state import Zone

logger = logging.getLogger(__name__)

# ── Espaço global de macro-ações ──────────────────────────────────────
ALL_MACROS = [
    'redraw_discard', 'redraw_lunar', 'redraw_pass',
    'regen_pass',
    'res_character', 'res_equipment', 'res_gift_event', 'res_ally',
    'res_caern', 'res_territory', 'res_hg', 'res_pass',
    'umbra_step', 'umbra_back', 'umbra_pass',
    'moot_call', 'moot_vote_yes', 'moot_vote_no', 'moot_pass',
    'combat_act', 'combat_pass', 'combat_end',
]

MACRO_INDEX = {name: i for i, name in enumerate(ALL_MACROS)}
N_ACTIONS = len(ALL_MACROS)

# Tipos de carta que NÃO são de recurso (excluídos da Resource Phase)
TIPOS_NAO_RECURSO = {'Combat Action', 'Combat Event', 'Moot',
                     'Board Meeting', 'Action'}

LUNAR_CARDS = {834, 854, 865, 869, 884, 890, 897}


# ── Legalidade ─────────────────────────────────────────────────────────

def legal_mask(bot) -> np.ndarray:
    """Máscara booleana sobre ALL_MACROS indicando ações válidas agora."""
    g = bot.game
    me = bot.player
    mask = np.zeros(N_ACTIONS, dtype=bool)

    if g.current_player.id != bot.player_id or getattr(me, 'eliminado', False):
        return mask

    if g.phase == 'redraw':
        if g.turn_number > 1 or not me.is_first_turn:
            mask[MACRO_INDEX['redraw_discard']] = True
        mask[MACRO_INDEX['redraw_lunar']] = True
        mask[MACRO_INDEX['redraw_pass']] = True
    elif g.phase == 'regeneration':
        mask[MACRO_INDEX['regen_pass']] = True
    elif g.phase == 'resource':
        mask[MACRO_INDEX['res_character']] = True
        mask[MACRO_INDEX['res_equipment']] = True
        mask[MACRO_INDEX['res_gift_event']] = True
        mask[MACRO_INDEX['res_ally']] = True
        mask[MACRO_INDEX['res_caern']] = True
        mask[MACRO_INDEX['res_territory']] = True
        mask[MACRO_INDEX['res_hg']] = True
        mask[MACRO_INDEX['res_pass']] = True
    elif g.phase == 'umbra':
        podem_ir, _ = me.personagens_que_podem_step()
        if podem_ir:
            mask[MACRO_INDEX['umbra_step']] = True
        mask[MACRO_INDEX['umbra_back']] = True
        mask[MACRO_INDEX['umbra_pass']] = True
    elif g.phase == 'moot':
        if not g.combat.is_active:
            mask[MACRO_INDEX['moot_call']] = True
        mask[MACRO_INDEX['moot_vote_yes']] = True
        mask[MACRO_INDEX['moot_vote_no']] = True
        mask[MACRO_INDEX['moot_pass']] = True
    elif g.phase == 'combat':
        if g.combat.is_active:
            mask[MACRO_INDEX['combat_act']] = True
            mask[MACRO_INDEX['combat_pass']] = True
            mask[MACRO_INDEX['combat_end']] = True
        else:
            mask[MACRO_INDEX['combat_act']] = True
            mask[MACRO_INDEX['combat_pass']] = True

    return mask


def available_macros(bot) -> list[str]:
    """Lista de macro-ações legais no momento."""
    return [name for name, ok in zip(ALL_MACROS, legal_mask(bot)) if ok]


# ── Fallback seguro ────────────────────────────────────────────────────

def _fallback(bot) -> str:
    """Ação segura quando nenhum executor retorna algo válido."""
    try:
        bot._pass_turn()
        return 'pass'
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] fallback falhou: %s', e)
        return 'wait'


# ── Executores ─────────────────────────────────────────────────────────

def _exe_redraw_discard(bot) -> str | None:
    if bot.game.phase != 'redraw':
        return None
    return bot._agir_redraw()


def _exe_redraw_lunar(bot) -> str | None:
    """Joga/remove Fase Lunar da mão (somente isso)."""
    me = bot.player
    g = bot.game
    if g.phase != 'redraw':
        return None
    for i, card in enumerate(me.hand):
        if card.card_id not in LUNAR_CARDS:
            continue
        if card.card_id == 884 and g.lunar_phase:
            g.remover_lunar_phase()
            return 'redraw_lunar_eclipse'
        if card.card_id == 884 and not g.lunar_phase:
            card.zone = Zone.DISCARD_SEPT
            me.discard_sept.append(me.hand.pop(i))
            return 'redraw_lunar_eclipse'
        if card.card_id == 897:
            bot._play_card(i)
            return 'redraw_phoebe'
        modelo_id = card.modelo_id or ''
        g.definir_lunar_phase(jogador_id=bot.player_id, nome=card.name,
                              card_id=card.card_id, modelo_id=modelo_id,
                              card_uid=id(card))
        card.zone = Zone.PACK_HOME
        me.pack_home.append(me.hand.pop(i))
        if modelo_id:
            from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
            modelo = CARTAS_EXEMPLO.get(modelo_id)
            if modelo:
                modo_idx = bot._escolher_melhor_modo(modelo_id)
                aplicar_carta(g, modelo, bot.player_id, modo_idx=modo_idx,
                              card_origem=card)
        return f'redraw_lunar_{card.card_id}'
    return None


def _exe_regen_pass(bot) -> str | None:
    if bot.game.phase != 'regeneration':
        return None
    bot._pass_turn()
    return 'pass_regen'


def _play_resource_type(bot, tipos: set[str]) -> str | None:
    """Joga a primeira carta da mão do(s) tipo(s) dado(s) que seja viável."""
    me = bot.player
    g = bot.game
    if g.phase != 'resource':
        return None
    if bot._cards_played_this_turn >= 3:
        return None

    from rage_web.game_engine.effects import ResolvedorEfeitos
    from rage_web.game_engine.rules import (pode_jogar_caern,
                                            pode_recrutar_ally)

    for i, card in enumerate(me.hand):
        ct = (card.card_type or '')
        if ct not in tipos:
            continue
        if ct in TIPOS_NAO_RECURSO:
            continue
        if not bot._pode_pagar_custos(card):
            continue
        if ct == 'Ally':
            if not pode_recrutar_ally(me, card):
                continue
        elif ct == 'Caern':
            if not pode_jogar_caern(me, card, g):
                continue
        elif 'equipment' in ct.lower():
            resolvedor = ResolvedorEfeitos(g)
            tem_alvo = any(
                resolvedor._validar_restricoes_equipamento(card, c)
                for c in me.pack_home
                if 'character' in (c.card_type or '').lower()
            )
            if not tem_alvo:
                continue
        if card.modelo_id:
            modo_idx = bot._escolher_melhor_modo(card.modelo_id)
            return bot._usar_carta_efeito(i, modo_idx, card)
        return bot._play_card(i)
    return None


def _exe_res_character(bot) -> str | None:
    return _play_resource_type(bot, {'Character'})


def _exe_res_equipment(bot) -> str | None:
    return _play_resource_type(
        bot, {ct for ct in ('Equipment',) if ct}
    )


def _exe_res_gift_event(bot) -> str | None:
    return _play_resource_type(bot, {'Gift', 'Event', 'Rite', 'Quest',
                                     'Past Life'})


def _exe_res_ally(bot) -> str | None:
    return _play_resource_type(bot, {'Ally'})


def _exe_res_caern(bot) -> str | None:
    return _play_resource_type(bot, {'Caern'})


def _exe_res_territory(bot) -> str | None:
    return _play_resource_type(bot, {'Territory', 'Realm'})


def _exe_res_hg(bot) -> str | None:
    return _play_resource_type(
        bot, {'Enemy', 'Victim', 'Battlefield', 'Spirit'}
    )


def _exe_res_pass(bot) -> str | None:
    if bot.game.phase != 'resource':
        return None
    bot._pass_turn()
    return 'pass_resource'


def _exe_umbra_step(bot) -> str | None:
    me = bot.player
    if bot.game.phase != 'umbra':
        return None
    if getattr(bot, '_umbra_agiu', False):
        return None
    podem_ir, _podem_voltar = me.personagens_que_podem_step()
    if not podem_ir:
        return None
    c = podem_ir[0]
    try:
        if not me.step_sideways(c):
            return None
        bot._umbra_agiu = True
        return f'umbra_step_{c.uid}'
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] step falhou: %s', e)
        return None


def _exe_umbra_back(bot) -> str | None:
    me = bot.player
    if bot.game.phase != 'umbra':
        return None
    _podem_ir, podem_voltar = me.personagens_que_podem_step()
    if not podem_voltar:
        return None
    c = podem_voltar[0]
    try:
        if not me.step_back(c):
            return None
        return f'umbra_back_{c.uid}'
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] step back falhou: %s', e)
        return None


def _exe_umbra_pass(bot) -> str | None:
    if bot.game.phase != 'umbra':
        return None
    bot._pass_turn()
    return 'pass_umbra'


def _exe_moot_call(bot) -> str | None:
    g = bot.game
    me = bot.player
    if g.phase != 'moot' or g.combat.is_active:
        return None
    if g.moot_atual and not g.moot_atual.resolvido:
        return None
    for i, card in enumerate(me.hand):
        ct = (card.card_type or '').lower()
        if ct not in ('moot', 'board meeting'):
            continue
        is_board = ct == 'board meeting'
        modelo_id = card.modelo_id or ''
        ok = g.chamar_moot(bot.player_id, nome=card.name,
                           is_board_meeting=is_board,
                           modelo_id=modelo_id, card_uid=id(card))
        if ok:
            return f'moot_call_{card.card_id}'
    return None


def _exe_moot_vote_yes(bot) -> str | None:
    return _moot_vote(bot, True)


def _exe_moot_vote_no(bot) -> str | None:
    return _moot_vote(bot, False)


def _moot_vote(bot, a_favor: bool) -> str | None:
    g = bot.game
    if g.phase != 'moot' or g.combat.is_active:
        return None
    if not (g.moot_atual and not g.moot_atual.resolvido):
        return None
    if getattr(bot, '_moot_votou_uid', None) == id(g.moot_atual):
        return None
    bot._moot_votou_uid = id(g.moot_atual)
    g.votar_moot(bot.player_id, a_favor=a_favor)
    g.resolver_moot()
    return 'moot_vote_yes' if a_favor else 'moot_vote_no'


def _exe_moot_pass(bot) -> str | None:
    if bot.game.phase != 'moot':
        return None
    bot._pass_turn()
    return 'pass_moot'


def _exe_combat_act(bot) -> str | None:
    """Delega a ação de combate ao PriorityBot (heuristico).

    Com combate inativo: _agir_combate cuida do ataque/defesa.
    Com combate ativo: _decide_combat gerencia os steps.
    Se o step não mudar e o bot não progredir, avança manualmente
    para evitar travar o jogo.
    """
    g = bot.game
    if g.phase != 'combat':
        return None
    if not g.combat.is_active:
        try:
            return bot._agir_combate()
        except Exception as e:  # pragma: no cover
            logger.warning('[QL] _agir_combate falhou: %s', e)
            return None
    try:
        step_antes = g.combat.step
        result = bot._decide_combat()
        if result in ('combat_wait', 'wait', 'combat_unknown'):
            if g.combat.step == step_antes:
                advance_combat_step(g)
                return f'combat_to_{g.combat.step}'
        return result
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] _decide_combat falhou: %s', e)
        return None


def _exe_combat_pass(bot) -> str | None:
    g = bot.game
    if g.phase != 'combat':
        return None
    if g.combat.is_active:
        step_antes = g.combat.step
        try:
            if step_antes in ('play_card', 'targeting'):
                advance_combat_step(g)
                return f'combat_to_{g.combat.step}'
        except Exception:  # pragma: no cover
            pass
        bot._pass_turn()
        return 'combat_wait'
    bot._pass_turn()
    return 'pass'


def _exe_combat_end(bot) -> str | None:
    g = bot.game
    if g.phase != 'combat' or not g.combat.is_active:
        return None
    try:
        end_combat(g)
        return 'end_combat'
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] end_combat falhou: %s', e)
        return None


def _exe_redraw_pass(bot) -> str | None:
    if bot.game.phase != 'redraw':
        return None
    bot._pass_turn()
    return 'pass_redraw'


EXECUTORS = {
    'redraw_discard': _exe_redraw_discard,
    'redraw_lunar': _exe_redraw_lunar,
    'redraw_pass': _exe_redraw_pass,
    'regen_pass': _exe_regen_pass,
    'res_character': _exe_res_character,
    'res_equipment': _exe_res_equipment,
    'res_gift_event': _exe_res_gift_event,
    'res_ally': _exe_res_ally,
    'res_caern': _exe_res_caern,
    'res_territory': _exe_res_territory,
    'res_hg': _exe_res_hg,
    'res_pass': _exe_res_pass,
    'umbra_step': _exe_umbra_step,
    'umbra_back': _exe_umbra_back,
    'umbra_pass': _exe_umbra_pass,
    'moot_call': _exe_moot_call,
    'moot_vote_yes': _exe_moot_vote_yes,
    'moot_vote_no': _exe_moot_vote_no,
    'moot_pass': _exe_moot_pass,
    'combat_act': _exe_combat_act,
    'combat_pass': _exe_combat_pass,
    'combat_end': _exe_combat_end,
}


def execute_macro(bot, macro: str) -> str | None:
    """Executa a macro-ação e retorna a ação técnica (ou None)."""
    executor = EXECUTORS.get(macro)
    if executor is None:
        return None
    try:
        return executor(bot)
    except Exception as e:  # pragma: no cover
        logger.warning('[QL] executor %s falhou: %s', macro, e)
        return None
