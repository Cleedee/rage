"""Constantes e regras básicas do Rage CCG."""

from __future__ import annotations

from typing import Optional

# Atributos base
RAGE_MIN = 0
RAGE_MAX = 10
GNOSIS_MIN = 0
GNOSIS_MAX = 10
HEALTH_MIN = 1
HEALTH_MAX = 20
RENOWN_MIN = 0
RENOWN_MAX = 30

# Deck building
COMBAT_DECK_MIN = 20
COMBAT_CARD_MAX_COPIES = 2
SEPT_DECK_MIN = 30
SEPT_CARD_MAX_COPIES = 3

# Renown Level padrao
STANDARD_RENOWN_LEVEL = 20
VP_TO_WIN = 20

# Umbra / Gauntlet
GAUNTLET_DEFAULT = 6  # Dificuldade padrao do Gauntlet
# Tipos de criatura que podem stepping sideways (todas por padrao)
CLASSES_QUE_STEPPAM = {'werewolf', 'garou', 'bastet', 'uktena',
                       'fianna', 'stargazer', 'black fury', 'wendigo',
                       'silver fang', 'shadow lord', 'get of fenris',
                       'bone gnawer', 'child of gaia', 'red talon',
                       'ratkin', 'ananasi', 'nakea', 'corax', 'gurahl',
                       'kitsune', 'nagah', 'mokole',  # Shifters
                       'spirit', 'incarna', 'totem',  # Spirits
                       }

# Fases do turno
PHASES = [
    'redraw',       # 1. Redraw: comprar/descartar sept hand
    'regeneration', # 2. Regeneration: curar dano nao-agravado
    'resource',     # 3. Resource: jogar Aliados/Equipamentos/Territorios
    'umbra',        # 4. Umbra: passo lateral
    'moot',         # 5. Moot: reuniões/votações
    'combat',       # 6. Combat: redraw combat, alfas, combate
]

# Tamanhos de mao padrao
HAND_SIZE_SEPT = 5
HAND_SIZE_COMBAT = 5

# Etapas do combate
COMBAT_STEPS = [
    'select_alpha', # Escolher alfa (maior Renome age primeiro)
    'declare',      # Escolher acao face-down
    'reveal',       # Revelar + "Ultimo a Declarar" pode Feint
    'resolve',      # Aplicar danos e efeitos
    'end',          # Remover mortos, mends
]

# Tipos de carta no jogo
CARD_TYPES = {
    'character', 'gift', 'rite', 'equipment',
    'ally', 'enemy', 'victim', 'event',
    'moot', 'action', 'combat_action', 'combat_event',
    'battlefield', 'caern', 'territory', 'quest',
    'past_life', 'board_meeting',
}

# Zonas do jogo
ZONES = [
    'deck_combat',      # Deck de combate
    'deck_sept',        # Deck de sept
    'hand',             # Mao
    'pack_home',        # Pack Home Ground (personagens em jogo)
    'hunting_grounds',  # Hunting Grounds
    'umbra',            # Umbra
    'discard_combat',   # Cemiterio de combate
    'discard_sept',     # Cemiterio de sept
    'victory_pile',     # Pilha de Vitoria
    'out_of_play',      # Fora de jogo temporariamente
    'removed',          # Removido permanentemente
]


def parse_custo_rage(custo_str: str) -> int | None:
    """Converte o campo damage (custo Rage) para inteiro.

    Regra (2.2.4):
    - Damage e o custo de Rage para jogar uma Combat Action.
    - Se o valor for 'X', o custo e variavel (escolha do jogador).
    - Se vazio ou invalido, retorna None (sem custo).

    Returns:
        int: custo numerico, ou 0 se 'X', ou None se invalido.
    """
    if not custo_str or custo_str.strip() == '':
        return None
    custo = custo_str.strip()
    if custo.upper() == 'X':
        return 0  # Variavel, tratado como 0 para simplificar
    try:
        return int(custo)
    except ValueError:
        return None


def encontrar_pagador_rage(jogador: 'PlayerState', custo: int
                           ) -> Optional['CardInstance']:
    """Encontra um personagem no Pack Home que pode pagar o custo de Rage.

    Regra (2.2.4):
    - Para usar uma Combat Action com custo Rage N, um personagem
      com Rage >= N deve ser designado como pagador.
    - O personagem e TAPPED (nao pode agir novamente neste combate).

    Args:
        jogador: Estado do jogador.
        custo: Custo de Rage necessario.

    Returns:
        CardInstance do personagem pagador, ou None se nao houver.
    """
    for c in jogador.pack_home:
        if c.is_tapped or c.rage < custo:
            continue
        # Respeita restricoes: criatura com 'nao_jogar_rage_3+'
        # nao pode pagar por cartas com custo >= 3
        if custo >= 3 and 'nao_jogar_rage_3+' in c.restricoes:
            continue
        return c
    return None


def encontrar_pagador_gnosis(jogador: 'PlayerState', custo: int
                             ) -> Optional['CardInstance']:
    """Encontra um personagem no Pack Home que pode pagar o custo de Gnosis.

    Regra (2.2.5):
    - Para usar um Gift, Rito, Equipamento ou Aliado com custo Gnosis N,
      um personagem com Gnosis >= N deve ser designado como pagador.
    - O personagem e TAPPED (nao pode agir novamente neste combate).

    Args:
        jogador: Estado do jogador.
        custo: Custo de Gnosis necessario.

    Returns:
        CardInstance do personagem pagador, ou None se nao houver.
    """
    for c in jogador.pack_home:
        if not c.is_tapped and c.gnosis >= custo:
            return c
    return None


TIPOS_HUNTING_GROUNDS = {'enemy', 'victim', 'battlefield',
                          'ally - enemy', 'ally - victim',
                          'enemy - victim'}


def zona_da_carta(tipo: str) -> str:
    """Retorna a zona apropriada para uma carta baseado no tipo.

    Regra (1.2):
    - Pack Home Ground: Character, Ally, Caern, Equipment, Gift, Rite,
      Territory, Realm, Event, Moot, Board Meeting, Quest, Past Life
    - Hunting Grounds: Enemy, Victim, Battlefield
    - Combat Deck: Combat Action, Combat Event (usados e descartados)
    - Ambos os lados: Caern, Territory, Event

    Returns:
        'pack_home' | 'hunting_grounds' | 'discard_combat'
    """
    if not tipo:
        return 'pack_home'
    t = tipo.lower().strip()
    if 'combat_event' in t or 'combat action' in t or t in ('combat_event', 'combat_action'):
        return 'discard_combat'
    if any(hg in t for hg in TIPOS_HUNTING_GROUNDS):
        return 'hunting_grounds'
    if t.startswith('character'):
        return 'pack_home'
    if t.startswith('ally'):
        return 'pack_home'
    return 'pack_home'


def _info_char(char: 'CardInstance') -> str:
    """Retorna o texto completo de um personagem para matching.

    Inclui nome, card_type, keywords e text (para Prey cujo tipo
    de criatura e determinado pelo texto da carta).
    """
    return f"{char.name or ''} {char.card_type or ''} {char.keywords or ''} {char.text or ''}".lower()


def _extrair_gnosis_requisito(opcao: str) -> tuple:
    """Extrai requisito de Gnosis de uma opcao, se houver.

    Formato: '(Gnosis: 3) + Fianna'
    Retorna: (gnosis_min, restante_texto) ou (0, opcao)
    """
    opcao = opcao.strip()
    if opcao.startswith('(Gnosis:'):
        partes = opcao.split(')', 1)
        if len(partes) == 2:
            gnosis_part = partes[0].replace('(Gnosis:', '').strip()
            try:
                gnosis_min = int(gnosis_part)
                resto = partes[1].strip()
                if resto.startswith('+'):
                    resto = resto[1:].strip()
                return (gnosis_min, resto)
            except ValueError:
                pass
    return (0, opcao)


def _opcao_matches_char(opcao: str, char_text: str,
                         char_gnosis: int) -> bool:
    """Verifica se uma opcao de requisito corresponde a um personagem.

    Opcoes podem ser:
    - 'Any': sempre OK
    - 'Character in the Umbra': verifica zona
    - 'Character with Quest': verifica quests
    - '(Gnosis: N) + Keyword': Gnosis >= N AND keyword no texto
    - 'Keyword': simplesmente verifica se keyword aparece no texto
    """
    opt_lower = opcao.lower().strip()

    # Any: qualquer personagem serve
    if opt_lower.startswith('any'):
        # 'Any' sozinho ou 'Any Gaia Character' etc
        if opt_lower == 'any':
            return True
        # Remove 'any ' do inicio e verifica se o resto aparece no texto
        resto = opt_lower[4:].strip()  # Remove 'any '
        if resto and resto in char_text:
            return True
        return False

    # Character in the Umbra: verificado externamente
    if 'character in the umbra' in opt_lower:
        return 'umbra' in char_text  # Simplificado: zona #

    if 'character with quest' in opt_lower:
        return False  # Verificado externamente

    # Extrai requisito de Gnosis se houver
    gnosis_min, texto = _extrair_gnosis_requisito(opcao)
    if gnosis_min > 0 and char_gnosis < gnosis_min:
        return False

    # Verifica se o texto do requisito aparece nos dados do personagem
    if not texto:
        return True
    return texto.lower() in char_text


def pode_recrutar_ally(player: 'PlayerState',
                        ally_card: 'CardInstance') -> bool:
    """Verifica se o jogador pode recrutar um Ally.

    Regra (4.4.1): recrutar um Ally requer um Character que atenda
    aos requisitos do Ally (campo `requires`).

    O campo `requires` usa formato separado por " - " (OR).
    Cada opcao pode ser:
    - 'Any': qualquer personagem
    - '(Gnosis: N) + Keyword': requer Gnosis >= N + keyword
    - 'Keyword': personagem deve ter a keyword
    - 'Character in the Umbra': personagem na Umbra
    - 'Character with Quest': personagem com quest ativa

    Args:
        player: Estado do jogador.
        ally_card: A carta Ally a ser recrutada.

    Returns:
        True se o jogador pode recrutar o Ally.
    """
    requires = (ally_card.requires or '').strip()
    if not requires:
        return True  # Sem requisito = sempre OK

    # Coleta personagens do jogador
    from rage_web.game_engine.state import Zone
    characters = [c for c in player.pack_home
                  if 'Character' in (c.card_type or '')]
    if not characters:
        return False  # Precisa de pelo menos 1 Character

    # Requisitos sao separados por " - " (OR)
    opcoes = [p.strip() for p in requires.split(' - ')]

    # Para cada personagem, verifica se atende ALGUMA opcao
    from rage_web.game_engine.state import Zone
    for char in characters:
        char_text = _info_char(char)
        char_gnosis = char.gnosis
        if _char_atende_requisitos(char_text, char_gnosis, opcoes,
                                    player, char):
            return True

    return False


def _char_atende_requisitos(char_text: str, char_gnosis: int,
                              opcoes: list[str],
                              player: 'PlayerState' = None,
                              char: 'CardInstance' = None) -> bool:
    """Verifica se um personagem atende a lista de opcoes.

    Args:
        char_text: Texto completo do personagem (_info_char).
        char_gnosis: Gnosis atual do personagem.
        opcoes: Lista de opcoes separadas por " - " (OR).
        player: Estado do jogador (para casos especiais).
        char: CardInstance do personagem (para zona/quests).

    Returns:
        True se o personagem atende ALGUMA opcao.
    """
    if char is not None and player is not None:
        from rage_web.game_engine.state import Zone
        # Verifica caso especial: 'Character in the Umbra'
        if any('character in the umbra' in o.lower() for o in opcoes):
            if char.zone == Zone.UMBRA:
                return True
        # Verifica caso especial: 'Character with Quest'
        if any('character with quest' in o.lower() for o in opcoes):
            if any(q for q in player.quests
                   if q.target_card_uid == id(char)):
                return True

    return any(_opcao_matches_char(o, char_text, char_gnosis)
               for o in opcoes)


def pode_usar_gift(player: 'PlayerState',
                    gift_card: 'CardInstance') -> bool:
    """Verifica se o jogador pode usar um Gift.

    Regra (Rage FOO Rule + secao Gifts do Quickstart):
    Para usar um Gift, uma criatura deve:
    1. Ter Gnosis >= Gnosis do Gift (custo).
    2. Atender um dos requisitos de keyword do Gift.

    Args:
        player: Estado do jogador.
        gift_card: A carta Gift a ser usada.

    Returns:
        True se o jogador pode usar o Gift.
    """
    requires = (gift_card.requires or '').strip()

    # Coleta personagens do jogador
    characters = [c for c in player.pack_home
                  if 'Character' in (c.card_type or '')]
    # Allies tambem podem usar Gifts (Rage FOO Rule)
    for c in player.pack_home:
        if 'Ally' in (c.card_type or '') and c not in characters:
            characters.append(c)

    if not characters:
        return False

    if not requires:
        # Sem requisito de keyword: apenas check de Gnosis
        gnosis_req = gift_card.gnosis or 0
        return any(c.gnosis >= gnosis_req for c in characters)

    # Parseia requisitos (formato " - " = OR)
    opcoes = [p.strip() for p in requires.split(' - ')]

    from rage_web.game_engine.state import Zone
    for char in characters:
        char_text = _info_char(char)
        char_gnosis = char.gnosis

        # Verifica se o personagem atende ALGUMA opcao
        if not _char_atende_requisitos(char_text, char_gnosis, opcoes,
                                        player, char):
            continue

        # Verifica Gnosis
        if char.gnosis < (gift_card.gnosis or 0):
            continue

        # Se passou de tudo, pode usar
        return True

    return False


def pode_usar_gift_para_presa(prey_card: 'CardInstance',
                                gift_card: 'CardInstance') -> bool:
    """Verifica se uma Presa (Victim/Enemy) pode usar um Gift.

    Regra (Quickstart - Gifts + Prey):
    - Prey pode usar Gifts que correspondam ao seu tipo de criatura.
    - 'Anyone but the player fighting the Prey can pay Gifts for them'
    - Prey so pode usar Gifts durante combate.
    - O custo (Rage/Gnosis) e pago pelo jogador, nao pela Presa.

    Args:
        prey_card: A carta da Presa (Victim/Enemy).
        gift_card: A carta Gift a ser usada.

    Returns:
        True se a Presa pode usar o Gift.
    """
    requires = (gift_card.requires or '').strip()

    # Monta texto da presa para verificar requisitos
    prey_text = _info_char(prey_card)
    prey_gnosis = prey_card.gnosis or 0

    if not requires:
        # Sem requisito de keyword: qualquer criatura serve
        # (nao check de Gnosis - o jogador paga)
        return True

    # Parseia requisitos (formato " - " = OR)
    opcoes = [p.strip() for p in requires.split(' - ')]

    # Remove qualificadores de Gnosis da requisicao
    # (Gnosis so importa para o pagador, nao para a Presa)
    opcoes_sem_gnosis = []
    for op in opcoes:
        gnosis_min, texto = _extrair_gnosis_requisito(op)
        if texto:
            opcoes_sem_gnosis.append(texto)
        else:
            opcoes_sem_gnosis.append(op if not gnosis_min else '')

    # Verifica se a presa atende ALGUMA opcao (OR)
    from rage_web.game_engine.state import Zone
    for op_texto in opcoes_sem_gnosis:
        if not op_texto:
            continue
        op_lower = op_texto.lower().strip()
        if op_lower == 'any' or op_lower in prey_text:
            return True

    # Fallback: verifica as opcoes ORIGINAIS sem stripping de Gnosis
    return any(_opcao_matches_char(o, prey_text, prey_gnosis)
               for o in opcoes)


def validar_timing_gift(gift_card: 'CardInstance', game_phase: str) -> bool:
    """Valida se o Gift pode ser usado na fase atual do jogo.

    Regra: Gifts podem ser jogados a qualquer momento, a menos que
    o texto da carta especifique uma restricao de timing.

    Args:
        gift_card: A carta Gift.
        game_phase: Fase atual do jogo.

    Returns:
        True se pode ser usado na fase atual.
    """
    text = (gift_card.text or '').lower()
    em_combate = (game_phase == 'combat')

    # 'May not be used during combat' -> so fora de combate
    if 'may not be used during combat' in text or 'cannot be used during combat' in text:
        return not em_combate

    # 'Play at the beginning/start of combat' -> so em combate
    if ('play at the beginning of combat' in text
        or 'play at the start of combat' in text):
        return em_combate

    # 'Combat Restricted' -> so durante combate
    if 'combat restricted' in text:
        return em_combate

    # 'Play during the Withdrawal step' -> so durante combate
    if 'play during the withdrawal' in text:
        return em_combate

    # Sem restricao explicita: pode em qualquer fase
    return True


def validar_opponent_gift(gift_card: 'CardInstance', game_phase: str) -> bool:
    """Valida se Gift mencionando 'opponent' so pode ser usado em combate.

    Regra (Quickstart): 'Gifts that can only be used in combat will
    either say so, or say they are used on an "opponent". You only
    have an "opponent" during combat.'

    Args:
        gift_card: A carta Gift.
        game_phase: Fase atual do jogo.

    Returns:
        True se pode ser usado.
    """
    text = (gift_card.text or '').lower()
    em_combate = (game_phase == 'combat')

    # So verifica se menciona 'opponent'
    if 'opponent' not in text:
        return True

    # Se ja tem restricao explicita de timing, respeita ela
    if ('play at the beginning of combat' in text
        or 'play at the start of combat' in text):
        return em_combate
    if 'combat restricted' in text:
        return em_combate
    if ('may not be used during combat' in text
        or 'cannot be used during combat' in text):
        return not em_combate

    # Menciona opponent sem outra restricao explicita: so em combate
    if not em_combate:
        return False

    return True


def gift_eh_permanente(gift_card: 'CardInstance') -> bool:
    """Verifica se um Gift e permanente (permanece em jogo apos usar).

    Regra: Gifts que dizem 'permanent' no texto nao sao descartados
    apos o uso. Ficam em jogo como marcadores.

    Args:
        gift_card: A carta Gift.

    Returns:
        True se o Gift e permanente.
    """
    text = (gift_card.text or '').lower()
    return 'permanent' in text


def pode_usar_rite(player: 'PlayerState',
                    rite_card: 'CardInstance') -> bool:
    """Verifica se o jogador pode usar um Rito.

    Regra (Quickstart 4.5.5):
    1. So pode ser usado por Garou, Fera e Cultists.
    2. Requer Renown do personagem >= Renown listado no Rito.
    3. Nao pode ser usado durante combate.

    Args:
        player: Estado do jogador.
        rite_card: A carta Rite a ser usada.

    Returns:
        True se pode usar o Rito.
    """
    renown_requerido = rite_card.renown or 0
    requires = (rite_card.requires or '').strip()

    # Coleta personagens do jogador e aliados
    characters = [c for c in player.pack_home
                  if 'Character' in (c.card_type or '')]
    for c in player.pack_home:
        if 'Ally' in (c.card_type or '') and c not in characters:
            characters.append(c)

    if not characters:
        return False

    # 1. Verifica Renown minimo
    if renown_requerido > 0:
        renown_max = max(c.renown for c in characters)
        if renown_max < renown_requerido:
            return False

    # 2. Verifica criatura classe: Garou, Fera ou Cultist
    # Keywords que indicam capacidade de usar Rites
    CLASSES_RITE = {'garou', 'fera', 'cultist', 'bastet', 'corax',
                    'gnawer', 'mokole', 'nagas', 'ratkin', 'gurahl',
                    'kitsune', 'hengeyokai', 'ajaba', 'ananas', 'kamay'}
    tem_classe = any(
        (_info_char(c).find(classe) >= 0)
        for c in characters
        for classe in CLASSES_RITE
    )
    if not tem_classe:
        # Fallback: se tem keyword 'Garou' ou similar no texto
        tem_garou_keyword = any(
            'garou' in (c.keyword or '').lower()
            or 'fera' in (c.keyword or '').lower()
            for c in characters
        )
        if not tem_garou_keyword:
            return False

    # 3. Verifica requisito de keyword (requires) se presente
    if requires:
        opcoes = [p.strip() for p in requires.split(' - ')]
        for char in characters:
            char_text = _info_char(char)
            if _char_atende_requisitos(char_text, char.gnosis or 0,
                                        opcoes, player, char):
                return True
        # Se tem requisito e nenhum personagem atende: negado
        return False

    return True


def validar_timing_rite(rite_card: 'CardInstance', game_phase: str) -> bool:
    """Valida se o Rito pode ser usado na fase atual.

    Regra: Rites cannot be played during a combat.

    Args:
        rite_card: A carta Rite.
        game_phase: Fase atual do jogo.

    Returns:
        True se pode ser usado.
    """
    text = (rite_card.text or '').lower()
    em_combate = (game_phase == 'combat')

    # Nao pode durante combate
    if em_combate:
        return False

    # Verifica timing especifico da carta
    if 'play after' in text and 'killed' in text:
        # Exige que o personagem tenha matado algo (validacao solta)
        pass

    return True


LUNAR_PHASE_IDS = {834, 854, 865, 869, 884, 890, 897}

def definir_lunar_phase_ids():
    """Retorna o set de IDs de cartas de Fase Lunar."""
    return LUNAR_PHASE_IDS


def validar_lunar_phase(card_id: int, game_phase: str) -> bool:
    """Valida se uma Fase Lunar pode ser jogada na fase atual.

    Regra (Quickstart + 4.5.2.C):
    - Lunar Phases only at the beginning of a turn (Redraw phase)
    - Or to cancel/supersede previous one

    Args:
        card_id: ID da carta.
        game_phase: Fase atual do jogo.

    Returns:
        True se pode ser jogada.
    """
    if card_id not in LUNAR_PHASE_IDS:
        return False  # Nao e uma Lunar Phase

    # So pode jogar durante Redraw phase (inicio do turno)
    if game_phase == 'redraw':
        return True

    # Exception: se ja tem uma fase ativa, pode substituir
    # (implementado na logica do bot via game.lunar_phase)
    return False


def carta_eh_evento_permanente(card: 'CardInstance',
                                 em_jogo_only: bool = True) -> bool:
    """Verifica se uma carta e um Evento que nao pode ser descartado
    voluntariamente.

    Regra (Quickstart + 4.5):
    - Events affect both sides of the Gauntlet.
    - Cannot be discarded voluntarily from play.
    - Duration: Variable

    Args:
        card: A carta para verificar.
        em_jogo_only: Se True, so retorna True se a carta estiver
                      em jogo (nao na mao).

    Returns:
        True se e um Evento permanente.
    """
    if not card:
        return False
    from rage_web.game_engine.state import Zone


def pode_jogar_territory(player: 'PlayerState',
                          territory_card: 'CardInstance') -> bool:
    """Verifica se o jogador pode jogar um Territorio/Realm.

    Regras (Quickstart + 4.3.3):
    - Territories have keyword requirements (`requires` field).
    - Realms require a character in the Umbra.
    - Only 1 Realm per pack.

    Args:
        player: Estado do jogador.
        territory_card: A carta Territory/Realm.

    Returns:
        True se pode jogar.
    """
    requires = (territory_card.requires or '').strip()
    ct = (territory_card.card_type or '').lower()
    eh_realm = 'realm' in ct

    characters = [c for c in player.pack_home
                  if 'Character' in (c.card_type or '')]
    for c in player.pack_home:
        if 'Ally' in (c.card_type or '') and c not in characters:
            characters.append(c)

    if not characters:
        return False

    # 1. Verifica requisito de keyword (requires)
    if requires:
        opcoes = [p.strip() for p in requires.split(' - ')]
        tem_char = any(
            _char_atende_requisitos(
                _info_char(c), c.gnosis or 0, opcoes, player, c
            )
            for c in characters
        )
        if not tem_char:
            return False

    # 2. Realm: precisa personagem na Umbra
    if eh_realm:
        if not player.umbra:
            return False
        # So 1 Realm por pack
        for c in player.pack_home:
            ct2 = (c.card_type or '').lower()
            if 'realm' in ct2:
                return False

    return True
    if em_jogo_only:
        if card.zone not in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS,
                              Zone.UMBRA):
            return False
    ct = (card.card_type or '').lower()
    if 'event' in ct:
        return True
    # Totems sao Events, mas verifica explicitamente
    from rage_web.game_engine.rules import TOTEM_IDS
    if card.card_id in TOTEM_IDS:
        return True
    # Lunar Phases
    LUNAR_CARDS = {834, 854, 865, 869, 884, 890, 897}
    if card.card_id in LUNAR_CARDS:
        return True
    return False


def impedir_descarte_voluntario(cards: list['CardInstance']) -> list['CardInstance']:
    """Filtra uma lista de cartas removendo Events que nao podem
    ser descartados voluntariamente.

    Args:
        cards: Lista de cartas candidatas a descarte.

    Returns:
        Lista filtrada (so cartas descartaveis).
    """
    return [c for c in cards if not carta_eh_evento_permanente(c)]


# IDs de cartas Totem conhecidas
TOTEM_IDS = {214, 215, 817, 818, 821, 824, 826, 830, 836, 838,
             850, 852, 855, 867, 868, 872, 877, 880, 892, 895,
             897, 900, 909, 912, 914, 918, 920, 1633}


def validar_totem_evento(player: 'PlayerState',
                          event_card: 'CardInstance') -> bool:
    """Valida requisitos para jogar um Totem.

    Regra (Quickstart + 4.5.2A):
    - Pack Totems require a keyword on a Character to bring into play.
    - A pack may not have more than one Pack Totem at any time.
    - Personal Totems only affect the character playing them.

    Args:
        player: Estado do jogador.
        event_card: A carta Totem (Evento).

    Returns:
        True se pode jogar o Totem.
    """
    requires = (event_card.requires or '').strip()
    text = (event_card.text or '').lower()

    # Coleta personagens do jogador
    characters = [c for c in player.pack_home
                  if 'Character' in (c.card_type or '')]
    # Allies tambem podem usar (se tiverem requisito)
    for c in player.pack_home:
        if 'Ally' in (c.card_type or '') and c not in characters:
            characters.append(c)

    if not characters:
        return False

    # 1. Verifica requisito de keyword (requires field)
    if requires:
        opcoes = [p.strip() for p in requires.split(' - ')]
        tem_char = any(
            _char_atende_requisitos(
                _info_char(c), c.gnosis or 0, opcoes, player, c
            )
            for c in characters
        )
        if not tem_char:
            return False

    # 2. Verifica limite de 1 Pack Totem por pack
    # Personal Totems nao contam para o limite
    if 'personal totem' not in text:
        # Conta Totems ativos no pack
        totens_ativos = 0
        for c in player.pack_home + player.hunting_grounds:
            if c.card_id in TOTEM_IDS:
                # Verifica se nao e Personal Totem
                ct_text = (c.text or '').lower()
                if 'personal totem' not in ct_text:
                    totens_ativos += 1
        if totens_ativos >= 1:
            return False  # So 1 Pack Totem por pack

    return True


def encontrar_caern(jogador: 'PlayerState') -> Optional['CardInstance']:
    """Encontra um Caern no Pack Home ou Hunting Grounds do jogador.

    Regra (2.2.4):
    - Um pack pode ter apenas um Caern em jogo.
    - Caerns sao Unique.
    - Caern existe em ambos os lados do Gauntlet.
    - Pode ser usado por todos os membros do pack.

    Returns:
        CardInstance do Caern, ou None se nao houver.
    """
    for c in jogador.pack_home:
        if c.card_type == 'Caern':
            return c
    # Tambem pode estar no Hunting Grounds
    for c in jogador.hunting_grounds:
        if c.card_type == 'Caern':
            return c
    return None


def _simplificar_req_caern(req: str) -> str:
    """Simplifica um requisito de Caern para busca.

    Trata plural/singular e prefixos como 'Any'.
    Ex: 'Bone Gnawers' -> 'bone gnawer'
        'Any Wyrm character' -> 'wyrm'
        'Fianna - Uktena' -> 'fianna' ou 'uktena'
        '(Ship)' -> 'ship'
    """
    texto = req.lower().strip()

    # Remove parenteses
    if texto.startswith('(') and texto.endswith(')'):
        texto = texto[1:-1].strip()

    # Remove prefixo 'any '
    if texto.startswith('any '):
        # Remove 'any' e pega primeira palavra chave
        words = texto[4:].strip().split()
        if words:
            return words[0]

    # Remove sufixos comuns
    words = texto.split()
    if words and words[-1] in ('character', 'form', 'creature'):
        words = words[:-1]
    if words:
        texto = ' '.join(words)

    # Remove 's' final para tratar plural
    if texto.endswith('s') and not texto.endswith('ss'):
        texto = texto[:-1]

    return texto


def pode_jogar_caern(play: 'PlayerState',
                      caern_card: 'CardInstance') -> bool:
    """Verifica se o jogador pode jogar um Caern.

    Regras:
    - Apenas um Caern por pack.
    - Requer personagem que atenda o requisito (requires).
    - Caern pode ser descartado se quiser trocar.

    Returns:
        True se pode jogar.
    """
    # 1. So pode ter um Caern (ignora o proprio card sendo checado)
    for c in play.pack_home + play.hunting_grounds:
        if c.card_type == 'Caern' and id(c) != id(caern_card):
            return False

    # 2. Verifica requisito de personagem
    req = (caern_card.requires or '').strip()
    if not req:
        return True  # Sem requisito, pode jogar

    # Split por ' - ' para opcoes OR
    # Mas cuidado: requisitos complexos como 'Black Fury - Silent Strider - Bubasti'
    # sao opcoes mutuamente exclusivas, ou seja, BASTA UM
    opcoes = [p.strip() for p in req.split(' - ')]

    for char in play.pack_home:
        char_text = f'{char.name} {char.card_type} {char.keywords}'.lower()
        for opcao in opcoes:
            req_simplificado = _simplificar_req_caern(opcao)
            if req_simplificado and req_simplificado in char_text:
                return True

    return False


def pode_step_sideways(personagem: 'CardInstance',
                       caern: Optional['CardInstance'] = None,
                       gauntlet: int = GAUNTLET_DEFAULT) -> bool:
    """Verifica se um personagem pode stepping sideways.

    Regra (2.2.4):
    - Precisa ser um Character.
    - Sua Creature Class pode stepping sideways.
    - Gnosis >= Gauntlet do Caern.

    Args:
        personagem: O personagem a verificar.
        caern: O Caern usado (opcional, usa padrao se None).
        gauntlet: Rating do Gauntlet (padrao 6 se nao houver Caern).

    Returns:
        True se o personagem pode stepping sideways.
    """
    if 'Character' not in (personagem.card_type or ''):
        return False
    # Verifica Gnosis
    gnosis_req = gauntlet
    if personagem.gnosis < gnosis_req:
        return False
    # Verifica Creature Class (keywords)
    kw = (personagem.keywords or '').lower()
    if kw and not any(c in kw for c in CLASSES_QUE_STEPPAM):
        return False
    return True
