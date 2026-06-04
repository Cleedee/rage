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
        if not c.is_tapped and c.rage >= custo:
            return c
    return None
