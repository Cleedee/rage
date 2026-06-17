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
    Past Lives: se character morre, vai pro VP valendo -3 Renown.
    """
    quest_card_uid: int       # uid da carta de quest em jogo
    target_card_uid: int      # uid do personagem alvo
    condition: str            # 'sem_dano_por_N_turnos'
    turns_remaining: int = 0  # turnos restantes para completar (N)
    turns_with_damage: int = 0  # turnos em que alvo tomou dano
    completed: bool = False
    reward_vp: int = 0
    reward_acao: str = ''     # 'shuffle_card_discard_to_deck', etc.
    failed_due_to_death: bool = False  # True se alvo morreu antes de completar


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
    tags: str = ''
    is_tapped: bool = False  # @DEPRECATED: nao usado no Rage CCG oficial

    # Buffs temporarios de efeitos passivos (modificar_atributo_passivo)
    buff_rage: int = 0
    buff_gnosis: int = 0
    buff_health: int = 0
    buff_reducao_dano: int = 0  # Reducao de dano adicional (ex: Fetal Position)
    buff_dano_proximo_ataque: int = 0  # Bonus de dano no proximo ataque (ex: Razor Claws)
    buff_dano_agravado: int = 0  # Dano agravado adicional (ex: Toxic Claws)
    is_face_down: bool = False
    modifiers: dict = field(default_factory=dict)
    ignorar_agravado: bool = False  # Purity of Spirit: converte dano agravado em normal
    modelo_id: Optional[str] = None  # ID do modelo de efeitos (effects.py)
    damage_aggravated: int = 0  # Quanto do dano e agravado (nao regenera)
    restricoes: list[str] = field(default_factory=list)
    # Restricoes ativas: 'nao_jogar_rage_3+', 'nao_fugir', etc.
    is_frenzied: bool = False
    damage_cards: list[CardInstance] = field(default_factory=list)
    # Cartas de combate reais (Combat Actions) anexadas como dano (regra 6.4)
    attached_equipment: list[CardInstance] = field(default_factory=list)
    attached_to: Optional[CardInstance] = None  # Se for equipamento, referencia a criatura que o possui
    # Equipamentos anexados a esta criatura
    attached_gifts: list[CardInstance] = field(default_factory=list)
    equipment_disabled: set[int] = field(default_factory=set)
    # IDs (uid) de equipamentos que a criatura optou por nao usar no combate atual
    # Regra 4.3.2: "Creatures can choose not to use equipment attached to them."
    # Gifts permanentes anexados a esta criatura (4.5.3)
    reducao_dano: int = 0
    # Reducao de dano passiva (ex: armaduras)
    is_aggravated: bool = False  # Se esta carta em si e dano agravado
    is_crinos: bool = False  # True = em forma Crinos (alterna via Shapeshift)

    @property
    def total_dano(self) -> int:
        """Soma do dano de Combat Actions reais anexadas como damage cards.

        Regra (6.4): quando uma Combat Action causa dano, a carta e
        anexada a` criatura alvo como damage card.
        A criatura morre quando total_dano >= health.
        """
        return sum(int(d.damage or '0') for d in self.damage_cards)

    def sync_health(self) -> int:
        """Recalcula health_current a partir de health - total_dano.

        Mantem a consistencia entre health_current e o valor
        real das damage cards anexadas (regra 6.4).
        Se a criatura esta em Crinos, usa health_morph como pool.

        Returns:
            O novo valor de health_current.
        """
        pool = self.health_morph if self.is_crinos and self.health_morph > 0 else self.health
        novo = max(0, pool - self.total_dano)
        self.health_current = novo
        return novo

    @property
    def effective_rage(self) -> int:
        """Rage efetivo da criatura, considerando modificadores e buffs."""
        base = self.rage
        if 'rage_breed' in self.restricoes:
            base = self.rage_morph if self.rage_morph > 0 else self.rage
        return max(0, base + self.buff_rage)

    @property
    def effective_gnosis(self) -> int:
        """Gnosis efetivo da criatura, considerando modificadores e buffs."""
        base = self.gnosis
        if 'gnosis_breed' in self.restricoes:
            base = self.gnosis_morph if self.gnosis_morph > 0 else self.gnosis
        return max(0, base + self.buff_gnosis)

    @property
    def effective_health(self) -> int:
        """Vida maxima efetiva da criatura, considerando buffs."""
        base = self.health
        if 'health_breed' in self.restricoes:
            base = self.health_morph if self.health_morph > 0 else self.health
        return max(0, base + self.buff_health)

    @property
    def effective_reducao_dano(self) -> int:
        """Reducao de dano efetiva (base + buff)."""
        return self.reducao_dano + self.buff_reducao_dano

    @property
    def buff_dano_ataque(self) -> int:
        """Bonus de dano no proximo ataque (Razor Claws, etc)."""
        return self.buff_dano_proximo_ataque

    def aplicar_buff(self, atributo: str, valor: int):
        """Aplica um buff temporario a esta criatura."""
        if atributo == 'rage':
            self.buff_rage += valor
        elif atributo == 'gnosis':
            self.buff_gnosis += valor
        elif atributo == 'health':
            self.buff_health += valor
        elif atributo == 'reducao_dano':
            self.buff_reducao_dano += valor
        elif atributo == 'dano_proximo_ataque':
            self.buff_dano_proximo_ataque += valor
        elif atributo == 'dano_agravado':
            self.buff_dano_agravado += valor

    def aplicar_attr_buff(self, attr: str, valor: int):
        """Aplica buff de atributo (usado pelo resolvedor de efeitos)."""
        self.aplicar_buff(attr, valor)

    def remover_buff(self, atributo: str, valor: int):
        """Remove um buff (reverte o delta)."""
        if atributo == 'rage':
            self.buff_rage = max(0, self.buff_rage - valor)
        elif atributo == 'gnosis':
            self.buff_gnosis = max(0, self.buff_gnosis - valor)
        elif atributo == 'health':
            self.buff_health = max(0, self.buff_health - valor)
        elif atributo == 'reducao_dano':
            self.buff_reducao_dano = max(0, self.buff_reducao_dano - valor)
        elif atributo == 'dano_proximo_ataque':
            self.buff_dano_proximo_ataque = max(0, self.buff_dano_proximo_ataque - valor)
        elif atributo == 'dano_agravado':
            self.buff_dano_agravado = max(0, self.buff_dano_agravado - valor)
        elif atributo == 'health':
            self.buff_health = max(0, self.buff_health - valor)
        elif atributo == 'reducao_dano':
            self.buff_reducao_dano = max(0, self.buff_reducao_dano - valor)


def anexar_dano(alvo: CardInstance, origem: CardInstance,
                valor: int, dono_id: str,
                is_aggravated: bool = False,
                carta_combate: CardInstance = None,
                game: Optional['GameState'] = None) -> None:
    """Anexa uma Combat Action real como damage card a uma criatura.

    Regra (6.4): quando uma Combat Action causa dano, a carta e
    anexada a criatura alvo como damage card.
    Requer `carta_combate` — a propria carta de combate usada.

    Se o alvo tiver modifier 'ignorar_agravado' (Purity of Spirit),
    dano agravado e convertido em normal.
    """
    if carta_combate is None:
        raise ValueError('anexar_dano requer carta_combate '
                         '(Combat Action real). Acoes sinteticas '
                         'foram removidas do motor.')

    # Purity of Spirit: converte dano agravado em normal e descarta o Gift
    destruiu_purity = False
    if is_aggravated and getattr(alvo, 'ignorar_agravado', False):
        is_aggravated = False
        destruiu_purity = True

    carta_combate.damage = str(valor)
    carta_combate.is_aggravated = is_aggravated
    carta_combate.owner_id = dono_id
    carta_combate.zone = Zone.OUT_OF_PLAY
    alvo.damage_cards.append(carta_combate)
    alvo.sync_health()

    # Descarta Purity of Spirit apos primeiro uso (se converteu dano)
    if destruiu_purity:
        alvo.ignorar_agravado = False
        for gift in list(alvo.attached_gifts):
            if getattr(gift, 'modelo_id', '') == 'purity-of-spirit':
                alvo.attached_gifts.remove(gift)
                gift.zone = Zone.DISCARD_SEPT
                # Encontra o dono do gift
                dono_gift = None
                if game:
                    for p in game.players:
                        if p.id == gift.owner_id:
                            dono_gift = p
                            break
                        if gift in p.pack_home:
                            dono_gift = p
                            break
                if dono_gift is None:
                    # Fallback: usa dono_id do alvo
                    if game:
                        for p in game.players:
                            if p.id == alvo.owner_id:
                                dono_gift = p
                                break
                if dono_gift:
                    dono_gift.discard_sept.append(gift)
                    if game:
                        game.add_log(
                            f'Purity of Spirit descartado apos proteger '
                            f'{alvo.name} de dano agravado')
                else:
                    # Ultimo fallback: discarta sem dono
                    pass
                break

def descartar_anexos(card: CardInstance, dono: PlayerState,
                     game: Optional[GameState] = None):
    """Move todas as cartas anexadas ao descarte do dono.

    Regra (6.4.2): quando uma criatura morre, descarte todas as
    cartas (exceto Past Lives) anexadas a ela.
    Inclui damage cards e equipamentos.

    Damage cards vao para DISCARD_COMBAT do jogador que as jogou
    (nao do dono da criatura que tomou o dano).
    Equipamentos vao para DISCARD_SEPT do dono da criatura.
    """
    from rage_web.game_engine.rules import zona_descarte

    # Descarta damage cards (sao Combat Actions reais anexadas como dano)
    for anexo in card.damage_cards:
        zona = zona_descarte(anexo.card_type or '')
        # Damage card vai para o descarte do JOGADOR QUE A JOGOU
        dono_dano = dono
        if anexo.owner_id and game:
            for p in game.players:
                if p.id == anexo.owner_id:
                    dono_dano = p
                    break
        if zona == 'discard_combat':
            anexo.zone = Zone.DISCARD_COMBAT
            dono_dano.discard_combat.append(anexo)
        else:
            anexo.zone = Zone.DISCARD_SEPT
            dono_dano.discard_sept.append(anexo)
    card.damage_cards.clear()
    # Descarta equipamentos anexados (regra 6.4.2)
    for eq in card.attached_equipment:
        zona = zona_descarte(eq.card_type or '')
        if zona == 'discard_combat':
            eq.zone = Zone.DISCARD_COMBAT
            dono.discard_combat.append(eq)
        else:
            eq.zone = Zone.DISCARD_SEPT
            dono.discard_sept.append(eq)
    card.attached_equipment.clear()

    # Descarta Personal Totem anexado a esta criatura (4.5.2B)
    # Procura no dicionario personal_totems do dono
    if dono and hasattr(dono, 'personal_totems'):
        totems_a_remover = []
        for totem_uid, character in list(dono.personal_totems.items()):
            if character is card:
                totems_a_remover.append(totem_uid)
                # Move o totem para o descarte
                for c in list(dono.pack_home):
                    if id(c) == totem_uid:
                        dono.pack_home.remove(c)
                        c.zone = Zone.DISCARD_SEPT
                        dono.discard_sept.append(c)
                        c.attached_to = None
                        if game:
                            game.add_log(
                                f'{c.name} descartado (criatura morreu)')
                        break
        for uid in totems_a_remover:
            del dono.personal_totems[uid]


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
    deck_strategy: str = 'midrange'
    has_passed: bool = False
    hand_size_sept: int = 5
    hand_size_combat: int = 5

    # Flag: primeiro turno (redraw inicial e especial)
    is_first_turn: bool = True

    # Regra 2.3: jogador eliminado (perdeu todos os Characters)
    eliminado: bool = False

    # Cartas em combate neste turno
    combatants: list[CardInstance] = field(default_factory=list)

    # Quests ativas neste jogador
    quests: list[QuestState] = field(default_factory=list)

    # Recrutamento: tipos de ally que este jogador pode recrutar
    can_recruit: list[str] = field(default_factory=list)

    # Personal Totems ativos: mapeia uid do totem -> Character
    personal_totems: dict[int, CardInstance] = field(default_factory=dict)

    # Gerador aleatorio (para reembaralhar decks)
    rng: random.Random = field(default_factory=random.Random)

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
        """Compra cartas do deck de combate.

        Regra (04-cartas-em-detalhe.md:685):
        Se o combat deck acabar, reembaralha o descarte de combate
        num novo combat deck, e continua comprando.
        Se nao houver cartas nem no deck nem no descarte,
        joga com a mao atual.
        """
        drawn = []
        for _ in range(count):
            if not self.deck_combat:
                # Tenta reembaralhar descarte
                if self.discard_combat:
                    self.deck_combat = list(self.discard_combat)
                    self.discard_combat.clear()
                    self.rng.shuffle(self.deck_combat)
                else:
                    break  # Sem cartas disponiveis
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

    @property
    def combat_hand(self) -> list[CardInstance]:
        """Retorna cartas de combate na mao.

        Regra (6.2): Combat Actions e Combat Events formam
        a 'combat hand' do jogador. Sept cards sao a 'sept hand'.
        """
        return [c for c in self.hand if c.card_type in
                ('Combat Action', 'Combat Event')]

    def _cartas_combate(self) -> list[CardInstance]:
        """Retorna cartas de combate na mao (alias para combat_hand)."""
        return self.combat_hand

    def descartar_da_mao(self, indices: list[int]) -> list[CardInstance]:
        """Descarta cartas da mao para o descarte apropriado.

        Args:
            indices: Lista de indices na mao para descartar.

        Returns:
            Lista de cartas descartadas.
        """
        from rage_web.game_engine.rules import zona_descarte
        descartadas = []
        # Ordena reverso para remover sem baguncar indices
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.hand):
                card = self.hand.pop(idx)
                zona = zona_descarte(card.card_type or '')
                if zona == 'discard_combat':
                    card.zone = Zone.DISCARD_COMBAT
                    self.discard_combat.append(card)
                else:
                    card.zone = Zone.DISCARD_SEPT
                    self.discard_sept.append(card)
                descartadas.append(card)
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

    def regeneration(self, game: Optional[GameState] = None) -> list[str]:
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

        # Trinity Hive Caern: BSD regeneram apenas na Umbra
        # (verifica se o pack deste jogador tem o Caern)
        trinity_hive_ativa = any(
            caern.card_id == 599
            for caern in self.pack_home + self.hunting_grounds
        )

        # Pentex Refinery (520): impede regeneracao de shapechangers
        # Enquanto a refinaria estiver em jogo, nenhum shapechanger
        # pode regenerar naturalmente. Gifts (Mother's Touch, etc)
        # ainda funcionam pois usam _resolver_curar.
        pentex_refinery_ativa = game and game.has_modifier(
            'pentex_refinery_impede_regeneracao')

        for c in self.pack_home:
            if not self._pode_regenerar(c):
                continue
            # Pentex Refinery: bloqueia regeneracao natural
            if pentex_refinery_ativa:
                logs.append(
                    f'{c.name} nao pode regenerar (Pentex Refinery)')
                continue
            # Verifica se ha dano para regenerar (damage_cards de Combat Actions)
            if not c.damage_cards:
                continue
            # Trinity Hive: BSD so regeneram na Umbra
            if trinity_hive_ativa:
                if 'black spiral dancer' in (c.keywords or '').lower():
                    if c.zone != Zone.UMBRA:
                        logs.append(
                            f'{c.name} (BSD) so regenera na Umbra '
                            f'(Trinity Hive)')
                        continue
                    # BSD na Umbra: pode regenerar agravado
                    if 'pode_regenerar_agravado' not in c.restricoes:
                        c.restricoes.append('pode_regenerar_agravado')

            # Tenta regenerar dano de Combat Actions primeiro
            pode_agravado = 'pode_regenerar_agravado' in c.restricoes
            if c.damage_cards:
                if pode_agravado:
                    candidatas = list(c.damage_cards)
                else:
                    candidatas = [d for d in c.damage_cards
                                  if not d.is_aggravated]
                if candidatas:
                    menor = min(candidatas,
                                key=lambda d: int(d.damage or '0'))
                    valor = int(menor.damage or '0')
                    c.damage_cards.remove(menor)
                    menor.zone = Zone.DISCARD_COMBAT
                    # Damage card vai para o descarte de combate do
                    # jogador que a jogou (dono original da carta),
                    # nao do dono da criatura que regenerou.
                    dono_dano = self
                    if menor.owner_id and game:
                        for p in game.players:
                            if p.id == menor.owner_id:
                                dono_dano = p
                                break
                    dono_dano.discard_combat.append(menor)
                    c.health_current = min(c.health_current + valor,
                                           c.health)
                    logs.append(f'{c.name} regenerou {valor} de dano '
                                f'({c.health_current}/{c.health})')
                    continue

            # Nao ha mais fallback de dano basico — toda regeneracao
            # ocorre sobre damage_cards de Combat Actions reais.
            logs.append(f'{c.name} nao tem Combat Actions para regenerar')
            continue
        return logs

    def pagar_custo_rage(self, custo: int) -> Optional[str]:
        """Paga um custo de Rage usando um personagem.

        Regra Rage CCG: personagens pagam custos de Rage/Gnosis
        sem ficar 'tapped'. A limitacao e que cada personagem so
        pode pagar um custo por turno, controlado pela stat.
        """
        from rage_web.game_engine.rules import encontrar_pagador_rage
        pagador = encontrar_pagador_rage(self, custo)
        if pagador:
            return pagador.name
        return None

    def pagar_custo_gnosis(self, custo: int) -> Optional[str]:
        """Paga um custo de Gnosis usando um personagem.

        Regra Rage CCG: personagens pagam custos de Rage/Gnosis
        sem ficar 'tapped'. A limitacao e que cada personagem so
        pode pagar um custo por turno, controlado pela stat.
        """
        from rage_web.game_engine.rules import encontrar_pagador_gnosis
        pagador = encontrar_pagador_gnosis(self, custo)
        if pagador:
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
    """Estado atual do combate.

    Steps (Cap. 6):
    - select_alpha: Escolher alfa
    - alpha_action: Alpha declara ataque/challenge
    - declaration: Declarar atacante+alvo; abilities na declaracao
    - pre_combat: Pack actions, redirect, cancel, step in (Closed Play)
    - beginning_of_combat: Open Play pre-rodadas
    - play_card (6.2.1): Cada criatura joga combat card face-down
    - targeting (6.2.2): Atribuir alvos
    - reveal (6.2.3): Revelar cartas + sub-steps: feinting (6.8.1),
      instinctive (6.8.2), alternative (6.6.5)
    - bluff (6.2.4): Verificar requisitos (6.9.1: ilegais),
      verificar bluffs (6.9.2: sucesso/falha)
    - resolution (6.2.5): Fast -> Normal -> Slow, aplicar dano
    - withdrawal (6.2.6): Atacante pode retirar (6.3.1)
    - between_rounds (6.2.7): Open Play entre rodadas;
      loop para play_card se combate continua
    - end: Fim do combate, cleanup (6.3)
    """
    is_active: bool = False
    step: str = ''
    attackers: list[str] = field(default_factory=list)
    defenders: list[str] = field(default_factory=list)

    # Alpha selection
    alphas: dict[str, str] = field(default_factory=dict)
    """player_id -> card_id do alpha selecionado"""
    alpha_order: list[str] = field(default_factory=list)
    """Ordem dos alphas por Renome (decrescente)"""
    current_alpha_index: int = 0
    """Indice do alpha atual em alpha_order"""
    alpha_actions_taken: int = 0
    """Contador de acoes alfa tomadas"""

    # ---- NOVOS CAMPOS (Cap. 6) ----

    # Rodada de combate atual (0 = pre-rodadas, 1+ = rodadas)
    round_number: int = 0

    # Combatentes ativos (atualizado a cada rodada)
    combatants: list[str] = field(default_factory=list)

    # Declaracao original (attackers vs defenders)
    original_attackers: list[str] = field(default_factory=list)
    original_defenders: list[str] = field(default_factory=list)

    # --- Play Card Step ---
    # played_cards[card_id] = action_name (strike, block, dodge, etc)
    played_cards: dict[str, str] = field(default_factory=dict)
    # played_combat_cards[criatura_card_id] = CardInstance da carta de combate jogada
    # Usado para rastrear qual Combat Action real foi usada (ex: Surprise Attack)
    # para que a carta original seja anexada como dano ao alvo (regra 6.4)
    played_combat_cards: dict[str, 'CardInstance'] = field(default_factory=dict)

    # --- Reveal Step Feint Sub-step (6.2.3 / 6.8) ---
    # Rastreia em qual mini-step do Reveal estamos:
    # '' = revelacao normal (antes de feinting/instinctive)
    # 'feinting' = janela de Feinting (6.8.1)
    # 'instinctive' = Instinctive Combat Actions (6.8.2)
    # 'alternative' = Alternative Combat Actions (6.6.5)
    # 'targeting_extra' = atribuir alvos das cartas extras (6.8.4)
    feint_substep: str = ''
    # face_down_order: ordem em que os cards foram jogados
    face_down_order: list[str] = field(default_factory=list)

    # --- Targeting Step ---
    # targets[card_id] = target_card_id (quem cada card mira)
    targets: dict[str, str] = field(default_factory=dict)

    # --- Play Card Step (face-down cards) ---
    # ce_face_down[creature_card_id] = ce_card_id
    # Combat Events jogados face-down (sao ilegais no Bluff Step)
    ce_face_down: dict[str, str] = field(default_factory=dict)

    # --- Bluff Step ---
    # Cartas ilegais (nao atendem requisitos)
    illegal_cards: set[str] = field(default_factory=set)
    # Cartas que sao bluff (Rage req maior que a Rage do personagem)
    bluff_cards: set[str] = field(default_factory=set)
    # Cartas que falharam o bluff
    bluff_failed: set[str] = field(default_factory=set)

    # --- Resolution Step ---
    # Dano pendente por velocidade: fast, normal, slow
    # damage_queue[card_id] = [(target_id, damage_value, speed), ...]
    damage_queue: list[tuple[str, str, int, str]] = field(default_factory=list)

    # --- Withdrawal ---
    # Se o atacante se retirou
    attacker_withdrew: bool = False

    # --- Combat Declaration Options (6.5.3, 6.5.4, 6.5.5) ---
    # Tipo de ataque: 'creature' (padrao), 'territory', 'battlefield', 'bind'
    attack_type: str = 'creature'
    # Para Territory: card_id do Territory atacado
    territory_target: Optional[str] = None
    # Para Battlefield: card_id do Battlefield atacado
    battlefield_target: Optional[str] = None
    # Para Bind: card_id do Spirit sendo vinculado
    bind_target: Optional[str] = None
    # Para autodefesa de Battlefield: dados do Battlefield como combatente
    # battlefield_self_defense[card_id] = dict com rage, gnosis, health, keywords
    battlefield_self_defense: dict[str, dict] = field(default_factory=dict)

    # Pack combat (6.5.8): combatentes adicionados via pack_attack/puxa_pack
    pack_added_attackers: list[str] = field(default_factory=list)
    """IDs dos combatentes adicionados como atacantes via pack combat."""
    pack_added_defenders: list[str] = field(default_factory=list)
    """IDs dos combatentes adicionados como defensores via pack combat."""

    # Metadados de compatibilidade com o sistema anterior
    # declarations: mapeia card_id -> action (antigo declare_action)
    declarations: dict[str, Optional[str]] = field(default_factory=dict)
    # declaration_order: ordem das declaracoes
    declaration_order: list[str] = field(default_factory=list)
    # extra_declarations: card_id -> action (acoes extras por equipamento)
    # Usado por Devilwhip e outros equipamentos que concedem acoes extras
    extra_declarations: dict[str, str] = field(default_factory=dict)
    # weapon_declarations: card_id -> weapon_card_id (armas usadas)
    weapon_declarations: dict[str, str] = field(default_factory=dict)

    # --- Restricted / Forced / Random Play (6.6.6) ---
    # restricoes_round[card_id] = dict com regras para esta rodada
    # Ex: {'restricted': 'rage_2', 'forced': True, 'random': True}
    restricoes_round: dict[str, dict] = field(default_factory=dict)

    # --- P8: Virtual Damage Actions ---
    # dano_actions[action_name] = {'damage': int, 'card_id': int, 'card_name': str}
    # Acoes geradas a partir de combat cards com efeito 'dano'
    dano_actions: dict[str, dict] = field(default_factory=dict)

    def get_restricoes(self, card_id: str) -> dict:
        """Retorna as restricoes de uma criatura para esta rodada."""
        return self.restricoes_round.get(card_id, {})

    def has_forced_play(self, card_id: str) -> bool:
        """6.6.6b: Criatura e forcada a jogar carta de combate."""
        return self.restricoes_round.get(card_id, {}).get('forced', False)

    def has_random_play(self, card_id: str) -> bool:
        """6.6.6c: Criatura joga carta aleatoria."""
        return self.restricoes_round.get(card_id, {}).get('random', False)

    def get_restricted_level(self, card_id: str) -> Optional[int]:
        """6.6.6a: Retorna o nivel maximo de Rage permitido (ex: 2).
        None = sem restricao."""
        res = self.restricoes_round.get(card_id, {})
        r = res.get('restricted')
        if r is not None:
            return int(r) if str(r).isdigit() else None
        return None

    def reset_restricoes_round(self):
        """Limpa restricoes ao fim de cada round de combate."""
        self.restricoes_round.clear()

    def aplicar_restricao_round(self, card_id: str, **kwargs):
        """Aplica restricoes a uma criatura para esta rodada.

        Args:
            card_id: ID da criatura.
            **kwargs: 'restricted'=int, 'forced'=bool, 'random'=bool

        Exemplo:
            combat.aplicar_restricao_round('123', restricted=2)
            combat.aplicar_restricao_round('456', forced=True)
            combat.aplicar_restricao_round('789', random=True)
        """
        if card_id not in self.restricoes_round:
            self.restricoes_round[card_id] = {}
        for k, v in kwargs.items():
            self.restricoes_round[card_id][k] = v

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

    def declare(self, card_id: str, action: str, extra: bool = False) -> bool:
        """Registra a acao de combate de uma criatura.

        Args:
            card_id: ID da criatura.
            action: Nome da acao (strike, block, etc).
            extra: Se True, permite uma segunda declaracao para criaturas
                   com acoes extras disponiveis (ex: Devilwhip).
                   A declaracao extra e rastreada em extra_declarations.
        """
        if not self.is_active:
            return False

        # Verifica se ja declarou (normal ou extra)
        if card_id in self.declarations:
            if not extra:
                return False
            # Modo extra: verifica se ja usou acao extra
            if card_id in self.extra_declarations:
                return False
            # Registra como acao extra
            self.extra_declarations[card_id] = action
            self.declaration_order.append(card_id)
            return True

        # Declaracao normal
        self.declarations[card_id] = action
        self.declaration_order.append(card_id)
        # Tambem registra no novo sistema (play_card)
        self.played_cards[card_id] = action
        self.face_down_order.append(card_id)
        return True

    def all_declared(self, combatants: list[str]) -> bool:
        """Verifica se todos os combatentes declararam.

        Criaturas com acoes extras disponiveis (ex: Devilwhip) podem
        declarar novamente mesmo apos all_declared retornar True.
        """
        return all(c in self.declarations for c in combatants)

    def has_extra_declaration(self, card_id: str) -> bool:
        """Verifica se uma criatura pode declarar uma acao extra.

        Usado por equipamentos como Devilwhip que concedem +1 acao
        de combate por rodada. A verificacao real de acoes extras
        disponiveis e feita em declare_action (combat_queue.py).
        """
        if card_id not in self.declarations:
            return False  # Ainda nao declarou a acao principal
        if card_id in self.extra_declarations:
            return False  # Ja usou a acao extra nesta rodada
        return True

    def selecionar_alfa(self, jogador_id: str, card_id: str):
        """Seleciona o alpha de um jogador."""
        self.alphas[jogador_id] = card_id
        self._recalcular_ordem_alfa()

    def _recalcular_ordem_alfa(self):
        """Ordena alphas por Renome decrescente.

        Regra (2.2.6):
        - Alpha com maior Renome age primeiro.
        - Empates sao resolvidos aleatoriamente.
        """
        pass

    def iniciar_nova_rodada(self):
        """Prepara para uma nova rodada de combate.
        Preserva declarations para o round anterior para log,
        mas limpa played_cards para o novo round.
        """
        self.round_number += 1
        self.played_cards.clear()
        self.face_down_order.clear()
        self.targets.clear()
        self.illegal_cards.clear()
        self.reset_restricoes_round()  # 6.6.6: restricoes sao por rodada
        self.bluff_cards.clear()
        self.bluff_failed.clear()
        self.damage_queue.clear()
        self.weapon_declarations.clear()
        # Mantem declarations para compatibilidade
        self.declarations.clear()
        self.declaration_order.clear()

    def limpar_combatentes_mortos(self, mortos: set[str]):
        """Remove combatentes mortos de todas as listas."""
        self.attackers = [c for c in self.attackers if c not in mortos]
        self.defenders = [c for c in self.defenders if c not in mortos]
        self.combatants = [c for c in self.combatants if c not in mortos]
        for cid in mortos:
            self.declarations.pop(cid, None)
            self.played_cards.pop(cid, None)
            if cid in self.declaration_order:
                self.declaration_order.remove(cid)
            if cid in self.face_down_order:
                self.face_down_order.remove(cid)


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
    modelo_id: str = ''  # ID do modelo de carta (ex: 'card_1185')
    card_uid: int = 0    # Python id() da instancia real da carta

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
class LunarPhaseState:
    """Estado de uma Fase Lunar ativa."""
    card_id: int = 0  # ID da carta Lunar Phase (ex: 890 = New Moon)
    nome: str = ''
    dono_id: str = ''  # Jogador que jogou
    modelo_id: str = ''  # ID do modelo de carta
    card_uid: int = 0  # Python id() da instancia
    ragabash_gnosis_bonus: bool = False  # New Moon: +1 Gnosis para Ragabash

    def efeito_global(self) -> str:
        """Descricao do efeito global desta fase lunar."""
        return f'{self.nome}'


def _anexar_personal_totem(totem_card: CardInstance, owner: PlayerState, game: 'GameState'):
    """Anexa um Personal Totem a um Character valido no pack.

    Regra (4.5.2B):
    - Personal Totem e jogado em um unico Character e so beneficia
      aquele Character.
    - O Character deve atender o requisito do Totem.
    - Um Character pode ter no maximo 1 Personal Totem.
    - Character com Personal Totem nao pode se beneficiar de Pack Totem.

    Args:
        totem_card: A carta do Personal Totem.
        owner: Jogador dono.
        game: Estado do jogo (para log).
    """
    requires = (totem_card.requires or '').strip()
    opcoes = [p.strip() for p in requires.split(' - ')] if requires else []

    # Busca Character viavel: atende requisito e nao tem totem pessoal
    from rage_web.game_engine.rules import _char_atende_requisitos, _info_char
    candidato = None
    for c in owner.pack_home:
        if 'Character' not in (c.card_type or ''):
            continue
        # Ja tem Personal Totem?
        if any(pt is c for pt in owner.personal_totems.values()):
            continue
        # Atende requisito?
        if opcoes:
            if _char_atende_requisitos(
                _info_char(c), c.gnosis or 0, opcoes, owner, c
            ):
                candidato = c
                break
        else:
            candidato = c
            break

    if candidato:
        # Anexa o totem ao Character
        totem_card.attached_to = candidato
        totem_card.zone = Zone.PACK_HOME
        if totem_card not in owner.pack_home:
            owner.pack_home.append(totem_card)
        owner.personal_totems[id(totem_card)] = candidato
        if game:
            game.add_log(
                f'{totem_card.name} anexado a {candidato.name} '
                f'(Personal Totem)')
    else:
        if game:
            game.add_log(
                f'{totem_card.name} nao pode ser anexado: '
                f'nenhum Character viavel no pack')


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

    # Fase Lunar ativa (None = nenhuma)
    lunar_phase: Optional['LunarPhaseState'] = None

    # Efeitos temporarios pendentes de expiracao
    pendencias: list[PendenciaEfeito] = field(default_factory=list)

    # Triggers de morte ativos (ex: Dream Hunter)
    death_triggers: list[DeathTrigger] = field(default_factory=list)

    # Modificadores globais do jogo (ex: Lake Nasser Wallow)
    game_modifiers: list[GameModifier] = field(default_factory=list)

    # Gerador de numeros aleatorios com seed (reprodutibilidade)
    rng: random.Random = field(default_factory=random.Random)

    # Triggers de combate (ex: Tzinzie nomeia Combat Action)
    combat_triggers: dict = field(default_factory=dict)

    # Rastreio de alpha por turno (ex: Allonzo Montoya nao pode 2x seguido)
    last_alpha_per_player: dict = field(default_factory=dict)

    # Alvos pre-selecionados para efeitos (ex: Allies Below - escolha do jogador)
    pending_targets: dict = field(default_factory=dict)
    """player_id -> card_id do alpha do ultimo combate."""

    # Efeitos ja usados neste turno (ex: Owl 1x/turno)
    used_effects: list[int] = field(default_factory=list)
    """Lista de id(CardInstance) dos efeitos ja usados neste turno."""

    def __post_init__(self):
        """Propaga o RNG do jogo para todos os jogadores."""
        for p in self.players:
            p.rng = self.rng

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
            # Reseta passes ao entrar em cada nova fase
            for p in self.players:
                p.reset_pass()
            # Executa acoes automaticas na transicao
            if self.phase == 'regeneration':
                for p in self.players:
                    logs = p.regeneration(game=self)
                    for log in logs:
                        self.add_log(log)
                # Verificar progresso das quests
                self._check_quests()
            elif self.phase == 'umbra':
                # Closed Play: personagens com Gnosis >= Gauntlet
                # PODEM stepping sideways (decisao do jogador/bot)
                # Nao fazemos auto-step aqui; o bot decide em _agir_umbra
                pass

            elif self.phase == 'moot':
                # Transicao para Moot: sem acao automatica
                pass

            # Limpeza ao final do Combat phase (volta ao redraw)
            if nova_fase == 'redraw' and self.phase == 'combat' and False:
                # (cleanup feito abaixo)
                pass

            elif self.phase == 'combat':
                # Redraw de combate ao entrar no Combat phase
                for p in self.players:
                    drawn = p.redraw_combat()
                    if drawn:
                        self.add_log(f'{p.name} comprou {len(drawn)} carta(s) de combate')
                # Selecao de alfas (automática para bots/jogador unico)
                from rage_web.game_engine.combat_queue import selecionar_alfa, calcular_ordem_alfa
                for p in self.players:
                    # Escolhe o personagem com maior Renome como alpha
                    # Exclui quem tem 'nao_pode_ser_alpha' (Caern Lua Crescente)
                    candidatos = [c for c in p.pack_home
                                  if ('Character' in (c.card_type or '')
                                  or 'Ally' in (c.card_type or ''))
                                  and 'nao_pode_ser_alpha' not in c.restricoes]
                    if not candidatos:
                        # Se todos estao impedidos, usa qualquer um
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

            # Executa efeitos de fim de turno (Mage of Celestial Chorus)
            self._check_end_of_turn_effects()

            # Fim do turno -> expirar efeitos + volta ao inicio
            logs_exp = self.expirar_pendencias('redraw')
            for l in logs_exp:
                self.add_log(l)

            # Caern of the Crescent Moon: restaura Renown e libera alpha
            if 'crescent_moon_restore' in self.combat_triggers:
                dados = self.combat_triggers.pop('crescent_moon_restore')
                for p in self.players:
                    if p.id == dados['player_id']:
                        for c in p.pack_home + p.hunting_grounds:
                            if c.card_id == dados['card_id']:
                                c.renown = dados['renown_original']
                                self.add_log(
                                    f'{c.name}: Renown restaurado '
                                    f'para {dados["renown_original"]} '
                                    f'(Caern Lua Crescente)')
                                break
            for p in self.players:
                for c in p.pack_home + p.hunting_grounds:
                    if 'nao_pode_ser_alpha' in c.restricoes:
                        c.restricoes.remove('nao_pode_ser_alpha')
            self.combat_triggers.pop('crescent_moon_used', None)

            self.phase = 'redraw'
            self.turn_number += 1
            self.current_player_index = 0
            for p in self.players:
                p.reset_pass()
            # Reseta efeitos 1x/turno
            self.used_effects.clear()
            # Aplica efeitos de Fase Lunar (ex: Full Moon -> Unlucky Lune)
            self._check_lunar_phase_effects()
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

            # Se alguma quest removida era Past Life, aplica penalties
            for q in completas:
                card_quest = self._find_card_by_uid(q.quest_card_uid)
                if card_quest:
                    ct = (card_quest.card_type or '').lower()
                    if 'past life' in ct or ct == 'past life':
                        # Past Life removida do pack_home
                        if card_quest in p.pack_home:
                            p.pack_home.remove(card_quest)
                        # Se alvo morreu: vai pro VP do dono valendo -3
                        if q.failed_due_to_death:
                            card_quest.zone = Zone.VICTORY_PILE
                            p.victory_pile.append(card_quest)
                            p.victory_points -= 3
                            self.add_log(
                                f'[Past Life] {card_quest.name} '
                                f'foi pro Victory Pile (-3 VP) '
                                f'(total: {p.victory_points})')
                        else:
                            # Completa ou falha normal: descarta
                            card_quest.zone = Zone.DISCARD_SEPT
                            p.discard_sept.append(card_quest)
                        self._recalcular_past_life_hand_size(p)

            # Remove quests completas/falhas
            p.quests = [q for q in p.quests if q not in completas]

    def _recalcular_past_life_hand_size(self, p: PlayerState):
        """Recalcula sept hand size baseado em Past Lives ativas.

        Regra: sept hand reduzido em 1 para cada Past Life em jogo.
        """
        # Conta Past Lives em jogo (pack_home)
        qtd = sum(1 for c in p.pack_home
                  if c.card_type
                  and ('past life' in c.card_type.lower()
                       or c.card_type.lower() == 'past life'))
        # Base = 5, reduz por Past Life
        novo_size = max(1, 5 - qtd)
        if p.hand_size_sept != novo_size:
            self.add_log(
                f'[Past Life] sept hand size: '
                f'{p.hand_size_sept} -> {novo_size}')
            p.hand_size_sept = novo_size

    def _recalcular_hand_sizes(self, p: PlayerState):
        """Recalcula hand sizes de sept e combate baseado em
        todas as cartas em jogo (Old Storm Chaser, Chimera, etc.).

        Regra (2.1.3): quando hand size e alterado, o redraw
        compra ate o novo tamanho.
        """
        # Primeiro recalcula efeitos base (Past Life)
        self._recalcular_past_life_hand_size(p)

        # Depois aplica bonus de cartas em jogo
        # Old Storm Chaser (207): +1 sept hand size
        tem_old_storm = any(
            c.card_id == 207 and c.zone in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS, Zone.UMBRA)
            for c in p.pack_home + p.hunting_grounds + p.umbra
        )
        if tem_old_storm:
            # Old Storm Chaser: +1 sept hand size (ja inclui no recalculo)
            bonus_soma = sum(
                1 for c in p.pack_home + p.hunting_grounds + p.umbra
                if c.card_id == 207  # Old Storm Chaser
                or c.card_id == 824   # Chimera
            )
            if bonus_soma > 0:
                novo = max(1, p.hand_size_sept + bonus_soma)
                if p.hand_size_sept != novo:
                    self.add_log(
                        f'[Hand Size] sept hand size: '
                        f'{p.hand_size_sept} -> {novo} '
                        f'(bonus de {bonus_soma} carta(s) em jogo)')
                    p.hand_size_sept = novo

    def _coletar_todas_vitimas_hg(self) -> list:
        """Coleta todas as presas do Hunting Grounds (global + players).

        Returns:
            Lista de (CardInstance, owner_id) de todas as presas vivas no HG.
        """
        result = []
        # HG global
        for c in self.hunting_grounds_cards:
            if ('Victim' in (c.card_type or '')
                    or 'Enemy' in (c.card_type or '')):
                if c.health_current > 0:
                    result.append((c, c.owner_id))
        # HG de cada jogador
        for p in self.players:
            for c in p.hunting_grounds:
                if ('Victim' in (c.card_type or '')
                        or 'Enemy' in (c.card_type or '')):
                    if c.health_current > 0:
                        result.append((c, p.id))
        return result

    def _coletar_todos_personagens(self) -> list:
        """Coleta todos os personagens (Character + Ally) de todos os jogadores.

        Returns:
            Lista de (CardInstance, PlayerState).
        """
        todos = []
        for p in self.players:
            for lista in (p.pack_home, p.umbra):
                for c in lista:
                    if ('Character' in (c.card_type or '')
                            or 'Ally' in (c.card_type or '')):
                        if c.health_current > 0:
                            todos.append((c, p))
        return todos

    def _check_victim_attacks(self):
        """Executa ataques automaticos de Presas (Victim/Enemy) no Hunting Grounds.

        Chamado ao fim do Combat phase, antes da verificacao de vitoria.
        Cada presa ataca conforme sua habilidade especial.
        """
        from rage_web.game_engine.state import anexar_dano
        from rage_web.game_engine.combat_queue import _remove_creature

        vitimas = self._coletar_todas_vitimas_hg()
        if not vitimas:
            return

        todos_personagens = self._coletar_todos_personagens()
        if not todos_personagens:
            return

        for vitima, dono_vitima_id in vitimas:
            alvo = None
            dono_alvo = None
            dano_base = max(1, vitima.effective_rage)
            agravado = False

            # --- 535 - Renegade Werewolf Hunter: ataca maior Renome BSD/Wyrm ---
            if vitima.card_id == 535:
                candidates = [
                    (c, p) for c, p in todos_personagens
                    if ('Black Spiral Dancer' in (c.keywords or '')
                        or 'Wyrm' in (c.keywords or ''))
                ]
                if candidates:
                    candidates.sort(key=lambda x: x[0].renown, reverse=True)
                    alvo, dono_alvo = candidates[0]
                    agravado = True

            # --- 565 - Vigilante: ataca quem matou a vitima de menor Renome ---
            elif vitima.card_id == 565:
                lowest = getattr(self, '_lowest_renown_victim_killed', None)
                if lowest:
                    killer_uid = lowest.get('killer_uid')
                    for c, p in todos_personagens:
                        if id(c) == killer_uid:
                            alvo, dono_alvo = c, p
                            self.add_log(
                                f'🔎 {vitima.name} mirou em '
                                f'{c.name} (matou {lowest.get("killer_name", "?")})'
                            )
                            break
                if alvo is None:
                    # Fallback: ataca personagem com maior Renome
                    todos_personagens.sort(key=lambda x: x[0].renown, reverse=True)
                    alvo, dono_alvo = todos_personagens[0]

            # --- 568 - Wild Animals: ataca maior Rage Wyrm ---
            elif vitima.card_id == 568:
                candidates = [
                    (c, p) for c, p in todos_personagens
                    if 'Wyrm' in (c.keywords or '')
                ]
                if candidates:
                    candidates.sort(key=lambda x: x[0].effective_rage, reverse=True)
                    alvo, dono_alvo = candidates[0]

            # --- 503 - Mage of the Celestial Chorus: remove no fim do turno ---
            elif vitima.card_id == 503:
                continue

            # --- Fomori Cop (slug fomori-cop_r5): descarta equipamento nao-fetich ---
            elif vitima.modelo_id == 'fomori-cop_r5':
                continue  # Auto-ataque removido: Rage e requisito para Combat Actions,
                         # nao dano direto. Habilidade principal e o descarte
                         # de equipamento no fim do Combat Phase (abaixo).

            # --- Outras presas sem auto-ataque ---
            else:
                continue

            if alvo and dono_alvo:
                self.add_log(
                    f'⚔️ {vitima.name} atacou {alvo.name} '
                    f'com {dano_base} de dano{" agravado" if agravado else ""}!'
                )
                # Cria carta de combate virtual para o dano da presa
                carta_virtual = CardInstance(
                    card_id=vitima.card_id,
                    name=vitima.name,
                    card_type='Combat Action',
                    zone=Zone.OUT_OF_PLAY,
                    owner_id=dono_vitima_id,
                    controller_id=dono_vitima_id,
                )
                anexar_dano(alvo, vitima, dano_base, dono_alvo.id,
                            is_aggravated=agravado,
                            carta_combate=carta_virtual,
                            game=self)
                # Flip para Crinos se threshold atingido
                from rage_web.game_engine.combat_queue import _flipar_para_crinos
                _flipar_para_crinos(self, alvo)

                if alvo.health_current <= 0:
                    _remove_creature(self, alvo)
                    alvo.zone = Zone.DISCARD_COMBAT
                    dono_alvo.discard_combat.append(alvo)
                    self.add_log(
                        f'💀 {alvo.name} foi morto por {vitima.name}!'
                    )

        # ── Fim do Combat Phase: Fomori Cop descarta equipamento nao-fetich de Gaia ──
        for vitima, dono_vitima_id in vitimas:
            if vitima.modelo_id == 'fomori-cop_r5' and vitima.health_current > 0:
                self._fomori_cop_discard_equipment()

    def registrar_kill_vitima(self, killer_card_uid: int):
        """Registra quem matou a vitima de menor Renome (para Vigilante)."""
        self._ultimo_killer_vitima = killer_card_uid

    def _fomori_cop_discard_equipment(self):
        """Fim do Combat Phase: Fomori Cop descarta um equipamento nao-Fetish
        de uma criatura Gaia (escolhido por um jogador aleatorio).

        Regra: "At the end of the Combat Phase, the Cop discards a piece of
        non-fetish Equipment equipped by a Gaia creature (chosen by a random player)."
        """
        from rage_web.game_engine.combat_queue import _find_owner

        # Coleta todas as criaturas Gaia com equipamento nao-Fetish
        alvos = []
        for p in self.players:
            for c in p.pack_home + p.hunting_grounds + p.umbra:
                if c.health_current <= 0:
                    continue
                if 'Gaia' not in (c.keywords or '') and 'Gaia' not in (c.card_type or ''):
                    continue
                for eq in c.attached_equipment[:]:
                    kw = (eq.keywords or '').lower()
                    tipo = (eq.card_type or '').lower()
                    if 'fetish' not in kw and 'fetish' not in tipo:
                        alvos.append((c, eq))

        if not alvos:
            self.add_log(
                'Fomori Cop: nenhum equipamento nao-Fetish em Gaia para descartar')
            return

        # Escolhe aleatoriamente (regra: chosen by a random player)
        from rage_web.game_engine.combat_queue import _find_owner
        idx = self.rng.randint(0, len(alvos) - 1)
        criatura, equipamento = alvos[idx]

        # Remove o equipamento da criatura
        if equipamento in criatura.attached_equipment:
            criatura.attached_equipment.remove(equipamento)
        equipamento.zone = Zone.DISCARD_COMBAT
        dono_eq = _find_owner(self, equipamento)
        if dono_eq:
            dono_eq.discard_combat.append(equipamento)

        self.add_log(
            f'Fomori Cop descartou {equipamento.name} de '
            f'{criatura.name} (equipamento nao-Fetish)')

    def _check_end_of_turn_effects(self):
        """Executa efeitos de fim de turno.

        - Mage of the Celestial Chorus (503): remove lowest Renown victim.
        - GameModifiers com duracao='end_of_turn': remove.
        - Purity of Spirit: fica anexado ate converter dano agravado;
          nao e limpo no fim do turno.
        """
        from rage_web.game_engine.combat_queue import _remove_creature

        # Limpa GameModifiers de fim de turno (inclui Purity of Spirit)
        self.game_modifiers = [
            m for m in self.game_modifiers
            if getattr(m, 'duration', '') != 'end_of_turn'
        ]

        # Nota: Purity of Spirit NAO e limpo no fim do turno.
        # O Gift fica anexado ate converter dano agravado em normal
        # (ocorre em state.py:anexar_dano, que descarta o Gift
        #  automaticamente apos o primeiro uso).

        # Procura Mage of the Celestial Chorus em qualquer HG
        mages = []
        for c, _ in self._coletar_todas_vitimas_hg():
            if c.card_id == 503 and c.health_current > 0:
                mages.append(c)

        if not mages:
            return

        for mage in mages:
            # Encontra a vitima de menor Renome (excluindo a Mage)
            vitimas = self._coletar_todas_vitimas_hg()
            vitimas_fora_mage = [
                (c, dono) for c, dono in vitimas
                if c.card_id != 503 and c.health_current > 0
            ]
            if not vitimas_fora_mage:
                continue

            # Menor Renome (desempate: menor health)
            vitimas_fora_mage.sort(key=lambda x: (x[0].renown, x[0].health_current))
            vitima_removida, _ = vitimas_fora_mage[0]

            # Remove do HG
            for p in self.players:
                if vitima_removida in p.hunting_grounds:
                    p.hunting_grounds.remove(vitima_removida)
                    break
            if vitima_removida in self.hunting_grounds_cards:
                self.hunting_grounds_cards.remove(vitima_removida)

            vitima_removida.zone = Zone.REMOVED
            self.add_log(
                f'🧙 {mage.name} removeu {vitima_removida.name} '
                f'(renown {vitima_removida.renown}) do Hunting Grounds!'
            )

    def _check_lunar_phase_effects(self):
        """Aplica efeitos de Fase Lunar ativa.

        - Full Moon: Unlucky Lune (558) ganha Rage 6.
        """
        if not self.lunar_phase:
            return

        nome_lua = (self.lunar_phase.nome or '').lower()

        if 'full moon' not in nome_lua and 'lua cheia' not in nome_lua:
            return

        # Full Moon: Unlucky Lune ganha Rage 6
        for c, _ in self._coletar_todas_vitimas_hg():
            if c.card_id == 558:  # Unlucky Lune
                if c.rage != 6:
                    c.rage = 6
                    self.add_log(
                        f'{c.name}: Rage = 6 (Full Moon)'
                    )
        # Personagens em jogo
        for p in self.players:
            for c in p.pack_home + p.umbra + p.hunting_grounds:
                if c.card_id == 558:
                    if c.rage != 6:
                        c.rage = 6
                        self.add_log(
                            f'{c.name}: Rage = 6 (Full Moon)'
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
        slug = card.modelo_id or ''
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

        elif slug == 'elethoi_r6':  # Elethoi
            # Só pode ser afetado por Gifts e ataques Umbrais
            if 'imune_fora_umbra' not in card.restricoes:
                card.restricoes.append('imune_fora_umbra')
            # Não pode ser vinculado
            if 'nao_pode_ser_vinculado' not in card.restricoes:
                card.restricoes.append('nao_pode_ser_vinculado')
            self.add_log(
                f'{card.name}: imune a ataques nao-umbrais e nao pode ser vinculado')

        elif slug == 'flame-spirit_r6':  # Flame Spirit (402)
            # So pode ser afetado por ataques Umbrais e Gifts
            if 'imune_fora_umbra' not in card.restricoes:
                card.restricoes.append('imune_fora_umbra')
            self.add_log(
                f'{card.name}: imune a ataques nao-umbrais (so Gifts e Umbra)')

        elif card.card_id == 630:  # Chronicle of the Black Labyrinth
            modifier = GameModifier(
                card_uid=id(card),
                modifier='chronicle_active'
            )
            self.game_modifiers.append(modifier)

        elif card.card_id == 167:  # King Albrecht
            modifier = GameModifier(
                card_uid=id(card),
                modifier='fast_striking_vs_wyrm'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: ataca primeiro contra Wyrm')

        elif card.card_id == 134:  # Grimfang
            modifier = GameModifier(
                card_uid=id(card),
                modifier='+3_moot_renown'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: +3 Renown em Moots')

        elif card.card_id == 176:  # Lord Albrecht
            trigger = DeathTrigger(
                trigger_card_uid=id(card),
                condition='killed_enemy_renown_4_plus',
                action='+1_vp_for_owner',
                originador_id=owner.id
            )
            self.death_triggers.append(trigger)
            self.add_log(
                f'{card.name}: Wyrm Renown 4+ viram +1 VP')

        elif slug == 'frenar_r1':  # Frenar (card_id=71)
            # Frenar pode trocar de lugar com o alpha se o alpha for atacado
            modifier = GameModifier(
                card_uid=id(card),
                modifier='frenar_alpha_switch'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode trocar de lugar com o alpha '
                f'se o alpha for atacado')

        elif card.card_id == 1671:  # Big Fisher
            modifier = GameModifier(
                card_uid=id(card),
                modifier='big_fisher_double_action'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: 2 acoes de combate por round')

        elif card.card_id == 180:  # Margrave Konietzko
            modifier = GameModifier(
                card_uid=id(card),
                modifier='margrave_moot_bonus'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: acao alpha extra se Moot falhar')
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

        # ── Deck 484: Ajaba Aggression ──

        elif card.card_id == 369:  # Ironjaw
            card.restricoes.append('ironjaw_bonus')
            self.add_log(
                f'{card.name}: +1 dano sem armas (Rivalry: Simba)')

        elif card.card_id == 373:  # Njoki Scarface
            card.restricoes.append('njoki_tough')
            self.add_log(
                f'{card.name}: precisa +1 dano extra pra morrer')

        elif card.card_id == 376:  # Thousand Cubs
            card.restricoes.append('thousand_cubs_moot')
            self.add_log(
                f'{card.name}: +2 Renome em Moots')

        elif slug == 'susan-anthony_r4':  # Susan Anthony
            modifier = GameModifier(
                card_uid=id(card),
                modifier='susan_anthony_kinfolk'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: {owner.name} pode comecar com '
                f'um Kinfolk Ally em jogo')

        elif card.card_id == 96:  # Clan of Hyenas
            card.restricoes.append('hyenas_escape')
            self.add_log(
                f'{card.name}: foge se tomou >=3 dano no round')

        elif card.card_id == 90:  # Unseelie Troll
            card.restricoes.append('considerado_crinos')
            self.add_log(
                f'{card.name}: considerado Crinos/Battle form')

        # ── Deck 484: Enemies ──

        elif card.card_id == 1335:  # Bitter Hatar
            card.restricoes.append('pode_ser_ally')
            self.add_log(
                f'{card.name}: pode ser jogado como Ally (Ananasi)')

        elif card.card_id == 1337:  # Ootani Oil Bane
            card.restricoes.append('impede_retirada')
            card.restricoes.append('impede_armas')
            self.add_log(
                f'{card.name}: sem withdraw ate mao vazia, sem armas')

        elif card.card_id == 553:  # Toreador Poseur
            card.restricoes.append('impede_retirada')
            self.add_log(
                f'{card.name}: nao pode withdraw; 3 rounds sem ferir = alpha penalty')

        # ── Segundo grupo ──

        elif card.card_id == 579:  # Caern of Rytthiku
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_attack_enemies_hg'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pack pode atacar Enemies no HG por VP')

        elif card.card_id == 586:  # Caern of the Unwashed Child
            modifier = GameModifier(
                card_uid=id(card),
                modifier='caern_unwashed_child',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: oponentes perdem 2 Rage/Gnosis em combate')

        elif card.card_id == 599:  # Trinity Hive Caern
            modifier = GameModifier(
                card_uid=id(card),
                modifier='trinity_hive_caern',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: BSD causam dano agravado. '
                f'Regeneram apenas na Umbra.')

        elif card.card_id == 520:  # Pentex Refinery
            modifier = GameModifier(
                card_uid=id(card),
                modifier='pentex_refinery_impede_regeneracao',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: shapechangers nao podem regenerar '
                f'enquanto estiver em jogo')

        elif slug == 'sky-river-caern':  # Sky River Caern (card_id=597)
            modifier = GameModifier(
                card_uid=id(card),
                modifier='sky_river_caern',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: nao-alfas imunes a challenge/sneak attack')

        elif card.card_id == 582:  # Caern of the Crescent Moon
            modifier = GameModifier(
                card_uid=id(card),
                modifier='crescent_moon_caern',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode dobrar Renown no Moot')

        elif card.card_id == 584:  # Caern of the Snow Leopard
            modifier = GameModifier(
                card_uid=id(card),
                modifier='snow_leopard_caern',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: personagem morto na Umbra '
                f'pode ser ressuscitado')

        elif card.card_id == 590:  # Council for Universal Trade
            modifier = GameModifier(
                card_uid=id(card),
                modifier='council_universal_trade',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: Gauntlet nunca acima de 6 ou abaixo de 4')

        elif card.card_id == 600:  # The Wheel of Ptah
            modifier = GameModifier(
                card_uid=id(card),
                modifier='wheel_of_ptah_caern',
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: controlador escolhe Moon Bridges')

        elif card.card_id == 780:  # Termite Mounds
            modifier = GameModifier(
                card_uid=id(card),
                modifier='termite_mounds_active'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: 1x/turno: olha topo 3 do combat deck')

        # ── Deck 524: Wailer special ──

        elif card.card_id == 42:  # Barnaby Shadrack
            # +2 sept cards ja resolvido via efeito comprar
            modifier = GameModifier(
                card_uid=id(card),
                modifier='barnaby_ignora_gifts'
            )
            self.game_modifiers.append(modifier)
            # start_equip: cria Submachine Gun (card_id 703) anexada
            submachine = CardInstance(
                card_id=703,
                name='Submachine Gun',
                card_type='Equipment',
                zone=Zone.PACK_HOME,
                owner_id=owner.id,
                controller_id=owner.id,
                damage='',
                is_aggravated=True,
                text=(
                    'Weapon. Firearm. The character can play up to 2'
                    ' Combat Actions of Rage 2 or lower each round.'
                ),
            )
            card.attached_equipment.append(submachine)
            owner.pack_home.append(submachine)
            self.add_log(
                f'{card.name}: comeca com Submachine Gun (dano agravado)'
            )
            self.add_log(
                f'{card.name}: ignora efeitos de Gifts')

        elif card.card_id == 64:  # Fangs-Through-Eye
            card.restricoes.append('nao_defende_fomori')
            self.add_log(
                f'{card.name}: nunca defende Fomori no HG')

        elif card.card_id == 347:  # Wailer
            modifier = GameModifier(
                card_uid=id(card),
                modifier='wailer_battle_form'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: forma Battle impede Combat Actions'
                f' de oponentes com menos Gnosis')

        elif card.card_id == 398:  # Enticer
            modifier = GameModifier(
                card_uid=id(card),
                modifier='enticer_bloqueia_round1'
            )
            self.game_modifiers.append(modifier)
            card.restricoes.append('enticer_sem_bluff_rage6')
            self.add_log(
                f'{card.name}: oponentes sem Combat Action no round 1'
                f' se tiverem menos Gnosis')

        elif card.card_id == 430:  # Pentex Executive
            modifier = GameModifier(
                card_uid=id(card),
                modifier='pentex_executive_votos_moot'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: 3 votos em Moot, pode destruir 1 Caern')

        elif card.card_id == 491:  # Greenpeace Assault Team
            modifier = GameModifier(
                card_uid=id(card),
                modifier='greenpeace_destroi_caern_wyrm'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: destroi 1 Caern Wyrm por Combat Phase')

        # ── Deck 537: Bloodsucking Champions ──

        elif card.card_id == 18:  # Count Vladimir Rustovitch
            modifier = GameModifier(
                card_uid=id(card),
                modifier='vladimir_auto_regenerate'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: regenera carta de dano mais baixa'
                f' apos combate se matou oponente')

        elif card.card_id == 663:  # Mage's Talisman
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_use_any_gift'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode usar Gifts de Gaia e Wyrm')

        elif card.card_id == 880:  # Kirijama, The Hidden Foe
            card.restricoes.append('personal_totem')
            modifier = GameModifier(
                card_uid=id(card),
                modifier='challenges_cannot_be_refused'
            )
            self.game_modifiers.append(modifier)
            # Anexa Kirijama a um Character que atenda 'Eater-of-Souls'
            _anexar_personal_totem(card, owner, self)
            self.add_log(
                f'{card.name}: desafios nao podem ser recusados')

        elif card.card_id == 1348:  # Tzinzie (Personal Totem)
            card.restricoes.append('personal_totem')
            # Anexa Tzinzi a um Character Ajaba/Bastet
            _anexar_personal_totem(card, owner, self)
            self.add_log(
                f'{card.name}: Personal Totem anexado')

        elif card.card_id == 29:  # Allonzo Montoya
            card.restricoes.append('regenerates')
            card.restricoes.append('nao_pode_alpha_2_turnos_seguidos')
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_use_sl_metis_bsd_gifts'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: regenera, nao pode alpha 2x consecutivo,'
                f' pode usar gifts Shadow Lords, Metis e BSD')

        elif card.card_id == 161:  # Juicy Johnes
            # Quando morto, quem o matou perde 2 Gnosis permanente
            trigger = DeathTrigger(
                trigger_card_uid=id(card),
                condition='juicy_johnes',
                action='reduce_gnosis:2',
                originador_id=owner.id
            )
            self.death_triggers.append(trigger)
            self.add_log(
                f'{card.name}: trigger de morte registrado'
                f' (killer perde 2 Gnosis)')

        elif card.card_id == 840:  # Eater-of-Souls
            # Permite equipar Fetish Equipment
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_equip_fetish'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pack pode equipar Fetish Equipment agora')

        # ── Umbral Wardens ──

        elif card.card_id == 247:  # Sees-through-Stars
            modifier = GameModifier(
                card_uid=id(card),
                modifier='sees_through_stars_gauntlet'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode usar Gauntlet de qualquer Caern')

        elif card.card_id == 62:  # Fade-To-Black
            modifier = GameModifier(
                card_uid=id(card),
                modifier='fade_to_black_gnosis_bonus'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: +2 Gnosis para step sideways/combat')

        elif card.card_id == 337:  # Tim Rowantree
            # Verifica se o pack do jogador tem um Caern
            has_caern = any(
                c.card_type == 'Caern'
                for c in owner.pack_home + owner.hunting_grounds + owner.umbra
            )
            if has_caern:
                card.rage += 2
                card.health += 1
                self.add_log(
                    f'{card.name}: +2 Rage +1 Saude (Caern no pack)')

        elif card.card_id == 231:  # Rainpuddle
            modifier = GameModifier(
                card_uid=id(card),
                modifier='rainpuddle_umbra_attacks'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: ataques afetam qualquer coisa na Umbra')

        elif card.card_id == 1662:  # Shadow-Weaver
            modifier = GameModifier(
                card_uid=id(card),
                modifier='shadow_weaver_caern'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: Ananasi agem como Gauntlet 1 Caern')

        # ── Presas com habilidades especiais (triggers de fim de combate/turno) ──

        elif card.card_id == 568:  # Wild Animals
            # Ataca maior Rage Wyrm no fim de cada Combat Phase
            # (processado em _check_victim_attacks)
            self.add_log(
                f'{card.name}: atacara maior Rage Wyrm no fim do combate')

        elif card.card_id == 565:  # Vigilante
            # Ataca quem matou a vitima de menor Renome
            # (processado em _check_victim_attacks)
            self.add_log(
                f'{card.name}: atacara quem matou a vitima mais fraca')

        elif card.card_id == 503:  # Mage of the Celestial Chorus
            # Remove menor Renome victim no fim do turno
            # (processado em _check_end_of_turn_effects)
            # Tambem pode usar ANY Gifts (registrado como modifier)
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_use_any_gift'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode usar ANY Gifts, '
                f'remove menor Renome victim no fim do turno')

        elif slug == 'fomori-cop_r5':  # Fomori Cop
            self.add_log(
                f'{card.name}: descarta equipamento nao-Fetish de Gaia '
                f'no fim do combate')
            # Pode receber restricao 'disarmed' se perder a Firearm
            # Se desarmado, Rage = 3 (afeta Restricted Play)

        elif card.card_id == 558:  # Unlucky Lune
            # Pode usar Auspice Gifts + Full Moon = Rage 6
            modifier = GameModifier(
                card_uid=id(card),
                modifier='can_use_auspice_gifts'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode usar Auspice Gifts, '
                f'Rage 6 com Full Moon')

        elif slug == 'hogling_r5':  # Hogling (496)
            # Imune a equipamentos nao-fetiche
            # (verificado em _processar_ataque por 'imune_equipamento_nao_fetich')
            if 'imune_equipamento_nao_fetich' not in card.restricoes:
                card.restricoes.append('imune_equipamento_nao_fetich')
            # Pode usar Gifts Metis
            modifier_name = 'can_use_metis_gifts'
            if not any(m.modifier == modifier_name
                       for m in self.game_modifiers):
                modifier = GameModifier(
                    card_uid=id(card),
                    modifier=modifier_name,
                )
                self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: imune a equipamentos nao-fetiche, '
                f'pode usar Gifts Metis')

        elif slug == 'carleson-ruah_r4':  # Carleson Ruah (4)
            # Carleson pode interromper a acao de outro alpha para
            # permitir que o alpha do seu pack aja primeiro, desde que
            # o alpha ataque uma criatura Wyrm.
            modifier = GameModifier(
                card_uid=id(card),
                modifier='carleson_ruah'
            )
            self.game_modifiers.append(modifier)
            self.add_log(
                f'{card.name}: pode interromper alpha para agir '
                f'primeiro vs Wyrm')

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
            elif t.condition == 'juicy_johnes':
                # Dispara quando a carta com o trigger MORRE
                if killed_card.card_id != trigger_card.card_id:
                    continue
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
            elif t.action.startswith('reduce_gnosis:'):
                # Reduz Gnosis do killer (ex: Juicy Johnes)
                quantidade = int(t.action.split(':', 1)[1].strip())
                if killer_player and killer_card:
                    killer_card.buff_gnosis -= quantidade
                    self.add_log(
                        f'{killer_card.name} perdeu {quantidade} Gnosis'
                        f' (trigger: {trigger_card.name})'
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

    # ------------------------------------------------------------------
    # Fases Lunares
    # ------------------------------------------------------------------

    def definir_lunar_phase(self, jogador_id: str, nome: str,
                             card_id: int = 0,
                             modelo_id: str = '',
                             card_uid: int = 0) -> bool:
        """Define a fase lunar ativa.

        Regra (Quickstart + 4.5.2.C):
        - Lunar Phases podem ser jogadas no inicio de qualquer turno
          (Redraw phase) ou para substituir a fase atual.
        - Apenas 1 fase lunar ativa por vez.
        - Fase anterior e descartada.

        Args:
            jogador_id: ID do jogador que jogou.
            nome: Nome da fase lunar.
            card_id: ID da carta Lunar Phase.
            modelo_id: ID do modelo de carta.
            card_uid: Python id() da instancia.

        Returns:
            True se foi definida.
        """
        descartada = ''
        if self.lunar_phase:
            descartada = self.lunar_phase.nome
            # Reverte Ragabash Gnosis bonus se a fase anterior era New Moon
            if self.lunar_phase.ragabash_gnosis_bonus:
                for p in self.players:
                    for c in p.pack_home + p.hunting_grounds + p.umbra:
                        keywords = (c.keywords or '').lower()
                        if 'ragabash' in keywords:
                            c.gnosis = max(0, c.gnosis - 1)
                self.add_log(
                    'Ragabash -1 Gnosis (New Moon substituida)')
            # Descarta a carta da fase lunar anterior do pack_home
            uid_antigo = self.lunar_phase.card_uid
            for p in self.players:
                for c in list(p.pack_home):
                    if id(c) == uid_antigo:
                        p.pack_home.remove(c)
                        c.zone = Zone.DISCARD_SEPT
                        p.discard_sept.append(c)
                        self.add_log(
                            f'{c.name} descartada (substituida por {nome})')
                        break
        self.lunar_phase = LunarPhaseState(
            card_id=card_id,
            nome=nome,
            dono_id=jogador_id,
            modelo_id=modelo_id,
            card_uid=card_uid,
        )
        if descartada:
            self.add_log(f'Fase Lunar {descartada} substituida por {nome}')
        else:
            self.add_log(f'Fase Lunar {nome} ativada')
        return True

    def remover_lunar_phase(self) -> Optional[str]:
        """Remove a fase lunar ativa (ex: Lunar Eclipse).

        Descarta a carta da fase lunar do pack_home do dono.

        Returns:
            Nome da fase removida, ou None se nao havia.
        """
        if not self.lunar_phase:
            return None
        nome = self.lunar_phase.nome
        uid_antigo = self.lunar_phase.card_uid
        # Reverte Ragabash Gnosis bonus se a fase removida era New Moon
        if self.lunar_phase.ragabash_gnosis_bonus:
            for p in self.players:
                for c in p.pack_home + p.hunting_grounds + p.umbra:
                    keywords = (c.keywords or '').lower()
                    if 'ragabash' in keywords:
                        c.gnosis = max(0, c.gnosis - 1)
            self.add_log(
                'Ragabash -1 Gnosis (New Moon removida)')
        # Descarta a carta da fase lunar
        for p in self.players:
            for c in list(p.pack_home):
                if id(c) == uid_antigo:
                    p.pack_home.remove(c)
                    c.zone = Zone.DISCARD_SEPT
                    p.discard_sept.append(c)
                    self.add_log(
                        f'{c.name} descartada (fase lunar removida)')
                    break
        self.lunar_phase = None
        self.add_log(f'Fase Lunar {nome} removida')
        return nome

    def chamar_moot(self, jogador_id: str, nome: str = 'Moot',
                     is_board_meeting: bool = False,
                     modelo_id: str = '',
                     card_uid: int = 0) -> bool:
        """Chama uma Junta (Moot ou Board Meeting).

        Regra (2.2.5):
        - So pode chamar 1 Junta por turno.
        - Personagem precisa Renown >= requisito (renown do card).
        - Gaia chama Moots, Wyrm chama Board Meetings.

        Args:
            jogador_id: ID do jogador que chamou.
            nome: Nome da Junta.
            is_board_meeting: True = Board Meeting, False = Moot.
            modelo_id: ID do modelo de carta (ex: 'card_1185').
            card_uid: Python id() da instancia real da carta.

        Returns:
            True se foi chamada.
        """
        if self.moot_atual and not self.moot_atual.resolvido:
            self.add_log(f'  Ja ha uma Junta em andamento')
            return False  # Ja tem uma Junta em andamento

        jogador = next((p for p in self.players if p.id == jogador_id), None)
        if not jogador:
            return False

        # Obtem renown e tipo da carta
        renown_min = 0
        ct_tipo = ''
        carta = self._find_card_by_uid(card_uid)
        if carta:
            renown_min = carta.renown or 0
            ct_tipo = (carta.card_type or '').lower()
        elif modelo_id:
            from rage_web.game_engine.effects import CARTAS_EXEMPLO
            modelo = CARTAS_EXEMPLO.get(modelo_id)
            if modelo:
                ct_tipo = (modelo.tipo or '').lower()

        if not ct_tipo:
            ct_tipo = 'moot' if 'moot' in nome.lower() else 'board meeting'

        # Valida Gaia vs Wyrm (reusa logica de combat_queue)
        from rage_web.game_engine.combat_queue import (_eh_pack_gaia,
                                                         _eh_pack_wyrm)
        chars = [c for c in jogador.pack_home
                 if 'character' in (c.card_type or '').lower()]
        if chars:
            eh_gaia = _eh_pack_gaia(jogador)
            eh_wyrm = _eh_pack_wyrm(jogador)

            if is_board_meeting:
                # Board Meeting: deve ser Wyrm OU neutro
                if eh_gaia and not eh_wyrm:
                    self.add_log(
                        f'{jogador.name}: pack Gaia nao pode chamar '
                        f'Board Meeting')
                    return False
            else:
                # Moot: deve ser Gaia OU neutro
                if eh_wyrm and not eh_gaia:
                    self.add_log(
                        f'{jogador.name}: pack Wyrm nao pode chamar Moot')
                    return False

        # Valida Renown minimo (se disponivel)
        if renown_min > 0:
            renown_jogador = sum(c.renown for c in jogador.pack_home
                                 if c.health_current > 0)
            if renown_jogador < renown_min:
                self.add_log(
                    f'{jogador.name}: Renown {renown_jogador} < '
                    f'{renown_min} necessario para {nome}')
                return False

        self.moot_atual = MootState(
            nome=nome,
            dono_id=jogador_id,
            is_board_meeting=is_board_meeting,
            modelo_id=modelo_id,
            card_uid=card_uid,
            renown_min=renown_min,
        )
        self.add_log(f'{jogador_id} chamou {nome} '
                     f'(Ren required: {renown_min})')
        return True

    def votar_moot(self, jogador_id: str, a_favor: bool) -> bool:
        """Vota na Junta atual com todo o Renome do jogador.

        Thousand Cubs (376): +2 Renome em Moots chamados por
        personagens de Renome menor.

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

        # Thousand Cubs: +2 Renome se votando em Moot de Renome menor
        motivo_bonus = ''
        for c in jogador.pack_home:
            if 'thousand_cubs_moot' in c.restricoes:
                # So se o dono da Junta tem Renome menor que o dela
                dono_moot = next(
                    (p for p in self.players
                     if p.id == self.moot_atual.dono_id), None)
                if dono_moot and dono_moot is not jogador:
                    renown_dono = sum(
                        cc.renown for cc in dono_moot.pack_home)
                    if renown_dono < c.renown:
                        renown_total += 2
                        motivo_bonus = f' (+2 Thousand Cubs)'
                        break

        self.moot_atual.votar(renown_total, a_favor)
        self.add_log(f'{jogador.name} votou {"SIM" if a_favor else "NAO"} '
                     f'com {renown_total} votos{motivo_bonus}')
        return True

    def resolver_moot(self) -> bool:
        """Resolve a votacao e aplica efeitos se aprovado."""
        if not self.moot_atual or self.moot_atual.resolvido:
            return False
        self.moot_atual.resolver()
        self.add_log(f'Junta {self.moot_atual.nome}: '
                     f'{self.moot_atual.resultado} '
                     f'({self.moot_atual.votos_sim} x {self.moot_atual.votos_nao})')

        # Se aprovado e tem modelo de carta, aplica os efeitos
        if self.moot_atual.aprovado and self.moot_atual.modelo_id:
            from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
            modelo = CARTAS_EXEMPLO.get(self.moot_atual.modelo_id)
            if modelo:
                card_origem = None
                for p in self.players:
                    for c in p.discard_sept:
                        if id(c) == self.moot_atual.card_uid:
                            card_origem = c
                            break
                aplicar_carta(self, modelo, self.moot_atual.dono_id,
                              modo_idx=0, card_origem=card_origem)

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

            duracao = pend.duracao
            if not isinstance(duracao, str):
                # Seguranca: se duracao nao for string (ex: int), ignora
                duracao = str(duracao)
            if duracao == 'end_of_turn' and fase_entrando == 'redraw':
                expirou = True
            elif duracao == 'end_of_combat' and fase_entrando != 'combat':
                expirou = True
            elif duracao == 'end_of_phase' and pend.fase_aplicada != fase_entrando:
                expirou = True
            elif duracao.startswith('after_'):
                # Formato: 'after_N_turns' - expira quando turno atual >= N
                try:
                    target_turn = int(duracao.split('_')[1])
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
                    elif pend.atributo == 'discard_gift':
                        # Descarta o Gift apos expiracao (ex: Patagia)
                        # Remove de attached_gifts se ainda estiver anexado
                        for p in self.players:
                            for zona_lista in (p.pack_home, p.hunting_grounds, p.umbra):
                                for criatura in zona_lista:
                                    if c in criatura.attached_gifts:
                                        criatura.attached_gifts.remove(c)
                                        log.append(
                                            f'{c.name} removido de '
                                            f'{criatura.name} (expiracao)')
                                        break
                        # Move para descarte
                        c.zone = Zone.DISCARD_SEPT
                        dono = self._find_player(c.owner_id)
                        if dono:
                            dono.discard_sept.append(c)
                        elif self.players:
                            self.players[0].discard_sept.append(c)
                        log.append(f'{c.name} descartado (fim do efeito)')
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
