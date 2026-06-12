"""Ciclo de combate com fila de acoes e 'Ultimo a Declarar'."""

from __future__ import annotations

from typing import Optional

from rage_web.game_engine.state import (
    CombatState, GameState, PlayerState, Zone,
    anexar_dano, descartar_anexos,
)
from rage_web.game_engine.rules import COMBAT_STEPS, COMBAT_STEPS_AUTO

# Mapeamento de steps antigos para novos (backward compat)
OLD_STEP_MAP = {
    'declare': 'play_card',
}

# --- Tipos de acoes de combate ---

# Acoes defensivas (block/dodge e similares)
ACOES_DEFENSIVAS = {'block', 'dodge'}


def _eh_pack_gaia(dono: Optional[PlayerState]) -> bool:
    """Verifica se o dono e um pack Gaia.
    Heuristica: personagens com 'Gaia' no tipo.
    """
    if not dono:
        return False
    for c in dono.pack_home + dono.hunting_grounds + dono.umbra:
        ct = (c.card_type or '').lower()
        if 'character' in ct and 'gaia' in ct:
            return True
    return False


def _eh_pack_wyrm(dono: Optional[PlayerState]) -> bool:
    """Verifica se o dono e um pack Wyrm.
    Heuristica: personagens com 'Wyrm' no tipo.
    """
    if not dono:
        return False
    for c in dono.pack_home + dono.hunting_grounds + dono.umbra:
        ct = (c.card_type or '').lower()
        if 'character' in ct and 'wyrm' in ct:
            return True
    return False


def _flipar_para_crinos(game: GameState, card: CardInstance) -> bool:
    """Flip para forma Crinos quando dano atinge threshold.

    Regra (14-ritos-moots.md):
    Se um personagem em Breed form toma dano e o dano total
    acumulado >= Rage OU >= Health da forma breed, ele flipa
    para a forma Crinos/Battle (a menos que impedido).
    Soh morre se o dano >= Crinos-form Health.

    Args:
        game: Estado da partida.
        card: A criatura.

    Returns:
        True se flipou para Crinos.
    """
    # So flipa se tiver morph values diferentes dos breed e
    # ja nao estiver em Crinos
    if card.is_crinos:
        return False
    if card.health_morph <= 0 and card.rage_morph <= 0:
        return False
    # Impedido de mudar de forma?
    if 'nao_pode_mudar_forma' in card.restricoes:
        return False
    # Verifica se os valores morph sao diferentes dos breed
    if (card.health_morph == card.health
        and card.rage_morph == card.rage
        and card.gnosis_morph == card.gnosis):
        return False  # Mesma forma (ex: Metis)

    # Calcula dano total acumulado
    dano_total = card.health - card.health_current
    if dano_total <= 0:
        return False

    # Threshold: menor entre Rage e Health da forma breed
    threshold = min(card.rage, card.health)
    if threshold <= 0:
        return False
    if dano_total < threshold:
        return False

    # Flip!
    card.is_crinos = True
    card.restricoes.append('rage_breed')
    card.restricoes.append('health_breed')
    card.restricoes.append('gnosis_breed')

    # Recalcula health_current: mesmo dano total,
    # mas o pool de vida agora e health_morph
    # (sync_health() usa health_morph quando is_crinos)
    if card.health_morph > 0:
        card.sync_health()

    game.add_log(
        f'  🔄 {card.name} flipou para forma Crinos! '
        f'(dano={dano_total}, R={card.rage_morph} '
        f'H={card.health_morph} G={card.gnosis_morph})'
    )
    return True


def _entrar_em_frenesi(game: GameState, card: CardInstance,
                        jogador: PlayerState) -> bool:
    """Faz uma criatura entrar em estado de frenesi.

    Regra (6.11.3 - Full Frenzy):
    - Flipa para forma Crinos
    - Define is_frenzied = True
    - Compra cartas do combate = Rage da forma atual
    - Adiciona restricao 'frenesi'

    Args:
        game: Estado da partida.
        card: A criatura que vai frenzir.
        jogador: O jogador que controla a criatura.

    Returns:
        True se entrou em frenesi.
    """
    if card.is_frenzied:
        return False

    # Nao pode frenzir se impedido
    if 'impede_frenzy' in game.game_modifiers:
        return False
    if 'nao_pode_frenzy' in card.restricoes:
        return False

    # Flipa para Crinos
    flipou = _flipar_para_crinos(game, card)

    # Marca como frenzied
    card.is_frenzied = True
    if 'frenesi' not in card.restricoes:
        card.restricoes.append('frenesi')

    # Compra cartas do combate = Rage efetivo (6.11.3)
    rage_efetivo = card.effective_rage
    compradas = 0
    if rage_efetivo > 0:
        compradas_lista = jogador.draw_combat(rage_efetivo)
        compradas = len(compradas_lista)
        if compradas > 0:
            game.add_log(
                f'  {card.name} frenzied! Comprou {compradas} '
                f'carta(s) de combate (Rage {rage_efetivo})'
            )

    # Armazena metadados do frenzy no card
    # (usando atributos dinâmicos, CardInstance nao e frozen)
    card.frenzy_cards_drawn = compradas
    # Hacked apart threshold = Health + Rage no momento do frenzy
    # (6.11.3: determinado quando o frenzy comeca, apos flipar para Crinos)
    card.frenzy_hack_threshold = card.health_current + card.effective_rage
    # Marca o health no inicio do frenzy para Hacked Apart
    card.frenzy_starting_health = card.health_current

    game.add_log(
        f'  🔥 {card.name} entrou em frenesi! '
        f'{"(Crinos)" if flipou else ""}'
        f' | Hacked apart: {card.frenzy_hack_threshold} de dano'
    )
    return True


def _sair_do_frenesi(game: GameState, card: CardInstance) -> bool:
    """Remove o estado de frenesi de uma criatura.

    Regra (6.11.2): Frenzy termina quando:
    - O combate termina
    - Um efeito cancela o frenzy
    - A criatura fica sem acoes viaveis

    Ao terminar, descarta aleatoriamente da mao de combate
    um numero de cartas igual as que foram compradas no frenzy.

    Args:
        game: Estado da partida.
        card: A criatura.

    Returns:
        True se saiu do frenesi.
    """
    if not card.is_frenzied:
        return False

    # (6.11.2) Descarta cartas do combat hand = cards drawn
    cards_drawn = getattr(card, 'frenzy_cards_drawn', 0)
    if cards_drawn > 0:
        dono = _find_owner(game, card)
        if dono:
            combat_hand = dono._cartas_combate()
            descartar = min(cards_drawn, len(combat_hand))
            if descartar > 0:
                # Seleciona aleatoriamente (usa rng do jogo para deterministico)
                descarte = game.rng.sample(combat_hand, descartar)
                for c in descarte:
                    c.zone = Zone.DISCARD_COMBAT
                    dono.hand.remove(c)
                    dono.discard_combat.append(c)
                game.add_log(
                    f'  Fim de frenesi: {card.name} descartou '
                    f'{descartar} carta(s) da mao de combate'
                )

    card.is_frenzied = False
    if 'frenesi' in card.restricoes:
        card.restricoes.remove('frenesi')
    # Limpa metadados
    for attr in ('frenzy_cards_drawn', 'frenzy_hack_threshold',
                 'frenzy_starting_health'):
        if hasattr(card, attr):
            delattr(card, attr)

    game.add_log(f'  {card.name} saiu do frenesi')
    return True


def _processar_morte(game: GameState, alvo: CardInstance, origem: CardInstance,
                      dono_origem: Optional[PlayerState],
                      em_combate: bool = False) -> bool:
    """Processa a morte de uma criatura.

    Regra (6.4.2):
    - Se morreu em combate: descarta anexos e vai pro Victory Pile
      do oponente.
    - Se morreu fora de combate ou por Presa: descarta anexos.
      Non-character -> descartado. Character -> removido do jogo.
    - Se morreu em combate mas foi morto por Presa (Victim/Enemy):
      descarta anexos e vai pro Victory Pile de ninguem (ou descarta).

    Args:
        game: Estado da partida.
        alvo: A criatura que morreu.
        origem: A criatura que causou o dano.
        dono_origem: Dono da origem (pode ser None se sem dono).
        em_combate: Se True, a morte ocorreu durante um combate.

    Returns:
        True se a criatura foi processada como morta.
    """
    if alvo.health_current > 0:
        return False

    # Salva zona original antes de processar morte
    zona_original_death = alvo.zone

    dono_alvo = _find_owner(game, alvo)

    # Descarta anexos (damage cards + equipamentos)
    # Hacked Apart (6.11.3): criatura frenzied continua lutando
    # mesmo morta, ate o fim do combate/frenzy ou ate atingir
    # o threshold de dano = Health + Rage (medido no inicio do frenzy).
    eh_hacked_apart = False
    if alvo.is_frenzied and em_combate:
        hack_threshold = getattr(alvo, 'frenzy_hack_threshold', 0)
        dano_total = alvo.health - alvo.health_current
        if dano_total >= hack_threshold:
            eh_hacked_apart = True  # Dano suficiente: morre de vez
    
    if dono_alvo:
        descartar_anexos(alvo, dono_alvo)
    else:
        # Sem dono (HG global): descarta anexos sem dono
        for anexo in list(alvo.attached_damage):
            anexo.zone = Zone.OUT_OF_PLAY
        alvo.attached_damage.clear()
        for eq in list(alvo.attached_equipment):
            eq.zone = Zone.OUT_OF_PLAY
        alvo.attached_equipment.clear()

    # Verifica se foi morto por uma Presa (Victim/Enemy)
    ct_origem = (origem.card_type or '').lower() if origem else ''
    morto_por_presa = any(t in ct_origem for t in ['victim', 'enemy'])

    if em_combate and not morto_por_presa and dono_origem:
        # Morte em combate: vai pro Victory Pile do oponente
        vp = alvo.renown if alvo.renown > 0 else 1
        ct_alvo = (alvo.card_type or '').lower()
        eh_gaia = _eh_pack_gaia(dono_origem)
        eh_wyrm = _eh_pack_wyrm(dono_origem)
        if eh_gaia and 'victim' in ct_alvo:
            vp = 0
        elif eh_wyrm and 'enemy' in ct_alvo:
            vp = 0
        if vp > 0:
            dono_origem.victory_points += vp
        # Hacked Apart: marca morte mas NAO remove do jogo ainda
        if eh_hacked_apart:
            alvo.zone = Zone.VICTORY_PILE
            _remove_creature(game, alvo)
            dono_origem.victory_pile.append(alvo)
            game.add_log(
                f'  Hacked Apart! {alvo.name} foi despedacado! '
                f'{dono_origem.name} ganhou {vp} VP '
                f'(total: {dono_origem.victory_points})'
            )
        elif alvo.is_frenzied:
            # Frenzied mas abaixo do threshold: morto mas continua
            # Nao move para VP, nao remove do jogo ainda
            alvo.frenzy_dead_but_fighting = True
            game.add_log(
                f'  {alvo.name} foi morto mas continua lutando '
                f'(frenesi)! {dono_origem.name} ganhou {vp} VP '
                f'(total: {dono_origem.victory_points})'
            )
        else:
            alvo.zone = Zone.VICTORY_PILE
            _remove_creature(game, alvo)
            dono_origem.victory_pile.append(alvo)
            if vp > 0:
                game.add_log(
                    f'  {alvo.name} foi destruido! '
                    f'{dono_origem.name} ganhou {vp} VP '
                    f'(total: {dono_origem.victory_points})'
                )
            else:
                game.add_log(
                    f'  {alvo.name} foi destruido! '
                    f'{dono_origem.name} ganhou 0 VP'
                )
        # Death triggers (disparam mesmo se Hacked Apart / frenzied)
        game.check_death_triggers(alvo, origem, dono_origem)
        game.check_kill_bonuses(alvo, dono_origem)
        # Tracking para Vigilante (565): registra quem matou a vitima
        # de menor Renome
        ct_alvo = (alvo.card_type or '').lower()
        if 'victim' in ct_alvo or 'enemy' in ct_alvo:
            if dono_origem and origem:
                # Verifica se esta e a vitima de menor Renome morta ate agora
                lowest = getattr(game, '_lowest_renown_victim_killed', None)
                if lowest is None or alvo.renown < lowest['renown']:
                    game._lowest_renown_victim_killed = {
                        'renown': alvo.renown,
                        'killer_uid': id(origem),
                        'killer_name': origem.name,
                    }
    else:
        # Morte fora de combate ou por Presa
        if 'Character' in (alvo.card_type or '') or 'Ally' in (alvo.card_type or ''):
            # Character/Ally: removido do jogo (nao vai pra VP de ninguem)
            alvo.zone = Zone.REMOVED
            _remove_creature(game, alvo)
            game.add_log(f'  {alvo.name} foi destruido e removido do jogo!')
        else:
            # Non-character: descartado
            alvo.zone = Zone.DISCARD_COMBAT
            _remove_creature(game, alvo)
            if dono_alvo:
                dono_alvo.discard_combat.append(alvo)
            game.add_log(f'  {alvo.name} foi destruido e descartado!')

    # Caern of the Snow Leopard (584): personagem morto na Umbra
    # pode ser ressuscitado sacrificando o Caern
    if dono_alvo and alvo.zone in (Zone.REMOVED, Zone.VICTORY_PILE):
        _check_caern_snow_leopard(game, alvo, dono_alvo,
                                   zona_original=zona_original_death)

    # Se o alpha defensor morreu, destroy Territories que defendia
    if (em_combate
        and 'territory_targets' in game.combat_triggers
        and str(alvo.card_id) in game.combat_triggers['territory_targets']):
        territory_card = game.combat_triggers['territory_targets'].pop(
            str(alvo.card_id))
        ct = (territory_card.card_type or '').lower()
        if 'territory' in ct or 'realm' in ct:
            if territory_card.zone == Zone.PACK_HOME:  # Ainda nao destruido
                _remove_creature(game, territory_card)
                if dono_alvo:
                    dono_alvo.discard_sept.append(territory_card)
                territory_card.zone = Zone.DISCARD_SEPT
                game.add_log(
                    f'  {territory_card.name} (Territory) destruido '
                    f'com a morte do alpha defensor!')

    # Marca quests como falhas se o character/Ally morreu
    if dono_alvo and ('Character' in (alvo.card_type or '')
                      or 'Ally' in (alvo.card_type or '')):
        for p in game.players:
            for q in p.quests:
                if (q.target_card_uid == id(alvo)
                    and not q.completed):
                    q.completed = True
                    q.failed_due_to_death = True

    return True

    game.add_log(
        f'[Caern] Leopardo da Neve: {alvo.name} ressuscitado '
        f'com vida cheia!'
    )


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
    # Acoes basicas
    'strike': {
        'damage': None,           # None = usa Rage da criatura (default)
        'rage_requirement': 0,    # Qualquer criatura pode atacar
        'speed': 'normal',
    },
    'claw': {
        'damage': None,
        'rage_requirement': 0,
        'speed': 'normal',
    },
    'bite': {
        'damage': None,
        'rage_requirement': 0,
        'speed': 'normal',
    },
    'weapon_strike': {
        'damage': None,           # Dano da arma + Rage da criatura
        'rage_requirement': 0,
        'speed': 'normal',
    },
    'ranged_strike': {
        'damage': None,
        'rage_requirement': 0,
        'speed': 'normal',
    },
    # Acoes defensivas
    'block': {
        'damage': 0,              # Block nao causa dano
        'rage_requirement': 0,
        'speed': 'normal',
        'block_value': None,      # None = Rage do defensor
    },
    'dodge': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
    },
    'flee': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'flee': True,
    },
    # Acoes especiais
    'head_butt': {
        'damage': 4,              # Dano fixo 4
        'rage_requirement': 2,    # Requer Rage 2+
        'speed': 'normal',
        'bounce_se_bloqueado': True,  # Dano volta ao atacante
    },
    'tail_lash': {
        'damage': 1,              # Dano base 1
        'rage_requirement': 1,    # Requer Rage 1+
        'speed': 'normal',
        'bonus_dano': 4,          # +4 se Rokea/Mokole
    },
    'anatomy_lesson': {
        'damage': 4,              # Dano fixo 4
        'rage_requirement': 6,    # Requer Rage 6+
        'speed': 'normal',
        'unblockable': True,       # Nao pode ser bloqueado/esquivado
        'retira_se_ferido': True,  # Criatura ferida deve retirar do combate
    },
    'savage_beatdown': {
        'damage': 3,
        'rage_requirement': 3,
        'speed': 'normal',
        'descarte_metade_se_frenetico': True,
    },
    'submission_hold': {
        'damage': 1,
        'rage_requirement': 2,
        'speed': 'normal',
        'retira_se_nao_frenetico': True,
        'nao_pode_esquivar_se_frenetico': True,
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
    def _get_renown(card_id: str) -> int:
        for p in game.players:
            for c in p.pack_home + p.umbra:
                if str(c.card_id) == card_id:
                    return c.renown
        return 0

    alphas = list(game.combat.alphas.values())
    # Ordena por Renome decrescente, desempatando aleatoriamente
    game.rng.shuffle(alphas)  # Embaralha para desempate aleatorio
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


def advance_combat_step(game: GameState) -> bool:
    """Avanca a maquina de steps de combate.

    Gerencia as transicoes entre steps do Capitulo 6:
    - Steps de auto-advance sao pulados automaticamente
      (pre_combat, beginning_of_combat, bluff, withdrawal)
    - Steps com acao do jogador esperam o bot agir
      (play_card, targeting, reveal)
    - Entre rounds: verifica se combate continua

    Returns:
        True se o step foi avancado, False se precisa de acao do jogador.
    """
    if not game.combat.is_active:
        return False

    step = game.combat.step
    combat = game.combat

    # Mapeia step antigo para novo (backward compat)
    if step in OLD_STEP_MAP:
        step = OLD_STEP_MAP[step]
        game.combat.step = step

    # ---- Steps de auto-advance (passam direto) ----
    if step in COMBAT_STEPS_AUTO:
        if step == 'pre_combat':
            # Stepping In (6.5.9): alpha substitui Presa
            if _preparar_stepping_in(game):
                game.add_log('  [Pre-Combat] Stepping In executado')
            else:
                game.add_log('  [Pre-Combat] Sem stepping in (auto)')
        elif step == 'beginning_of_combat':
            game.add_log('  [Beginning-of-Combat] Sem gifts pre-combate (auto)')
        elif step == 'bluff':
            _processar_bluff(game)
        elif step == 'withdrawal':
            if _processar_withdrawal(game):
                game.add_log('  [Withdrawal] Atacante retirou-se')
                # Com withdrawal, combate termina
                idx = COMBAT_STEPS.index(step)
                if idx + 1 < len(COMBAT_STEPS):
                    prox = COMBAT_STEPS[idx + 1]
                    game.combat.step = prox
                    game.add_log(f'  Step: {step} -> {prox}')
                return True
            game.add_log('  [Withdrawal] Atacante continua (auto)')

        # Avanca para o proximo step
        idx = COMBAT_STEPS.index(step)
        if idx + 1 < len(COMBAT_STEPS):
            prox = COMBAT_STEPS[idx + 1]
            game.combat.step = prox
            game.add_log(f'  Step: {step} -> {prox}')
            return True
        else:
            # Fim dos steps - deve ir para end
            game.combat.step = 'end'
            return True

    # ---- Steps de inicio de combate ----
    if step == 'declaration':
        # Declaration step: atacante declarado, alvo definido
        # (ja foi feito em start_combat)
        # Avanca para pre_combat
        game.combat.step = 'pre_combat'
        game.add_log('  [Declaration] Alvo declarado, avancando...')
        return True

    if step == 'between_rounds':
        # Verifica condicoes de fim (6.3)
        if not combat.attackers or not combat.defenders:
            game.add_log('  Sem atacantes ou defensores - fim do combate')
            game.combat.step = 'end'
            return True
        # Por enquanto, sempre encerra apos 1 rodada
        # (multi-round sera implementado posteriormente)
        game.add_log('  Fim da rodada - encerrando combate')
        game.combat.step = 'end'
        return True

    # Steps que precisam de acao do jogador: retorna False
    return False


def start_combat(game: GameState, attackers: list[str],
                 defenders: list[str],
                 attack_type: str = 'creature',
                 target_card_id: Optional[str] = None) -> bool:
    """Inicia um combate entre atacantes e defensores.

    Args:
        game: Estado da partida.
        attackers: Lista de IDs das criaturas atacantes.
        defenders: Lista de IDs das criaturas defensoras.
        attack_type: Tipo de ataque ('creature', 'territory',
                      'battlefield', 'bind').
        target_card_id: ID do Territory/Battlefield/Spirit atacado
                         (usado para attack_type != 'creature').

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

    # Verifica se atacantes e defensores sao combatentes validos
    for atk in attackers:
        if atk != 'hg' and not _eh_combatente_valido(game, atk):
            game.add_log(f'Combate cancelado: {atk} nao e um combatente valido')
            return False
    for dfd in defenders:
        if dfd != 'hg' and not _eh_combatente_valido(game, dfd):
            game.add_log(f'Combate cancelado: {dfd} nao e um combatente valido')
            return False

    # Verifica se ataque a Prey no HG tem alvo valido
    for dfd in defenders:
        if dfd not in ('hg',) and _eh_prey_no_hg(game, dfd):
            break  # Alvo valido
    else:
        for dfd in defenders:
            if dfd != 'hg' and _find_card(game, dfd):
                break  # Alvo valido (outra criatura)
        else:
            if 'hg' in defenders:
                game.add_log('Combate cancelado: ataque HG requer alvo especifico')
                return False

    # Verifica Gauntlet
    for atk in attackers:
        for dfd in defenders:
            if not _mesmo_lado_gauntlet(game, atk, dfd):
                game.add_log(
                    f'Combate cancelado: {atk} e {dfd} estao em '
                    f'lados diferentes do Gauntlet')
                return False

    # Preserva alphas do estado de combate anterior
    alphas_anteriores = dict(game.combat.alphas) if game.combat else {}
    # Reseta tracking de vitimas para Vigilante
    game._lowest_renown_victim_killed = None
    game.combat = CombatState(
        is_active=True,
        step='declaration',  # Novo: comeca pelo Declaration Step (6.1)
        attackers=attackers,
        defenders=defenders,
        original_attackers=list(attackers),
        original_defenders=list(defenders),
        alphas=alphas_anteriores,
        attack_type=attack_type,
        territory_target=target_card_id if attack_type == 'territory'
                         else None,
        battlefield_target=target_card_id if attack_type == 'battlefield'
                           else None,
        bind_target=target_card_id if attack_type == 'bind' else None,
    )

    # Popula combatants com atacantes + defensores
    game.combat.combatants = list(attackers) + [d for d in defenders if d not in attackers]

    game.add_log(
        f'Combate iniciado: {len(attackers)} atacante(s) vs '
        f'{len(defenders)} defensor(es)'
    )

    # Prey no HG se defende automaticamente (Block)
    # Tzinzie (1348): trigger de inicio de combate
    _check_tzinzie_trigger(game)

    # Caern of the Unwashed Child (586): oponentes perdem 2 Rage ou Gnosis
    _check_caern_unwashed_child(game)

    # Sky River Caern (597): nao-alfas imunes a challenge/sneak attack
    _check_sky_river_caern(game)

    # Trata ataque a Territory: substitui defensor pelo alpha do dono
    # Regra (Quickstart): o alpha do pack controlador pode defender
    novos_defensores = []
    for dfd in defenders:
        card = _find_card(game, dfd)
        if card:
            ct = (card.card_type or '').lower()
            if 'territory' in ct or 'realm' in ct:
                dono = _find_owner(game, card)
                if dono:
                    alpha_id = game.combat.alphas.get(dono.id)
                    if alpha_id:
                        # Substitui Territory pelo alpha defensor
                        novos_defensores.append(alpha_id)
                        game.add_log(
                            f'  {card.name} (Territory) defendido por '
                            f'alpha {alpha_id}')
                        # Marca Territory para destruicao se alpha morrer
                        if 'territory_targets' not in game.combat_triggers:
                            game.combat_triggers['territory_targets'] = {}
                        game.combat_triggers['territory_targets'][alpha_id] = card
                        continue
                # Sem alpha defensor: Territory destruido imediatamente
                game.add_log(
                    f'  {card.name} (Territory) sem defensor - '
                    f'destruido!')
                _remove_creature(game, card)
                if dono:
                    dono.discard_sept.append(card)
                card.zone = Zone.DISCARD_SEPT
                continue
        novos_defensores.append(dfd)

    # Atualiza defensores
    if novos_defensores != defenders:
        game.combat.defenders = novos_defensores
        if not novos_defensores:
            game.combat = CombatState()
            game.add_log('Territory destruido, combate cancelado')
            return False

    # ---- Battlefield: autodefesa se nenhum alpha defendeu ----
    if attack_type == 'battlefield' and target_card_id:
        bf_card = _find_card(game, target_card_id)
        if bf_card:
            # Verifica se algum defensor e o alpha do dono
            dono_bf = _find_owner(game, bf_card)
            alpha_defendeu = False
            if dono_bf:
                alpha_id = game.combat.alphas.get(dono_bf.id)
                if alpha_id and alpha_id in game.combat.defenders:
                    alpha_defendeu = True
            if not alpha_defendeu:
                # Autodefesa: Battlefield vira combatente com
                # Rage/Gnosis/Health = Renown
                bf_renown = getattr(bf_card, 'renown', 3) or 3
                # Cria uma entrada para o Battlefield como combatente
                game.combat.battlefield_self_defense[target_card_id] = {
                    'rage': bf_renown,
                    'gnosis': bf_renown,
                    'health': bf_renown,
                    'health_current': bf_renown,
                    'renown': bf_renown,
                    'card': bf_card,
                }
                # Adiciona o Battlefield como defensor
                if target_card_id not in game.combat.defenders:
                    game.combat.defenders.append(target_card_id)
                if target_card_id not in game.combat.combatants:
                    game.combat.combatants.append(target_card_id)
                game.add_log(
                    f'  {bf_card.name} (Battlefield) em autodefesa '
                    f'(Rg/Gn/Hp={bf_renown})')

    return True


def _eh_combatente_valido(game: GameState, card_id: str) -> bool:
    """Verifica se um card_id corresponde a um combatente valido.

    Regra: apenas cartas com capacidade de combate podem atacar
    ou ser alvo de ataques:
    - Character, Ally: podem atacar e ser atacados
    - Enemy, Victim, Battlefield: podem ser atacados (no HG)
    - Equipment, Gift, Event, Action, etc.: NAO sao combatentes

    Se a carta nao for encontrada em nenhuma zona (ex: acabou de
    ser jogada ou e um ID de teste), retorna True (comportamento
    leniente para compatibilidade).
    """
    if card_id == 'hg':
        return True  # Hunting Grounds e alvo valido (compatibilidade)
    card = _find_card(game, card_id)
    if card is None:
        return True  # Carta nao encontrada - assume valida (leniente)
    ct = (card.card_type or '').lower()
    TIPOS_COMBATENTES = {'character', 'ally', 'enemy', 'victim',
                          'battlefield', 'territory', 'realm'}
    return any(t in ct for t in TIPOS_COMBATENTES)


def _eh_prey_no_hg(game: GameState, card_id: str) -> bool:
    """Verifica se card_id corresponde a uma presa no Hunting Grounds."""
    card = _find_card(game, card_id)
    if card is None:
        return False
    ct = (card.card_type or '').lower()
    if not any(t in ct for t in ('victim', 'enemy', 'battlefield')):
        return False
    # Verifica se a carta esta em alguma zona de HG
    for p in game.players:
        if card in p.hunting_grounds:
            return True
    if card in game.hunting_grounds_cards:
        return True
    return False


def _eh_atacante_da_presa(game: GameState, prey_card_id: str,
                           player_id: str) -> bool:
    """Verifica se o jogador e o atacante de uma presa no combate atual.

    Os pares sao indexados: atacantes[i] vs defensores[i].
    Se o atacante do par pertence a player_id, retorna True.
    """
    for i, dfd in enumerate(game.combat.defenders):
        if dfd == prey_card_id:
            if i < len(game.combat.attackers):
                a_id = game.combat.attackers[i]
                card = _find_card(game, a_id)
                if card and card.owner_id == player_id:
                    return True
    return False
    return False


def get_combatants(game: GameState) -> list[str]:
    """Retorna lista de IDs de todas as criaturas no combate.

    Exclui alvos especiais como 'hg' (hunting grounds) que
    nao sao criaturas e nao declaram acoes.
    """
    result = []
    for cid in game.combat.attackers + game.combat.defenders:
        if cid != 'hg':
            if _eh_combatente_valido(game, cid):
                result.append(cid)
    return result


def _jogar_ce_face_down(game: GameState, criatura_id: str,
                           ce_card_id: str) -> bool:
    """Joga um Combat Event face-down no Play Card Step.

    A criatura joga um CE face-down como se fosse uma
    Combat Action. O CE sera revelado no Reveal Step e
    descartado como ilegal no Bluff Step (6.9.1).

    Args:
        game: Estado da partida.
        criatura_id: ID da criatura jogando o CE.
        ce_card_id: ID do card CE sendo jogado.

    Returns:
        True se o CE foi jogado com sucesso.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step not in ('play_card',):
        return False
    if criatura_id not in get_combatants(game):
        return False

    ce_card = _find_card(game, ce_card_id)
    if not ce_card:
        return False

    ct = (ce_card.card_type or '').lower()
    if 'combat event' not in ct and ct != 'combat_event':
        return False  # So CE pode ser jogado face-down

    # Remove CE da mao e move para descarte (ilegal no Bluff Step)
    dono = _find_owner(game, ce_card)
    if not dono:
        return False
    if ce_card in dono.hand:
        dono.hand.remove(ce_card)
    elif ce_card in dono.combat_hand:
        dono.combat_hand.remove(ce_card)
    else:
        return False

    # Move para discard_combat (ja que sera ilegal)
    ce_card.zone = Zone.DISCARD_COMBAT
    dono.discard_combat.append(ce_card)

    # Registra no estado do combate para tracking
    game.combat.ce_face_down[criatura_id] = ce_card_id

    action_name = f'ce_{ce_card_id}'
    if not declare_action(game, criatura_id, action_name,
                           acoes_extra=['ce']):
        # Reverte se nao foi possivel declarar
        dono.discard_combat.remove(ce_card)
        dono.hand.append(ce_card)
        ce_card.zone = Zone.HAND
        game.combat.ce_face_down.pop(criatura_id, None)
        return False

    game.add_log(f'  {ce_card.name} jogado face-down por '
                 f'{_find_card(game, criatura_id).name}')
    return True


def _registrar_acao_dano(game: GameState, card: CardInstance,
                          criatura_id: str) -> Optional[str]:
    """P8: Registra uma acao virtual de dano a partir de um combat card.

    Examina o modelo da carta em busca de efeitos do tipo 'dano'.
    Se encontrar, cria uma acao virtual 'dano_<uid>' com o valor de
    dano do primeiro efeito de dano encontrado.

    A acao e registrada em game.combat.dano_actions e a carta e
    consumida da mao de combate.

    Args:
        game: Estado da partida.
        card: Carta de combate (Combat Action, Combat Event, etc.).
        criatura_id: ID da criatura que usara a acao.

    Returns:
        Nome da acao virtual (ex: 'dano_12345') ou None se a carta
        nao tem efeito de dano.
    """
    if not card.modelo_id:
        return None

    from rage_web.game_engine.effects import CARTAS_EXEMPLO
    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
    if not modelo or not modelo.modos:
        return None

    # Procura o primeiro efeito de dano em qualquer modo
    dano_valor = None
    for modo in modelo.modos:
        for efeito in (modo.efeitos or []):
            from rage_web.game_engine.effects import EfeitoTipo
            if getattr(efeito, 'tipo', None) == EfeitoTipo.DANO:
                dano_valor = getattr(efeito, 'quantidade', None)
                break
        if dano_valor is not None:
            break

    if dano_valor is None or dano_valor <= 0:
        return None

    # Cria nome unico para acao virtual
    uid = id(card)
    action_name = f'dano_{uid}'

    # Registra no estado do combate
    game.combat.dano_actions[action_name] = {
        'damage': dano_valor,
        'card_id': card.card_id,
        'card_name': card.name,
    }

    # Consome a carta da mao de combate
    dono = _find_owner(game, card)
    if dono and card in dono.combat_hand:
        dono.combat_hand.remove(card)
    card.zone = Zone.DISCARD_COMBAT
    if dono:
        dono.discard_combat.append(card)

    game.add_log(f'  {card.name} registrado como acao de dano '
                 f'(dano: {dano_valor})')

    return action_name


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
    if game.combat.step not in ('declare', 'declaration', 'play_card'):
        return False
    if card_id not in get_combatants(game):
        return False

    # Valida se a acao e permitida
    if action not in COMBAT_ACTIONS:
        # Verifica em acoes extras (Combat Actions especificas)
        if not acoes_extra or action not in acoes_extra:
            # Permite Combat Events jogados face-down (ce_<id>)
            if not action.startswith('ce_'):
                # P8: Permite acoes virtuais de dano (dano_<uid>)
                if not action.startswith('dano_'):
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

    Aceita steps 'declare' (old), 'play_card' (novo) ou
    'declaration' (quando todas as acoes foram declaradas
    diretamente via declare_action no novo fluxo).
    Avanca para o step 'reveal'.
    """
    if not game.combat.is_active:
        return False
    if game.combat.step not in ('declare', 'play_card', 'declaration'):
        return False

    # Antes de revelar, auto-declara 'block' para presas que ainda
    # nao receberam declaracao de nenhum jogador.
    # Regra: qualquer jogador exceto o atacante pode declarar por uma presa.
    # Se ninguem o fez, a presa bloqueia por padrao.
    for dfd in game.combat.defenders:
        if dfd != 'hg' and _eh_prey_no_hg(game, dfd):
            if dfd not in game.combat.declarations:
                card = _find_card(game, dfd)
                if card:
                    declare_action(game, dfd, 'block', acoes_extra=['block'])
                    game.add_log(
                        f'  {card.name} (Presa) defende-se automaticamente'
                    )

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
                        idx = game.rng.randint(0, len(dono.hand) - 1)
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
    """Encontra uma carta pelo ID em qualquer zona de qualquer jogador
    ou no Hunting Grounds global."""
    for p in game.players:
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra,
                          p.hand, p.discard_combat, p.discard_sept,
                          p.victory_pile):
            for c in zone_list:
                if str(c.card_id) == card_id:
                    return c
    # Procura no HG global
    for c in game.hunting_grounds_cards:
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
    """Remove uma criatura de sua zona atual e limpa buffs."""
    # Limpa buffs da criatura
    _limpar_buffs(game, card)
    # Tenta remover das zonas dos jogadores
    for p in game.players:
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra):
            if card in zone_list:
                zone_list.remove(card)
                return
    # Tenta remover do Hunting Grounds global
    if card in game.hunting_grounds_cards:
        game.hunting_grounds_cards.remove(card)
        return


def _limpar_buffs(game: GameState, card: CardInstance):
    """Limpa todos os buffs de uma criatura quando ela morre/sai de jogo."""
    # Reverte buff_rage
    if card.buff_rage != 0:
        card.buff_rage = 0
    if card.buff_gnosis != 0:
        card.buff_gnosis = 0
    if card.buff_health != 0:
        card.buff_health = 0
    if card.buff_reducao_dano != 0:
        card.buff_reducao_dano = 0


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


def _preparar_stepping_in(game: GameState) -> bool:
    """Processa Stepping In (6.5.9) no Pre-Combat Step.

    Quando uma Presa (Victim/Enemy) e atacada, um alpha do mesmo
    alinhamento pode substitui-la como defensor:
    - Gaia alpha step in for Victim
    - Wyrm alpha step in for Enemy
    - Maior Renome decide (sorteio se empate)

    Returns:
        True se algum stepping in ocorreu.
    """
    combat = game.combat
    if not combat.is_active:
        return False

    stepped_in = False

    for i, dfd_id in enumerate(list(combat.defenders)):
        if dfd_id == 'hg':
            continue

        card = _find_card(game, dfd_id)
        if not card:
            continue

        ct = (card.card_type or '').lower()
        is_victim = 'victim' in ct
        is_enemy = 'enemy' in ct

        if not (is_victim or is_enemy):
            continue

        if not _eh_prey_no_hg(game, dfd_id):
            continue

        # Encontra alphas que podem substituir
        # Gaia alpha for Victim, Wyrm alpha for Enemy
        alphas_que_podem: list[tuple[str, str, CardInstance]] = []

        for pid, alpha_id in combat.alphas.items():
            alpha_card = _find_card(game, alpha_id)
            if not alpha_card:
                continue
            if alpha_card.health_current <= 0:
                continue

            dono = _find_owner(game, alpha_card)
            if not dono:
                continue

            eh_gaia = _eh_pack_gaia(dono)
            eh_wyrm = _eh_pack_wyrm(dono)

            if is_victim and eh_gaia:
                alphas_que_podem.append((pid, alpha_id, alpha_card))
            elif is_enemy and eh_wyrm:
                alphas_que_podem.append((pid, alpha_id, alpha_card))

        if not alphas_que_podem:
            continue

        # Maior Renome decide; empates aleatorios
        if len(alphas_que_podem) > 1:
            game.rng.shuffle(alphas_que_podem)
        alphas_que_podem.sort(key=lambda x: x[2].renown, reverse=True)

        _, stepping_alpha_id, stepping_alpha = alphas_que_podem[0]

        # Substitui Presa pelo alpha
        combat.defenders[i] = stepping_alpha_id
        game.add_log(f'  [Stepping In] {stepping_alpha.name} '
                     f'substitui {card.name} como defensor')

        # Registra stepping in (para tracking futuro)
        if not hasattr(combat, 'stepped_in_alphas'):
            combat.stepped_in_alphas = []
        combat.stepped_in_alphas.append(dfd_id)
        stepped_in = True

    return stepped_in


def _processar_withdrawal(game: GameState) -> bool:
    """Processa Withdrawal Step (6.3.1).

    O atacante pode retirar do combate, encerrando-o.
    Withdrawal nao e uma acao.
    Maim impede withdrawal.
    Frenzied nao pode withdrawal.

    Returns:
        True se o combate foi encerrado por withdrawal.
    """
    combat = game.combat
    if not combat.is_active:
        return False
    if combat.step != 'withdrawal':
        return False

    # Verifica se algum atacante esta frenzied (impede withdrawal)
    for atk_id in combat.attackers:
        if atk_id == 'hg':
            continue
        card = _find_card(game, atk_id)
        if card and card.is_frenzied:
            game.add_log('  [Withdrawal] Frenzied nao pode retirar')
            return False

    # Verifica Maim (impede withdrawal)
    # TODO: implementar Maim check

    return False  # Por enquanto, nunca retira


def _tentar_desafio(game: GameState, alpha_id: str,
                      alvo_id: str) -> bool:
    """Alpha desafia um nao-alpha (6.5.2).

    O desafiado pode recusar. Se aceitar, inicia combate.
    Soh pode desafiar criaturas (nao Territory/Battlefield).
    Se recusar, combate nao acontece e a acao alpha termina.

    Args:
        game: Estado da partida.
        alpha_id: ID do alpha que desafia.
        alvo_id: ID do alvo do desafio.

    Returns:
        True se o combate foi iniciado (desafio aceito).
    """
    alvo = _find_card(game, alvo_id)
    if not alvo:
        return False

    ct = (alvo.card_type or '').lower()
    if not any(t in ct for t in ('character', 'ally')):
        # Soh pode desafiar criaturas
        return False

    # Alpha nao pode desafiar outro alpha
    if alvo_id in game.combat.alphas.values():
        return False

    alpha = _find_card(game, alpha_id)
    if not alpha:
        return False

    # ── O desafiado decide se aceita (6.5.2) ──
    aceita = _desafiado_aceita_desafio(game, alvo, alpha)

    if aceita:
        from rage_web.game_engine.combat_queue import start_combat
        start_combat(game, [alpha_id], [alvo_id])
        game.add_log(
            f'  [Challenge] {alpha.name} desafiou {alvo.name} — ACEITO')
        return True
    else:
        game.add_log(
            f'  [Challenge] {alvo.name} RECUSOU o desafio '
            f'de {alpha.name} (acao alpha encerrada)')
        return False


def _tem_modifier(game: GameState, card_uid: int, modifier_name: str) -> bool:
    """Verifica se uma criatura tem um modifier específico ativo."""
    for m in game.game_modifiers:
        if m.card_uid == card_uid and m.modifier == modifier_name and m.ativo:
            return True
    return False


def _desafiado_aceita_desafio(game: GameState,
                                alvo: CardInstance,
                                desafiante: CardInstance) -> bool:
    """Decide se o desafiado aceita o desafio (6.5.2).

    Criterios:
    1. Se alvo tem modifier 'pode_recusar_qualquer_desafio': sempre recusa
       (Heightened Senses, etc)
    2. Se desafiante tem modifier 'challenges_cannot_be_refused': sempre aceita
    3. Se Rage do alvo >= Rage do desafiante + 2: aceita (confianca)
    4. Se HP do alvo <= Rage do desafiante * 2: recusa (risco de morte)
    5. Se alvo tem carta defensiva na mao: +30% de aceitar
    6. Fator aleatorio

    Returns:
        True se aceita o desafio.
    """
    rage_alvo = alvo.effective_rage
    rage_des = desafiante.effective_rage
    hp_alvo = alvo.health_current or alvo.health
    dano_esperado = rage_des

    # 0. Modifiers especiais de recusa/aceitação
    # Heightened Senses: pode recusar QUALQUER challenge
    if _tem_modifier(game, id(alvo), 'pode_recusar_qualquer_desafio'):
        game.add_log(f'  {alvo.name} pode recusar qualquer desafio (modifier)')
        return False
    # Kirijama/desafiante com modifier: desafios não podem ser recusados
    if _tem_modifier(game, id(desafiante), 'challenges_cannot_be_refused'):
        game.add_log(f'  {desafiante.name}: desafio não pode ser recusado')
        return True

    # Fatores de decisao
    score = 50  # Neutro (50% base)

    # 1. Vantagem de Rage
    if rage_alvo >= rage_des + 2:
        score += 30  # Confiante
    elif rage_alvo >= rage_des:
        score += 10  # Leve vantagem
    elif rage_alvo < rage_des - 3:
        score -= 30  # Desvantagem grande
    else:
        score -= 10  # Leve desvantagem

    # 2. Risco de morte
    if hp_alvo <= dano_esperado:
        score -= 40  # Morte quase certa
    elif hp_alvo <= dano_esperado * 2:
        score -= 15  # Risco alto

    # 3. Tem carta defensiva na mao de combate?
    tem_defesa = False
    dono = _find_player(game, alvo.owner_id)
    if dono:
        for card in dono.combat_hand:
            nome = (card.name or '').lower()
            ct = (card.card_type or '').lower()
            if ('block' in nome or 'dodge' in nome
                or 'defend' in nome or 'evasion' in nome
                or 'flee' in nome
                or 'block and strike' in nome):
                tem_defesa = True
                break
            # Tambem checa por tipo Combat Action defensiva
            if 'combat action' in ct or 'combat event' in ct:
                texto = (card.text or '').lower()
                if any(p in texto for p in ('block', 'dodge', 'flee',
                                              'evasion', 'defend')):
                    tem_defesa = True
                    break
    if tem_defesa:
        score += 30

    # 4. Fator aleatorio
    score += game.rng.randint(-20, 20)

    # 5. Desafiante com Rage muito alta: medo extra
    if rage_des >= 7:
        score -= 10
    if rage_des >= 9:
        score -= 10

    return score >= 50


def _processar_bluff(game: GameState) -> bool:
    """Processa Bluff Step (6.9).

    Fluxo:
    1. Identifica cartas ilegais (6.9.1): cartas que nao atendem
       requisitos nao-Rage (Gnosis, forma, keywords, etc.)
    2. Identifica blefes (6.9.2): Combat Actions com Rage requirement
       maior que a Rage efetiva da criatura.
    3. Remove ilegais.
    4. Determina sucesso/falha dos blefes (simultaneo).
    5. Remove blefes falhos.

    Returns:
        True se processado.
    """
    if game.combat.step != 'bluff':
        return False

    game.combat.illegal_cards.clear()
    game.combat.bluff_cards.clear()
    game.combat.bluff_failed.clear()

    combatants = get_combatants(game)

    # --- Fase 1: Identificar ilegais e blefes ---
    for cid, action in list(game.combat.declarations.items()):
        if cid not in combatants:
            continue
        if not action:
            continue

        card = _find_card(game, cid)
        if not card:
            continue

        props = COMBAT_ACTION_PROPS.get(action, {})
        rage_req = props.get('rage_requirement', 0)

        # 6.9.1: Verificar ilegais (requisitos nao-Rage)
        # Combat Events jogados face-down sao ilegais
        if action.startswith('ce_'):
            game.combat.illegal_cards.add(cid)
            game.add_log(f'  [Bluff] {card.name} jogou Combat Event '
                         f'face-down -> ILEGAL (6.9.1)')
            continue

        # 6.6.6a: Restricted Play — se a carta nao atende a
        # restricao, e considerada ilegal.
        nivel_restrito = game.combat.get_restricted_level(cid)
        if nivel_restrito is not None:
            if rage_req > nivel_restrito:
                game.combat.illegal_cards.add(cid)
                game.add_log(
                    f'  [Bluff] {card.name}: {action} requer Rage '
                    f'{rage_req} > {nivel_restrito} (Restricted Play) '
                    f'-> ILEGAL (6.6.6a)')
                continue

        # 6.9.2: Verificar blefe (Rage requirement > Rage)
        if card.effective_rage < rage_req:
            game.combat.bluff_cards.add(cid)
            game.add_log(f'  [Bluff] {card.name} esta blefando com {action} '
                         f'(Rage {card.effective_rage} < {rage_req})')

    # Descartar ilegais ANTES de verificar blefes (6.9.1 ordem)
    for cid in list(game.combat.illegal_cards):
        if cid in game.combat.declarations:
            del game.combat.declarations[cid]
        game.combat.targets.pop(cid, None)
        card = _find_card(game, cid)
        game.add_log(f'  [Bluff] {(card.name if card else cid)}: '
                     f'carta ilegal descartada (6.9.1)')

    # --- Fase 2: Determinar sucesso/falha dos blefes ---
    # Todas as verificacoes sao simultaneas
    for cid in list(game.combat.bluff_cards):
        if cid not in game.combat.declarations:
            game.combat.bluff_cards.discard(cid)
            continue

        card = _find_card(game, cid)
        card_name = card.name if card else cid

        target_id = game.combat.targets.get(cid)

        if target_id:
            target_bluffed = target_id in game.combat.bluff_cards
            target_has_declaration = target_id in game.combat.declarations

            if target_bluffed:
                game.add_log(f'  [Bluff] {card_name}: blefe OK '
                             f'(alvo tambem blefou)')
            elif not target_has_declaration:
                game.add_log(f'  [Bluff] {card_name}: blefe OK '
                             f'(alvo sem carta legal)')
            else:
                game.combat.bluff_failed.add(cid)
                game.add_log(f'  [Bluff] {card_name}: blefe FALHOU '
                             f'(alvo jogou carta real)')
        else:
            targeted_by_non_bluff = any(
                tgt_id == cid and src_id not in game.combat.bluff_cards
                for src_id, tgt_id in game.combat.targets.items()
            )
            if targeted_by_non_bluff:
                game.combat.bluff_failed.add(cid)
                game.add_log(f'  [Bluff] {card_name}: blefe FALHOU '
                             f'(atacado por carta real)')
            else:
                game.add_log(f'  [Bluff] {card_name}: blefe OK '
                             f'(sem alvo, sem ataque real)')

    # Remover blefes falhos
    for cid in game.combat.bluff_failed:
        if cid in game.combat.declarations:
            del game.combat.declarations[cid]
        game.combat.targets.pop(cid, None)
        card = _find_card(game, cid)
        game.add_log(f'  [Bluff] {(card.name if card else cid)}: '
                     f'removido do combate (blefe falhou)')

    return True


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

    Aceita steps 'reveal', 'resolution' (novo) e 'declare' (old).
    Apos resolucao, avanca para 'withdrawal' (novo sistema)
    ou 'end' (old system).
    """
    if not game.combat.is_active:
        return False
    step = game.combat.step
    # Aceita 'reveal' (antigo), 'resolution' (novo), 'declare' (antigo pre-reveal),
    # 'play_card' (novo), ou 'declaration' (pular para resolucao)
    if step not in ('reveal', 'resolution', 'declare', 'play_card', 'declaration'):
        return False

    # Se ainda esta em declare/play_card/declaration, revela primeiro
    if step in ('declare', 'play_card', 'declaration'):
        combatants = get_combatants(game)
        if not game.combat.all_declared(combatants):
            return False
        reveal_all(game)

    # Define o step apropriado
    game.combat.step = 'resolution'
    game.add_log('━ Resolvendo combate...')

    def _processar_ataque(origem_id: str, alvo_id: str):
        """Processa um ataque de origem contra alvo."""
        if alvo_id == 'hg':
            # Compatibilidade: HG generico (fallback)
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
        pode_esquivar = True
        if acao_alvo == 'dodge' and 'nao_pode_esquivar' in alvo_card.restricoes:
            game.add_log(
                f'  {alvo_card.name} tentou esquivar, mas nao pode! '
                f'(restricao de Submission Hold)'
            )
            pode_esquivar = False
            # Trata como se nao tivesse bloqueado - o dano sera aplicado
            # Continua para a aplicacao de dano abaixo

        # Alvo pode bloquear/esquivar (a menos que seja unblockable)
        bloqueou_ou_esquivou = False
        reducao_block = 0
        if acao_alvo in ('block', 'dodge') and not is_unblockable:
            if acao_alvo == 'dodge' and pode_esquivar:
                # Dodge: dano totalmente evitado
                game.add_log(f'  {alvo_card.name} esquivou do ataque de '
                             f'{origem_card.name}')
                # Head Butt: se esquivado, vira damage card no atacante
                if acao_origem == 'head_butt':
                    keywords = (origem_card.keywords or '').lower()
                    if 'mokole' not in keywords:
                        anexar_dano(origem_card, origem_card, 4, dono_dono)
                        _flipar_para_crinos(game, origem_card)
                        game.add_log(
                            f'  Head Butt esquivado! {origem_card.name} '
                            f'recebe 4 de dano de volta'
                        )
                return  # Dodge: sem dano
            elif acao_alvo == 'block':
                # Block: reduz dano pela Rage do defensor
                reducao_block = alvo_card.effective_rage
                game.add_log(
                    f'  {alvo_card.name} bloqueou o ataque de '
                    f'{origem_card.name} (reducao: {reducao_block})'
                )
                bloqueou_ou_esquivou = True
                # Head Butt: se bloqueado, vira damage card no atacante (exceto Mokole)
                if acao_origem == 'head_butt':
                    keywords = (origem_card.keywords or '').lower()
                    if 'mokole' not in keywords:
                        anexar_dano(origem_card, origem_card, 4, dono_dono)
                        _flipar_para_crinos(game, origem_card)
                        game.add_log(
                            f'  Head Butt bloqueado! {origem_card.name} '
                            f'recebe 4 de dano de volta'
                        )
                    else:
                        game.add_log(
                            f'  Head Butt bloqueado, mas {origem_card.name} '
                            f'e Mokole (sem dano de volta)'
                        )
                # Nao retorna - continua para aplicar dano reduzido

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

        # Grand Klaive (306): dano agravado (Weapon)
        for eq in origem_card.attached_equipment:
            if eq.card_id == 306:  # Grand Klaive
                war_knife_aggravated = True
                game.add_log(
                    f'  Grand Klaive: dano agravado '
                    f'({origem_card.name})')
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
        # Calcula dano base: primeiro da acao, depois Rage da criatura
        if skin_blocks:
            dano = 0
        else:
            # Dano basico: usa damage da acao (se definido) ou Rage da criatura
            # P8: Verifica se e acao virtual de dano (dano_<uid>)
            if acao_origem.startswith('dano_'):
                dano_info = game.combat.dano_actions.get(acao_origem)
                if dano_info:
                    dano_base = dano_info['damage']
                    game.add_log(
                        f'  {origem_card.name} usou {dano_info["card_name"]} '
                        f'(dano: {dano_base})')
                else:
                    dano_base = origem_card.effective_rage
            else:
                acao_dano = props.get('damage')
                if acao_dano is not None:
                    dano_base = acao_dano
                    game.add_log(
                        f'  {origem_card.name} usou {acao_origem} '
                        f'(dano: {dano_base})')
                else:
                    dano_base = origem_card.effective_rage

            # Buff de dano no proximo ataque (Razor Claws, etc)
            if origem_card.buff_dano_proximo_ataque > 0:
                bonus = origem_card.buff_dano_proximo_ataque
                dano_base += bonus
                origem_card.buff_dano_proximo_ataque = 0  # Consume o buff
                game.add_log(
                    f'  {origem_card.name}: +{bonus} dano '
                    f'(buff proximo ataque)')

            # Grand Klaive (306): +1 Rage em Crinos
            if origem_card.is_crinos:
                for eq in origem_card.attached_equipment:
                    if eq.card_id == 306:
                        dano_base += 1
                        game.add_log(
                            f'  Grand Klaive: +1 Rage em Crinos '
                            f'({origem_card.name})')
                        break

            dano = max(0, dano_base - alvo_card.reducao_dano)
            # Head Butt bloqueado: nao causa dano ao defensor (ja tomou bounce)
            if bloqueou_ou_esquivou and acao_origem == 'head_butt':
                dano = 0
                game.add_log(
                    f'  Head Butt foi bloqueado! {alvo_card.name} '
                    f'toma 0 de dano (bounce de 4 no atacante)'
                )
            # Block reduz o dano pela Rage do defensor
            elif bloqueou_ou_esquivou:
                dano = max(0, dano - reducao_block)
                if dano == 0:
                    game.add_log(
                        f'  {alvo_card.name} bloqueou todo o dano '
                        f'({reducao_block} >= {dano_base})'
                    )

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
        # Trinity Hive Caern (599): BSD causam dano agravado
        trinity_aggravated = False
        if not war_knife_aggravated:
            if game.has_modifier('trinity_hive_caern'):
                dono_origem = _find_owner(game, origem_card)
                if dono_origem:
                    # Verifica se o dono do atacante tem o Caern
                    tem_caern = any(
                        mod.modifier == 'trinity_hive_caern'
                        for mod in game.game_modifiers
                        if any(
                            id(c) == mod.card_uid
                            for c in dono_origem.pack_home
                            + dono_origem.hunting_grounds
                        )
                    )
                    if tem_caern:
                        kw = (origem_card.keywords or '').lower()
                        if 'black spiral dancer' in kw:
                            trinity_aggravated = True
                            game.add_log(
                                f'  Trinity Hive: {origem_card.name} '
                                f'causa dano agravado!')

        anexar_dano(alvo_card, origem_card, dano, dono_dono,
                    is_aggravated=(war_knife_aggravated
                                   or trinity_aggravated))
        game.add_log(f'  {origem_card.name} causou {dano} de dano a '
                     f'{alvo_card.name} '
                     f'({alvo_card.health_current}/{alvo_card.health})')

        # Flip para Crinos: verifica threshold a cada dano aplicado
        # (regra: dano acumulado >= min(rage, health) da forma breed)
        if dano > 0:
            _flipar_para_crinos(game, alvo_card)

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

        # Morte (usa _processar_morte para logica unificada)
        if alvo_card.health_current <= 0:
            # Verifica se o alvo pode ser vinculado (Elethoi: nao pode)
            if ('nao_pode_ser_vinculado' in alvo_card.restricoes
                    and game.combat.attack_type == 'bind'
                    and str(alvo_card.card_id) == game.combat.bind_target):
                # Bind falha: alvo morre normalmente
                dono_alvo = _find_owner(game, alvo_card)
                if dono_alvo:
                    game.add_log(
                        f'  [Bind] {alvo_card.name} nao pode ser vinculado! '
                        f'Morrendo normalmente...')
                _processar_morte(game, alvo_card, origem_card,
                                 dono_origem, em_combate=True)
                return

            # 6.5.5: Attacking to Bind — em vez de matar o Spirit,
            # cura todo dano e ele se torna um Ally
            if (game.combat.attack_type == 'bind'
                    and str(alvo_card.card_id) == game.combat.bind_target):
                dono_alvo = _find_owner(game, alvo_card)
                if dono_alvo:
                    # Cura todo dano
                    alvo_card.health_current = alvo_card.health
                    alvo_card.damage_aggravated = 0
                    alvo_card.attached_damage.clear()
                    # Move da zona do dono original para Pack Home do atacante
                    for zone_list in (dono_alvo.pack_home,
                                      dono_alvo.hunting_grounds,
                                      dono_alvo.umbra):
                        if alvo_card in zone_list:
                            zone_list.remove(alvo_card)
                            break
                    # Torna-se Ally do atacante
                    if dono_origem:
                        dono_origem.pack_home.append(alvo_card)
                        alvo_card.owner_id = dono_origem.id
                        alvo_card.controller_id = dono_origem.id
                        alvo_card.zone = Zone.PACK_HOME
                        # Marca como Ally
                        ct = (alvo_card.card_type or '').lower()
                        if 'spirit' in ct:
                            if 'character' in ct:
                                alvo_card.card_type = 'Character - Spirit Ally'
                            else:
                                alvo_card.card_type = 'Ally - Bound Spirit'
                        game.add_log(
                            f'  [Bind] {alvo_card.name} foi vinculado! '
                            f'Tornou-se Ally de {dono_origem.name}')
                    else:
                        # Fallback: apenas remove e descarta
                        dono_alvo.discard_sept.append(alvo_card)
                        alvo_card.zone = Zone.DISCARD_SEPT
                # Bind: nao gera VP (o Spirit nao morreu)
            else:
                _processar_morte(game, alvo_card, origem_card,
                                 dono_origem, em_combate=True)

                # Marca dano em quests (se alvo era alvo de quest, reseta)
                for p in game.players:
                    for q in p.quests:
                        if q.target_card_uid == id(alvo_card) and not q.completed:
                            # Alvo tomou dano fatal -> quest falhou
                            q.completed = True
                            q.failed_due_to_death = True
                            game.add_log(
                                f'  Quest falhou: {alvo_card.name} '
                                f'(alvo da quest) foi destruido'
                            )

    # ---- Ordem de resolucao por velocidade (6.10.1) ----
    # Fast Striking -> Normal -> Slow Striking
    # Criaturas mortas em Fast nao resolvem suas acoes em Normal/Slow
    def _get_dead_ids() -> set[str]:
        """Retorna IDs das criaturas mortas (health_current <= 0)."""
        dead = set()
        for p in game.players:
            for zone_list in (p.pack_home, p.hunting_grounds, p.umbra):
                for c in zone_list:
                    if c.health_current <= 0:
                        cid = str(c.card_id)
                        dead.add(cid)
        return dead

    def _processar_lado_velocidade(velocidade: str):
        """Processa ataques de uma velocidade especifica.

        1. Atacantes com esta velocidade atacam defensores
        2. Defensores com acao ofensiva desta velocidade contra-atacam
        3. Remove mortos apos cada velocidade
        """
        mortos = _get_dead_ids()
        game.combat.limpar_combatentes_mortos(mortos)

        # Atacantes -> Defensores (usando targets para pack combat)
        for a_id in game.combat.attackers:
            if a_id == 'hg':
                continue
            acao_a = game.combat.declarations.get(a_id, 'strike')
            props_a = COMBAT_ACTION_PROPS.get(acao_a, {})
            if props_a.get('speed', 'normal') != velocidade:
                continue
            if acao_a not in ACOES_OFENSIVAS:
                continue
            # Pack combat: usa target especifico, fallback para pareamento por indice
            d_id = game.combat.targets.get(a_id)
            if not d_id:
                i = game.combat.attackers.index(a_id)
                d_id = (game.combat.defenders[i]
                        if i < len(game.combat.defenders) else None)
            if d_id and d_id != 'hg':
                _processar_ataque(a_id, d_id)

        mortos = _get_dead_ids()
        game.combat.limpar_combatentes_mortos(mortos)

        # Defensores ofensivos -> Atacantes (contra-ataque, tb com targets)
        for d_id in game.combat.defenders:
            if d_id == 'hg':
                continue
            acao_d = game.combat.declarations.get(d_id, 'strike')
            props_d = COMBAT_ACTION_PROPS.get(acao_d, {})
            if props_d.get('speed', 'normal') != velocidade:
                continue
            if acao_d not in ACOES_OFENSIVAS:
                continue
            # Pack combat: usa target especifico, fallback para pareamento por indice
            a_id = game.combat.targets.get(d_id)
            if not a_id:
                i = game.combat.defenders.index(d_id)
                a_id = (game.combat.attackers[i]
                        if i < len(game.combat.attackers) else None)
            if a_id and a_id != 'hg':
                _processar_ataque(d_id, a_id)

        mortos = _get_dead_ids()
        game.combat.limpar_combatentes_mortos(mortos)
        if mortos:
            game.add_log(f'  [Fim {velocidade}] {len(mortos)} criatura(s) removida(s)')

    game.add_log('━ Resolucao por velocidade:')

    # 1. Fast Striking
    _processar_lado_velocidade('fast')

    # 2. Normal
    _processar_lado_velocidade('normal')

    # 3. Slow Striking
    _processar_lado_velocidade('slow')

    # Clan of Hyenas (96): foge do combate se tomou >=3 dano neste round
    _check_hyenas_escape(game)

    # Avanca para withdrawal step (novo sistema)
    game.combat.step = 'withdrawal'
    game.add_log('━ Resolucao concluida, aguardando withdrawal...')
    return True


def verificar_vitoria(game: GameState) -> Optional[str]:
    """Verifica condicoes de vitoria.

    Regra (2.3):
    - Ao final de qualquer Combat phase, se um jogador tem VP
      >= renown_level, venceu.
    - Se dois ou mais tem, o com mais VP vence.
    - Se empate, continua.
    - Se um jogador perde todos os seus Characters, esta fora de jogo.
      (Se restar apenas 1 jogador, esse jogador vence.)

    Returns:
        ID do vencedor, ou None se ninguem venceu.
    """
    # Regra 2.3: verificar eliminacao e vitoria
    # Primeiro: verifica se algum jogador perdeu todos os Characters
    # (so apos turno 1 para compatibilidade com testes)
    if game.turn_number > 1:
        for p in game.players:
            if not _tem_character(p) and not p.eliminado:
                _eliminar_jogador(game, p)

    # Conta jogadores ativos (nao eliminados)
    jogadores_ativos = [p for p in game.players if not p.eliminado]

    # Se restou apenas 1 jogador, ele vence
    if len(jogadores_ativos) == 1:
        return jogadores_ativos[0].id
    if len(jogadores_ativos) == 0:
        return None  # Todos eliminados

    # Verifica VP >= renown_level (apenas jogadores ativos)
    # Regra 2.3: se o jogador atingiu VP suficiente no turno em que
    # foi eliminado, ele ainda vence
    vencedores = [p for p in jogadores_ativos
                  if p.victory_points >= p.renown_level]
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


def _tem_character(player: PlayerState) -> bool:
    """Verifica se o jogador tem pelo menos 1 Character em jogo.

    Regra (2.3): Characters incluem personagens no pack,
    Hunting Grounds e Umbra.
    """
    for c in player.pack_home:
        if 'Character' in (c.card_type or ''):
            return True
    for c in player.hunting_grounds:
        if 'Character' in (c.card_type or ''):
            return True
    for c in player.umbra:
        if 'Character' in (c.card_type or ''):
            return True
    return False


def _eliminar_jogador(game: GameState, player: PlayerState) -> None:
    """Elimina um jogador da partida (Regra 2.3).

    Quando um jogador perde todos os seus Characters:
    1. Todas as cartas no Pack Home (exceto combat deck e discards)
       sao removidas do jogo.
    2. Cartas fora do Pack Home (Hunting Grounds, Umbra, etc.)
       permanecem em jogo.
    3. O jogador nao pode mais jogar cartas de sept.
    4. O jogador pode jogar cartas de combate para Presas no Hunting Grounds.
    5. O jogador nao pode ser alvo de cartas que afetam packs, VP, etc.
    """
    game.add_log(f'{player.name} foi eliminado! (sem Characters em jogo)')

    # 1. Remover todas as cartas do Pack Home (exceto Characters que ja foram perdidas)
    # Mantem apenas o combat deck e discards
    cartas_removidas = []
    for c in list(player.pack_home):
        # Characters ja foram perdidos (por isso estamos aqui)
        # Remove tudo do pack_home
        c.zone = Zone.OUT_OF_PLAY
        cartas_removidas.append(c)
    player.pack_home.clear()

    # 2. Cartas fora do Pack Home permanecem em jogo (Hunting Grounds, Umbra)
    # Nao fazemos nada aqui - elas ja estao nas listas corretas

    # 3. Marcar jogador como eliminado (nao pode jogar sept cards)
    player.eliminado = True

    if cartas_removidas:
        game.add_log(f'  {len(cartas_removidas)} carta(s) removidas do Pack Home')


def _jogador_eh_alvo_valido(player: PlayerState) -> bool:
    """Verifica se um jogador pode ser alvo de efeitos (Regra 2.3).

    Um jogador eliminado (sem Characters) nao pode ser alvo de cartas
    que afetam packs, Victory Piles, etc.
    """
    return not getattr(player, 'eliminado', False)


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


def _reverter_para_breed(game: GameState):
    """Reverte todas as criaturas para forma Breed ao final do combate.

    Regra: apos o combate, criaturas em Crinos voltam a
    forma Breed. Apenas se aplica a criaturas que tenham
    morph values diferentes dos breed (ou seja, que fliparam).
    """
    for p in game.players:
        for c in p.pack_home + p.hunting_grounds + p.umbra:
            if c.is_crinos and c.health_morph != c.health:
                # Volta para forma breed
                c.is_crinos = False
                # Remove restricoes breed
                for r in ['rage_breed', 'health_breed', 'gnosis_breed']:
                    if r in c.restricoes:
                        c.restricoes.remove(r)
                health_antes = c.health_current
                # Recalcula health_current via sync (usa damage cards)
                c.sync_health()
                game.add_log(
                    f'  ↩️ {c.name} voltou a forma Breed '
                    f'(H {health_antes}/{c.health_morph} -> '
                    f'{c.health_current}/{c.health})'
                )
                # Se morreu ao voltar (dano > breed health)
                if c.health_current <= 0:
                    game.add_log(
                        f'  {c.name} nao resistiu a volta a forma Breed!'
                    )
                    _eliminar_jogador(game, p) if not p.eliminado else None


def end_combat(game: GameState) -> bool:
    """Encerra o combate e reseta o estado.

    Aceita step 'end' (novo), 'withdrawal' ou qualquer step
    antigo (resolve/declare/reveal) para compatibilidade.
    """
    if not game.combat.is_active:
        return False

    if game.combat.step not in ('end', 'withdrawal'):
        resolve_combat(game)

    # Reverte formas Crinos para Breed
    _reverter_para_breed(game)

    # Validacao pos-combate: sincroniza health_current de
    # todas as criaturas com base nas damage cards (regra 6.4)
    for p in game.players:
        for c in p.pack_home + p.hunting_grounds + p.umbra:
            c.sync_health()

    # ---- Battlefield sweep (6.5.4c) ----
    if game.combat.attack_type == 'battlefield':
        bf_id = game.combat.battlefield_target
        if bf_id:
            # Verifica se um lado varreu o campo
            atacantes_vivos = [
                cid for cid in game.combat.original_attackers
                if cid in game.combat.combatants
                or cid in [str(c.card_id) for c in game.players[0].pack_home]
            ]
            defensores_vivos = [
                cid for cid in game.combat.original_defenders
                if cid in game.combat.combatants
                or cid in [str(c.card_id) for c in game.players[0].pack_home]
            ]
            # Se um lado varreu, coloca Battlefield no VP do varredor
            if atacantes_vivos and not defensores_vivos:
                # Atacante varreu
                bf_card = _find_card(game, bf_id)
                if bf_card:
                    bf_renown = getattr(bf_card, 'renown', 3) or 3
                    dono_atacante = _find_owner(
                        game, game.combat.attackers[0])
                    if dono_atacante:
                        dono_atacante.victory_points += bf_renown
                        game.add_log(
                            f'  [Battlefield] Atacante varreu! '
                            f'{bf_card.name} concedeu '
                            f'{bf_renown} VP a {dono_atacante.name}')
            elif defensores_vivos and not atacantes_vivos:
                # Defensor varreu
                bf_card = _find_card(game, bf_id)
                if bf_card:
                    bf_renown = getattr(bf_card, 'renown', 3) or 3
                    dono_defensor = _find_owner(
                        game, game.combat.defenders[0])
                    if dono_defensor:
                        dono_defensor.victory_points += bf_renown
                        game.add_log(
                            f'  [Battlefield] Defensor varreu! '
                            f'{bf_card.name} concedeu '
                            f'{bf_renown} VP a {dono_defensor.name}')

    # Restaura debuff do Caern of the Unwashed Child
    if 'unwashed_child_debuff' in game.combat_triggers:
        debuff = game.combat_triggers.pop('unwashed_child_debuff')
        for chave, dados in debuff.items():
            # Encontra a criatura e restaura
            for p in game.players:
                if p.id == dados['player_id']:
                    for c in p.pack_home + p.umbra + p.hunting_grounds:
                        if c.card_id == dados['card_id']:
                            setattr(c, dados['atributo'],
                                    dados['valor_original'])
                            game.add_log(
                                f'[Caern] {c.name}: {dados["atributo"]} '
                                f'restaurado para {dados["valor_original"]}')
                            break

    # Reabastece combat hand de todos os jogadores (Regra 6.3)
    # Apos cada combate, jogadores reabastecem sua mao de combate
    # ate o tamanho maximo (hand_size_combat). Se o combat deck
    # acabar, reshuffle do descarte.
    for p in game.players:
        antes = len(p.combat_hand)
        drawn = p.redraw_combat(descartar_primeiro=False)
        depois = antes + len(drawn)
        if drawn:
            game.add_log(f'{p.name} reabasteceu mao de combate '
                         f'({len(drawn)} carta(s), agora {depois}/{p.hand_size_combat})')
        elif antes < p.hand_size_combat:
            game.add_log(f'{p.name} sem cartas de combate no deck '
                         f'({antes}/{p.hand_size_combat})')

    # Executa ataques automaticos de presas no HG
    game._check_victim_attacks()

    # Limpa estado de frenesi de todas as criaturas (6.11.2)
    for p in game.players:
        for c in p.pack_home + p.hunting_grounds + p.umbra:
            if c.is_frenzied:
                _sair_do_frenesi(game, c)
                # Se estava morto mas lutando (Hacked Apart),
                # agora e finalmente removido (6.11.3)
                if getattr(c, 'frenzy_dead_but_fighting', False):
                    c.zone = Zone.VICTORY_PILE
                    _remove_creature(game, c)
                    dono = _find_owner(game, c)
                    if dono:
                        dono.victory_pile.append(c)
                    game.add_log(
                        f'  {c.name} finalmente sucumbiu aos ferimentos '
                        f'(fim do frenesi)')
            elif 'frenesi' in c.restricoes:
                c.restricoes.remove('frenesi')

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


def _check_caern_unwashed_child(game: GameState):
    """Caern of the Unwashed Child (586): oponentes perdem 2 Rage/Gnosis

    "Opponents facing your pack lose either 2 Gnosis or 2 Rage for
     the duration of the combat (caern holder chooses which)."

    Aplica o debuff aos personagens do atacante se o defensor
    tiver este Caern. Armazena valores originais em combat_triggers
    para restauracao em end_combat.
    """
    if not game.has_modifier('caern_unwashed_child'):
        return

    # Encontra quem tem o Caern (o defensor)
    dono_caern = None
    for p in game.players:
        for mod in game.game_modifiers:
            if mod.modifier == 'caern_unwashed_child':
                # Verifica se o dono do card_uid pertence a este jogador
                for c in p.pack_home + p.hunting_grounds:
                    if id(c) == mod.card_uid:
                        dono_caern = p
                        break
                if dono_caern:
                    break
        if dono_caern:
            break

    if not dono_caern:
        return

    # Oponentes sao os que NAO sao o dono do Caern
    oponentes = [p for p in game.players if p.id != dono_caern.id]
    if not oponentes:
        return

    # Escolhe qual atributo reduzir: Rage (padrao para bot)
    # Regra: caern holder chooses. Para bot, escolhe Rage.
    atributo = 'rage'

    # Aplica o debuff a todos os personagens dos oponentes
    reducao = 2
    for op in oponentes:
        for c in op.pack_home:
            if c.card_id == 0 or c.card_id == -1:
                continue  # Pula cartas temporarias
            valor_original = getattr(c, atributo, 0)
            if valor_original <= 1:
                continue  # Nao pode reduzir abaixo de 1
            novo_valor = max(1, valor_original - reducao)
            setattr(c, atributo, novo_valor)
            # Salva original para restaurar depois
            if 'unwashed_child_debuff' not in game.combat_triggers:
                game.combat_triggers['unwashed_child_debuff'] = {}
            chave = f'{op.id}_{c.card_id}'
            game.combat_triggers['unwashed_child_debuff'][chave] = {
                'player_id': op.id,
                'card_id': c.card_id,
                'atributo': atributo,
                'valor_original': valor_original,
            }
            game.add_log(
                f'[Caern] {c.name} perdeu {reducao} {atributo} '
                f'({valor_original} -> {novo_valor})')


def _check_sky_river_caern(game: GameState):
    """Sky River Caern (597): nao-alfas imunes a challenge/sneak attack.

    Se o defensor tem Sky River Caern, verifica se o atacante
    esta atacando um nao-alfa (que nao seja o maior Renown).
    Se sim, bloqueia o ataque.
    """
    if not game.has_modifier('sky_river_caern'):
        return

    # Encontra packs que tem Sky River Caern
    packs_protegidos = set()
    for p in game.players:
        for mod in game.game_modifiers:
            if mod.modifier == 'sky_river_caern':
                for c in p.pack_home + p.hunting_grounds:
                    if id(c) == mod.card_uid:
                        packs_protegidos.add(p.id)
                        break

    if not packs_protegidos:
        return

    # Verifica se algum defensor esta em pack protegido e nao e o Alpha
    for dfd_id in list(game.combat.defenders):
        dfd = _find_card(game, dfd_id)
        if not dfd:
            continue
        if dfd.owner_id not in packs_protegidos:
            continue
        dono = _find_owner(game, dfd)
        if not dono:
            continue
        # Alpha = maior Renown no pack
        alfa = max(
            [c for c in dono.pack_home if c.health_current > 0],
            key=lambda x: x.renown,
            default=None
        )
        if alfa and dfd.card_id != alfa.card_id:
            # Nao-alfa atacado! Bloqueia
            game.combat.defenders.remove(dfd_id)
            game.add_log(
                f'Sky River Caern: {dfd.name} nao pode ser atacado '
                f'(nao e o Alpha do pack)')

    # Se nao sobrou defensores, remove atacantes
    if not game.combat.defenders:
        game.combat.attackers.clear()
        game.combat.is_active = False
        game.add_log('Combat cancelado (Sky River Caern)')


def _check_caern_snow_leopard(game: GameState, alvo: CardInstance,
                               dono: PlayerState,
                               zona_original: Optional[str] = None):
    """Caern of the Snow Leopard (584): personagem morto na Umbra
    pode ser ressuscitado sacrificando o Caern.

    Quando um personagem e morto na Umbra, o dono pode descartar
    este Caern para trazer o personagem de volta com vida cheia
    para o mundo fisico (pack_home).

    Args:
        game: Estado da partida.
        alvo: Personagem que morreu.
        dono: Dono do personagem.
        zona_original: Zona do personagem antes de morrer.
    """
    # So funciona para Character/Ally morto na Umbra
    if 'Character' not in (alvo.card_type or '') and 'Ally' not in (alvo.card_type or ''):
        return
    if zona_original != Zone.UMBRA:
        return

    # Verifica se o dono tem Caern of the Snow Leopard em jogo
    caern = None
    for c in dono.pack_home + dono.hunting_grounds:
        if c.card_id == 584:
            caern = c
            break
    if not caern:
        return

    # Ressuscita!
    # Remove da zona de morte
    _remove_creature(game, alvo)
    if alvo in dono.victory_pile:
        dono.victory_pile.remove(alvo)

    # Move de volta ao pack_home com vida cheia
    alvo.zone = Zone.PACK_HOME
    alvo.zone_original = Zone.PACK_HOME
    alvo.health_current = alvo.health
    alvo.attached_damage.clear()
    alvo.attached_equipment.clear()
    dono.pack_home.append(alvo)

    # Descarta o Caern
    caern.zone = Zone.DISCARD_SEPT
    if caern in dono.pack_home:
        dono.pack_home.remove(caern)
    else:
        dono.hunting_grounds.remove(caern)
    dono.discard_sept.append(caern)

    game.add_log(
        f'[Caern] Leopardo da Neve: {alvo.name} ressuscitado '
        f'da Umbra com vida cheia!'
    )


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
