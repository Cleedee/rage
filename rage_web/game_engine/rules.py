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
    - Ambos os lados: Caern, Territory, Event

    Returns:
        'pack_home' | 'hunting_grounds'
    """
    if not tipo:
        return 'pack_home'
    t = tipo.lower().strip()
    if any(hg in t for hg in TIPOS_HUNTING_GROUNDS):
        return 'hunting_grounds'
    if t.startswith('character'):
        return 'pack_home'
    if t.startswith('ally'):
        return 'pack_home'
    return 'pack_home'


def _info_char(char: 'CardInstance') -> str:
    """Retorna o texto completo de um personagem para matching."""
    return f"{char.name or ''} {char.card_type or ''} {char.keywords or ''}".lower()


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
    for char in characters:
        char_text = _info_char(char)
        char_gnosis = char.gnosis

        # Verifica caso especial: 'Character in the Umbra'
        algum_umbra = any(
            'character in the umbra' in o.lower() for o in opcoes)
        if algum_umbra and char.zone == Zone.UMBRA:
            return True

        # Verifica caso especial: 'Character with Quest'
        algum_quest = any(
            'character with quest' in o.lower() for o in opcoes)
        if algum_quest and any(
            q for q in player.quests
            if q.target_card_uid == id(char)
        ):
            return True

        # Verifica opcoes normais
        if any(_opcao_matches_char(o, char_text, char_gnosis)
               for o in opcoes):
            return True

    return False


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
