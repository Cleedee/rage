"""Ciclo de combate com fila de acoes e 'Ultimo a Declarar'."""

from __future__ import annotations

from typing import Optional

from rage_web.game_engine.state import CombatState, GameState, PlayerState
from rage_web.game_engine.rules import COMBAT_STEPS


# --- Tipos de acoes de combate ---

COMBAT_ACTIONS = {
    'strike',           # Ataque basico
    'block',            # Defesa
    'dodge',            # Esquiva
    'feint',            # Finta (muda acao apos ver as outras)
    'instinctive',      # Acao instintiva (quando stymied)
    'ranged_strike',    # Ataque a distancia
    'claw',             # Ataque com garras
    'bite',             # Mordida
    'weapon_strike',    # Ataque com arma
    'use_gift',         # Usar Gift em combate
    'use_equipment',    # Usar Equipment em combate
    'flee',             # Fugir do combate
}


def _mesmo_lado_gauntlet(game: GameState, card_id_a: str,
                          card_id_b: str) -> bool:
    """Verifica se duas criaturas estao no mesmo lado do Gauntlet.

    Regra (5):
    - Criaturas na Umbra so podem atacar com outras na Umbra.
    - Criaturas no mundo fisico so com outras no mundo fisico.
    - Hunting Grounds ('hg') existe em ambos os lados.
    """
    if card_id_a == 'hg' or card_id_b == 'hg':
        return True

    def _esta_na_umbra(cid: str) -> bool:
        for p in game.players:
            for c in p.umbra:
                if str(c.card_id) == cid:
                    return True
        return False

    a_umbra = _esta_na_umbra(card_id_a)
    b_umbra = _esta_na_umbra(card_id_b)
    return a_umbra == b_umbra


def start_combat(game: GameState, attackers: list[str],
                 defenders: list[str]) -> bool:
    """Inicia um combate entre atacantes e defensores.

    Args:
        game: Estado da partida.
        attackers: Lista de IDs das criaturas atacantes.
        defenders: Lista de IDs das criaturas defensoras.

    Returns:
        True se o combate foi iniciado.
    """
    if game.combat.is_active:
        return False

    # Verifica Gauntlet
    for atk in attackers:
        for dfd in defenders:
            if not _mesmo_lado_gauntlet(game, atk, dfd):
                game.add_log(
                    f'Combate cancelado: {atk} e {dfd} estao em '
                    f'lados diferentes do Gauntlet')
                return False

    game.combat = CombatState(
        is_active=True,
        step='declare',
        attackers=attackers,
        defenders=defenders,
    )

    game.add_log(
        f'Combate iniciado: {len(attackers)} atacante(s) vs '
        f'{len(defenders)} defensor(es)'
    )
    return True


def get_combatants(game: GameState) -> list[str]:
    """Retorna lista de IDs de todas as criaturas no combate.

    Exclui alvos especiais como 'hg' (hunting grounds) que
    nao sao criaturas e nao declaram acoes.
    """
    result = []
    for cid in game.combat.attackers + game.combat.defenders:
        if cid != 'hg':
            result.append(cid)
    return result


def declare_action(game: GameState, card_id: str, action: str) -> bool:
    """Declara uma acao de combate para uma criatura.

    A ordem da declaracao importa: quem declara por ultimo
    ganha vantagem no Reveal Step (pode usar Feint).

    Args:
        game: Estado da partida.
        card_id: ID da criatura que esta declarando.
        action: Nome da acao (ex: 'strike', 'block', 'dodge').

    Returns:
        True se a declaracao foi aceita.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'declare':
        return False
    if card_id not in get_combatants(game):
        return False
    if action not in COMBAT_ACTIONS:
        return False

    success = game.combat.declare(card_id, action)
    if success:
        last = game.combat.last_to_declare
        game.add_log(
            f'{card_id} declarou {action}'
            f'{" (Ultimo a Declarar!)" if card_id == last else ""}'
        )
    return success


def can_feint(game: GameState, card_id: str) -> bool:
    """Verifica se uma criatura pode usar Feint.

    So pode Feint quem declarou por ultimo (ou tem habilidade
    especial que permita), e estamos no Reveal Step.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'reveal':
        return False
    # Regra basica: so o ultimo a declarar pode Feint
    return card_id == game.combat.last_to_declare


def feint_action(game: GameState, card_id: str, new_action: str) -> bool:
    """Troca a acao declarada usando Feint.

    So pode ser feito no Reveal Step pela criatura que
    declarou por ultimo.
    """
    if not can_feint(game, card_id):
        return False
    if new_action not in COMBAT_ACTIONS:
        return False

    old_action = game.combat.declarations.get(card_id)
    game.combat.declarations[card_id] = new_action

    if old_action:
        game.add_log(f'{card_id} usou Feint: {old_action} -> {new_action}')
    return True


def reveal_all(game: GameState) -> bool:
    """Revela todas as acoes de combate declaradas.

    Avanca do step 'declare' para 'reveal'.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'declare':
        return False

    combatants = get_combatants(game)
    if not game.combat.all_declared(combatants):
        return False  # Nem todos declararam

    game.combat.step = 'reveal'
    game.add_log('Acoes reveladas!')
    for cid, action in game.combat.declarations.items():
        game.add_log(f'  {cid}: {action}')

    return True


def resolve_combat(game: GameState) -> bool:
    """Resolve o combate: aplica danos e efeitos.

    Avanca do step 'reveal' para 'resolve'.
    Apos resolucao, avanca para 'end'.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'reveal' and game.combat.step != 'declare':
        return False

    # Se ainda esta em declare, revela primeiro
    if game.combat.step == 'declare':
        combatants = get_combatants(game)
        if not game.combat.all_declared(combatants):
            return False
        reveal_all(game)

    game.combat.step = 'resolve'
    game.add_log('Resolvendo combate...')

    # Logica simples de resolucao:
    # strike causa dano igual ao Rage da criatura
    # block anula o dano recebido
    # dodge evita o ataque
    # (versao inicial basica - sera expandida)
    for cid, action in game.combat.declarations.items():
        game.add_log(f'  {cid}: {action} resolvido')

    game.combat.step = 'end'
    game.add_log('Combate encerrado.')
    return True


def end_combat(game: GameState) -> bool:
    """Encerra o combate e reseta o estado."""
    if not game.combat.is_active:
        return False

    if game.combat.step != 'end':
        resolve_combat(game)

    game.combat = CombatState()
    game.add_log('--- Fim do combate ---')
    return True


def get_declaration_summary(game: GameState) -> dict:
    """Retorna resumo das declaracoes para debug.

    So revela acoes apos o Reveal Step.
    """
    summary = {
        'is_active': game.combat.is_active,
        'step': game.combat.step,
        'attackers': game.combat.attackers,
        'defenders': game.combat.defenders,
        'declarations': {},
        'last_to_declare': game.combat.last_to_declare,
    }

    if game.combat.step in ('reveal', 'resolve', 'end'):
        # Revela as acoes
        summary['declarations'] = dict(game.combat.declarations)
    else:
        # Em 'declare', mostra apenas quantos declararam
        declared = len(game.combat.declarations)
        total = len(get_combatants(game))
        summary['declared_count'] = f'{declared}/{total}'

    return summary
