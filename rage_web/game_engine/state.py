"""Estado do jogo: partida, jogadores, criaturas em jogo."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def _default_anunciador():
    from rage_web.game_engine.anunciador import Anunciador
    return Anunciador()


@dataclass
class QuestState:
    """Estado de uma quest ativa no jogador.

    Mnesis Dreams: marca um personagem e conta turnos sem dano.
    """
    quest_card_uid: int       # uid da carta de quest em jogo
    target_card_uid: int      # uid do personagem alvo
    condition: str            # 'sem_dano_por_N_turnos'
    turns_remaining: int = 0  # turnos restantes para completar (N)
    turns_with_damage: int = 0  # turnos em que alvo tomou dano
    completed: bool = False
    reward_vp: int = 0
    reward_acao: str = ''     # 'shuffle_card_discard_to_deck', etc.


@dataclass
class DeathTrigger:
    """Trigger que dispara quando uma criatura morre.

    Ex: Dream Hunter — se morto por Mokole, dono busca carta.
    """
    trigger_card_uid: int     # uid da carta com o trigger
    condition: str            # 'killed_by_type: Mokole', 'any', etc.
    action: str               # 'search_deck_type:Quest/Rite/Junta'
    originador_id: str = ''   # jogador que se beneficia
    usado: bool = False       # trigger ja foi usado (one-shot)


@dataclass
class GameModifier:
    """Modificador global do jogo aplicado por cartas em jogo.

    Ex: Lake Nasser Wallow — Rites/Gifts cruzam Gauntlet.
    """
    card_uid: int
    modifier: str             # 'rites_gifts_cross_gauntlet'
    ativo: bool = True


@dataclass
class PendenciaEfeito:
    """Efeito temporario que expira em determinado momento.

    Quando a duracao expira, o delta e revertido no atributo da carta
    ou a restricao e removida.
    """
    card_uid: int  # id() da CardInstance afetada
    atributo: str  # 'rage', 'gnosis', 'health', 'restricao'
    delta: int     # valor a reverter (para stats)
    duracao: str   # 'end_of_turn', 'end_of_combat'
    valor_str: str = ''  # nome da restricao (para atributo='restricao')
    turno_aplicado: int = 0
    fase_aplicada: str = ''


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
    # Atributos de forma alternativa (Breed/Metis/etc)
    rage_morph: int = 0
    gnosis_morph: int = 0
    health_morph: int = 0
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
    restricoes: list[str] = field(default_factory=list)
    # Restricoes ativas: 'nao_jogar_rage_3+', 'nao_fugir', etc.
    is_frenzied: bool = False
    attached_damage: list[CardInstance] = field(default_factory=list)
    # Cartas de dano anexadas a esta criatura (regra 6.4)
    attached_equipment: list[CardInstance] = field(default_factory=list)
    # Equipamentos anexados a esta criatura
    reducao_dano: int = 0
    # Reducao de dano passiva (ex: armaduras)
    is_aggravated: bool = False  # Se esta carta em si e dano agravado

    @property
    def effective_rage(self) -> int:
        """Rage efetivo da criatura, considerando modificadores.

        Se a criatura tem a restricao 'rage_breed', usa o rage_morph
        como Rage efetivo em todas as formas.
        """
        if 'rage_breed' in self.restricoes:
            return self.rage_morph if self.rage_morph > 0 else self.rage
        return self.rage

    @property
    def effective_gnosis(self) -> int:
        """Gnosis efetivo da criatura, considerando modificadores."""
        if 'gnosis_breed' in self.restricoes:
            return self.gnosis_morph if self.gnosis_morph > 0 else self.gnosis
        return self.gnosis

    @property
    def effective_health(self) -> int:
        """Vida maxima efetiva da criatura, considerando modificadores."""
        if 'health_breed' in self.restricoes:
            return self.health_morph if self.health_morph > 0 else self.health
        return self.health


def criar_carta_dano(origem: CardInstance, valor: int,
                     dono_id: str, is_aggravated: bool = False
                     ) -> CardInstance:
    """Cria uma carta de dano a partir da origem.

    Regra (6.4): quando um card causa dano a uma criatura,
    ele se torna uma damage card anexada sob a criatura.
    """
    return CardInstance(
        card_id=origem.card_id,
        name=origem.name,
        card_type=origem.card_type,
        zone=Zone.OUT_OF_PLAY,
        owner_id=dono_id,
        controller_id=dono_id,
        damage=str(valor),
        is_aggravated=is_aggravated,
    )


def anexar_dano(alvo: CardInstance, origem: CardInstance,
                valor: int, dono_id: str,
                is_aggravated: bool = False) -> CardInstance:
    """Aplica dano e anexa a damage card a uma criatura.

    1. Cria a damage card a partir da origem.
    2. Anexa a `alvo.attached_damage`.
    3. Reduz `health_current` do alvo.

    Returns:
        A damage card criada.
    """
    damage_card = criar_carta_dano(origem, valor, dono_id, is_aggravated)
    alvo.attached_damage.append(damage_card)
    alvo.health_current = max(0, alvo.health_current - valor)
    return damage_card


def descartar_anexos(card: CardInstance, dono: PlayerState):
    """Move todas as cartas anexadas ao descarte do dono.

    Regra (6.4.2): quando uma criatura morre, descarte todas as
    cartas (exceto Past Lives) anexadas a ela.
    """
    for anexo in card.attached_damage:
        anexo.zone = Zone.DISCARD_COMBAT
        dono.discard_combat.append(anexo)
    card.attached_damage.clear()


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
    out_of_play: list[CardInstance] = field(default_factory=list)

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

    # Quests ativas neste jogador
    quests: list[QuestState] = field(default_factory=list)

    # Recrutamento: tipos de ally que este jogador pode recrutar
    can_recruit: list[str] = field(default_factory=list)

    @property
    def caerns_no_hunting_grounds(self) -> list[CardInstance]:
        """Retorna lista de Caerns no Hunting Grounds do jogador."""
        return [c for c in self.hunting_grounds if c.card_type == 'Caern']

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
        """Fase de Regeneration: remove a menor carta de dano nao-agravado.

        Regra (2.2.2):
        - Todo Character regenera.
        - Ally/Prey regeneram se creature class permite.
        - Cada criatura regenera a damage card de menor valor
          nao-agravada (se houver).
        - Dano agravado NAO regenera.

        Returns:
            Lista de logs.
        """
        logs = []
        for c in self.pack_home:
            if not self._pode_regenerar(c):
                continue
            if not c.attached_damage:
                continue
            # Filtra damage cards: so pode regenerar nao-agravadas,
            # a menos que a criatura tenha 'pode_regenerar_agravado'
            pode_agravado = 'pode_regenerar_agravado' in c.restricoes
            if pode_agravado:
            # Pode regenerar qualquer dano (incluindo agravado)
                normais = list(c.attached_damage)
            else:
                # Filtra apenas damage cards nao-agravadas
                normais = [d for d in c.attached_damage
                           if not d.is_aggravated]
            if not normais:
                logs.append(f'{c.name} tem apenas dano agravado')
                continue
            # Remove a de menor valor
            menor = min(normais, key=lambda d: int(d.damage or '0'))
            valor = int(menor.damage or '0')
            c.attached_damage.remove(menor)
            c.health_current = min(c.health_current + valor, c.health)
            logs.append(f'{c.name} regenerou {valor} de dano '
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
    anunciador: 'Anunciador' = field(default_factory=_default_anunciador)

    # Estado de Moot (Juntas)
    moot_atual: Optional['MootState'] = None

    # Efeitos temporarios pendentes de expiracao
    pendencias: list[PendenciaEfeito] = field(default_factory=list)

    # Triggers de morte ativos (ex: Dream Hunter)
    death_triggers: list[DeathTrigger] = field(default_factory=list)

    # Modificadores globais do jogo (ex: Lake Nasser Wallow)
    game_modifiers: list[GameModifier] = field(default_factory=list)

    # Gerador de numeros aleatorios com seed (reprodutibilidade)
    rng: random.Random = field(default_factory=random.Random)

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
            nova_fase = PHASES[idx + 1]
            # Expirar efeitos temporarios antes de entrar na nova fase
            logs_exp = self.expirar_pendencias(nova_fase)
            for l in logs_exp:
                self.add_log(l)
            self.phase = nova_fase
            # Executa acoes automaticas na transicao
            if self.phase == 'regeneration':
                for p in self.players:
                    logs = p.regeneration()
                    for log in logs:
                        self.add_log(log)
                # Verificar progresso das quests
                self._check_quests()
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
            # Fim do Combat phase: vitimas atacam automaticamente
            self._check_victim_attacks()

            # Verificar vitoria
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

            # Fim do turno -> expirar efeitos + volta ao inicio
            logs_exp = self.expirar_pendencias('redraw')
            for l in logs_exp:
                self.add_log(l)
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

    def _find_card_by_uid(self, uid: int) -> Optional[CardInstance]:
        """Encontra uma CardInstance pelo uid (id() da instancia)."""
        for p in self.players:
            for zone_list in [p.pack_home, p.hunting_grounds, p.umbra,
                              p.hand, p.deck_combat, p.deck_sept,
                              p.discard_combat, p.discard_sept, p.victory_pile]:
                for c in zone_list:
                    if id(c) == uid:
                        return c
        for c in self.hunting_grounds_cards:
            if id(c) == uid:
                return c
        return None

    def _check_quests(self):
        """Verifica progresso de todas as quests ativas.

        Chamado na regeneration phase.
        - Se o alvo tomou dano no turno anterior, reseta contador.
        - Se passou N turnos sem dano, completa a quest.
        """
        for p in self.players:
            completas = []
            for q in p.quests:
                if q.completed:
                    completas.append(q)
                    continue

                # Procura a carta alvo pelo uid
                target = self._find_card_by_uid(q.target_card_uid)
                if target is None:
                    # Alvo nao existe mais (foi destruido)
                    q.completed = False
                    completas.append(q)
                    self.add_log(f'Quest falhou: alvo de {target.name if target else "?"} desapareceu')
                    continue

                # Decrementa turnos restantes
                q.turns_remaining -= 1
                if q.turns_remaining <= 0:
                    # Quest completa!
                    q.completed = True
                    completas.append(q)
                    self.add_log(f'✨ {p.name} completou quest! (+{q.reward_vp} VP)')
                    p.victory_points += q.reward_vp

                    # Acoes especiais
                    if q.reward_acao == 'shuffle_card_discard_to_deck':
                        # Shuffle uma carta do sept discard para sept deck
                        if p.discard_sept:
                            carta = p.discard_sept.pop(
                                self.rng.randint(0, len(p.discard_sept) - 1)
                            )
                            carta.zone = Zone.DECK_SEPT
                            p.deck_sept.append(carta)
                            self.add_log(f'{p.name} shufflou {carta.name} do discard para o deck')

            # Remove quests completas/falhas
            p.quests = [q for q in p.quests if q not in completas]

    def _check_victim_attacks(self):
        """Executa ataques automaticos de Victimas no Hunting Grounds.

        Chamado ao fim do Combat phase, antes da verificacao de vitoria.
        Cada vitima ataca o personagem mais vulneravel/conveniente.
        """
        from rage_web.game_engine.state import anexar_dano

        vitimas = [c for c in self.hunting_grounds_cards
                   if c.card_type and 'Victim' in c.card_type
                   and c.health_current > 0]

        if not vitimas:
            return

        # Coleta personagens de todos os jogadores
        todos_personagens = []
        for p in self.players:
            todos_personagens.extend(
                (c, p) for c in p.pack_home
                if 'Character' in (c.card_type or '')
                or 'Ally' in (c.card_type or '')
            )

        if not todos_personagens:
            return

        for vitima in vitimas:
            alvo = None
            dono_alvo = None

            # 535 - Renegade Werewolf Hunter: ataca BSD com maior Renome
            if vitima.card_id == 535:
                bsd_candidates = [
                    (c, p) for c, p in todos_personagens
                    if 'Black Spiral Dancer' in (c.keywords or '')
                    or 'Wyrm' in (c.keywords or '')
                ]
                if not bsd_candidates:
                    continue
                bsd_candidates.sort(key=lambda x: x[0].renown, reverse=True)
                alvo, dono_alvo = bsd_candidates[0]

            # 565 - Vigilante: ataca quem matou vitima de menor Renome
            elif vitima.card_id == 565:
                if not todos_personagens:
                    continue
                # Escolhe aleatoriamente entre os personagens
                idx = self.rng.randint(0, len(todos_personagens) - 1) if self.rng else 0
                alvo, dono_alvo = todos_personagens[idx]

            # 568 - Wild Animals: ataca maior Rage Wyrm
            elif vitima.card_id == 568:
                wyrm_candidates = [
                    (c, p) for c, p in todos_personagens
                    if 'Wyrm' in (c.keywords or '')
                ]
                if not wyrm_candidates:
                    continue
                wyrm_candidates.sort(key=lambda x: x[0].effective_rage, reverse=True)
                alvo, dono_alvo = wyrm_candidates[0]

            if alvo and dono_alvo:
                dano = max(1, vitima.effective_rage)
                agravado = (vitima.card_id == 535)  # Werewolf Hunter does aggravated
                self.add_log(
                    f'⚔️ {vitima.name} atacou {alvo.name} '
                    f'com {dano} de dano{" agravado" if agravado else ""}!'
                )
                anexar_dano(alvo, vitima, dano, dono_alvo.id,
                            is_aggravated=agravado)

                # Se alvo morreu, vai pro Victory Pile de ninguem (desaparece)
                if alvo.health_current <= 0:
                    from rage_web.game_engine.combat_queue import _remove_creature
                    _remove_creature(self, alvo)
                    alvo.zone = Zone.DISCARD_COMBAT
                    dono_alvo.discard_combat.append(alvo)
                    self.add_log(
                        f'💀 {alvo.name} foi morto por {vitima.name}!'
                    )

    def register_card_passives(self, card: CardInstance, owner: PlayerState):
        """Registra efeitos passivos especiais de cartas sem efeitos
        estruturados.

        Cartas especiais:
        - Dream Hunter (573): death trigger quando morto por Mokole
        - Lake Nasser Wallow (609): Rites/Gifts cruzam Gauntlet
        - Sand's Last King (374): pode recrutar Ajaba/Bastet/Silent Striders

        Args:
            card: A carta que entrou em jogo.
            owner: O jogador dono.
        """
        if card.card_id == 573:  # Dream Hunter
            trigger = DeathTrigger(
                trigger_card_uid=id(card),
                condition='killed_by_type:Mokole',
                action='search_deck_type:Quest/Rite/Moot',
                originador_id=owner.id
            )
            self.death_triggers.append(trigger)
            self.add_log(f'{card.name}: trigger de morte registrado')

        elif card.card_id == 609:  # Lake Nasser Wallow
            modifier = GameModifier(
                card_uid=id(card),
                modifier='rites_gifts_cross_gauntlet'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: Rites e Gifts cruzam o Gauntlet agora')

        elif card.card_id == 374:  # Sand's Last King
            tribos = ['Ajaba', 'Bastet', 'Silent Striders']
            for t in tribos:
                if t not in owner.can_recruit:
                    owner.can_recruit.append(t)
            self.add_log(
                f'{card.name}: {owner.name} pode recrutar '
                f'Ajaba, Bastet e Silent Striders')

        elif card.card_id == 175:  # Longtooth Soulkiller
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_use_7th_gen_gifts'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: {owner.name} pode usar Gifts de 7a Geracao')

        elif card.card_id == 227:  # Questor
            modifier = GameModifier(
                card_uid=id(card),
                modifier='questor_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: bonus de +1 VP por vitima no HG ativado')

        elif card.card_id == 630:  # Chronicle of the Black Labyrinth
            modifier = GameModifier(
                card_uid=id(card),
                modifier='chronicle_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: Wyrm ganha +1 VP por vitima')

        elif card.card_id == 777:  # The Pit
            modifier = GameModifier(
                card_uid=id(card),
                modifier='the_pit_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: {owner.name} ganha +1 VP por vitima')

        elif card.card_id == 716:  # War Knife of Benning Simon
            modifier = GameModifier(
                card_uid=id(card),
                modifier='war_knife_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: dano agravado com Combat Actions Rage <= 4')

        elif card.card_id == 697:  # Skin of the Hellbound
            modifier = GameModifier(
                card_uid=id(card),
                modifier='skin_hellbound_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: imune a dano de Rage 6+')

    def register_death_trigger(self, trigger: DeathTrigger):
        """Registra um death trigger."""
        self.death_triggers.append(trigger)

    def check_death_triggers(self, killed_card: CardInstance,
                              killer_card: Optional[CardInstance] = None,
                              killer_player: Optional[PlayerState] = None):
        """Verifica triggers de morte quando uma criatura morre.

        Args:
            killed_card: A carta que foi destruida.
            killer_card: A carta que causou a destruicao.
            killer_player: O jogador que controla o killer.
        """
        for t in self.death_triggers:
            if t.usado:
                continue

            trigger_card = self._find_card_by_uid(t.trigger_card_uid)
            if trigger_card is None:
                continue

            # Verifica condicao
            if t.condition == 'any':
                pass  # Qualquer morte dispara
            elif t.condition.startswith('killed_by_type:'):
                tipo_necessario = t.condition.split(':', 1)[1].strip().lower()
                if killer_card is None:
                    continue
                # Verifica em keywords, nome e card_type
                keywords = (killer_card.keywords or '').lower()
                nome = (killer_card.name or '').lower()
                card_type = (killer_card.card_type or '').lower()
                if (tipo_necessario not in keywords
                        and tipo_necessario not in nome
                        and tipo_necessario not in card_type):
                    continue
            else:
                continue  # Condicao nao reconhecida

            # Executa acao
            if t.action.startswith('search_deck_type:'):
                tipos = t.action.split(':', 1)[1].strip()
                tipos_lista = [x.strip() for x in tipos.split('/')]
                # Beneficiario: primeiro o killer_player, depois originador
                beneficiario = killer_player or self._find_player(t.originador_id)
                if beneficiario:
                    # Procura no sept deck por carta do tipo
                    encontrada = None
                    for i, c in enumerate(beneficiario.deck_sept):
                        if any(tt.lower() in (c.card_type or '').lower()
                               or tt.lower() in (c.name or '').lower()
                               for tt in tipos_lista):
                            encontrada = beneficiario.deck_sept.pop(i)
                            break
                    if encontrada:
                        encontrada.zone = Zone.HAND
                        beneficiario.hand.append(encontrada)
                        self.add_log(
                            f'{beneficiario.name} buscou {encontrada.name} '
                            f'do deck (trigger: {trigger_card.name})'
                        )
                    else:
                        self.add_log(
                            f'{beneficiario.name} nao encontrou carta '
                            f'do tipo {tipos} no deck'
                        )
            elif t.action == 'gain_vp':
                # Dar VP ao originador
                beneficiario = self._find_player(t.originador_id)
                if beneficiario:
                    beneficiario.victory_points += 1
                    self.add_log(
                        f'{beneficiario.name} ganhou 1 VP (trigger: {trigger_card.name})'
                    )
            else:
                self.add_log(f'Trigger action nao implementada: {t.action}')

            t.usado = True

    def has_modifier(self, modifier: str) -> bool:
        """Verifica se um modificador global esta ativo."""
        for m in self.game_modifiers:
            if m.modifier == modifier and m.ativo:
                # Verifica se a carta ainda esta em jogo
                # Tenta uid da instancia primeiro, depois card_id
                card = self._find_card_by_uid(m.card_uid)
                if card is None:
                    # Tenta buscar por card_id
                    for p in self.players:
                        for zone_list in [p.pack_home, p.hunting_grounds,
                                          p.umbra]:
                            for c in zone_list:
                                if c.card_id == m.card_uid:
                                    card = c
                                    break
                if card is not None and card.zone in (
                        Zone.PACK_HOME, Zone.HUNTING_GROUNDS, Zone.UMBRA):
                    return True
                # Carta foi removida, desativa modificador
                if card is None:
                    m.ativo = False
        return False

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

    def _find_card_by_uid(self, uid: int) -> Optional[CardInstance]:
        """Busca uma CardInstance pelo seu Python id() em todas as zonas.

        Inclui cartas em OUT_OF_PLAY (que nao estao em nenhuma lista).
        """
        for p in self.players:
            for zone_cards in (p.pack_home, p.hunting_grounds,
                               p.umbra, p.hand,
                               p.discard_combat, p.discard_sept,
                               p.deck_combat, p.deck_sept,
                               p.victory_pile, p.out_of_play):
                for c in zone_cards:
                    if id(c) == uid:
                        return c
        for c in self.hunting_grounds_cards:
            if id(c) == uid:
                return c
        return None

    def check_kill_bonuses(self, killed_card: CardInstance,
                             killer_player: PlayerState) -> None:
        """Verifica bonus de VP por matar criaturas.

        Cartas que concedem bonus:
        - Questor (227): +1 VP ao matar Victim do Hunting Grounds
        - The Pit (777): +1 VP ao matar qualquer Victim
        - Chronicle of the Black Labyrinth (630): +1 VP ao matar Victim
          se o controlador for Wyrm
        """
        if killed_card.card_type != 'Victim':
            return

        z_orig = killed_card.zone
        if z_orig != Zone.HUNTING_GROUNDS and z_orig != Zone.PACK_HOME:
            return

        # Questor: so bonus se vitima estava no Hunting Grounds
        questor_bonus = False
        if z_orig == Zone.HUNTING_GROUNDS and self.has_modifier('questor_active'):
            # Verifica se quem matou e dono do Questor
            for m in self.game_modifiers:
                if m.modifier == 'questor_active' and m.ativo:
                    card = self._find_card_by_uid(m.card_uid)
                    if card and card.zone in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS, Zone.UMBRA):
                        dono = self._find_player(card.owner_id)
                        if dono and dono.id == killer_player.id:
                            killer_player.victory_points += 1
                            questor_bonus = True
                            self.add_log(
                                f'Questor: +1 VP ({killed_card.name} do HG)')
                            break

        # The Pit: bonus para qualquer vitima (nao cumulativo com Questor?)
        if not questor_bonus and self.has_modifier('the_pit_active'):
            for m in self.game_modifiers:
                if m.modifier == 'the_pit_active' and m.ativo:
                    card = self._find_card_by_uid(m.card_uid)
                    if card and card.zone in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS, Zone.UMBRA):
                        dono = self._find_player(card.owner_id)
                        if dono and dono.id == killer_player.id:
                            killer_player.victory_points += 1
                            self.add_log(
                                f'The Pit: +1 VP ({killed_card.name} morta)')
                            break

        # Chronicle: bonus para Wyrm
        if self.has_modifier('chronicle_active'):
            for m in self.game_modifiers:
                if m.modifier == 'chronicle_active' and m.ativo:
                    card = self._find_card_by_uid(m.card_uid)
                    if card and card.zone in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS, Zone.UMBRA):
                        dono = self._find_player(card.owner_id)
                        if dono and dono.id == killer_player.id:
                            # Chronicle bonus: +1 VP
                            killer_player.victory_points += 1
                            self.add_log(
                                f'Chronicle: +1 VP ({killed_card.name} morta)')
                            break

    def expirar_pendencias(self, fase_entrando: str) -> list[str]:
        """Reverte efeitos temporarios cuja duracao expirou.

        Args:
            fase_entrando: Proxima fase do turno (usada para decidir
                           o que expira).

        Returns:
            Lista de mensagens de log.
        """
        log = []
        removidas = []
        for pend in self.pendencias:
            expirou = False

            if pend.duracao == 'end_of_turn' and fase_entrando == 'redraw':
                expirou = True
            elif pend.duracao == 'end_of_combat' and fase_entrando != 'combat':
                expirou = True
            elif pend.duracao == 'end_of_phase' and pend.fase_aplicada != fase_entrando:
                expirou = True
            elif pend.duracao.startswith('after_'):
                # Formato: 'after_N_turns' - expira quando turno atual >= N
                try:
                    target_turn = int(pend.duracao.split('_')[1])
                    if self.turn_number >= target_turn:
                        expirou = True
                except (ValueError, IndexError):
                    pass

            if expirou:
                c = self._find_card_by_uid(pend.card_uid)
                if c:
                    if pend.atributo == 'rage':
                        c.rage = max(0, c.rage - pend.delta)
                        log.append(f'{c.name}: bonus de rage expirou')
                    elif pend.atributo == 'gnosis':
                        c.gnosis = max(0, c.gnosis - pend.delta)
                        log.append(f'{c.name}: bonus de gnosis expirou')
                    elif pend.atributo == 'health':
                        c.health = max(1, c.health - pend.delta)
                        log.append(f'{c.name}: bonus de vida expirou')
                    elif pend.atributo == 'restricao' and pend.valor_str:
                        if pend.valor_str in c.restricoes:
                            c.restricoes.remove(pend.valor_str)
                            log.append(f'{c.name}: restricao "{pend.valor_str}" expirou')
                    elif pend.atributo == 'zona' and pend.valor_str:
                        # Move a carta de volta para a zona original
                        zonas_rev = {
                            'pack_home': Zone.PACK_HOME,
                            'hunting_grounds': Zone.HUNTING_GROUNDS,
                            'umbra': Zone.UMBRA,
                            'discard_combat': Zone.DISCARD_COMBAT,
                            'hand': Zone.HAND,
                        }
                        zona_retorno = zonas_rev.get(pend.valor_str)
                        if zona_retorno:
                            # Remove da lista atual (inclui out_of_play)
                            for p in self.players:
                                for lista in (p.pack_home, p.hunting_grounds,
                                              p.umbra, p.hand, p.out_of_play):
                                    if c in lista:
                                        lista.remove(c)
                                        break
                            # Adiciona na lista correta
                            map_destino = {
                                Zone.PACK_HOME: [p.pack_home for p in self.players],
                                Zone.UMBRA: [p.umbra for p in self.players],
                                Zone.HUNTING_GROUNDS: [p.hunting_grounds for p in self.players],
                            }
                            # Tenta encontrar o dono original
                            dono = self._find_player(c.owner_id)
                            if dono:
                                if zona_retorno == Zone.PACK_HOME:
                                    dono.pack_home.append(c)
                                elif zona_retorno == Zone.UMBRA:
                                    dono.umbra.append(c)
                                elif zona_retorno == Zone.HUNTING_GROUNDS:
                                    dono.hunting_grounds.append(c)
                            c.zone = zona_retorno
                            log.append(f'{c.name} retornou para {pend.valor_str}')
                removidas.append(pend)

        # Limpa restricoes de fim de turno (ex: nao_pode_frenzy)
        if fase_entrando == 'redraw':
            for p in self.players:
                for zone_cards in (p.pack_home, p.hunting_grounds, p.umbra):
                    for c in zone_cards:
                        if 'nao_pode_frenzy' in c.restricoes:
                            c.restricoes.remove('nao_pode_frenzy')
                            log.append(f'{c.name}: restricao "nao_pode_frenzy" expirou')

        for r in removidas:
            self.pendencias.remove(r)
        return log

    def add_log(self, message: str):
        """Adiciona entrada no log da partida."""
        entry = f'[T{self.turn_number} {self.phase.upper()}] {message}'
        self.log.append(entry)
