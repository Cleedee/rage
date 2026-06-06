"""Ciclo de combate com fila de acoes e 'Ultimo a Declarar'."""

from __future__ import annotations

from typing import Optional

from rage_web.game_engine.state import (
    CombatState, GameState, PlayerState, Zone,
    anexar_dano, descartar_anexos,
)
from rage_web.game_engine.rules import COMBAT_STEPS


# --- Tipos de acoes de combate ---

# Acoes defensivas (block/dodge e similares)
ACOES_DEFENSIVAS = {'block', 'dodge'}

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
    'head_butt',        # Head Butt (dano 4, bounce se bloqueado)
    'tail_lash',        # Tail Lash (dano 1, +4 se Rokea/Mokole)
    'anatomy_lesson',   # Anatomy Lesson (dano 4, unblockable, retira)
    'savage_beatdown',  # Savage Beatdown (dano 3, descarte se frenzied)
    'submission_hold',  # Submission Hold (dano 1, remove ou anti-dodge)
}


# -----------------------------------------------------------------------
# Validadores de Combat Actions
# -----------------------------------------------------------------------
# Cada validador recebe (game, criatura) e retorna None se valido,
# ou uma string de erro se invalido.


def _find_criatura(game: GameState, card_id: str):
    """Busca uma criatura pelo card_id em todas as zonas visiveis.

    Args:
        game: Estado da partida.
        card_id: ID da criatura (string).

    Returns:
        CardInstance ou None se nao encontrada.
    """
    for p in game.players:
        for zone_cards in (p.pack_home, p.hunting_grounds,
                           p.umbra, p.hand):
            for c in zone_cards:
                if str(c.card_id) == card_id:
                    return c
    return None


def _validar_tail_lash(game: GameState, criatura) -> Optional[str]:
    """Valida se a criatura pode usar Tail Lash.

    Restricoes:
    - So pode ser usado por Rokea ou Mokole (keywords).
    - Nao pode ser usado com arma (attached_equipment do tipo Weapon).
    """
    keywords = (criatura.keywords or '').lower()
    is_rokea = 'rokea' in keywords
    is_mokole = 'mokole' in keywords
    if not is_rokea and not is_mokole:
        return ('Tail Lash so pode ser usado por Rokea ou Mokole '
                f'(keywords: {criatura.keywords})')
    # Verifica se tem arma equipada
    for eq in criatura.attached_equipment:
        eq_kw = (eq.keywords or '').lower()
        if 'weapon' in eq_kw:
            return ('Tail Lash nao pode ser usado com arma '
                    f'({eq.name} equipado)')
    return None


def _validar_tail_lash_bonus(game: GameState, criatura) -> Optional[str]:
    """Valida se a criatura recebe o bônus de +4 do Tail Lash.

    O bônus de +4 dano se aplica apenas se a criatura NÃO está
    em forma Homid.
    """
    keywords = (criatura.keywords or '').lower()
    is_homid = 'homid' in keywords
    if is_homid:
        return 'Bônus de +4 não se aplica em forma Homid'
    return None


def _validar_anatomy_lesson(game: GameState, criatura) -> Optional[str]:
    """Valida se a criatura pode usar Anatomy Lesson.

    Restricoes:
    - Requer: not frenzied.
    """
    if criatura.is_frenzied:
        return 'Anatomy Lesson requer: not frenzied'
    return None


COMBAT_ACTION_VALIDATORS: dict[str, list] = {
    'tail_lash': [_validar_tail_lash],
    'tail_lash_bonus': [_validar_tail_lash_bonus],
    'anatomy_lesson': [_validar_anatomy_lesson],
    'submission_hold': [_validar_anatomy_lesson],  # mesma regra: not frenzied
}


# -----------------------------------------------------------------------
# Propriedades de Combat Actions
# -----------------------------------------------------------------------

COMBAT_ACTION_PROPS: dict[str, dict] = {
    'anatomy_lesson': {
        'unblockable': True,       # Dano nao pode ser bloqueado/esquivado
        'retira_se_ferido': True,  # Criatura ferida deve retirar do combate
    },
    'savage_beatdown': {
        'descarte_metade_se_frenetico': True,  # Oponente descarta metade da mao se alvo frenzied
    },
    'submission_hold': {
        'retira_se_nao_frenetico': True,     # Remove do combate se alvo NAO frenzied
        'nao_pode_esquivar_se_frenetico': True,  # Alvo frenzied nao pode esquivar
    },
}


def _get_oponente_no_combate(game: GameState, card_id: str) -> Optional[str]:
    """Retorna o ID do oponente direto de uma criatura no combate.

    Os pares sao: atacantes[i] vs defensores[i].
    """
    if card_id in game.combat.attackers:
        idx = game.combat.attackers.index(card_id)
        if idx < len(game.combat.defenders):
            return game.combat.defenders[idx]
    elif card_id in game.combat.defenders:
        idx = game.combat.defenders.index(card_id)
        if idx < len(game.combat.attackers):
            return game.combat.attackers[idx]
    return None


def _tem_whip_equipado(game: GameState, card_id: str) -> bool:
    """Verifica se uma criatura tem Whip of the Wicked (720) equipado."""
    criatura = _find_criatura(game, card_id)
    if not criatura:
        return False
    for eq in criatura.attached_equipment:
        if eq.card_id == 720:  # Whip of the Wicked
            return True
    return False


def _validar_whip_constraint(game: GameState, card_id: str,
                              action: str) -> Optional[str]:
    """Valida constraint da Whip of the Wicked: oponente deve declarar
    acoes defensivas (block/dodge) antes de acoes ofensivas.

    Se o oponente direto tiver Whip equipado, o declarante precisa
    ja ter declarado um block/dodge antes de poder declarar ofensivas.

    Returns:
        None se valido, string de erro se violado.
    """
    # Acoes defensivas sao sempre permitidas
    if action in ACOES_DEFENSIVAS:
        return None

    oponente_id = _get_oponente_no_combate(game, card_id)
    if not oponente_id:
        return None

    if not _tem_whip_equipado(game, oponente_id):
        return None

    # Oponente tem Whip: verifica se ja declarou alguma acao defensiva
    declarou_defesa = any(
        a in ACOES_DEFENSIVAS
        for cid, a in game.combat.declarations.items()
        if cid == card_id
    )

    if not declarou_defesa:
        return (f'{card_id} deve declarar block ou dodge primeiro '
                f'(Whip of the Wicked no oponente)')

    return None


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

    # Verifica se criatura nao pode ser alpha 2 turnos seguidos (Allonzo Montoya)
    if 'nao_pode_alpha_2_turnos_seguidos' in criatura.restricoes:
        last_alpha = game.last_alpha_per_player.get(jogador_id)
        if last_alpha == str(criatura.card_id):
            game.add_log(f'{criatura.name} foi alpha no ultimo combate,'
                         f' nao pode ser alpha agora')
            return False

    game.combat.selecionar_alfa(jogador_id, card_id)
    # Registra alpha atual para Next turn check
    game.last_alpha_per_player[jogador_id] = str(criatura.card_id)
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
    - Criaturas na Umbra so podem atacar outras na Umbra.
    - Criaturas no mundo fisico so com outras no mundo fisico.
    - Criaturas em Hunting Grounds existem em ambos os lados.
    - Caern, Territory e Spirits existem em ambos os lados.
    """
    if card_id_a == 'hg' or card_id_b == 'hg':
        return True

    def _lado(cid: str) -> int:
        """Returns: -1 = umbra, 0 = ambos os lados, 1 = mundo fisico."""
        for p in game.players:
            for c in p.umbra:
                if str(c.card_id) == cid:
                    return -1
            for c in p.hunting_grounds:
                if str(c.card_id) == cid:
                    return 0
            for c in p.pack_home:
                if str(c.card_id) == cid:
                    if c.card_type in ('Caern', 'Territory') or 'Spirit' in (c.keywords or ''):
                        return 0
                    return 1
        # Zona neutra de Hunting Grounds
        for c in game.hunting_grounds_cards:
            if str(c.card_id) == cid:
                return 0
        return 1  # padrao: mundo fisico

    lado_a = _lado(card_id_a)
    lado_b = _lado(card_id_b)

    if lado_a == 0 or lado_b == 0:
        return True

    return lado_a == lado_b


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

    # Limpa restricoes temporarias de combates anteriores
    # (preserva restricoes permanentes de efeitos como rage_breed)
    RESTRICOES_COMBATE = {'nao_pode_esquivar'}
    for p in game.players:
        for zone_cards in (p.pack_home, p.hunting_grounds, p.umbra):
            for c in zone_cards:
                c.restricoes = [r for r in c.restricoes
                                if r not in RESTRICOES_COMBATE]

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

    # Tzinzie (1348): trigger de inicio de combate
    _check_tzinzie_trigger(game)

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


def declare_action(game: GameState, card_id: str, action: str,
                     acoes_extra: Optional[list[str]] = None) -> bool:
    """Declara uma acao de combate para uma criatura.

    A ordem da declaracao importa: quem declara por ultimo
    ganha vantagem no Reveal Step (pode usar Feint).

    Args:
        game: Estado da partida.
        card_id: ID da criatura que esta declarando.
        action: Nome da acao (ex: 'strike', 'block', 'dodge').
        acoes_extra: Lista opcional de acoes extras permitidas
                      (ex: Combat Actions especificas como 'tail_lash').

    Returns:
        True se a declaracao foi aceita.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'declare':
        return False
    if card_id not in get_combatants(game):
        return False

    # Valida se a acao e permitida
    if action not in COMBAT_ACTIONS:
        # Verifica em acoes extras (Combat Actions especificas)
        if not acoes_extra or action not in acoes_extra:
            return False

    # Valida restricoes especificas da Combat Action
    if action in COMBAT_ACTION_VALIDATORS:
        criatura = _find_criatura(game, card_id)
        if criatura:
            for validador in COMBAT_ACTION_VALIDATORS[action]:
                erro = validador(game, criatura)
                if erro:
                    game.add_log(f'Acao recusada: {erro}')
                    return False

    # Whip of the Wicked (720): oponente deve declarar block/dodge primeiro
    erro_whip = _validar_whip_constraint(game, card_id, action)
    if erro_whip:
        game.add_log(f'Whip of the Wicked: {erro_whip}')
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

    # Tzinzie (1348): se oponente revelou a acao nomeada, descarta
    if 1348 in game.combat_triggers:
        tz = game.combat_triggers[1348]
        named_action = tz.get('named_action', '')
        owner_id = tz.get('owner_id', '')
        for cid, action in game.combat.declarations.items():
            # Verifica se e um oponente que revelou a acao
            card = _find_card(game, cid)
            if card and action == named_action:
                dono = _find_owner(game, card)
                if dono and dono.id != owner_id:
                    # Descarta uma carta aleatoria da mao
                    if dono.hand:
                        import random as rng
                        idx = rng.randint(0, len(dono.hand) - 1)
                        descartada = dono.hand.pop(idx)
                        descartada.zone = Zone.DISCARD_COMBAT
                        dono.discard_combat.append(descartada)
                        game.add_log(
                            f'Tzinzie: {dono.name} descartou '
                            f'{descartada.name} da mao (revelou {action})'
                        )
                    break

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


def _retirar_do_combate(game: GameState, criatura: CardInstance) -> bool:
    """Retira uma criatura do combate (retreat/withdraw).

    A criatura e removida das listas de attackers/defenders
    e movida para o discard de combate do seu dono.

    Returns:
        True se a criatura foi retirada com sucesso.
    """
    combat = game.combat
    if not combat.is_active:
        return False

    # Remove das listas de combate
    if criatura.card_id in [str(c) for c in combat.attackers]:
        combat.attackers = [a for a in combat.attackers
                            if str(a) != str(criatura.card_id)]
    if criatura.card_id in [str(c) for c in combat.defenders]:
        combat.defenders = [d for d in combat.defenders
                            if str(d) != str(criatura.card_id)]

    # Remove da zona atual e move para discard
    dono = _find_owner(game, criatura)
    _remove_creature(game, criatura)
    criatura.zone = Zone.DISCARD_COMBAT
    if dono:
        dono.discard_combat.append(criatura)
    return True


def _find_owner(game: GameState, card: CardInstance) -> Optional[PlayerState]:
    """Encontra o jogador dono de uma carta."""
    return _find_player(game, card.owner_id)


ACOES_OFENSIVAS = {'strike', 'claw', 'bite', 'weapon_strike',
                    'ranged_strike', 'use_gift',
                    'head_butt', 'tail_lash', 'anatomy_lesson',
                    'savage_beatdown', 'submission_hold'}


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

        # Se o alvo ja morreu neste combate, ignora o ataque
        if alvo_card.zone == Zone.VICTORY_PILE or alvo_card.health_current <= 0:
            game.add_log(
                f'  {origem_card.name} atacou {alvo_card.name} '
                f'mas ele ja estava morto.'
            )
            return

        # Verifica imunidade (ex: Elethoi so e afetado por Gift/Umbral)
        if 'imune_fora_umbra' in alvo_card.restricoes:
            if origem_card.zone != Zone.UMBRA:
                game.add_log(
                    f'  {alvo_card.name} e imune a ataques nao-umbrais. '
                    f'{origem_card.name} nao causou dano.'
                )
                return

        acao_origem = game.combat.declarations.get(origem_id, 'strike')
        acao_alvo = game.combat.declarations.get(alvo_id, 'strike')

        # Origem precisa acao ofensiva
        if acao_origem not in ACOES_OFENSIVAS:
            return

        # Calcula dono da origem (necessario para Head Butt bounce e dano)
        dono_origem = _find_owner(game, origem_card)
        dono_dono = dono_origem.id if dono_origem else origem_card.owner_id

        # Verifica propriedades especiais da acao
        props = COMBAT_ACTION_PROPS.get(acao_origem, {})
        is_unblockable = props.get('unblockable', False)
        retira_se_ferido = props.get('retira_se_ferido', False)

        # Verifica se o alvo tem restricao de nao poder esquivar
        if acao_alvo == 'dodge' and 'nao_pode_esquivar' in alvo_card.restricoes:
            game.add_log(
                f'  {alvo_card.name} tentou esquivar, mas nao pode! '
                f'(restricao de Submission Hold)'
            )
            # Trata como se nao tivesse bloqueado — o dano sera aplicado
            # Continua para a aplicacao de dano abaixo
        # Alvo pode bloquear/esquivar (a menos que seja unblockable)
        elif acao_alvo in ('block', 'dodge') and not is_unblockable:
            game.add_log(f'  {alvo_card.name} {acao_alvo}ou o ataque de '
                         f'{origem_card.name}')
            # Head Butt: se bloqueado, vira damage card no atacante (exceto Mokole)
            if acao_origem == 'head_butt':
                keywords = (origem_card.keywords or '').lower()
                if 'mokole' not in keywords:
                    anexar_dano(origem_card, origem_card, 4, dono_dono)
                    game.add_log(
                        f'  Head Butt bloqueado! {origem_card.name} '
                        f'recebe 4 de dano de volta'
                    )
                else:
                    game.add_log(
                        f'  Head Butt bloqueado, mas {origem_card.name} '
                        f'e Mokole (sem dano de volta)'
                    )
            return

        if is_unblockable and acao_alvo in ('block', 'dodge'):
            game.add_log(
                f'  {alvo_card.name} tentou {acao_alvo}, mas '
                f'{acao_origem} e unblockable!'
            )

        # War Knife (716): dano agravado se Rage <= 4
        war_knife_aggravated = False
        for eq in origem_card.attached_equipment:
            if eq.card_id == 716:  # War Knife of Benning Simon
                if origem_card.effective_rage <= 4:
                    war_knife_aggravated = True
                    game.add_log(
                        f'  War Knife: dano agravado '
                        f'({origem_card.name} Rage {origem_card.effective_rage} <= 4)')
                break

        # Skin of the Hellbound (697): imune a dano de Rage 6+
        skin_blocks = False
        for eq in alvo_card.attached_equipment:
            if eq.card_id == 697:  # Skin of the Hellbound
                if origem_card.effective_rage >= 6:
                    skin_blocks = True
                    game.add_log(
                        f'  Skin of the Hellbound: {alvo_card.name} '
                        f'imune a dano de Rage {origem_card.effective_rage} '
                        f'({origem_card.name})')
                break

        # Aplica dano e cria damage card (regra 6.4)
        if skin_blocks:
            dano = 0
        else:
            dano = max(0, origem_card.effective_rage - alvo_card.reducao_dano)

        # Ironjaw (369): +1 dano se nem ela nem alvo tem arma
        if 'ironjaw_bonus' in origem_card.restricoes:
            tem_arma_origem = any(
                'weapon' in (eq.keywords or '').lower()
                for eq in origem_card.attached_equipment)
            tem_arma_alvo = any(
                'weapon' in (eq.keywords or '').lower()
                for eq in alvo_card.attached_equipment)
            if not tem_arma_origem and not tem_arma_alvo:
                dano += 1
                game.add_log(f'  Ironjaw: +1 dano (sem armas)')

        # Njoki Scarface (373): reduz 1 de dano (precisa +1 card pra morrer)
        if 'njoki_tough' in alvo_card.restricoes:
            dano = max(0, dano - 1)
            game.add_log(f'  Njoki scarface reduziu 1 de dano')

        if alvo_card.reducao_dano > 0 and not skin_blocks:
            game.add_log(f'  {alvo_card.name} reduziu {alvo_card.reducao_dano} '
                         f'de dano (equipamento)')
        anexar_dano(alvo_card, origem_card, dano, dono_dono,
                    is_aggravated=war_knife_aggravated)
        game.add_log(f'  {origem_card.name} causou {dano} de dano a '
                     f'{alvo_card.name} '
                     f'({alvo_card.health_current}/{alvo_card.health})')

        # Retirada do combate (Anatomy Lesson: criatura ferida deve retirar)
        if retira_se_ferido and alvo_card.health_current < alvo_card.health:
            if _retirar_do_combate(game, alvo_card):
                game.add_log(
                    f'  {alvo_card.name} ferida por {acao_origem}! '
                    f'Retirou-se do combate.'
                )

        # Savage Beatdown: se alvo frenzied, oponente descarta metade da mao
        if props.get('descarte_metade_se_frenetico') and alvo_card.is_frenzied:
            dono_alvo = _find_owner(game, alvo_card)
            if dono_alvo:
                mao = dono_alvo.hand
                import math
                qtd = math.ceil(len(mao) / 2)
                if qtd > 0:
                    descartadas = mao[:qtd]
                    for c in descartadas:
                        c.zone = Zone.DISCARD_COMBAT
                        mao.remove(c)
                        dono_alvo.discard_combat.append(c)
                    game.add_log(
                        f'  Savage Beatdown! {alvo_card.name} esta '
                        f'frenzied. {dono_alvo.name} descartou '
                        f'{len(descartadas)} carta(s) (metade da mao).'
                    )

        # Submission Hold: efeito baseado no estado do alvo
        if props.get('retira_se_nao_frenetico'):
            if not alvo_card.is_frenzied:
                # Alvo nao-frenzied: remove do combate
                if _retirar_do_combate(game, alvo_card):
                    game.add_log(
                        f'  Submission Hold! {alvo_card.name} '
                        f'(nao-frenzied) retirou-se do combate.'
                    )
            elif props.get('nao_pode_esquivar_se_frenetico'):
                # Alvo frenzied: nao pode esquivar na proxima rodada
                alvo_card.restricoes.append('nao_pode_esquivar')
                game.add_log(
                    f'  Submission Hold! {alvo_card.name} (frenzied) '
                    f'nao podera esquivar na proxima rodada.'
                )

        # Morte
        if alvo_card.health_current <= 0:
            dono_alvo = _find_owner(game, alvo_card)
            # Descarta cartas anexadas (regra 6.4.2)
            if dono_alvo:
                descartar_anexos(alvo_card, dono_alvo)
            vp = alvo_card.renown if alvo_card.renown > 0 else 1
            if dono_origem:
                dono_origem.victory_points += vp
                alvo_card.zone = Zone.VICTORY_PILE
                _remove_creature(game, alvo_card)
                dono_origem.victory_pile.append(alvo_card)
                game.add_log(f'  {alvo_card.name} foi destruido! '
                             f'{dono_origem.name} ganhou {vp} VP '
                             f'(total: {dono_origem.victory_points})')

                # Death triggers (ex: Dream Hunter)
                game.check_death_triggers(
                    alvo_card, origem_card, dono_origem
                )

                # Kill bonuses (Questor, The Pit, Chronicle)
                game.check_kill_bonuses(alvo_card, dono_origem)

                # Marca dano em quests (se alvo era alvo de quest, reseta)
                for p in game.players:
                    for q in p.quests:
                        if q.target_card_uid == id(alvo_card) and not q.completed:
                            # Alvo tomou dano fatal -> quest falhou
                            q.completed = True
                            game.add_log(
                                f'  Quest falhou: {alvo_card.name} '
                                f'(alvo da quest) foi destruido'
                            )

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

    # Clan of Hyenas (96): foge do combate se tomou >=3 dano neste round
    _check_hyenas_escape(game)

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


def lone_wolf_circles_dodge(game: GameState, lone_card_id: str,
                              dodge_target_id: str) -> bool:
    """Lone Wolf Circles cancela propria acao e esquiva de um ataque.

    Regra: apos revelar no primeiro round, Lone pode cancelar sua
    acao de combate e esquivar de uma acao de combate contra ele.
    Deve ser chamado apos reveal_all() e antes de resolve_combat().

    Args:
        game: Estado da partida.
        lone_card_id: ID da instancia de Lone Wolf Circles.
        dodge_target_id: ID da criatura cuja acao Lone quer esquivar.

    Returns:
        True se o dodge foi aplicado.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step != 'reveal':
        return False

    lone = _find_card(game, lone_card_id)
    if not lone or lone.card_id != 174:  # 174 = Lone Wolf Circles
        return False

    alvo = _find_card(game, dodge_target_id)
    if not alvo:
        return False

    # Cancela a acao do Lone (define como 'dodge')
    game.combat.declarations[lone_card_id] = 'dodge'
    game.add_log(
        f'{lone.name} cancelou sua acao e esquivou (Lone Wolf Circles)'
    )

    # Esquiva da acao do alvo: se for ofensiva, muda pra 'dodge' tbm
    # (assim o processamento ve que lone 'dodged' e nao aplica dano)
    dodge_acao = game.combat.declarations.get(dodge_target_id, '')
    if dodge_acao in ACOES_OFENSIVAS:
        game.add_log(
            f'{lone.name} esquivou do ataque de {alvo.name}'
        )
    else:
        game.add_log(
            f'{lone.name} esquivou (acao defensiva contra {alvo.name})'
        )

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


def _check_tzinzie_trigger(game: GameState):
    """Verifica se algum jogador tem Tzinzie (1348) ativo no combate.

    Tzinzie: Personal Totem. No inicio do combate, o dono pode nomear
    uma Combat Action. Quando oponente revela essa acao, descarta
    uma carta aleatoria da mao de combate.
    """
    for p in game.players:
        for c in p.pack_home + p.hunting_grounds:
            if c.card_id == 1348:  # Tzinzie
                # Nomeia a acao mais comum: strike
                game.combat_triggers[1348] = {
                    'named_action': 'strike',
                    'owner_id': p.id,
                    'card_uid': id(c),
                }
                game.add_log(
                    f'{p.name} nomeou strike (Tzinzie)')
                return


def _check_hyenas_escape(game: GameState):
    """Clan of Hyenas (96): foge do combate se tomou >=3 dano neste round.

    Verifica todos os combatentes. Se um deles e o Clan of Hyenas
    e tem >=3 de dano total anexado (attached_damage), remove-o
    do combate e devolve ao pack home.
    """
    from rage_web.game_engine.combat_queue import get_combatants
    combatentes = get_combatants(game)
    for cid in combatentes:
        carta = _find_card(game, cid)
        if not carta or carta.card_id != 96:
            continue
        dano_total = sum(getattr(d, 'rage', 0) or 0
                        for d in carta.attached_damage)
        if dano_total >= 3:
            dono = _find_owner(game, carta)
            if dono and carta in dono.pack_home:
                game.add_log(
                    f'  Clan of Hyenas fugiu do combate '
                    f'(tomou {dano_total} de dano)')
                # Remove do combate (apenas remove das listas de combatentes)
                if cid in game.combat.attackers:
                    game.combat.attackers.remove(cid)
                if cid in game.combat.defenders:
                    game.combat.defenders.remove(cid)
                if cid in game.combat.declarations:
                    del game.combat.declarations[cid]
                break


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
