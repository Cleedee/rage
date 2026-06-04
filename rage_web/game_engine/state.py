"""Estado do jogo: partida, jogadores, criaturas em jogo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Zone(Enum):
    """Zonas do jogo onde uma carta pode estar."""
    DECK_COMBAT = 'deck_combat'
    DECK_SEPT = 'deck_sept'
    HAND = 'hand'
    PACK_HOME = 'pack_home'
    HUNTING_GROUNDS = 'hunting_grounds'
    UMBRA = 'umbra'
    DISCARD_COMBAT = 'discard_combat'
    DISCARD_SEPT = 'discard_sept'
    VICTORY_PILE = 'victory_pile'
    OUT_OF_PLAY = 'out_of_play'
    REMOVED = 'removed'


@dataclass
class CardInstance:
    """Uma carta especifica em jogo (com ID unico)."""
    card_id: int              # ID da carta no banco
    name: str
    card_type: str            # Character, Gift, Equipment, etc.
    zone: Zone
    owner_id: str             # ID do jogador dono
    controller_id: str        # ID do jogador que controla

    # Atributos (copiados do banco no inicio)
    rage: int = 0
    gnosis: int = 0
    health: int = 0
    health_current: int = 0
    renown: int = 0
    damage: str = ''
    requires: str = ''
    text: str = ''
    keywords: str = ''
    is_tapped: bool = False
    is_face_down: bool = False
    modifiers: dict = field(default_factory=dict)
    modelo_id: Optional[str] = None  # ID do modelo de efeitos (effects.py)


@dataclass
class PlayerState:
    """Estado de um jogador na partida."""
    id: str
    name: str

    # Zonas
    deck_combat: list[CardInstance] = field(default_factory=list)
    deck_sept: list[CardInstance] = field(default_factory=list)
    hand: list[CardInstance] = field(default_factory=list)
    pack_home: list[CardInstance] = field(default_factory=list)
    hunting_grounds: list[CardInstance] = field(default_factory=list)
    umbra: list[CardInstance] = field(default_factory=list)
    discard_combat: list[CardInstance] = field(default_factory=list)
    discard_sept: list[CardInstance] = field(default_factory=list)
    victory_pile: list[CardInstance] = field(default_factory=list)

    # Atributos do jogador
    rage_pool: int = 0
    gnosis_pool: int = 0
    victory_points: int = 0
    renown_level: int = 20
    has_passed: bool = False
    hand_size_sept: int = 5
    hand_size_combat: int = 5

    # Flag: primeiro turno (redraw inicial e especial)
    is_first_turn: bool = True

    # Cartas em combate neste turno
    combatants: list[CardInstance] = field(default_factory=list)

    @property
    def total_cards_in_play(self) -> int:
        """Cartas que o jogador tem em jogo (pack home + hunting grounds + umbra)."""
        return (len(self.pack_home) + len(self.hunting_grounds)
                + len(self.umbra))

    def draw_combat(self, count: int = 1) -> list[CardInstance]:
        """Compra cartas do deck de combate."""
        drawn = []
        for _ in range(count):
            if self.deck_combat:
                card = self.deck_combat.pop(0)
                card.zone = Zone.HAND
                self.hand.append(card)
                drawn.append(card)
        return drawn

    def draw_sept(self, count: int = 1) -> list[CardInstance]:
        """Compra cartas do deck de sept."""
        drawn = []
        for _ in range(count):
            if self.deck_sept:
                card = self.deck_sept.pop(0)
                card.zone = Zone.HAND
                self.hand.append(card)
                drawn.append(card)
        return drawn

    def redraw_sept(self) -> list[CardInstance]:
        """Redraw de sept: compra cartas ate encher a mao de sept.

        Regra (2.2.2):
        - Primeiro turno: compra mao inicial de sept
        - Turnos seguintes: descarte (externo) + compra ate encher

        O descarte e opcional e feito pelo jogador/bot ANTES
        de chamar este metodo.

        Returns:
            Lista de cartas compradas.
        """
        # Conta cartas que NAO sao de combate (sept cards)
        sept_cards = [c for c in self.hand if c.card_type not in
                      ('Combat Action', 'Combat Event', '')]
        current = len(sept_cards)
        if current < self.hand_size_sept:
            qtd = self.hand_size_sept - current
            return self.draw_sept(qtd)
        return []

    def redraw_combat(self) -> list[CardInstance]:
        """Redraw de combate (inicio do Combat phase).

        Regra (2.2.6):
        - Pode descartar qualquer carta de combate da mao
        - DEPOIS compra ate encher a mao de combate

        O descarte e opcional e feito pelo jogador/bot ANTES
        de chamar este metodo.

        Returns:
            Lista de cartas compradas.
        """
        # Conta cartas de combate na mao
        combat_cards = [c for c in self.hand if c.card_type in
                        ('Combat Action', 'Combat Event')]
        current = len(combat_cards)
        if current < self.hand_size_combat:
            qtd = self.hand_size_combat - current
            return self.draw_combat(qtd)
        return []

    def regeneration(self) -> list[str]:
        """Fase de Regeneration: cura dano nao-agravado.

        Regra (2.2.2):
        - Personagens curam o menor dano nao-agravado
        - So curam 1 carta de dano por turno

        Returns:
            Lista de logs.
        """
        logs = []
        for c in self.pack_home:
            if c.health_current < c.health:
                # Cura 1 de dano (simplificado: sem dano agravado)
                c.health_current = min(c.health_current + 1, c.health)
                logs.append(f'{c.name} regenerou 1 de vida')
        return logs

    def pagar_custo_rage(self, custo: int) -> Optional[str]:
        """Paga um custo de Rage tappando um personagem."""
        from rage_web.game_engine.rules import encontrar_pagador_rage
        pagador = encontrar_pagador_rage(self, custo)
        if pagador:
            pagador.is_tapped = True
            return pagador.name
        return None

    def pagar_custo_gnosis(self, custo: int) -> Optional[str]:
        """Paga um custo de Gnosis tappando um personagem.

        Regra (2.2.5):
        - Personagem com Gnosis >= custo e selecionado.
        - Tapped enquanto durar o efeito.

        Args:
            custo: Custo de Gnosis a pagar.

        Returns:
            Nome do personagem que pagou, ou None se nao pode pagar.
        """
        from rage_web.game_engine.rules import encontrar_pagador_gnosis
        pagador = encontrar_pagador_gnosis(self, custo)
        if pagador:
            pagador.is_tapped = True
            return pagador.name
        return None

    def pass_turn(self):
        """Marca que o jogador passou a vez."""
        self.has_passed = True

    def reset_pass(self):
        """Reseta o passe para o novo turno."""
        self.has_passed = False
        self.is_first_turn = False


@dataclass
class CombatState:
    """Estado atual do combate."""
    is_active: bool = False
    step: str = ''            # declare, reveal, resolve, end
    attackers: list[str] = field(default_factory=list)        # IDs dos atacantes
    defenders: list[str] = field(default_factory=list)        # IDs dos defensores
    declarations: dict[str, Optional[str]] = field(default_factory=dict)
    """card_id -> nome da acao declarada (None = nao declarou ainda)"""
    declaration_order: list[str] = field(default_factory=list)
    """Ordem de declaracao (ultimo = vantagem)"""

    @property
    def last_to_declare(self) -> Optional[str]:
        """Retorna o ID da criatura que declarou por ultimo, se houver."""
        if self.declaration_order:
            return self.declaration_order[-1]
        return None

    def declare(self, card_id: str, action: str) -> bool:
        """Declara uma acao de combate para uma criatura.

        Retorna True se a declaracao foi aceita.
        """
        if not self.is_active:
            return False
        if card_id in self.declarations:
            return False  # Ja declarou
        self.declarations[card_id] = action
        self.declaration_order.append(card_id)
        return True

    def all_declared(self, combatants: list[str]) -> bool:
        """True quando todas as criaturas envolvidas declararam."""
        return all(c in self.declarations for c in combatants)


@dataclass
class GameState:
    """Estado completo de uma partida."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    players: list[PlayerState] = field(default_factory=list)
    current_player_index: int = 0
    phase: str = 'redraw'     # redraw, regeneration, resource, umbra, moot, combat
    turn_number: int = 1
    combat: CombatState = field(default_factory=CombatState)
    log: list[str] = field(default_factory=list)

    # Hunting Grounds (cartas neutras)
    hunting_grounds_cards: list[CardInstance] = field(default_factory=list)

    # Sistema de anuncio de efeitos (Rage: anuncio -> resposta -> resolucao)
    anunciador: 'Anunciador' = None

    def __post_init__(self):
        from rage_web.game_engine.stack import Anunciador
        if self.anunciador is None:
            self.anunciador = Anunciador()

    @property
    def current_player(self) -> PlayerState:
        """Jogador ativo no momento."""
        return self.players[self.current_player_index]

    def next_player(self):
        """Passa para o proximo jogador."""
        self.current_player_index = (
            self.current_player_index + 1
        ) % len(self.players)

    def next_phase(self):
        """Avança para a proxima fase do turno.

        Sequencia oficial:
        1. redraw -> 2. regeneration -> 3. resource ->
        4. umbra -> 5. moot -> 6. combat -> (proximo turno) redraw
        """
        from rage_web.game_engine.rules import PHASES
        idx = PHASES.index(self.phase)
        if idx + 1 < len(PHASES):
            self.phase = PHASES[idx + 1]
            # Executa acoes automaticas na transicao
            if self.phase == 'regeneration':
                for p in self.players:
                    logs = p.regeneration()
                    for log in logs:
                        self.add_log(log)
            elif self.phase == 'combat':
                # Redraw de combate ao entrar no Combat phase
                for p in self.players:
                    drawn = p.redraw_combat()
                    if drawn:
                        self.add_log(f'{p.name} comprou {len(drawn)} carta(s) de combate')
                # Untap todas as criaturas
                for p in self.players:
                    for c in p.pack_home:
                        if c.is_tapped:
                            c.is_tapped = False
                            self.add_log(f'{c.name} destapped')
        else:
            # Fim do turno -> volta ao inicio
            self.phase = 'redraw'
            self.turn_number += 1
            self.current_player_index = 0
            for p in self.players:
                p.reset_pass()
            # Redraw de sept no inicio do turno
            for p in self.players:
                drawn = p.redraw_sept()
                if drawn:
                    self.add_log(f'{p.name} comprou {len(drawn)} carta(s) de sept')

    def add_log(self, message: str):
        """Adiciona entrada no log da partida."""
        entry = f'[T{self.turn_number} {self.phase.upper()}] {message}'
        self.log.append(entry)
