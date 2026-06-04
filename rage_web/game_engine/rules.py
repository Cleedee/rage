"""Constantes e regras básicas do Rage CCG."""

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
    'gather',       # Comprar cartas
    'action',       # Acoes principais
    'combat',       # Combate
    'discard',      # Descarte
]

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
