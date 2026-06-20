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


def _get_active_equipment(card) -> list:
    """Retorna equipamentos que a criatura optou por USAR no momento.

    Regra 4.3.2: "Creatures can choose not to use equipment attached to them."
    Equipamentos cujo uid esta em card.equipment_disabled sao ignorados.
    """
    if not hasattr(card, 'attached_equipment'):
        return []
    disabled = getattr(card, 'equipment_disabled', set())
    return [eq for eq in card.attached_equipment if id(eq) not in disabled]


# ── Limites de Rage por equipamento ──
# Chainsaw (slug: chainsaw): permite CAs ate Rage 10, descartada apos Rg>=6
# Shotgun (slug: shotgun): permite CAs ate Rage 7
# Rocket Launcher (slug: rocket-launcher): permite 1 CA ate Rage 12, descartado apos uso
EQUIPMENT_RAGE_LIMITS: dict[str, int] = {
    'chainsaw': 10,
    'shotgun': 7,
    'rocket-launcher': 12,
}


def _equipamento_melhor_limite(card) -> int:
    """Retorna o maior limite de Rage que os equipamentos ativos do card permitem.

    Considera Chainsaw (10), Shotgun (7), Rocket Launcher (12).
    Retorna 0 se nenhum equipamento relevante estiver ativo.
    """
    max_limit = 0
    for eq in _get_active_equipment(card):
        slug = getattr(eq, 'modelo_id', '') or ''
        limit = EQUIPMENT_RAGE_LIMITS.get(slug, 0)
        if limit > max_limit:
            max_limit = limit
    return max_limit


# ── Listas de "acoes" vs "nao-acoes" (Sidebar: Actions and actions) ──
# Acoes: sao bloqueadas por efeitos de 'impedir_acoes'
ACOES_QUE_SAO_ACAO: set[str] = {
    'play_action',          # Jogar Action card
    'play_gift',            # Jogar Gift card
    'play_rite',            # Jogar Rite card
    'play_caern_territory', # Jogar Caern ou Territory
    'equipar',              # Equipar
    'ally_recruit',         # Trazer Ally ao jogo
    'step_sideways',        # Stepping sideways
    'play_moot_bm',         # Jogar Moot ou Board Meeting
    'votar_junta',          # Votar numa Junta
    'alpha_action',         # Undertaking an alpha action
    'step_in',              # Stepping in
    'defender_territorio',  # Defending a Territory
    'defender_battlefield', # Defending a Battlefield
    'combat_action',        # Playing a Combat Action
}
# Naoo-acoes: NAO sao bloqueadas por impedir_acoes
ACOES_QUE_NAO_SAO_ACAO: set[str] = {
    'use_ability',          # Usar habilidade especial
    'play_event',           # Jogar Event card
    'play_quest',           # Jogar Quest card
    'play_past_life',       # Jogar Past Life
    'use_equipment',        # Usar Equipment
    'play_battlefield',     # Jogar Battlefield
    'bring_prey',           # Trazer Prey ao jogo
    'use_caern_ability',    # Usar habilidade de Caern/Territory
    'regenerar',            # Regenerating
    'combat_event',         # Jogar Combat Event
    'ser_alpha',            # Being Alpha
    'withdraw',             # Withdrawing do combate
}


def pode_tomar_acao(criatura, tipo_acao: str) -> bool:
    """Verifica se a criatura pode tomar um tipo de acao.

    Regra "Sidebar: Actions and actions":
    - Se 'impedir_acoes' bloqueia a criatura, apenas acoes
      na lista ACOES_QUE_NAO_SAO_ACAO sao permitidas.
    - ACOES_QUE_SAO_ACAO sao bloqueadas.

    Args:
        criatura: CardInstance da criatura.
        tipo_acao: String identificando o tipo de acao.

    Returns:
        True se a criatura pode realizar a acao.
    """
    if not hasattr(criatura, 'restricoes'):
        return True
    if 'nao_pode_agir' not in criatura.restricoes:
        return True
    # Se esta impedido de agir, so permite "nao-acoes"
    return tipo_acao in ACOES_QUE_NAO_SAO_ACAO


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

    # Nao pode frenzir se impedido (New Moon etc.)
    if game.has_modifier('impede_frenzy'):
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
    
    # Sticky Paws (6.10.4): recuperar equipamento roubado
    # Se o dono original derrota o ladrao em combate, recupera
    # a propriedade. So ocorre se em_combate=True e o dono_origem
    # e o mesmo do stolen_from.
    if em_combate and dono_origem:
        for eq in list(alvo.attached_equipment):
            stolen_from = getattr(eq, 'stolen_from', None)
            if stolen_from is not None and dono_origem.id == stolen_from:
                # Dono original derrotou o ladrao: recupera!
                alvo.attached_equipment.remove(eq)
                eq.stolen_from = None  # Limpa marcacao
                # Anexa de volta a um packmate viavel do dono original
                anexado = False
                for c in dono_origem.pack_home:
                    if c.health_current > 0:
                        c.attached_equipment.append(eq)
                        eq.attached_to = c
                        eq.zone = Zone.OUT_OF_PLAY
                        anexado = True
                        game.add_log(
                            f'{eq.name} recuperado por {dono_origem.name} '
                            f'(Sticky Paws) — anexado em {c.name}')
                        break
                if not anexado:
                    # Sem packmate vivo: vai pro descarte
                    eq.zone = Zone.DISCARD_SEPT
                    dono_origem.discard_sept.append(eq)
                    game.add_log(
                        f'{eq.name} recuperado por {dono_origem.name} '
                        f'mas sem packmate — descartado')

    if dono_alvo:
        descartar_anexos(alvo, dono_alvo, game=game)
    else:
        # Sem dono (HG global): descarta anexos sem dono
        for anexo in list(alvo.damage_cards):
            anexo.zone = Zone.OUT_OF_PLAY
        alvo.damage_cards.clear()
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
        # Helper: remove o morto das listas de combatentes
        def _remover_de_combate(card: CardInstance):
            cid_str = str(card.card_id)
            if cid_str in game.combat.attackers:
                game.combat.attackers.remove(cid_str)
            if cid_str in game.combat.defenders:
                game.combat.defenders.remove(cid_str)
            if cid_str in game.combat.combatants:
                game.combat.combatants.remove(cid_str)
            game.combat.declarations.pop(cid_str, None)
            game.combat.targets.pop(cid_str, None)

        if eh_hacked_apart:
            alvo.zone = Zone.VICTORY_PILE
            _remove_creature(game, alvo)
            dono_origem.victory_pile.append(alvo)
            _remover_de_combate(alvo)
            game.add_log(
                f'  Hacked Apart! {alvo.name} foi despedacado! '
                f'{dono_origem.name} ganhou {vp} VP '
                f'(total: {dono_origem.victory_points})'
            )
        elif alvo.is_frenzied:
            # Frenzied mas abaixo do threshold: morto mas continua
            # Nao move para VP, nao remove do jogo ainda
            # PERMANECE nas listas de combatentes (frenzy_dead_but_fighting)
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
            _remover_de_combate(alvo)
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
            # Non-character: descarta na pilha correta
            from rage_web.game_engine.rules import zona_descarte
            zona = zona_descarte(alvo.card_type or '')
            if zona == 'discard_combat':
                alvo.zone = Zone.DISCARD_COMBAT
                if dono_alvo:
                    dono_alvo.discard_combat.append(alvo)
            else:
                alvo.zone = Zone.DISCARD_SEPT
                if dono_alvo:
                    dono_alvo.discard_sept.append(alvo)
            _remove_creature(game, alvo)
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
    'careful_strike',   # Careful Strike (nao pode ser esquivado)
    'block_and_roll',   # Block and Roll (fast strike, block + counter)
    'block_and_strike', # Block and Strike (block + ataque)
    'evade_and_strike', # Evade and Strike (Kailindo, dodge + ataque)
    'fast_strike',      # Fast Strike (ataque rapido)
    'planned_strike',   # Planned Strike (dano nao pode ser redirecionado)
    'stunning_strike',  # Stunning Strike (fast, remove frenesi)
    'aggressive_bite',  # Aggressive Bite (nao Homid, impede fuga)
    'mitey_bitey',      # Mitey Bitey (vs alvo com Rage 2x+)
    'spirited_strike',  # Spirited Strike (Klaive bonus)
    'fetal_position',   # Fetal Position (block ataque <=6)
    'forceful_wind',    # Forceful Wind (Kailindo, encerra combate)
    'body_slam',        # Body Slam (+2 dano se sem acao anterior)
    'bum_rush',         # Bum Rush (evento, pack ataca)
    'pack_defense',     # Pack Defense (evento, puxa pack)
    'attacking_the_wyrm',  # Attacking the Wyrm (pack action, alpha ataca HG)
    'lucky_blow',       # Lucky Blow (dano 1)
    'off_balanced',     # Off-balanced Attack (-1 Rage prox rodada)
    'overextended',     # Overextended Attack (sem acao prox rodada)
    'reckless_swing',   # Reckless Swing (se esquivado, sem acao prox)
    'sap_spirit',       # Sap Spirit (so Umbra, unblockable)
    'stinging_wound',   # Stinging Wound (+1 Rage oponente se danificado)
    'surprise_attack',  # Surprise Attack (se danificar 1a rodada, vitima nao causa dano)
    'blood_atami',      # Blood Atami (-2 R/G enquanto danificado)
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
    # Verifica se tem arma equipada e ATIVA (criatura pode optar por nao usar)
    for eq in _get_active_equipment(criatura):
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
    # Acoes de combate adicionais
    'careful_strike': {
        'damage': None,           # Dano = Rage do atacante
        'rage_requirement': 3,
        'speed': 'normal',
        'nao_pode_esquivar': True,
    },
    'block_and_roll': {
        'damage': 1,              # Contra-ataque de 1
        'rage_requirement': 0,
        'speed': 'fast',
        'block_value': 2,         # Bloqueia ate 2
    },
    'block_and_strike': {
        'damage': None,           # Dano = Rage
        'rage_requirement': 4,
        'speed': 'normal',
        'block_value': 2,
    },
    'evade_and_strike': {
        'damage': None,           # Dano = Rage
        'rage_requirement': 3,
        'speed': 'normal',
        'dodge_all': True,        # Esquiva todos os ataques
    },
    'fast_strike': {
        'damage': None,
        'rage_requirement': 5,
        'speed': 'fast',
    },
    'planned_strike': {
        'damage': None,
        'rage_requirement': 4,
        'speed': 'normal',
        'nao_pode_redirecionar': True,
    },
    'stunning_strike': {
        'damage': None,
        'rage_requirement': 5,
        'speed': 'fast',
        'remove_frenesi': True,
    },
    'aggressive_bite': {
        'damage': None,
        'rage_requirement': 4,
        'speed': 'normal',
        'requer_nao_homod': True,
        'impede_fuga': True,
    },
    'mitey_bitey': {
        'damage': None,
        'rage_requirement': 2,
        'speed': 'normal',
        'vs_alto_rage': True,
    },
    'spirited_strike': {
        'damage': None,
        'rage_requirement': 3,
        'speed': 'normal',
        'cancela_actions_inimigas': True,
    },
    'fetal_position': {
        'damage': 0,
        'rage_requirement': 2,
        'speed': 'normal',
        'block_value': 6,         # Bloqueia ataque <=6
    },
    'forceful_wind': {
        'damage': 0,
        'rage_requirement': 4,
        'speed': 'normal',
        'encerra_combate': True,
    },
    'body_slam': {
        'damage': None,
        'rage_requirement': 4,
        'speed': 'normal',
        'bonus_sem_acao_anterior': 2,
    },
    'bum_rush': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'pack_attack': True,
    },
    'pack_defense': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'puxa_pack': True,
    },
    'attacking_the_wyrm': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'pack_attack': True,
        'draw_per_pack_member': True,
    },
    'lucky_blow': {
        'damage': 1,
        'rage_requirement': 2,
        'speed': 'normal',
    },
    'off_balanced': {
        'damage': None,
        'rage_requirement': 1,
        'speed': 'normal',
        'penalidade_rage_prox': -1,
    },
    'overextended': {
        'damage': None,
        'rage_requirement': 2,
        'speed': 'normal',
        'sem_acao_prox': True,
    },
    'reckless_swing': {
        'damage': None,
        'rage_requirement': 2,
        'speed': 'normal',
        'sem_acao_se_esquivado': True,
    },
    'sap_spirit': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'unblockable': True,
        'so_umbra': True,
    },
    'stinging_wound': {
        'damage': 1,
        'rage_requirement': 1,
        'speed': 'normal',
        'bonus_rage_oponente': 1,
    },
    'surprise_attack': {
        'damage': None,
        'rage_requirement': 2,
        'speed': 'normal',
        'vitima_nao_causa_dano_1a': True,
    },
    'blood_atami': {
        'damage': 0,
        'rage_requirement': 0,
        'speed': 'normal',
        'penalidade_rg': -2,
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
    for eq in _get_active_equipment(criatura):
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
    # ── Carleson Ruah: interrompe ordem para alpha agir 1o vs Wyrm ──
    # Se o pack de Carleson tem um alpha e ha Wyrm no oponente,
    # este alpha age primeiro (independente de Renome).
    if game.has_modifier('carleson_ruah'):
        for p in game.players:
            # Verifica se Carleson esta no pack deste jogador
            tem_carleson = any(
                c.card_id == 4 for c in p.pack_home)
            if not tem_carleson:
                continue
            meu_alpha_id = game.combat.alphas.get(p.id)
            if not meu_alpha_id:
                continue
            # Verifica se algum oponente tem criatura Wyrm
            for opp in game.players:
                if opp.id == p.id:
                    continue
                tem_wyrm = False
                for oc in opp.pack_home + opp.hunting_grounds + opp.umbra:
                    ct = (oc.card_type or '').lower()
                    if 'character' in ct and 'wyrm' in ct:
                        tem_wyrm = True
                        break
                if tem_wyrm:
                    # Bota o alpha de Carleson como primeiro
                    if meu_alpha_id in alphas:
                        alphas.remove(meu_alpha_id)
                        alphas.insert(0, meu_alpha_id)
                    game.add_log(
                        f'  Carleson Ruah: alpha de {p.name} '
                        f'age primeiro (interrompe vs Wyrm)')
                    break

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
    - Steps de auto-advance (pre_combat, beginning_of_combat, bluff):
      processados automaticamente (ações padrão).
    - Steps com ação do jogador (play_card, targeting, reveal):
      retornam False para que o bot/jogador decida.
    - Declaration step: transita automaticamente (já resolvido
      em start_combat), mas permite Hunting Party/Shieldmate.
    - Withdrawal step: verifica se atacante se retira ou continua.
    - between_rounds: verifica condições de fim; se continuar,
      faz loop para play_card (nova rodada).

    Returns:
        True se o step foi avançado (transição automática feita),
        False se precisa de ação do jogador/bot.
    """
    if not game.combat.is_active:
        return False

    step = game.combat.step
    combat = game.combat

    # Mapeia step antigo para novo (backward compat)
    if step in OLD_STEP_MAP:
        step = OLD_STEP_MAP[step]
        game.combat.step = step

    # ─── Steps de auto-advance ───
    # Estes steps têm transições automáticas (sem ação do jogador).
    if step in COMBAT_STEPS_AUTO:
        if step == 'pre_combat':
            # 6.1.2: Stepping In (6.5.9), pack actions, combat cancelling
            _preparar_stepping_in(game)
            game.add_log('  [Pre-Combat] Auto')

        elif step == 'beginning_of_combat':
            # 6.1.3: Open Play — gifts pré-combate, frenzy inicial
            # (Bot pode jogar Spirit of the Fray etc. aqui)
            game.add_log('  [Beginning-of-Combat] Open Play (auto)')

        elif step == 'bluff':
            # 6.2.4: Processa ilegais (6.9.1) + bluffs (6.9.2)
            _processar_bluff(game)

        # Avança para o próximo step na sequência
        idx = COMBAT_STEPS.index(step)
        if idx + 1 < len(COMBAT_STEPS):
            prox = COMBAT_STEPS[idx + 1]
            game.combat.step = prox
            game.add_log(f'  Step: {step} → {prox}')
            return True
        else:
            game.combat.step = 'end'
            return True

    # ─── Steps de transição manual ───

    if step == 'declaration':
        # 6.1.1: Declaration step — atacante/alvo já definido em start_combat.
        # Avança para pre_combat. As cartas de declaração (Hunting Party,
        # Shieldmate) podem ser jogadas aqui — implementado via efeitos.
        game.combat.step = 'pre_combat'
        game.add_log('  [Declaration] → pre_combat')
        return True

    if step == 'withdrawal':
        # 6.2.6 / 6.3.1: Atacante decide retirar ou continuar.
        if _processar_withdrawal(game):
            game.add_log('  [Withdrawal] Atacante retirou-se — combate encerrado')
            game.combat.step = 'end'
            return True
        # Se não retirou, avança para between_rounds
        game.add_log('  [Withdrawal] Atacante continua')
        game.combat.step = 'between_rounds'
        return True

    if step == 'between_rounds':
        # 6.2.7 / 6.3: Verifica condições de fim de combate.
        # Se combate continua, faz loop para play_card (nova rodada).

        # (a) Sem atacantes ou defensores → encerra
        if not combat.attackers or not combat.defenders:
            game.add_log('  Sem atacantes ou defensores — encerrando combate')
            game.combat.step = 'end'
            return True

        # (b) Limite de segurança: max 10 rodadas
        if combat.round_number >= 10:
            game.add_log('  Limite de 10 rodadas atingido — encerrando combate')
            game.combat.step = 'end'
            return True

        # (c) 6.3: Nenhuma Combat Action válida na rodada → encerra
        # Verifica se alguma criatura jogou uma Combat Action real
        # (exclui None e ''). Ilegais e blefes falhos já foram removidos.
        actions_validas = any(
            v is not None and v != ''
            for v in combat.declarations.values()
        )
        if not actions_validas:
            game.add_log(
                '  Nenhuma Combat Action válida — '
                'encerrando combate (6.3)')
            game.combat.step = 'end'
            return True

        # (d) Inicia nova rodada
        combat.round_number += 1
        game.add_log(
            f'  ⏳ Rodada {combat.round_number} — preparando...')

        # Limpa estado da rodada anterior
        combat.declarations.clear()
        combat.declaration_order.clear()
        combat.played_cards.clear()
        combat.face_down_order.clear()
        combat.targets.clear()
        combat.ce_face_down.clear()
        combat.illegal_cards.clear()
        combat.bluff_cards.clear()
        combat.bluff_failed.clear()
        combat.damage_queue.clear()
        combat.attacker_withdrew = False
        combat.extra_declarations.clear()
        combat.played_combat_cards.clear()
        combat.dano_actions.clear()

        # Reaplica efeitos de equipamento por rodada
        # (ex: Devilwhip concede +1 ação extra por rodada)
        _reaplicar_efeitos_equipamento_rodada(game)

        # Loop: volta para play_card
        game.combat.step = 'play_card'
        return True

    # ─── Steps que precisam de ação do jogador ───
    # Estes steps esperam o bot ou jogador interagir:
    # - play_card (6.2.1): jogar combat card face-down
    # - targeting (6.2.2): atribuir alvos
    # - reveal (6.2.3): revelar cartas + feinting
    return False


def start_combat(game: GameState, attackers: list[str],
                 defenders: list[str],
                 attack_type: str = 'creature',
                 target_card_id: Optional[str] = None,
                 card_ability: bool = False) -> bool:
    """Inicia um combate entre atacantes e defensores (6.1).

    Regra (6.1):
    - O combate começa quando um alpha declara um ataque.
    - Declaration step (6.1.1): attacker declara alvo;
      atacante pode jogar Hunting Party; defensor pode Shieldmate.
    - Pre-Combat step (6.1.2): pack actions, stepping in, redirect.
    - Beginning-of-Combat step (6.1.3): Open Play para gifts.
    - Em seguida começam as rodadas de combate (6.2).

    Regra (6.5.1):
    - Apenas alfas podem declarar ataques, a menos que seja
      uma carta/abilidade (card_ability=True).

    Args:
        game: Estado da partida.
        attackers: Lista de IDs das criaturas atacantes.
        defenders: Lista de IDs das criaturas defensoras.
        attack_type: Tipo de ataque ('creature', 'territory',
                      'battlefield', 'bind').
        target_card_id: ID do Territory/Battlefield/Spirit atacado
                         (usado para attack_type != 'creature').
        card_ability: True se o combate foi iniciado por uma carta
                       ou abilidade (pack attack, evento, etc).
                       False se é uma ação de alfa (padrão).

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

    # Regra (6.5.1): apenas alfas podem declarar ataques,
    # a menos que o combate foi iniciado por carta/abilidade.
    if not card_ability:
        for atk in attackers:
            if atk == 'hg':
                continue
            atk_card = _find_card(game, atk)
            if not atk_card:
                continue
            dono = _find_owner(game, atk_card)
            if dono:
                if game.combat:
                    alpha_id = game.combat.alphas.get(dono.id)
                    if alpha_id and str(atk_card.card_id) != alpha_id:
                        game.add_log(
                            f'Combate cancelado: {atk_card.name} nao e o '
                            f'alpha de {dono.name} (regra 6.5.1)')
                        return False
                # Se nao tem combat state ou alpha, permite (fallback)

    # ── Sky River Caern: bloqueia ataque a nao-alfa ANTES do Frenar ──
    # Regra: "Non-alpha members of your pack cannot be challenged or
    # sneak attacked." So protege membros do pack, NAO Presa no HG.
    if game.has_modifier('sky_river_caern'):
        alphas_atuais = dict(game.combat.alphas) if game.combat else {}
        packs_caern = set()
        for mod in list(game.game_modifiers):
            if mod.modifier == 'sky_river_caern':
                for p in game.players:
                    for c in p.pack_home + p.umbra:
                        if id(c) == mod.card_uid:
                            packs_caern.add(p.id)
                            break
        for dfd in list(defenders):
            if dfd == 'hg':
                continue
            dfd_card = _find_card(game, dfd)
            if not dfd_card:
                continue
            # Pula cartas no Hunting Grounds (Enemy/Victim nao sao
            # membros do pack, regra 4.4.2)
            if dfd_card.zone == Zone.HUNTING_GROUNDS:
                continue
            if dfd_card.owner_id not in packs_caern:
                continue
            alpha_card_id = alphas_atuais.get(dfd_card.owner_id)
            if alpha_card_id and str(dfd_card.card_id) == alpha_card_id:
                continue
            game.add_log(
                f'Sky River Caern: {dfd_card.name} nao pode ser atacado '
                f'(nao e o Alpha do pack)')
            return False

    # ── Frenar (slug='frenar_r1'): troca de lugar com o alpha se atacado ──
    if game.has_modifier('frenar_alpha_switch'):
        alphas_atuais = dict(game.combat.alphas) if game.combat else {}
        novos_defensores = list(defenders)
        for dfd in list(novos_defensores):
            if dfd == 'hg':
                continue
            dfd_card = _find_card(game, dfd)
            if not dfd_card:
                continue
            for pid, alpha_id in alphas_atuais.items():
                if dfd != alpha_id:
                    continue
                dono_alpha = _find_owner(game, dfd_card)
                if not dono_alpha:
                    continue
                for c in dono_alpha.pack_home:
                    if c.health_current <= 0:
                        continue
                    if getattr(c, 'modelo_id', '') == 'frenar_r1':
                        i = novos_defensores.index(dfd)
                        novos_defensores[i] = str(c.card_id)
                        game.add_log(
                            f'  [Frenar] {c.name} trocou de lugar '
                            f'com {dfd_card.name} (alpha atacado)!'
                        )
                        break
                break
        defenders = novos_defensores

    # Preserva alphas do estado de combate anterior
    alphas_anteriores = dict(game.combat.alphas) if game.combat else {}
    game._lowest_renown_victim_killed = None
    game.combat = CombatState(
        is_active=True,
        step='declaration',
        attackers=attackers,
        defenders=defenders,
        original_attackers=list(attackers),
        original_defenders=list(defenders),
        round_number=1,
        alphas=alphas_anteriores,
        attack_type=attack_type,
        territory_target=target_card_id if attack_type == 'territory' else None,
        battlefield_target=target_card_id if attack_type == 'battlefield' else None,
        bind_target=target_card_id if attack_type == 'bind' else None,
    )

    game.combat.combatants = list(attackers) + [d for d in defenders if d not in attackers]

    game.add_log(
        f'Combate iniciado: {len(attackers)} atacante(s) vs '
        f'{len(defenders)} defensor(es)'
    )

    _check_tzinzie_trigger(game)
    _check_caern_unwashed_child(game)

    # Trata ataque a Territory: substitui defensor pelo alpha do dono
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
                        novos_defensores.append(alpha_id)
                        alpha_card = _find_card(game, alpha_id)
                        alpha_name = alpha_card.name if alpha_card else alpha_id
                        game.add_log(
                            f'  {card.name} (Territory) defendido por '
                            f'alpha {alpha_name}')
                        if 'territory_targets' not in game.combat_triggers:
                            game.combat_triggers['territory_targets'] = {}
                        game.combat_triggers['territory_targets'][alpha_id] = card
                        continue
                game.add_log(f'  {card.name} (Territory) sem defensor - destruido!')
                _remove_creature(game, card)
                if dono:
                    dono.discard_sept.append(card)
                card.zone = Zone.DISCARD_SEPT
                continue
        novos_defensores.append(dfd)

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
            dono_bf = _find_owner(game, bf_card)
            alpha_defendeu = False
            if dono_bf:
                alpha_id = game.combat.alphas.get(dono_bf.id)
                if alpha_id and alpha_id in game.combat.defenders:
                    alpha_defendeu = True
            if not alpha_defendeu:
                bf_renown = getattr(bf_card, 'renown', 3) or 3
                game.combat.battlefield_self_defense[target_card_id] = {
                    'rage': bf_renown,
                    'gnosis': bf_renown,
                    'health': bf_renown,
                    'health_current': bf_renown,
                    'renown': bf_renown,
                    'card': bf_card,
                }
                if target_card_id not in game.combat.defenders:
                    game.combat.defenders.append(target_card_id)
                if target_card_id not in game.combat.combatants:
                    game.combat.combatants.append(target_card_id)
                game.add_log(
                    f'  {bf_card.name} (Battlefield) em autodefesa '
                    f'(Rg/Gn/Hp={bf_renown})')

    # ── Mindspeak: pack coordination entre personagens vinculados ──
    for link in list(game.mindspeak_links):
        caster_uid = link['caster_uid']
        packmate_uid = link['packmate_uid']
        player_id = link['player_id']

        def _uid_to_card_str(uid: int) -> str | None:
            for p in game.players:
                for c in p.pack_home + p.hunting_grounds + p.umbra:
                    if id(c) == uid and c.health_current > 0:
                        return str(c.card_id)
            return None

        caster_cid = _uid_to_card_str(caster_uid)
        packmate_cid = _uid_to_card_str(packmate_uid)
        if not caster_cid or not packmate_cid:
            continue  # Um dos dois morreu

        # Se o caster esta atacando, packmate pode juntar-se
        if caster_cid in game.combat.attackers:
            if packmate_cid not in game.combat.attackers:
                game.combat.attackers.append(packmate_cid)
                game.combat.combatants.append(packmate_cid)
                game.add_log(
                    f'  [🧠 Mindspeak] {link["packmate_name"]} juntou-se '
                    f'ao ataque de {link["caster_name"]}!')

        # Se o caster esta defendendo, packmate pode juntar-se
        if caster_cid in game.combat.defenders:
            if packmate_cid not in game.combat.defenders:
                game.combat.defenders.append(packmate_cid)
                game.combat.combatants.append(packmate_cid)
                game.add_log(
                    f'  [🧠 Mindspeak] {link["packmate_name"]} juntou-se '
                    f'a defesa de {link["caster_name"]}!')

        # Se o packmate esta atacando, caster pode juntar-se
        if packmate_cid in game.combat.attackers:
            if caster_cid not in game.combat.attackers:
                game.combat.attackers.append(caster_cid)
                game.combat.combatants.append(caster_cid)
                game.add_log(
                    f'  [🧠 Mindspeak] {link["caster_name"]} juntou-se '
                    f'ao ataque de {link["packmate_name"]}!')

        # Se o packmate esta defendendo, caster pode juntar-se
        if packmate_cid in game.combat.defenders:
            if caster_cid not in game.combat.defenders:
                game.combat.defenders.append(caster_cid)
                game.combat.combatants.append(caster_cid)
                game.add_log(
                    f'  [🧠 Mindspeak] {link["caster_name"]} juntou-se '
                    f'a defesa de {link["packmate_name"]}!')

    # ── Playing for Prey (6.6.3): determina quem joga por cada presa ──
    for i, dfd in enumerate(game.combat.defenders):
        if dfd == 'hg':
            continue
        dfd_card = _find_card(game, dfd)
        if not dfd_card:
            continue
        ct = (dfd_card.card_type or '').lower()
        if not any(t in ct for t in ('victim', 'enemy')):
            continue
        # Esta presa esta sendo atacada
        if i < len(game.combat.attackers):
            atk_id = game.combat.attackers[i]
            atk_card = _find_card(game, atk_id)
            if atk_card:
                game.combat.prey_attackers[atk_card.owner_id] = True
                # Jogador designado para jogar pela presa:
                # qualquer um EXCETO o atacante
                candidatos = []
                for p in game.players:
                    if p.id != atk_card.owner_id and not p.eliminado:
                        candidatos.append(p)
                if candidatos:
                    # Escolhe o que tem mais cartas de combate na mao
                    candidatos.sort(key=lambda p: len(p.hand), reverse=True)
                    escolhido = candidatos[0]
                    game.combat.prey_player[dfd] = escolhido.id
                    game.add_log(
                        f'  [Presa] {dfd_card.name}: {escolhido.name} '
                        f'jogara por esta presa')

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
        dono.hand.remove(ce_card)
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

    # Registra no estado do combate (inclui Rage requirement do banco)
    game.combat.dano_actions[action_name] = {
        'damage': dano_valor,
        'card_id': card.card_id,
        'rage_requirement': getattr(card, 'rage', 0),
        'card_name': card.name,
        'speed': getattr(card, 'speed', 'normal'),
    }

    # ── Nao descarta a carta imediatamente (regra 6.4) ──
    # A Combat Action revelada e anexada a criatura alvo como dano.
    # Na Regeneracao, ela e desanexada e vai para o descarte de combate
    # do dono da carta. Isso e feito pela funcao anexar_dano() na
    # resolucao do combate, que usa played_combat_cards.
    # Por enquanto, apenas remove da mao de combate.
    dono = _find_owner(game, card)
    if dono and card in dono.hand:
        dono.hand.remove(card)
    card.zone = Zone.OUT_OF_PLAY

    game.add_log(f'  {card.name} registrado como acao de dano '
                 f'(dano: {dano_valor})')

    return action_name


def declare_action(game: GameState, card_id: str, action: str,
                     acoes_extra: Optional[list[str]] = None,
                     carta_combate: Optional[CardInstance] = None) -> bool:
    """Declara uma acao de combate para uma criatura.

    A ordem da declaracao importa: quem declara por ultimo
    ganha vantagem no Reveal Step (pode usar Feint).

    Args:
        game: Estado da partida.
        card_id: ID da criatura que esta declarando.
        action: Nome da acao (ex: 'strike', 'block', 'dodge').
        acoes_extra: Lista opcional de acoes extras permitidas
                      (ex: Combat Actions especificas como 'tail_lash').
        carta_combate: A carta de Combat Action real que foi jogada
                       (ex: Surprise Attack, Reckless Swing).
                       Se fornecida, a carta e rastreada em
                       game.combat.played_combat_cards para que
                       possa ser anexada como dano ao alvo (regra 6.4).

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

    # ── Sidebar: Actions and actions — Combat Action e ACTION ──
    # Criaturas impedidas de agir nao podem declarar Combat Actions
    # (excecao: Combat Events NAO sao acoes — permitidos)
    if not action.startswith('ce_') and not action.startswith('dano_'):
        criatura = _find_criatura(game, card_id)
        if criatura and not pode_tomar_acao(criatura, 'combat_action'):
            game.add_log(
                f'{criatura.name} nao pode declarar {action} '
                f'(impedido de agir)')
            return False

    # Whip of the Wicked (720): oponente deve declarar block/dodge primeiro
    erro_whip = _validar_whip_constraint(game, card_id, action)
    if erro_whip:
        game.add_log(f'Whip of the Wicked: {erro_whip}')
        return False

    # ── Verifica se e uma acao extra (Devilwhip, etc.) ──
    criatura = _find_criatura(game, card_id)
    is_extra = False
    if criatura and card_id in game.combat.declarations:
        # Criatura ja declarou — verifica se tem acoes extras
        extras = getattr(criatura, 'acoes_extras_disponiveis', 0)
        if extras > 0:
            max_rage = getattr(criatura, 'acoes_extras_max_rage', 2)
            is_extra = True
            # Decrementa contador de acoes extras
            setattr(criatura, 'acoes_extras_disponiveis', extras - 1)
            unblockable = getattr(criatura, 'acoes_extras_unblockable', False)
            game.add_log(
                f'  [Acao Extra] {criatura.name} usa acao extra'
                f' (Rg<={max_rage})'
                f'{" [inbloqueavel]" if unblockable else ""}'
            )
        else:
            return False  # Ja declarou e nao tem extras

    success = game.combat.declare(card_id, action, extra=is_extra)
    if success:
        # Marca a criatura como tendo declarado (play_card step)
        game.combat.played_cards[card_id] = action
        last = game.combat.last_to_declare
        card_declaring = _find_card(game, card_id)
        card_name = card_declaring.name if card_declaring else card_id
        # Resolve nome da acao para formato legivel
        from .action_descriptions import _resolve_action_name
        acao_nome = _resolve_action_name(action, card_name, game)
        extra_tag = ' [EXTRA]' if is_extra else ''
        game.add_log(
            f'{acao_nome}{extra_tag}'
            f'{" (Ultimo a Declarar!)" if card_id == last else ""}'
        )

    # ── Rastreia a carta de combate jogada (regra 6.4) ──
    # Se uma Combat Action real foi usada (ex: Surprise Attack),
    # armazena a referencia para que ela seja anexada como dano
    # ao alvo na resolucao do combate, em vez de criar uma copia.
    if carta_combate is not None and success:
        game.combat.played_combat_cards[card_id] = carta_combate

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

    # Antes de revelar, verifica presas que ainda nao declararam.
    # Regra (6.6.3): o jogador designado joga pela presa.
    for dfd in game.combat.defenders:
        if dfd == 'hg' or not _eh_prey_no_hg(game, dfd):
            continue
        if dfd in game.combat.declarations:
            continue
        prey_card = _find_card(game, dfd)
        if not prey_card:
            continue

        # Tenta encontrar carta defensiva na mao do designado
        designado_id = game.combat.prey_player.get(dfd)
        declarou = False
        if designado_id:
            desig = next((p for p in game.players
                          if p.id == designado_id), None)
            if desig and desig.combat_hand:
                for acao_tentada in ('block', 'dodge'):
                    for cc in desig.combat_hand:
                        nome_slug = (cc.name or '').lower()\
                            .replace(' ', '_').replace('-', '_')
                        if nome_slug == acao_tentada:
                            props = COMBAT_ACTION_PROPS.get(acao_tentada, {})
                            req = props.get('rage_requirement', 0)
                            if prey_card.effective_rage >= req:
                                declare_action(
                                    game, dfd, acao_tentada,
                                    acoes_extra=[acao_tentada],
                                    carta_combate=cc)
                                game.combat.played_combat_cards[dfd] = cc
                                game.add_log(
                                    f'  {prey_card.name} '
                                    f'(Presa) defende-se com {cc.name}')
                                declarou = True
                                break
                        elif nome_slug == 'evasion' and acao_tentada == 'dodge':
                            props = COMBAT_ACTION_PROPS.get('dodge', {})
                            req = props.get('rage_requirement', 0)
                            if prey_card.effective_rage >= req:
                                declare_action(
                                    game, dfd, 'dodge',
                                    acoes_extra=['dodge'],
                                    carta_combate=cc)
                                game.combat.played_combat_cards[dfd] = cc
                                game.add_log(
                                    f'  {prey_card.name} '
                                    f'(Presa) defende-se com {cc.name}')
                                declarou = True
                                break
                    if declarou:
                        break

        if not declarou:
            # Nenhuma carta defensiva encontrada — presa sem acao
            game.combat.declarations[dfd] = ''
            game.add_log(
                f'  {prey_card.name} (Presa) nao tem defesa '
                f'disponivel — fica sem acao')

    combatants = get_combatants(game)
    if not game.combat.all_declared(combatants):
        return False  # Nem todos declararam

    game.combat.step = 'reveal'
    game.combat.feint_substep = 'feinting'  # 6.8: abre janela de Feinting
    game.add_log('Acoes reveladas! (janela de Feinting aberta)')
    game.add_log('  [Reveal] Feinting (6.8.1), Instinctive (6.8.2) '
                 'e Alternative (6.6.5) disponiveis neste sub-step.')
    for cid, action in game.combat.declarations.items():
        if action:
            card_revealed = _find_card(game, cid)
            card_name = card_revealed.name if card_revealed else cid
            from .action_descriptions import _resolve_action_name
            acao_nome = _resolve_action_name(action, card_name, game)
            game.add_log(f'  {acao_nome}')
        else:
            game.add_log(f'  {cid}: {action}')

    # Tzinzie (1348): se oponente revelou a acao nomeada, descarta
    # Regra (4.5.2B): so funciona se o Character com Tzinzie ainda
    # estiver em combate
    if 1348 in game.combat_triggers:
        tz = game.combat_triggers[1348]
        named_action = tz.get('named_action', '')
        owner_id = tz.get('owner_id', '')
        char_id = tz.get('character_id', '')
        # Verifica se o Character com Tzinzie ainda esta em combate
        char_em_combate = char_id in (
            game.combat.attackers + game.combat.defenders
        ) if game.combat else False
        if not char_em_combate:
            game.add_log(
                'Tzinzie: Character fora do combate, efeito cancelado')
        else:
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

    # ── Pack Combat (6.5.8): processa efeitos de pack attack/defense ──
    # NOTA: nao chamamos aqui porque cartas ilegais ainda nao foram
    # removidas. O processamento ocorre em _processar_bluff() apos
    # a limpeza de ilegais.

    return True


def _reaplicar_efeitos_equipamento_rodada(game: GameState) -> None:
    """Reaplica efeitos de equipamento que duram por rodada.

    Chamado no inicio de cada rodada de combate (between_rounds -> play_card).
    Percorre todas as criaturas em combate e verifica se possuem
    equipamentos que concedem acoes extras ou outros efeitos por rodada.

    Exemplos:
    - Devilwhip (card_id 638): +1 acao extra de combate (Rg<=2, ou Rg<=3 para Bane)
    """
    from rage_web.game_engine.effects import CARTAS_EXEMPLO, EfeitoTipo

    combat = game.combat
    if not combat.is_active:
        return

    # Coleta todas as criaturas em combate (atacantes + defensores)
    combatantes_ids = set()
    for cid in combat.attackers + combat.defenders:
        if cid != 'hg':
            combatantes_ids.add(cid)

    for cid in combatantes_ids:
        criatura = _find_card(game, cid)
        if not criatura:
            continue

        # Verifica se a criatura e Bane
        criatura_type = (criatura.card_type or '').lower()
        criatura_kw = (criatura.keywords or '').lower()
        is_bane = 'bane' in criatura_type or 'bane' in criatura_kw

        # Verifica equipamentos anexados (apenas os ATIVOS)
        for eq in _get_active_equipment(criatura):
            modelo_id = getattr(eq, 'modelo_id', None)
            if not modelo_id:
                continue

            modelo = CARTAS_EXEMPLO.get(modelo_id)
            if not modelo:
                continue

            # Procura o melhor efeito ACAO_EXTRA_POR_RODADA aplicavel
            # (equipamentos com multiplos modos: escolhe o modo correto)
            melhor_efeito = None
            melhor_max_rage = -1

            for modo in modelo.modos:
                for efeito in modo.efeitos:
                    if efeito.tipo == EfeitoTipo.ACAO_EXTRA_POR_RODADA:
                        params = efeito.params or {}
                        max_rage = params.get('max_rage', 2)

                        # Se o modo requer Bane (Rg3+) e a criatura nao e Bane, pula
                        if max_rage >= 3 and not is_bane:
                            continue
                        # Se a criatura e Bane e o modo e Rg2, pode usar mas prefere Rg3
                        if is_bane and max_rage >= 3:
                            if melhor_efeito is None or max_rage > melhor_max_rage:
                                melhor_efeito = efeito
                                melhor_max_rage = max_rage
                        elif not is_bane and max_rage <= 2:
                            if melhor_efeito is None:
                                melhor_efeito = efeito
                                melhor_max_rage = max_rage

            if melhor_efeito is None:
                # Fallback: usa o primeiro efeito encontrado
                for modo in modelo.modos:
                    for efeito in modo.efeitos:
                        if efeito.tipo == EfeitoTipo.ACAO_EXTRA_POR_RODADA:
                            melhor_efeito = efeito
                            break
                    if melhor_efeito:
                        break

            if not melhor_efeito:
                continue

            params = melhor_efeito.params or {}
            max_rage = params.get('max_rage', 2)
            qtd = params.get('qtd_acoes', 1)
            unblockable = params.get('unblockable', False)

            effective_max_rage = max_rage

            # Aplica o buff na criatura
            extras_atuais = getattr(criatura, 'acoes_extras_disponiveis', 0)
            setattr(criatura, 'acoes_extras_disponiveis', extras_atuais + qtd)
            setattr(criatura, 'acoes_extras_max_rage', effective_max_rage)
            if unblockable:
                setattr(criatura, 'acoes_extras_unblockable', True)

            game.add_log(
                f'  [Equip] {eq.name} em {criatura.name}: '
                f'+{qtd} acao extra (Rg<={effective_max_rage})'
            )


def _find_card(game: GameState, card_id: str) -> Optional[CardInstance]:
    """Encontra uma carta pelo ID em qualquer zona de qualquer jogador
    ou no Hunting Grounds global.

    Prioriza zonas ativas (pack_home, hunting_grounds, umbra, hand)
    sobre zonas de descarte/vitoria, para evitar que damage cards
    (que copiam o card_id da origem) sejam encontradas no lugar da
    carta original."""
    # Primeira passada: zonas ativas (cartas "vivas")
    for p in game.players:
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra,
                          p.hand):
            for c in zone_list:
                if str(c.card_id) == card_id:
                    return c
    # Segunda passada: zonas de descarte/vitoria
    for p in game.players:
        for zone_list in (p.discard_combat, p.discard_sept,
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
        for zone_list in (p.pack_home, p.hunting_grounds, p.umbra,
                          p.discard_combat, p.discard_sept, p.victory_pile):
            if card in zone_list:
                zone_list.remove(card)
                # Se era um Plague Vermin, atualiza stats dos restantes
                if card.card_id == 524:
                    game._atualizar_plague_vermin_stats()
                return
    # Tenta remover do Hunting Grounds global
    if card in game.hunting_grounds_cards:
        game.hunting_grounds_cards.remove(card)
        # Se era um Plague Vermin, atualiza stats dos restantes
        if card.card_id == 524:
            game._atualizar_plague_vermin_stats()
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

    # Remove da zona atual e move para o descarte apropriado
    dono = _find_owner(game, criatura)
    _remove_creature(game, criatura)
    from rage_web.game_engine.rules import zona_descarte
    zona = zona_descarte(criatura.card_type or '')
    if zona == 'discard_combat':
        criatura.zone = Zone.DISCARD_COMBAT
        if dono:
            dono.discard_combat.append(criatura)
    else:
        criatura.zone = Zone.DISCARD_SEPT
        if dono:
            dono.discard_sept.append(criatura)
    return True


def _find_owner(game: GameState, card: CardInstance) -> Optional[PlayerState]:
    """Encontra o jogador dono de uma carta."""
    return _find_player(game, card.owner_id)


def _processar_flee_e_step_sideways(game: GameState,
                                      velocidade: str) -> int:
    """Processa acoes de combate flee/step_sideways (Parting Shots 6.10.4).

    Regra (6.10.4): "A creature using a Combat Action that removes it
    from combat (or makes it step sideways) is still affected by Combat
    Actions targeting him that resolve at the same time."

    Esta funcao deve ser chamada DEPOIS que todos os ataques e
    contra-ataques da velocidade atual ja resolveram, mas ainda dentro
    do mesmo passo de velocidade. Assim, a criatura que declarou flee
    ou step_sideways ja tomou todo o dano de ataques simultaneos antes
    de ser removida.

    Args:
        game: Estado da partida.
        velocidade: 'fast', 'normal' ou 'slow'.

    Returns:
        Numero de criaturas que fugiram / step sideways.
    """
    if not game.combat.is_active:
        return 0

    processados = 0
    combat = game.combat

    # Reune todos os combatentes vivos
    combatentes = set()
    for cid in combat.combatants:
        if cid == 'hg':
            continue
        card = _find_card(game, cid)
        if card and card.health_current > 0:
            combatentes.add(cid)

    for cid in combatentes:
        acao = combat.declarations.get(cid, '')
        if not acao:
            continue

        # So processa acoes desta velocidade
        acao_speed = 'normal'
        if acao.startswith('dano_'):
            dano_info = combat.dano_actions.get(acao, {})
            acao_speed = dano_info.get('speed', 'normal')
        else:
            props = COMBAT_ACTION_PROPS.get(acao, {})
            acao_speed = props.get('speed', 'normal')
        if acao_speed != velocidade:
            continue

        card = _find_card(game, cid)
        if not card or card.health_current <= 0:
            continue  # Mortos nao fogem

        def _remover_de_listas(card_id_str: str):
            """Helper: remove card_id de todas as listas de combate."""
            for lista in (combat.attackers, combat.defenders,
                          combat.combatants):
                if card_id_str in lista:
                    lista.remove(card_id_str)
            combat.declarations.pop(card_id_str, None)
            combat.targets.pop(card_id_str, None)
            # Remove de lista de combat cards jogados
            combat.played_combat_cards.pop(card_id_str, None)
            combat.played_cards.pop(card_id_str, None)
            combat.ce_face_down.pop(card_id_str, None)
            if card_id_str in combat.face_down_order:
                combat.face_down_order.remove(card_id_str)
            # damage_queue e uma lista de tuplas (origem, alvo, dano, speed)
            combat.damage_queue = [
                d for d in combat.damage_queue if d[0] != card_id_str
            ]
            if hasattr(combat, 'dano_actions'):
                for k in list(combat.dano_actions.keys()):
                    if card_id_str in k:
                        combat.dano_actions.pop(k, None)

        if acao == 'flee':
            cid_str = str(card.card_id)
            dono = _find_owner(game, card)
            # Remove da zona atual e move para descarte
            if dono:
                for zone_list in (dono.pack_home, dono.hunting_grounds,
                                  dono.umbra):
                    if card in zone_list:
                        zone_list.remove(card)
                        break
            from rage_web.game_engine.rules import zona_descarte
            zona = zona_descarte(card.card_type or '')
            if zona == 'discard_combat':
                card.zone = Zone.DISCARD_COMBAT
                if dono:
                    dono.discard_combat.append(card)
            else:
                card.zone = Zone.DISCARD_SEPT
                if dono:
                    dono.discard_sept.append(card)
            _remover_de_listas(cid_str)
            game.add_log(
                f'  {card.name} fugiu do combate (Parting Shot)!'
            )
            processados += 1

        elif acao == 'step_sideways':
            cid_str = str(card.card_id)
            dono = _find_owner(game, card)
            if dono:
                # Move da zona atual para Umbra
                for zone_list in (dono.pack_home,
                                  dono.hunting_grounds):
                    if card in zone_list:
                        zone_list.remove(card)
                        break
                card.zone = Zone.UMBRA
                dono.umbra.append(card)
            _remover_de_listas(cid_str)
            game.add_log(
                f'  {card.name} step sideways para a Umbra '
                f'(Parting Shot)!'
            )
            processados += 1

    if processados:
        # Limpa combatentes que morreram apos as remocoes
        mortos_ids = set()
        for cid in list(combat.combatants):
            if cid == 'hg':
                continue
            card = _find_card(game, cid)
            if card and card.health > 0 and card.health_current <= 0:
                mortos_ids.add(cid)
        if mortos_ids:
            game.combat.limpar_combatentes_mortos(mortos_ids)

    return processados


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

    A decisao de retirar e estrategica:
    - Se o atacante tem cartas de combate na mao, NAO retira
      (quer continuar lutando)
    - Se o atacante esta em desvantagem numerica ou o alpha
      esta muito ferido, retira
    - Se nao ha carta de combate E alpha esta saudavel,
      retira (nao vale a pena continuar)

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

    # ── Verificacao de vitoria ──
    # Se nao ha mais defensores vivos, combate encerra
    # (atacante venceu)
    defensores_vivos = []
    for def_id in combat.defenders:
        if def_id == 'hg':
            continue
        card = _find_card(game, def_id)
        if card and card.health_current > 0:
            defensores_vivos.append(def_id)

    if not defensores_vivos:
        game.add_log(
            '  [Withdrawal] Nenhum defensor vivo — combat encerrado')
        game.add_log('  [Withdrawal] Atacante retirou-se do combate')
        return True

    # Verifica se atacantes ainda estao vivos
    atacantes_vivos = []
    for atk_id in combat.attackers:
        if atk_id == 'hg':
            continue
        card = _find_card(game, atk_id)
        if card and card.health_current > 0:
            atacantes_vivos.append(atk_id)

    if not atacantes_vivos:
        game.add_log(
            '  [Withdrawal] Nenhum atacante vivo — combat encerrado')
        return True

    # ── Decisao estrategica de withdrawal ──
    # Encontra o jogador atacante
    jogador_atacante = None
    alpha_atacante = None
    if atacantes_vivos:
        atk_id = atacantes_vivos[0]
        card = _find_card(game, atk_id)
        if card:
            for p in game.players:
                if p.id == card.owner_id:
                    jogador_atacante = p
                    alpha_atacante = card
                    break

    if jogador_atacante:
        # 1. Se tem cartas de combate na mao → NAO retira
        if jogador_atacante.combat_hand:
            game.add_log(
                f'  [Withdrawal] {jogador_atacante.name} tem '
                f'{len(jogador_atacante.combat_hand)} carta(s) de '
                f'combate — continua lutando')
            return False

        # 2. Se o alpha esta muito ferido (HP <= 30%) → retira
        if alpha_atacante and alpha_atacante.health > 0:
            hp_ratio = (alpha_atacante.health_current /
                        alpha_atacante.health)
            if hp_ratio <= 0.3:
                game.add_log(
                    f'  [Withdrawal] {alpha_atacante.name} muito ferido '
                    f'({alpha_atacante.health_current}/'
                    f'{alpha_atacante.health}) — retirando')
                game.add_log('  [Withdrawal] Atacante retirou-se do combate')
                return True

        # 3. Se esta em desvantagem numerica (mais defensores) → retira
        if (len(combat.attackers) > 0 and
                len(combat.defenders) > len(combat.attackers)):
            game.add_log(
                f'  [Withdrawal] Atacante em desvantagem numerica '
                f'({len(combat.attackers)}x{len(combat.defenders)})'
                f' — retirando')
            game.add_log('  [Withdrawal] Atacante retirou-se do combate')
            return True

    # 4. Sem cartas de combate e sem desvantagem critica →
    #    retira mesmo assim (nao vale a pena continuar)
    game.add_log('  [Withdrawal] Atacante retirou-se do combate')
    return True


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
        game.add_log(
            f'  [Challenge] {alpha.name} desafiou {alvo.name} — ACEITO')
        start_combat(game, [alpha_id], [alvo_id])
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


def _process_pack_combat(game: GameState) -> None:
    """Processa Pack Combat (6.5.8).

    Escaneia acoes reveladas em busca de Combat Events com
    propriedade 'pack_attack' (Bum Rush) ou 'puxa_pack'
    (Pack Defense). Quando encontrada, expande os combatentes
    adicionando todos os personagens vivos do pack do dono.

    Regras:
    - Só pode trazer criaturas do próprio pack
    - Criaturas no Hunting Grounds não entram (salvo exceção em carta)
    - Ao fim da rodada, os extras são removidos
    - Pack defending no Hunting Grounds funciona igual
    """
    if not game.combat.is_active:
        return

    combatants_list = get_combatants(game)
    pack_actions_processed = set()

    for cid, action in list(game.combat.declarations.items()):
        if action is None:
            continue
        # Pula cartas marcadas como ilegais (ja removidas apos bluff)
        if cid in game.combat.illegal_cards:
            continue
        if not action.startswith('ce_'):
            # Só Combat Events podem ter pack_attack/puxa_pack
            props = COMBAT_ACTION_PROPS.get(action, {})
            is_pack_attack = props.get('pack_attack', False)
            is_puxa_pack = props.get('puxa_pack', False)
            if not is_pack_attack and not is_puxa_pack:
                continue
        else:
            # Combat Events: busca no ce_face_down qual carta foi jogada
            ce_card_id = game.combat.ce_face_down.get(cid)
            if not ce_card_id:
                continue
            # Mapeia o nome do CE para ver se tem props conhecidas
            ce_card = _find_card(game, ce_card_id)
            if not ce_card:
                continue
            nome_slug = (ce_card.name or '').lower().replace(' ', '_').replace('-', '_')
            props = COMBAT_ACTION_PROPS.get(nome_slug, {})
            if not props.get('pack_attack') and not props.get('puxa_pack'):
                continue
            action = nome_slug
            # Registra a acao nas declarations para que a resolucao
            # possa identificar o pack combat
            game.combat.declarations[cid] = nome_slug
            is_pack_attack = props.get('pack_attack', False)
            is_puxa_pack = props.get('puxa_pack', False)

        if cid in pack_actions_processed:
            continue
        pack_actions_processed.add(cid)

        card = _find_card(game, cid)
        if not card:
            continue

        dono = _find_owner(game, card)
        if not dono:
            continue

        # Encontra todos os personagens vivos no Pack Home do dono
        # Regra: só pode trazer criaturas do próprio pack
        for c in dono.pack_home:
            if c.health_current <= 0:
                continue
            cid_str = str(c.card_id)

            # Pula quem já está no combate
            if cid_str in combatants_list:
                continue

            # Verifica se é um combatente válido
            if not _eh_combatente_valido(game, cid_str):
                continue

            if is_pack_attack:
                if cid_str not in game.combat.attackers:
                    game.combat.attackers.append(cid_str)
                    game.combat.pack_added_attackers.append(cid_str)
                    game.add_log(
                        f'  [Pack Attack] {c.name} juntou-se ao ataque!'
                    )
            if is_puxa_pack:
                if cid_str not in game.combat.defenders:
                    game.combat.defenders.append(cid_str)
                    game.combat.pack_added_defenders.append(cid_str)
                    game.add_log(
                        f'  [Pack Defense] {c.name} juntou-se a defesa!'
                    )

        # Conta quantos do pack entraram (para Attacking the Wyrm)
        joining_count = 0
        if props.get('draw_per_pack_member'):
            for c in dono.pack_home:
                if c.health_current <= 0:
                    continue
                cid_str = str(c.card_id)
                if cid_str not in combatants_list:
                    continue
                if _eh_combatente_valido(game, cid_str):
                    # Ja estava no combate ou entrou via pack
                    if cid_str in game.combat.attackers or cid_str in game.combat.defenders:
                        joining_count += 1
            # Tira o alpha da contagem (ele ja estava atacando)
            alpha_id = game.combat.alphas.get(dono.id, '')
            if alpha_id and alpha_id in (game.combat.attackers + game.combat.defenders):
                joining_count = max(0, joining_count - 1)
            if joining_count > 0:
                drawn = dono.draw_combat(joining_count)
                game.add_log(
                    f'  [Attacking the Wyrm] {dono.name} comprou '
                    f'{len(drawn)} carta(s) de combate '
                    f'({joining_count} do pack)'
                )

        if is_pack_attack:
            game.add_log(
                f'  [Pack Combat] {card.name} iniciou ataque em pack!'
            )
        elif is_puxa_pack:
            game.add_log(
                f'  [Pack Combat] {card.name} iniciou defesa em pack!'
            )

    # Remove de ilegais as acoes de pack que acabamos de processar
    # (ainda serao descartadas como ilegais, mas o efeito ja ocorreu)
    for cid in pack_actions_processed:
        game.combat.illegal_cards.discard(cid)


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

    # ── Funcao auxiliar: verifica se carta nao pode ser blefada ──
    def _carta_nao_pode_blefar(carta) -> bool:
        reqs = (getattr(carta, 'requires', '') or '').lower()
        if 'not bluffed' in reqs or 'nao bluffavel' in reqs:
            return True
        texto = (getattr(carta, 'text', '') or '').lower()
        if 'cannot be bluffed' in texto:
            return True
        meta = getattr(carta, '_metadata', None) or {}
        texto_meta = (meta.get('texto_original', '') or '').lower()
        if 'cannot be bluffed' in texto_meta:
            return True
        return False

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

        # Para acoes virtuais (dano_<uid>), busca requirement do card
        if action.startswith('dano_'):
            dano_info = game.combat.dano_actions.get(action, {})
            rage_req = dano_info.get('rage_requirement', 0) or 0

        # 6.9.1: Verificar ilegais (requisitos nao-Rage)
        # Combat Events jogados face-down: verifica se tem
        # propriedades conhecidas (pack_attack, puxa_pack, etc.)
        # Se tiver, e legitimo (ex: Bum Rush, Pack Defense).
        if action.startswith('ce_'):
            ce_card_id = game.combat.ce_face_down.get(cid)
            if ce_card_id:
                ce_card = _find_card(game, ce_card_id)
                if ce_card:
                    nome_slug = (ce_card.name or '').lower().replace(
                        ' ', '_').replace('-', '_')
                    ce_props = COMBAT_ACTION_PROPS.get(nome_slug, {})
                    # Se tem pack_attack ou puxa_pack, e legitimo
                    if ce_props.get('pack_attack') or ce_props.get('puxa_pack'):
                        game.add_log(
                            f'  [Bluff] {ce_card.name} e um Combat Event '
                            f'legitimo -> permitido')
                        # Nao marca como ilegal; processa na resolucao
                    else:
                        game.combat.illegal_cards.add(cid)
                        game.add_log(
                            f'  [Bluff] {card.name} jogou Combat Event '
                            f'face-down -> ILEGAL (6.9.1)')
                        continue
                else:
                    game.combat.illegal_cards.add(cid)
                    game.add_log(
                        f'  [Bluff] {card.name} jogou Combat Event '
                        f'face-down -> ILEGAL (6.9.1)')
                    continue
            else:
                game.combat.illegal_cards.add(cid)
                game.add_log(
                    f'  [Bluff] {card.name} jogou Combat Event '
                    f'face-down -> ILEGAL (6.9.1)')
                continue

        # 6.6.6a: Restricted Play — se a carta nao atende a
        # restricao, e considerada ilegal.
        nivel_restrito = game.combat.get_restricted_level(cid)
        # ── Equipamentos que elevam limite de Rage ──
        # Chainsaw (10), Shotgun (7), Rocket Launcher (12)
        eq_rage_limit = _equipamento_melhor_limite(card)
        if eq_rage_limit > 0:
            nivel_restrito = eq_rage_limit  # Equipamento define o limite
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

        # ── Cartas que NAO PODEM ser blefadas (6.9.1) ──
        # Verifica a carta de combate usada (regra 6.4).
        carta_usada = game.combat.played_combat_cards.get(cid)
        if carta_usada and _carta_nao_pode_blefar(carta_usada):
            game.combat.illegal_cards.add(cid)
            game.add_log(
                f'  [Bluff] {carta_usada.name} nao pode ser '
                f'blefada (regra 6.9.1) -> ILEGAL')
            continue

    # Descartar ilegais ANTES de verificar blefes (6.9.1 ordem)
    for cid in list(game.combat.illegal_cards):
        if cid in game.combat.declarations:
            del game.combat.declarations[cid]
        game.combat.targets.pop(cid, None)
        card = _find_card(game, cid)
        game.add_log(f'  [Bluff] {(card.name if card else cid)}: '
                     f'carta ilegal descartada (6.9.1)')
        # Move a carta de combate usada para o descarte do dono
        carta_combate = game.combat.played_combat_cards.pop(cid, None)
        if carta_combate:
            dono = _find_owner(game, carta_combate)
            if dono:
                for lista in (dono.hand, dono.combat_hand,
                              dono.pack_home, dono.umbra,
                              dono.hunting_grounds, dono.discard_combat,
                              dono.discard_sept, dono.victory_pile,
                              dono.out_of_play):
                    if carta_combate in lista:
                        lista.remove(carta_combate)
                        break
                carta_combate.zone = Zone.DISCARD_COMBAT
                dono.discard_combat.append(carta_combate)

    # ── Pack Combat (6.5.8): processa pack_attack/puxa_pack APOS
    # descartar ilegais, para que cartas ilegais nao ativem efeitos ──
    _process_pack_combat(game)

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

    # ── Mover cartas de combate usadas para o descarte correto ──
    # Cartas ilegais e blefes falhos sao descartadas para o
    # combat discard do JOGADOR que controlava a carta.
    todas_removidas = (list(game.combat.illegal_cards)
                       + list(game.combat.bluff_failed))
    for cid in todas_removidas:
        carta_combate = game.combat.played_combat_cards.pop(cid, None)
        if carta_combate is None:
            continue
        # Encontra o dono da carta de combate
        dono = _find_owner(game, carta_combate)
        if dono:
            # Garante que a carta nao esta em nenhuma zona ativa
            for lista in (dono.hand, dono.combat_hand,
                          dono.pack_home, dono.umbra,
                          dono.hunting_grounds, dono.discard_combat,
                          dono.discard_sept, dono.victory_pile,
                          dono.out_of_play):
                if carta_combate in lista:
                    lista.remove(carta_combate)
                    break
            # Move para o descarte de combate do dono
            carta_combate.zone = Zone.DISCARD_COMBAT
            dono.discard_combat.append(carta_combate)
            nome = getattr(carta_combate, 'name', '?')
            game.add_log(f'  [Bluff] {nome} descartada '
                         f'(dono: {dono.name})')

    return True


ACOES_OFENSIVAS = {
    'head_butt', 'tail_lash', 'anatomy_lesson',
    'savage_beatdown', 'submission_hold',
    'careful_strike', 'fast_strike', 'planned_strike',
    'stunning_strike', 'aggressive_bite', 'spirited_strike',
    'body_slam', 'lucky_blow', 'off_balanced', 'overextended',
    'reckless_swing', 'sap_spirit', 'stinging_wound',
    'surprise_attack', 'blood_atami', 'mitey_bitey',
    'evade_and_strike', 'block_and_strike',
    'forceful_wind', 'bum_rush', 'attacking_the_wyrm',
    'block_and_roll',
}


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

        acao_origem = game.combat.declarations.get(origem_id, '')
        acao_alvo = game.combat.declarations.get(alvo_id, '')

        # Origem precisa acao ofensiva
        # Acoes virtuais de dano (dano_<uid>) sao sempre ofensivas
        if acao_origem not in ACOES_OFENSIVAS and not acao_origem.startswith('dano_'):
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

        # Dodge universal: criatura com modifier 'dodge_all_next_round'
        # (ex: Backbite: 'The Gift user dodges all attacks in the next round')
        if _tem_modifier(game, id(alvo_card), 'dodge_all_next_round'):
            if is_unblockable:
                game.add_log(f'  {alvo_card.name} tentou esquivar de '
                             f'{origem_card.name}, mas o ataque e unblockable!')
            else:
                game.add_log(f'  {alvo_card.name} esquivou de todos ataques '
                             f'(dodge_all_next_round)')
                return  # Dodge universal: sem dano

        # Alvo pode bloquear/esquivar (a menos que seja unblockable)
        bloqueou_ou_esquivou = False
        reducao_block = 0
        if acao_alvo in ('block', 'dodge') and not is_unblockable:
            if acao_alvo == 'dodge' and pode_esquivar:
                # Dodge: dano totalmente evitado
                game.add_log(f'  {alvo_card.name} esquivou do ataque de '
                             f'{origem_card.name}')
                return  # Dodge: sem dano
            elif acao_alvo == 'block':
                # Block: reduz dano pela Rage do defensor
                reducao_block = alvo_card.effective_rage
                game.add_log(
                    f'  {alvo_card.name} bloqueou o ataque de '
                    f'{origem_card.name} (reducao: {reducao_block})'
                )
                bloqueou_ou_esquivou = True

        if is_unblockable and acao_alvo in ('block', 'dodge'):
            game.add_log(
                f'  {alvo_card.name} tentou {acao_alvo}, mas '
                f'{acao_origem} e unblockable!'
            )

        # War Knife (716): dano agravado se Rage <= 4 (apenas se ativo)
        war_knife_aggravated = False
        for eq in _get_active_equipment(origem_card):
            if eq.card_id == 716:  # War Knife of Benning Simon
                if origem_card.effective_rage <= 4:
                    war_knife_aggravated = True
                    game.add_log(
                        f'  War Knife: dano agravado '
                        f'({origem_card.name} Rage {origem_card.effective_rage} <= 4)')
                break

        # Grand Klaive (306): dano agravado (Weapon, apenas se ativo)
        for eq in _get_active_equipment(origem_card):
            if eq.card_id == 306:  # Grand Klaive
                war_knife_aggravated = True
                game.add_log(
                    f'  Grand Klaive: dano agravado '
                    f'({origem_card.name})')
                break

        # Skin of the Hellbound (697): imune a dano de Rage 6+ (apenas se ativo)
        skin_blocks = False
        for eq in _get_active_equipment(alvo_card):
            if eq.card_id == 697:  # Skin of the Hellbound
                if origem_card.effective_rage >= 6:
                    skin_blocks = True
                    game.add_log(
                        f'  Skin of the Hellbound: {alvo_card.name} '
                        f'imune a dano de Rage {origem_card.effective_rage} '
                        f'({origem_card.name})')
                break

        # Hogling (496): imune a equipamentos nao-fetiche
        # Verifica se o alvo tem a restricao de Hogling
        hogling_blocks = 'imune_equipamento_nao_fetich' in getattr(
            alvo_card, 'restricoes', [])
        if hogling_blocks:
            # Verifica se o atacante tem equipamento Weapon nao-Fetish ativo
            atacante_tem_weapon_nao_fetish = False
            for eq in _get_active_equipment(origem_card):
                keywords = (getattr(eq, 'keywords', '') or '').lower()
                tipo = (getattr(eq, 'card_type', '') or '').lower()
                if 'weapon' in keywords or 'weapon' in tipo:
                    if 'fetish' not in tipo and 'fetish' not in keywords:
                        atacante_tem_weapon_nao_fetish = True
                        break
            if atacante_tem_weapon_nao_fetish:
                hogling_blocks = True
                game.add_log(
                    f'  Hogling: {alvo_card.name} imune a dano de '
                    f'{origem_card.name} (equipamento nao-fetiche)')
            else:
                hogling_blocks = False
        else:
            hogling_blocks = False

        # Patagia (1016): so pode ser atingido por Weapon Equipment
        # Verifica se o alvo tem restricao 'patagia_active'
        patagia_blocks = 'patagia_active' in getattr(alvo_card, 'restricoes', [])
        if patagia_blocks:
            # Verifica se o atacante tem algum Weapon Equipment ativo
            atacante_tem_weapon = False
            for eq in _get_active_equipment(origem_card):
                kw = (getattr(eq, 'keywords', '') or '').lower()
                ct = (getattr(eq, 'card_type', '') or '').lower()
                if 'weapon' in kw or 'weapon' in ct:
                    atacante_tem_weapon = True
                    break
            if not atacante_tem_weapon:
                patagia_blocks = True
                game.add_log(
                    f'  Patagia: {alvo_card.name} imune a dano de '
                    f'{origem_card.name} (sem Weapon Equipment)')
            else:
                patagia_blocks = False

        # Aplica dano e cria damage card (regra 6.4)
        # Calcula dano base: primeiro da acao, depois Rage da criatura
        if skin_blocks or hogling_blocks or patagia_blocks:
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

            # Grand Klaive (306): +1 Rage em Crinos (so se ativo)
            if origem_card.is_crinos:
                for eq in _get_active_equipment(origem_card):
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

        # Ironjaw (369): +1 dano se nem ela nem alvo tem arma (considerando apenas equipamentos ativos)
        if 'ironjaw_bonus' in origem_card.restricoes:
            tem_arma_origem = any(
                'weapon' in (eq.keywords or '').lower()
                for eq in _get_active_equipment(origem_card))
            tem_arma_alvo = any(
                'weapon' in (eq.keywords or '').lower()
                for eq in _get_active_equipment(alvo_card))
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

        # ── Usa a carta de combate original se disponivel (regra 6.4) ──
        # Se uma Combat Action real foi jogada (ex: Surprise Attack),
        # a carta original e anexada ao alvo em vez de criar uma copia.
        carta_combate = game.combat.played_combat_cards.get(origem_id)
        if carta_combate is not None:
            # Usa a carta original como damage card
            carta_combate.damage = str(dano)
            carta_combate.is_aggravated = (war_knife_aggravated
                                            or trinity_aggravated)
            carta_combate.owner_id = dono_dono
            carta_combate.zone = Zone.OUT_OF_PLAY
            alvo_card.damage_cards.append(carta_combate)
            alvo_card.sync_health()
            del game.combat.played_combat_cards[origem_id]
            game.add_log(
                f'  {origem_card.name} usou {carta_combate.name} '
                f'causando {dano} de dano a {alvo_card.name} '
                f'({alvo_card.health_current}/{alvo_card.health})')
        else:
            # Sem Combat Action real — a declaracao nao causa dano.
            # Acoes sinteticas (strike, claw, etc) foram removidas.
            game.add_log(
                f'  {origem_card.name} nao tinha carta de combate: '
                f'sem dano a {alvo_card.name}')
            return  # Nao aplica dano

        # ── Equipamentos descartados apos uso: Chainsaw (Rg>=6), Rocket Launcher (1 uso) ──
        if dano > 0:
            for eq in _get_active_equipment(origem_card):
                eq_slug = getattr(eq, 'modelo_id', '') or ''
                if eq_slug == 'chainsaw':
                    # Descobre o Rage requirement da Combat Action usada
                    rage_req = 0
                    if acao_origem.startswith('dano_'):
                        dano_info = game.combat.dano_actions.get(
                            acao_origem, {})
                        rage_req = dano_info.get('rage_requirement', 0) or 0
                    else:
                        props = COMBAT_ACTION_PROPS.get(acao_origem, {})
                        rage_req = props.get('rage_requirement', 0) or 0
                    if rage_req >= 6:
                        # Descarta Chainsaw
                        if eq in origem_card.attached_equipment:
                            origem_card.attached_equipment.remove(eq)
                        eq.zone = Zone.DISCARD_SEPT
                        dono_origem.discard_sept.append(eq)
                        game.add_log(
                            f'  Chainsaw descartada! {origem_card.name} '
                            f'usou Combat Action de Rage {rage_req} '
                            f'(>=6)')
                elif eq_slug == 'rocket-launcher':
                    # Rocket Launcher: descarta apos 1 uso
                    if eq in origem_card.attached_equipment:
                        origem_card.attached_equipment.remove(eq)
                    eq.zone = Zone.DISCARD_SEPT
                    dono_origem.discard_sept.append(eq)
                    game.add_log(
                        f'  Rocket Launcher descartada! '
                        f'{origem_card.name} usou em combate')

        # Flip para Crinos: verifica threshold a cada dano aplicado
        # (regra: dano acumulado >= min(rage, health) da forma breed)
        if dano > 0:
            _flipar_para_crinos(game, alvo_card)

        # Retirada do combate (Anatomy Lesson: criatura ferida deve retirar)
        # Nao retira se a criatura ja morreu (health_current <= 0)
        if (retira_se_ferido and alvo_card.health_current < alvo_card.health
                and alvo_card.health_current > 0):
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
                    alvo_card.damage_cards.clear()
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
        """Retorna IDs das criaturas mortas (health_current <= 0).

        So considera cartas com health > 0 (criaturas, aliados).
        Cartas sem vida (Caern, Gift, Equipment, Event) tem
        health=0 e nao sao consideradas 'mortas'.
        """
        dead = set()
        for p in game.players:
            for zone_list in (p.pack_home, p.hunting_grounds, p.umbra):
                for c in zone_list:
                    if c.health > 0 and c.health_current <= 0:
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
            acao_a = game.combat.declarations.get(a_id, '')
            props_a = COMBAT_ACTION_PROPS.get(acao_a, {})
            # Velocidade: acoes normais de COMBAT_ACTION_PROPS
            # ou acoes virtuais (dano_<uid>) de dano_actions
            if acao_a.startswith('dano_'):
                dano_info = game.combat.dano_actions.get(acao_a, {})
                acao_speed = dano_info.get('speed', 'normal')
            else:
                acao_speed = props_a.get('speed', 'normal')
            if acao_speed != velocidade:
                continue
            if acao_a not in ACOES_OFENSIVAS and not acao_a.startswith('dano_'):
                continue
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
            acao_d = game.combat.declarations.get(d_id, '')
            props_d = COMBAT_ACTION_PROPS.get(acao_d, {})
            # Velocidade: acoes normais de COMBAT_ACTION_PROPS
            # ou acoes virtuais (dano_<uid>) de dano_actions
            if acao_d.startswith('dano_'):
                dano_info = game.combat.dano_actions.get(acao_d, {})
                acao_speed = dano_info.get('speed', 'normal')
            else:
                acao_speed = props_d.get('speed', 'normal')
            if acao_speed != velocidade:
                continue
            if acao_d not in ACOES_OFENSIVAS and not acao_d.startswith('dano_'):
                continue
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

        # ── Parting Shots (6.10.4): processa flee/step_sideways ──
        # Regra: "A creature using a Combat Action that removes it from
        #  combat (or makes it step sideways) is still affected by
        #  Combat Actions targeting him that resolve at the same time."
        # A remocao so acontece DEPOIS que todos os ataques e
        # contra-ataques desta velocidade ja resolveram, garantindo
        # que a criatura ainda sofre dano antes de fugir.
        _processar_flee_e_step_sideways(game, velocidade)

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

    # ── Pack Combat cleanup (6.5.8): remove combatentes adicionados via pack ──
    removidos = 0
    for cid in list(game.combat.pack_added_attackers):
        if cid in game.combat.attackers:
            game.combat.attackers.remove(cid)
            removidos += 1
    for cid in list(game.combat.pack_added_defenders):
        if cid in game.combat.defenders:
            game.combat.defenders.remove(cid)
            removidos += 1
    game.combat.pack_added_attackers.clear()
    game.combat.pack_added_defenders.clear()
    if removidos:
        game.add_log(
            f'  [Pack Combat] {removidos} combatente(s) extra(s) '
            f'retornaram ao pack')

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

    Metis tem forma breed = Crinos (regra A1.4), entao nao
    sao revertidos (health_morph == health).
    """
    for p in game.players:
        for c in p.pack_home + p.hunting_grounds + p.umbra:
            if not c.is_crinos:
                continue
            if c.health_morph == c.health:
                # Metis: breed = Crinos, nao precisa reverter
                continue
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

    # Limpa tracking de pack combat
    game.combat.pack_added_attackers.clear()
    game.combat.pack_added_defenders.clear()

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

    # ── Devolve criaturas recrutadas temporariamente (Allies Below) ──
    for p in game.players:
        devolvidas = []
        for c in list(p.pack_home):
            if 'recrutado_temporario' in c.restricoes:
                c.restricoes.remove('recrutado_temporario')
                c.zone = Zone.HUNTING_GROUNDS
                p.hunting_grounds.append(c)
                devolvidas.append(c)
                game.add_log(
                    f'  {c.name} retornou ao Hunting Grounds '
                    f'(fim do recrutamento temporario)')
        # Remove do pack_home apos iteracao
        for c in devolvidas:
            if c in p.pack_home:
                p.pack_home.remove(c)

    # Limpa modificadores de dodge universal (Backbite: 'dodges all attacks')
    game.game_modifiers = [
        m for m in game.game_modifiers
        if m.modifier != 'dodge_all_next_round'
    ]

    game.combat = CombatState()
    # Reset has_passed para todos (jogadores podem ter passado
    # durante o combate como defensores, e precisam de nova chance
    # para agir na fase de combate apos o encerramento - regra 6.3)
    for p in game.players:
        p.reset_pass()
    game.add_log('--- Fim do combate ---')
    return True


def _check_tzinzie_trigger(game: GameState):
    """Verifica se algum jogador tem Tzinzie (1348) ativo no combate.

    Tzinzie: Personal Totem. No inicio do combate, o dono pode nomear
    uma Combat Action. Quando oponente revela essa acao, descarta
    uma carta aleatoria da mao de combate.

    Regra (4.5.2B): Personal Totem so beneficia o Character ao qual
    esta anexado. So ativa se o Character com Tzinzie estiver em combate.
    """
    for p in game.players:
        # Procura Tzinzie anexado a um Character em combate
        for totem_uid, character in list(p.personal_totems.items()):
            totem_card = None
            # Encontra a carta Tzinzie (pelo uid guardado)
            for c in p.pack_home + p.hunting_grounds:
                if id(c) == totem_uid:
                    totem_card = c
                    break
            if totem_card and totem_card.card_id == 1348:
                # Verifica se o Character esta em combate
                combatentes = set()
                if game.combat:
                    combatentes = set(
                        game.combat.attackers + game.combat.defenders
                    )
                char_id = str(id(character))
                if char_id in combatentes:
                    game.combat_triggers[1348] = {
                        'named_action': 'strike',
                        'owner_id': p.id,
                        'card_uid': totem_uid,
                        'character_id': char_id,
                    }
                    game.add_log(
                        f'{character.name} nomeou strike (Tzinzie)')
                    return


def _check_hyenas_escape(game: GameState):
    """Clan of Hyenas (96): foge do combate se tomou >=3 dano neste round.

    Verifica todos os combatentes. Se um deles e o Clan of Hyenas
    e tem >=3 de dano total, remove-o do combate e devolve ao pack home.
    """
    from rage_web.game_engine.combat_queue import get_combatants
    combatentes = get_combatants(game)
    for cid in combatentes:
        carta = _find_card(game, cid)
        if not carta or carta.card_id != 96:
            continue
        dano_total = carta.total_dano
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

    \"Opponents facing your pack lose either 2 Gnosis or 2 Rage for
     the duration of the combat (caern holder chooses which).\"""

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
    """Sky River Caern (slug='sky-river-caern'): nao-alfas imunes
    a challenge/sneak attack.

    Se o defensor tem Sky River Caern, verifica se o atacante
    esta atacando um nao-alfa. Se sim, bloqueia o ataque.
    """
    if not game.has_modifier('sky_river_caern'):
        return

    # Encontra packs que tem Sky River Caern
    packs_protegidos = set()
    for p in game.players:
        for mod in game.game_modifiers:
            if mod.modifier == 'sky_river_caern':
                # Verifica todas as zonas (pack_home, HG, umbra)
                for c in p.pack_home + p.hunting_grounds + p.umbra:
                    if id(c) == mod.card_uid:
                        packs_protegidos.add(p.id)
                        break

    if not packs_protegidos:
        return

    # Alpha oficial do combate (selecionado no Moot)
    alphas_combate = game.combat.alphas  # {player_id: card_id_str}

    # Verifica se algum defensor esta em pack protegido e nao e o Alpha
    for dfd_id in list(game.combat.defenders):
        dfd = _find_card(game, dfd_id)
        if not dfd:
            continue
        # Pula Presa no Hunting Grounds (nao sao membros do pack, 4.4.2)
        if dfd.zone == Zone.HUNTING_GROUNDS:
            continue
        if dfd.owner_id not in packs_protegidos:
            continue

        # Determina se o defensor e o alpha oficial deste jogador
        alpha_card_id = alphas_combate.get(dfd.owner_id)
        if alpha_card_id and str(dfd.card_id) == alpha_card_id:
            continue  # E o alpha — ataque permitido

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
    alvo.damage_cards.clear()
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
