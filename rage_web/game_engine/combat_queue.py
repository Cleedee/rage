"""Ciclo de combate com fila de acoes e 'Ultimo a Declarar'."""

from __future__ import annotations

from typing import Optional

from rage_web.game_engine.state import CombatState, GameState, PlayerState, Zone
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


def selecionar_alfa(game: GameState, jogador_id: str, card_id: str) -> bool:
    """Seleciona o alpha de um jogador para o combate.

    Regra (2.2.6):
    - Cada jogador seleciona um Character ou Ally como alpha.
    - Alpha com maior Renome age primeiro.
    - Se alpha morrer, nao pode selecionar outro ate o proximo Combat phase.

    Args:
        game: Estado da partida.
        jogador_id: ID do jogador.
        card_id: ID da criatura a ser alpha.

    Returns:
        True se o alpha foi selecionado.
    """
    jogador = None
    for p in game.players:
        if p.id == jogador_id:
            jogador = p
            break
    if not jogador:
        return False

    # Verifica se a criatura existe no pack do jogador
    criatura = None
    for c in jogador.pack_home:
        if str(c.card_id) == card_id:
            criatura = c
            break
    if not criatura:
        return False

    # So pode ser Character ou Ally
    if 'Character' not in (criatura.card_type or '') and 'Ally' not in (criatura.card_type or ''):
        return False

    game.combat.selecionar_alfa(jogador_id, card_id)
    game.add_log(f'{jogador.name} selecionou {criatura.name} como alpha')
    return True


def calcular_ordem_alfa(game: GameState) -> list[str]:
    """Calcula a ordem dos alphas por Renome decrescente.

    Regra (2.2.6):
    - Alpha com maior Renome age primeiro.
    - Empates sao resolvidos aleatoriamente.

    Returns:
        Lista de card_ids na ordem de acao.
    """
    import random

    def _get_renown(card_id: str) -> int:
        for p in game.players:
            for c in p.pack_home + p.umbra:
                if str(c.card_id) == card_id:
                    return c.renown
        return 0

    alphas = list(game.combat.alphas.values())
    # Ordena por Renome decrescente, desempatando aleatoriamente
    random.shuffle(alphas)  # Embaralha para desempate aleatorio
    alphas.sort(key=lambda cid: _get_renown(cid), reverse=True)
    game.combat.alpha_order = alphas
    game.combat.current_alpha_index = 0
    game.combat.alpha_actions_taken = 0
    return alphas


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


def _find_card(game: GameState, card_id: str) -> Optional[CardInstance]:
    """Encontra uma carta pelo ID em qualquer zona de qualquer jogador."""
    for p in game.players:
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra,
                          p.hand, p.discard_combat, p.discard_sept,
                          p.victory_pile):
            for c in zone_list:
                if str(c.card_id) == card_id:
                    return c
    return None


def _find_player(game: GameState, player_id: str) -> Optional[PlayerState]:
    """Encontra um jogador pelo ID."""
    for p in game.players:
        if p.id == player_id:
            return p
    return None


def _remove_creature(game: GameState, card: CardInstance):
    """Remove uma criatura de sua zona atual."""
    for p in game.players:
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra):
            if card in zone_list:
                zone_list.remove(card)
                return


def _find_owner(game: GameState, card: CardInstance) -> Optional[PlayerState]:
    """Encontra o jogador dono de uma carta."""
    return _find_player(game, card.owner_id)


ACOES_OFENSIVAS = {'strike', 'claw', 'bite', 'weapon_strike',
                    'ranged_strike', 'use_gift'}


def resolve_combat(game: GameState) -> bool:
    """Resolve o combate: aplica danos e efeitos.

    Regra (6.10):
    - strike/claw/bite/weapon_strike causa dano = Rage do atacante.
    - block/dodge anulam o dano de um ataque.
    - Criatura com health_current <= 0 morre e vai pra Victory Pile.
    - Atacar Hunting Grounds ('hg') concede 1 VP.

    Avanca do step 'reveal' para 'resolve'.
    Apos resolucao, avanca para 'end'.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step not in ('reveal', 'declare'):
        return False

    # Se ainda esta em declare, revela primeiro
    if game.combat.step == 'declare':
        combatants = get_combatants(game)
        if not game.combat.all_declared(combatants):
            return False
        reveal_all(game)

    game.combat.step = 'resolve'
    game.add_log('━ Resolvendo combate...')

    def _processar_ataque(origem_id: str, alvo_id: str):
        """Processa um ataque de origem contra alvo."""
        if alvo_id == 'hg':
            origem = _find_card(game, origem_id)
            if origem:
                dono = _find_owner(game, origem)
                if dono:
                    dono.victory_points += 1
                    game.add_log(f'  {origem.name} atacou Hunting Grounds! '
                                 f'+1 VP (total: {dono.victory_points})')
            return

        origem_card = _find_card(game, origem_id)
        alvo_card = _find_card(game, alvo_id)
        if not origem_card or not alvo_card:
            return

        acao_origem = game.combat.declarations.get(origem_id, 'strike')
        acao_alvo = game.combat.declarations.get(alvo_id, 'strike')

        # Origem precisa acao ofensiva
        if acao_origem not in ACOES_OFENSIVAS:
            return

        # Alvo pode bloquear/esquivar
        if acao_alvo in ('block', 'dodge'):
            game.add_log(f'  {alvo_card.name} {acao_alvo}ou o ataque de '
                         f'{origem_card.name}')
            return

        # Aplica dano
        dano = origem_card.rage
        alvo_card.health_current = max(0, alvo_card.health_current - dano)
        game.add_log(f'  {origem_card.name} causou {dano} de dano a '
                     f'{alvo_card.name} '
                     f'({alvo_card.health_current}/{alvo_card.health})')

        # Morte
        if alvo_card.health_current <= 0:
            dono_origem = _find_owner(game, origem_card)
            vp = alvo_card.renown if alvo_card.renown > 0 else 1
            if dono_origem:
                dono_origem.victory_points += vp
                alvo_card.zone = Zone.VICTORY_PILE
                _remove_creature(game, alvo_card)
                dono_origem.victory_pile.append(alvo_card)
                game.add_log(f'  {alvo_card.name} foi destruido! '
                             f'{dono_origem.name} ganhou {vp} VP '
                             f'(total: {dono_origem.victory_points})')

    # Processa atacantes contra defensores (match por indice)
    for i, a_id in enumerate(game.combat.attackers):
        if a_id == 'hg':
            continue
        d_id = (game.combat.defenders[i]
                if i < len(game.combat.defenders) else None)
        if d_id:
            _processar_ataque(a_id, d_id)

    # Processa contra-ataques: defensores ofensivos atacam de volta
    for i, d_id in enumerate(game.combat.defenders):
        if d_id == 'hg':
            continue
        a_id = (game.combat.attackers[i]
                if i < len(game.combat.attackers) else None)
        if not a_id:
            continue
        acao = game.combat.declarations.get(d_id, 'strike')
        if acao in ACOES_OFENSIVAS:
            _processar_ataque(d_id, a_id)

    game.combat.step = 'end'
    game.add_log('━ Combate encerrado.')
    return True


def verificar_vitoria(game: GameState) -> Optional[str]:
    """Verifica se alguem atingiu VP necessario para vencer.

    Regra (2.3):
    - Ao final de qualquer Combat phase, se um jogador tem VP
      >= renown_level, venceu.
    - Se dois ou mais tem, o com mais VP vence.
    - Se empate, continua.

    Returns:
        ID do vencedor, ou None se ninguem venceu.
    """
    vencedores = [p for p in game.players
                  if p.victory_points >= game.renown_level]
    if not vencedores:
        return None
    # Maior VP vence, desempate por ordem
    vencedores.sort(key=lambda p: p.victory_points, reverse=True)
    if len(vencedores) == 1:
        return vencedores[0].id
    # Empate no topo: continua
    if vencedores[0].victory_points == vencedores[1].victory_points:
        return None
    return vencedores[0].id


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
