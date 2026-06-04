"""Estado do jogo: partida, jogadores, criaturas em jogo."""

from __future__ import annotations

import random
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
    damage_aggravated: int = 0  # Quanto do dano e agravado (nao regenera)


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

    def _cartas_sept(self) -> list[CardInstance]:
        """Retorna cartas de sept na mao (nao-combate)."""
        return [c for c in self.hand if c.card_type not in
                ('Combat Action', 'Combat Event', '')]

    def _cartas_combate(self) -> list[CardInstance]:
        """Retorna cartas de combate na mao."""
        return [c for c in self.hand if c.card_type in
                ('Combat Action', 'Combat Event')]

    def descartar_da_mao(self, indices: list[int]) -> list[CardInstance]:
        """Descarta cartas da mao para o descarte apropriado.

        Args:
            indices: Lista de indices na mao para descartar.

        Returns:
            Lista de cartas descartadas.
        """
        descartadas = []
        # Ordena reverso para remover sem baguncar indices
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.hand):
                card = self.hand.pop(idx)
                card.zone = Zone.DISCARD_COMBAT
                descartadas.append(card)
                self.discard_combat.append(card)
        return descartadas

    def redraw_sept(self, descartar_primeiro: bool = True
                    ) -> list[CardInstance]:
        """Redraw de sept: descarta opcional + compra ate encher.

        Regra (2.2.2):
        - Primeiro turno: compra mao inicial de sept (sem descarte).
        - Turnos seguintes: pode descartar qualquer carta de sept
          da mao, DEPOIS compra ate encher.

        Args:
            descartar_primeiro: Se True, o jogador/bot pode descartar
                                antes de comprar. O descarte e opcional
                                e feito externamente.

        Returns:
            Lista de cartas compradas.
        """
        sept_hand = self._cartas_sept()
        current = len(sept_hand)
        if current < self.hand_size_sept:
            qtd = self.hand_size_sept - current
            return self.draw_sept(qtd)
        return []

    def redraw_combat(self, descartar_primeiro: bool = True
                      ) -> list[CardInstance]:
        """Redraw de combate: descarta opcional + compra ate encher.

        Regra (2.2.6):
        - Ao entrar no Combat phase, pode descartar qualquer carta
          de combate da mao, DEPOIS compra ate encher.

        Args:
            descartar_primeiro: Se True, o jogador/bot pode descartar
                                antes de comprar.

        Returns:
            Lista de cartas compradas.
        """
        combat_hand = self._cartas_combate()
        current = len(combat_hand)
        if current < self.hand_size_combat:
            qtd = self.hand_size_combat - current
            return self.draw_combat(qtd)
        return []

    @staticmethod
    def _pode_regenerar(c: CardInstance) -> bool:
        """Verifica se criatura pode regenerar.

        Regra (2.2.2):
        - Todo Character regenera.
        - Ally/Prey regeneram se creature class permite.
        - Class: Garou, Bastet, Fera, Fomori, Vampire, Monster
        - Nao regeneram: Banes, Animal, Faerie, Human, Spirit
        - Nao regeneram criaturas mortas (health_current <= 0).

        Returns:
            True se pode regenerar.
        """
        if c.health_current <= 0:
            return False
        if c.card_type == 'Character':
            return True
        # Allies/Prey: checar keywords
        kw = (c.keywords or '').lower()
        nao_regeneram = {'bane', 'animal', 'faerie', 'human', 'spirit',
                         'wraith', 'chulorviah', 'cult',
                         'cultist'}
        if any(nr in kw for nr in nao_regeneram):
            return False
        # Se tem classe que regenera
        regeneram = {'garou', 'bastet', 'fera', 'fomori',
                     'vampire', 'monster', 'werewolf',
                     'ajaba', 'ananasi', 'corax', 'gurahl',
                     'kitsune', 'mokole', 'nagah', 'nuwisha',
                     'ratkin', 'rokea', 'shifter', 'shapeshifter'}
        return any(r in kw for r in regeneram)

    def regeneration(self) -> list[str]:
        """Fase de Regeneration: cura dano nao-agravado.

        Regra (2.2.2):
        - Todo Character regenera.
        - Ally/Prey regeneram se creature class permite.
        - Cada criatura cura 1 de dano nao-agravado por turno.
        - Cura o menor dano primeiro (simplificado: 1 HP).
        - Dano agravado NAO regenera.

        Returns:
            Lista de logs.
        """
        logs = []
        for c in self.pack_home:
            if not self._pode_regenerar(c):
                continue
            dano_atual = c.health - c.health_current
            if dano_atual <= 0:
                continue
            # Separar dano agravado do normal
            dano_normal = dano_atual - c.damage_aggravated
            if dano_normal <= 0:
                # So tem dano agravado, nao regenera
                logs.append(f'{c.name} tem apenas dano agravado '
                            f'({c.damage_aggravated})')
                continue
            # Cura 1 de dano normal
            c.health_current = min(c.health_current + 1, c.health)
            logs.append(f'{c.name} regenerou 1 de dano '
                        f'({c.health_current}/{c.health})')
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

    def personagens_que_podem_step(self) -> list[CardInstance]:
        """Retorna personagens que podem stepping sideways.

        Usa o Caern do pack (se houver) ou Gauntlet padrao.
        """
        from rage_web.game_engine.rules import (encontrar_caern,
                                                  pode_step_sideways,
                                                  GAUNTLET_DEFAULT)
        caern = encontrar_caern(self)
        # Se tem Caern, usa o Gauntlet dele; se nao, padrao
        gauntlet = getattr(caern, 'damage', GAUNTLET_DEFAULT)
        try:
            gauntlet = int(gauntlet) if gauntlet else GAUNTLET_DEFAULT
        except (ValueError, TypeError):
            gauntlet = GAUNTLET_DEFAULT

        # Personagens em Pack Home que podem ir para Umbra
        podem_ir = []
        for c in self.pack_home:
            if pode_step_sideways(c, caern, gauntlet):
                podem_ir.append(c)
        # Personagens na Umbra que podem voltar
        podem_voltar = [c for c in self.umbra
                        if pode_step_sideways(c, caern, gauntlet)]
        return podem_ir, podem_voltar

    def step_sideways(self, card: CardInstance) -> bool:
        """Move um personagem do Pack Home para a Umbra."""
        if card in self.pack_home:
            self.pack_home.remove(card)
            card.zone = Zone.UMBRA
            self.umbra.append(card)
            return True
        return False

    def step_back(self, card: CardInstance) -> bool:
        """Move um personagem da Umbra de volta ao Pack Home."""
        if card in self.umbra:
            self.umbra.remove(card)
            card.zone = Zone.PACK_HOME
            self.pack_home.append(card)
            return True
        return False

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
    step: str = ''            # select_alpha, declare, reveal, resolve, end
    attackers: list[str] = field(default_factory=list)
    defenders: list[str] = field(default_factory=list)
    declarations: dict[str, Optional[str]] = field(default_factory=dict)
    declaration_order: list[str] = field(default_factory=list)

    # Alpha selection
    alphas: dict[str, str] = field(default_factory=dict)
    """player_id -> card_id do alpha selecionado"""
    alpha_order: list[str] = field(default_factory=list)
    """Ordem dos alphas por Renome (decrescente)"""
    current_alpha_index: int = 0
    """Indice do alpha atual em alpha_order"""
    alpha_actions_taken: int = 0
    """Contador de acoes alfa tomadas"""

    @property
    def last_to_declare(self) -> Optional[str]:
        if self.declaration_order:
            return self.declaration_order[-1]
        return None

    @property
    def current_alpha(self) -> Optional[str]:
        """Retorna o ID do alpha que esta agindo agora."""
        if self.alpha_order and self.current_alpha_index < len(self.alpha_order):
            return self.alpha_order[self.current_alpha_index]
        return None

    def declare(self, card_id: str, action: str) -> bool:
        if not self.is_active:
            return False
        if card_id in self.declarations:
            return False
        self.declarations[card_id] = action
        self.declaration_order.append(card_id)
        return True

    def all_declared(self, combatants: list[str]) -> bool:
        return all(c in self.declarations for c in combatants)

    def selecionar_alfa(self, jogador_id: str, card_id: str):
        """Seleciona o alpha de um jogador.

        Args:
            jogador_id: ID do jogador.
            card_id: ID da criatura escolhida como alpha.
        """
        self.alphas[jogador_id] = card_id
        # Recalcula ordem decrescente de Renome
        self._recalcular_ordem_alfa()

    def _recalcular_ordem_alfa(self):
        """Ordena alphas por Renome decrescente.

        Regra (2.2.6):
        - Alpha com maior Renome age primeiro.
        - Empates sao resolvidos aleatoriamente.
        """
        # A ordem e recalculada externamente em combat_queue.py
        pass


@dataclass
class MootState:
    """Estado de uma Junta (Moot ou Board Meeting) sendo votada."""
    nome: str = ''
    dono_id: str = ''  # Jogador que chamou a Junta
    renown_min: int = 0  # Renome minimo para chamar
    votos_sim: int = 0
    votos_nao: int = 0
    aprovado: bool = False
    resolvido: bool = False
    is_board_meeting: bool = False  # True = Board Meeting (Wyrm), False = Moot (Gaia)

    @property
    def resultado(self) -> str:
        if self.resolvido:
            return 'APROVADO' if self.aprovado else 'REJEITADO'
        return 'VOTACAO'

    def votar(self, renown: int, a_favor: bool):
        if a_favor:
            self.votos_sim += renown
        else:
            self.votos_nao += renown

    def resolver(self):
        """Resolve a votacao: sim > nao = aprovado."""
        self.aprovado = self.votos_sim > self.votos_nao
        self.resolvido = True


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
    renown_level: int = 20  # VP needed to win (Rule 2.3)
    winner: Optional[str] = None  # Player ID who won

    # Hunting Grounds (cartas neutras)
    hunting_grounds_cards: list[CardInstance] = field(default_factory=list)

    # Sistema de anuncio de efeitos (Rage: anuncio -> resposta -> resolucao)
    anunciador: 'Anunciador' = None

    # Estado de Moot (Juntas)
    moot_atual: Optional['MootState'] = None

    # Gerador de numeros aleatorios com seed (reprodutibilidade)
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        from rage_web.game_engine.anunciador import Anunciador
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
            elif self.phase == 'umbra':
                # Closed Play: personagens com Gnosis >= Gauntlet
                # PODEM stepping sideways (decisao do jogador/bot)
                # Nao fazemos auto-step aqui; o bot decide em _agir_umbra
                pass

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
                # Selecao de alfas (automática para bots/jogador unico)
                from rage_web.game_engine.combat_queue import selecionar_alfa, calcular_ordem_alfa
                for p in self.players:
                    # Escolhe o personagem com maior Renome como alpha
                    candidatos = [c for c in p.pack_home
                                  if 'Character' in (c.card_type or '')
                                  or 'Ally' in (c.card_type or '')]
                    if candidatos:
                        melhor = max(candidatos, key=lambda c: c.renown)
                        selecionar_alfa(self, p.id, str(melhor.card_id))
                calcular_ordem_alfa(self)
        else:
            # Fim do Combat phase -> verificar vitoria
            from rage_web.game_engine.combat_queue import verificar_vitoria
            winner_id = verificar_vitoria(self)
            if winner_id:
                self.winner = winner_id
                winner_name = self._find_player(winner_id).name
                winner_vp = self._find_player(winner_id).victory_points
                self.add_log(f'🏆 {winner_name} venceu a partida! '
                             f'(VP: {winner_vp})')
                # Nao avanca fase, partida terminou
                return

            # Fim do turno -> volta ao inicio
            self.phase = 'redraw'
            self.turn_number += 1
            self.current_player_index = 0
            for p in self.players:
                p.reset_pass()
            # Redraw de sept no inicio do turno
            # Regra (2.2.2): primeiro turno ja comprou mao inicial
            # nos turnos seguintes: pode descartar + compra ate encher
            # O descarte e opcional e feito pelo bot/jogador antes
            for p in self.players:
                drawn = p.redraw_sept(descartar_primeiro=False)
                if drawn:
                    self.add_log(f'{p.name} comprou {len(drawn)} carta(s) de sept')

    def _find_player(self, player_id: str) -> Optional[PlayerState]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def chamar_moot(self, jogador_id: str, nome: str = 'Moot',
                     is_board_meeting: bool = False) -> bool:
        """Chama uma Junta (Moot ou Board Meeting).

        Regra (2.2.5):
        - So pode chamar 1 Junta por turno.
        - Personagem precisa Renown >= requisito.
        - Gaia chama Moots, Wyrm chama Board Meetings.

        Args:
            jogador_id: ID do jogador que chamou.
            nome: Nome da Junta.
            is_board_meeting: True = Board Meeting, False = Moot.

        Returns:
            True se foi chamada.
        """
        if self.moot_atual and not self.moot_atual.resolvido:
            return False  # Ja tem uma Junta em andamento

        self.moot_atual = MootState(
            nome=nome,
            dono_id=jogador_id,
            is_board_meeting=is_board_meeting,
        )
        self.add_log(f'{jogador_id} chamou {nome}')
        return True

    def votar_moot(self, jogador_id: str, a_favor: bool) -> bool:
        """Vota na Junta atual com todo o Renome do jogador.

        Returns:
            True se o voto foi computado.
        """
        if not self.moot_atual or self.moot_atual.resolvido:
            return False
        jogador = next((p for p in self.players if p.id == jogador_id), None)
        if not jogador:
            return False
        # Soma Renome de todos os personagens do jogador
        renown_total = sum(c.renown for c in jogador.pack_home)
        self.moot_atual.votar(renown_total, a_favor)
        self.add_log(f'{jogador.name} votou {"SIM" if a_favor else "NAO"} '
                     f'com {renown_total} votos')
        return True

    def resolver_moot(self) -> bool:
        """Resolve a Junta atual."""
        if not self.moot_atual or self.moot_atual.resolvido:
            return False
        self.moot_atual.resolver()
        self.add_log(f'Junta {self.moot_atual.nome}: '
                     f'{self.moot_atual.resultado} '
                     f'({self.moot_atual.votos_sim} x {self.moot_atual.votos_nao})')
        return True

    def add_log(self, message: str):
        """Adiciona entrada no log da partida."""
        entry = f'[T{self.turn_number} {self.phase.upper()}] {message}'
        self.log.append(entry)
