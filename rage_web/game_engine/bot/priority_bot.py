"""Bot com arvore de decisao baseada em prioridades.

Arvore de decisao:
1. SOBREVIVER - Curar, bloquear, fugir
2. ELIMINAR AMEACA - Atacar maior threat
3. DESENVOLVER MESA - Jogar personagens, equipamentos
4. ATACAR - Buscar VP, atacar vulneravel
"""

from __future__ import annotations

import logging
from typing import Optional

from rage_web.game_engine.bot.evaluator import BoardEvaluator, TargetPrioritizer
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.combat_queue import (
    COMBAT_ACTIONS, can_feint, declare_action, end_combat,
    feint_action, get_combatants, reveal_all, resolve_combat,
    start_combat,
)
from rage_web.game_engine.state import CardInstance, GameState, PlayerState, Zone

logger = logging.getLogger(__name__)


class PriorityBot:
    """Bot que toma decisoes baseado em arvore de prioridades.

    Niveis de dificuldade:
        easy:   acoes aleatorias viaveis
        medium: heuristica simples (avaliador)
        hard:   arvore de decisao completa
    """

    def __init__(self, game: GameState, player_id: str,
                 difficulty: str = 'medium'):
        self.game = game
        self.player_id = player_id
        self.difficulty = difficulty
        self.evaluator = BoardEvaluator(game, player_id)
        self.prioritizer = TargetPrioritizer(game, player_id)
        # Heuristicas do bot
        self._cards_played_this_turn = 0
        self._umbra_agiu = False  # So uma acao de Umbra por fase
        self._feinted_ids = set()  # IDs que ja usaram Feint neste combate
        # Slow deck detection
        self._vp_history: list[float] = []  # VP total ao final de cada turno
        self._vp_rate: float = 0.0  # VP/turn medio
        # Ataques por fase de combate
        self._ataques_feitos: set[str] = set()

    @property
    def player(self) -> PlayerState:
        for p in self.game.players:
            if p.id == self.player_id:
                return p
        raise ValueError(f'Jogador {self.player_id} nao encontrado')

    # ------------------------------------------------------------------
    # Arvore de decisao principal
    # ------------------------------------------------------------------

    def decide(self) -> str:
        """Decide a proxima acao do bot.

        Regras:
        - Nao ha "contagem de acoes" ou "pool de acoes" no Rage.
        - Cada Combat Action tem custo de Rage (carta deve ter Rage suficiente).
        - Cada alfa tem uma acao alfa por combate.
        - Recursos (Equipment/Ally) gastam uma "acao" de um personagem.
        - O bot simplifica: faz o que faz sentido na fase atual.

        Returns:
            Descricao da acao escolhida.
        """
        if self.difficulty == 'easy':
            return self._decide_easy()

        g = self.game

        # Se o jogador foi eliminado, passa automaticamente
        if getattr(self.player, 'eliminado', False):
            self._pass_turn()
            return 'pass_eliminated'

        # Se esta em combate, age no combate
        if g.combat.is_active:
            return self._decide_combat()

        # Se nao e a vez do bot, passa
        if g.current_player.id != self.player_id:
            return 'wait'

        # Reseta heuristicas por turno
        if g.turn_number > getattr(self, '_last_turn_heuristic', 0):
            self._cards_played_this_turn = 0
            self._last_turn_heuristic = g.turn_number
            self._umbra_agiu = False
            self._ataques_feitos.clear()

        # --- Acoes por fase ---

        if g.phase == 'redraw':
            return self._agir_redraw()

        if g.phase == 'regeneration':
            # Atualiza historico de VP ao fim de cada turno
            if len(self._vp_history) < g.turn_number:
                self._vp_history.append(self.player.victory_points)
                if len(self._vp_history) >= 4:
                    ultimos = self._vp_history[-4:]
                    self._vp_rate = (ultimos[-1] - ultimos[0]) / len(ultimos)
            self._pass_turn()
            return 'pass_regen'

        if g.phase == 'resource':
            return self._agir_recurso()

        if g.phase == 'umbra':
            return self._agir_umbra()

        if g.phase == 'moot':
            return self._agir_moot()

        # Combat phase
        return self._agir_combate()

    def _is_slow_deck(self) -> bool:
        """Detecta se o deck esta progredindo devagar.

        Retorna True se a taxa de VP/turno estiver abaixo de 0.8
        apos o turno 5, indicando um deck de controle lento.
        """
        if self.game.turn_number <= 5:
            return False
        if len(self._vp_history) < 4:
            return False
        # VP rate = (VP atual - VP ha 3 turnos) / 3
        taxa = self._vp_rate
        return taxa < 0.8

    def _agir_recurso(self) -> str:
        """Age na fase de Resource.

        P7: Otimizacao da fase de Resource.
        Avalia cada carta por pontuacao estrategica:
        - Personagens tem prioridade maxima
        - Cartas que compram (card draw) sao jogadas PRIMEIRO
        - Buffs sao jogados DEPOIS dos personagens
        - Cartas sem alvo viavel sao ignoradas
        - Max 3 cartas por turno (preservar mao)
        """
        me = self.player

        if self._cards_played_this_turn >= 3:
            self._pass_turn()
            return 'pass_resource_limit'

        from rage_web.game_engine.rules import zona_da_carta

        # ── P7: Pontua cada carta viavel ──
        # Primeiro, identifica o que ja tem em jogo
        tem_character = any(
            'character' in (c.card_type or '').lower()
            for c in me.pack_home
        )
        tem_caern = any(
            (c.card_type or '') == 'Caern'
            for c in me.pack_home
        )
        tem_hg = bool(me.hunting_grounds)

        # TIPOS que NAO sao de recurso
        TIPOS_NAO_RECURSO = {'Combat Action', 'Combat Event', 'Moot', 'Board Meeting'}

        scored = []
        for i, card in enumerate(me.hand):
            ct = (card.card_type or '')
            if ct in TIPOS_NAO_RECURSO:
                continue

            score = 0
            zona = zona_da_carta(ct)

            # Nao joga se nao pode pagar
            if not self._pode_pagar_custos(card):
                score -= 50

            # 1. Character: prioridade maxima (precisa de combatentes)
            if ct == 'Character':
                score += 100
                if not tem_character:
                    score += 50  # Primeiro character e critico
                # Se ja tem personagens, ainda vale (mais = melhor)
                score += card.rage * 3 + card.gnosis * 2 + card.health * 2

            # 2. Card Draw (comprar cartas): jogar PRIMEIRO
            #    (identifica por efeito 'comprar' no modelo)
            elif card.modelo_id:
                from rage_web.game_engine.effects import CARTAS_EXEMPLO
                modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                if modelo and modelo.modos:
                    for modo in modelo.modos:
                        for efeito in (modo.efeitos or []):
                            if getattr(efeito, 'tipo', '') == 'comprar':
                                score += 80  # Card draw e sempre bom
                            elif getattr(efeito, 'tipo', '') in (
                                'modificar_atributo', 'modificar_rage',
                                'modificar_gnosis', 'inspiration',
                            ):
                                if tem_character:
                                    score += 60  # Buff util se tem chars
                                else:
                                    score -= 20  # Buff sem char e inutil

            # 3. Caern: alta prioridade se nao tem
            if ct == 'Caern':
                if not tem_caern:
                    score += 90
                else:
                    score += 30  # Segundo Caern ainda util
                from rage_web.game_engine.rules import pode_jogar_caern
                if not pode_jogar_caern(me, card, self.game):
                    score -= 100  # Unico por nome

            # 4. Hunting Grounds cards: uteis se nao tem alvos
            elif zona == 'hunting_grounds':
                score += 40
                if not tem_hg:
                    score += 30  # Precisa de alvos no HG
                # Verifica VP: Gaia nao ganha VP por Victim
                ct_lower = ct.lower()
                from rage_web.game_engine.combat_queue import _eh_pack_gaia
                if _eh_pack_gaia(me) and 'victim' in ct_lower:
                    score -= 20  # Gaia nao ganha VP por Victim
                from rage_web.game_engine.combat_queue import _eh_pack_wyrm
                if _eh_pack_wyrm(me) and 'enemy' in ct_lower:
                    score -= 20  # Wyrm nao ganha VP por Enemy

            # 5. Ally: util se tem personagens
            elif 'ally' in ct.lower() and zona == 'pack_home':
                from rage_web.game_engine.rules import pode_recrutar_ally
                if pode_recrutar_ally(me, card):
                    score += 50 if tem_character else 20
                else:
                    score -= 30  # Nao pode recrutar ainda

            # 6. Territory: util
            elif ct == 'Territory':
                score += 35

            # 7. Equipment: util se tem personagens para equipar
            elif 'equipment' in ct.lower():
                if tem_character:
                    # Verifica se tem alvo viavel
                    from rage_web.game_engine.effects import ResolvedorEfeitos
                    resolvedor = ResolvedorEfeitos(self.game)
                    tem_alvo = any(
                        resolvedor._validar_restricoes_equipamento(card, c)
                        for c in me.pack_home
                        if 'character' in (c.card_type or '').lower()
                    )
                    if tem_alvo:
                        score += 45
                    else:
                        score -= 30  # Nao tem quem equipe
                else:
                    score -= 20  # Equipment sem personagem e inutil

            # 8. Rite: util se tem personagens com Renown
            elif ct == 'Rite':
                from rage_web.game_engine.rules import (pode_usar_rite,
                                                         validar_timing_rite)
                if (validar_timing_rite(card, self.game.phase)
                    and pode_usar_rite(me, card)):
                    score += 40
                else:
                    score -= 20

            # 9. Quest / Past Life: util se tem personagens
            elif ct in ('Quest', 'Past Life'):
                if tem_character and card.modelo_id:
                    score += 30
                else:
                    score -= 10

            # 10. Gift / Event: util se tem personagens
            elif ct == 'Gift':
                if tem_character:
                    score += 35
                else:
                    score -= 10
            elif ct in ('Event', 'Action'):
                score += 20

            # 11. Cartas sem modelo_id: inuteis
            if not card.modelo_id and score < 50:
                score -= 30

            scored.append((i, score, card))

        # Ordena por pontuacao (melhores primeiro)
        scored.sort(key=lambda x: x[1], reverse=True)

        for i, score, card in scored:
            if score <= 0:
                continue  # Nao joga cartas com pontuacao negativa

            ct = (card.card_type or '')
            zona = zona_da_carta(ct)

            if ct == 'Character':
                self._play_card(i)
                self._cards_played_this_turn += 1
                return f'play_character_{card.card_id}'

            elif ct == 'Caern':
                from rage_web.game_engine.rules import pode_jogar_caern
                if pode_jogar_caern(me, card, self.game):
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_caern_{card.card_id}'

            elif zona == 'hunting_grounds':
                self._play_card(i)
                self._cards_played_this_turn += 1
                return f'play_hg_{card.card_id}'

            elif 'ally' in ct.lower() and zona == 'pack_home':
                from rage_web.game_engine.rules import pode_recrutar_ally
                if pode_recrutar_ally(me, card):
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_ally_{card.card_id}'

            elif ct in ('Territory',):
                self._play_card(i)
                self._cards_played_this_turn += 1
                return f'play_territory_{card.card_id}'

            elif 'equipment' in ct.lower():
                from rage_web.game_engine.effects import CARTAS_EXEMPLO
                if card.modelo_id:
                    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                    if modelo and modelo.modos:
                        tem_equipar = any(
                            e.tipo == 'equipar'
                            for modo in modelo.modos
                            for e in modo.efeitos
                        )
                        if tem_equipar:
                            modo_idx = self._escolher_melhor_modo(card.modelo_id)
                            self._cards_played_this_turn += 1
                            return self._usar_carta_efeito(i, modo_idx, card)
                self._play_card(i)
                self._cards_played_this_turn += 1
                return f'play_equipment_{card.card_id}'

            elif ct == 'Rite':
                from rage_web.game_engine.rules import (pode_usar_rite,
                                                         validar_timing_rite)
                if (validar_timing_rite(card, self.game.phase)
                    and pode_usar_rite(me, card)):
                    if card.modelo_id:
                        modo_idx = self._escolher_melhor_modo(card.modelo_id)
                        self._cards_played_this_turn += 1
                        return self._usar_carta_efeito(i, modo_idx, card)
                    else:
                        self._play_card(i)
                        self._cards_played_this_turn += 1
                        return f'play_rite_{card.card_id}'

            elif ct in ('Quest', 'Past Life'):
                if card.modelo_id:
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    self._cards_played_this_turn += 1
                    return self._usar_carta_efeito(i, modo_idx, card)

            elif ct in ('Gift', 'Event', 'Action'):
                # Usa via efeito
                if card.modelo_id:
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    self._cards_played_this_turn += 1
                    return self._usar_carta_efeito(i, modo_idx, card)
                else:
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_{ct.lower()}_{card.card_id}'

        self._pass_turn()
        return 'pass_resource_no_valid_card'

        # 4.5 Joga Eventos / Totems (permanecem em jogo, efeitos globais)
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            if ct == 'Event' and card.modelo_id:
                if self._pode_pagar_custos(card):
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    self._cards_played_this_turn += 1
                    return self._usar_carta_efeito(i, modo_idx, card)

        # 5. Tenta jogar efeitos de Gifts/Events/Actions
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            eh_hg = zona_da_carta(ct) == 'hunting_grounds'
            eh_ally = ('Ally' in ct and zona_da_carta(ct) == 'pack_home')
            eh_recurso = (ct in ('Equipment', 'Territory', 'Caern',
                                  'Equipment - Fetish - Bane Fetish')
                          or eh_ally or eh_hg)
            if (card.modelo_id
                and card.card_type not in TIPOS_NAO_RECURSO
                and not eh_recurso):
                if self._pode_pagar_custos(card):
                    from rage_web.game_engine.effects import CARTAS_EXEMPLO
                    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                    if modelo and modelo.modos:
                        modo = modelo.modos[0]
                        if modo.efeitos:
                            tem_stub = any(
                                e.tipo in TIPOS_STUB for e in modo.efeitos)
                            if not tem_stub:
                                modo_idx = self._escolher_melhor_modo(card.modelo_id)
                                self._cards_played_this_turn += 1
                                return self._usar_carta_efeito(i, modo_idx, card)

        self._pass_turn()
        return 'pass_resource'

    def _agir_redraw(self) -> str:
        """Age na fase de Redraw: descartar + comprar.

        Regra (2.2.2):
        - Primeiro turno: mao inicial ja foi comprada.
        - Turnos seguintes: descarte opcional + compra ate encher.

        P6: Redraw seletivo — avalia cada carta por:
        - Utilidade (tem modelo_id, tipo, custo)
        - Redundancia (ja tem carta similar no pack)
        - Custo beneficio (carta cara sem personagem pra pagar)
        - Sempre descarta as PIORES primeiro.
        """
        if self.game.turn_number == 1 and self.player.is_first_turn:
            self._pass_turn()
            return 'pass_redraw'

        me = self.player

        # Tenta jogar uma Fase Lunar (se tiver na mao)
        # (feito ANTES do descarte para garantir que cartas
        #  de Fase Lunar nao sao descartadas)
        LUNAR_CARDS = {834, 854, 865, 869, 884, 890, 897}
        for i, card in enumerate(me.hand):
            if card.card_id in LUNAR_CARDS:
                if (self.game.lunar_phase
                    and self.game.lunar_phase.card_id == 884):
                    break
                if card.card_id == 884 and self.game.lunar_phase:
                    removida = self.game.remover_lunar_phase()
                    return 'redraw_lunar_eclipse'
                if card.card_id == 884 and not self.game.lunar_phase:
                    card.zone = Zone.DISCARD_SEPT
                    me.discard_sept.append(me.hand.pop(i))
                    return 'redraw_lunar_eclipse'
                if card.card_id == 897:
                    self._play_card(i)
                    return 'redraw_phoebe'
                modelo_id = card.modelo_id or ''
                self.game.definir_lunar_phase(
                    jogador_id=self.player_id,
                    nome=card.name,
                    card_id=card.card_id,
                    modelo_id=modelo_id,
                    card_uid=id(card),
                )
                card.zone = Zone.PACK_HOME
                me.pack_home.append(me.hand.pop(i))
                if modelo_id:
                    from rage_web.game_engine.effects import (CARTAS_EXEMPLO,
                                                                aplicar_carta)
                    modelo = CARTAS_EXEMPLO.get(modelo_id)
                    if modelo:
                        modo_idx = self._escolher_melhor_modo(modelo_id)
                        aplicar_carta(self.game, modelo, self.player_id,
                                      modo_idx=modo_idx, card_origem=card)
                return f'redraw_lunar_{card.card_id}'

        # P6: Pontua cada carta para decidir o que descartar
        # ---------------------------------------------------
        PONTOS_MODELO_ID = 50
        PONTOS_PERSONAGEM = 40
        PONTOS_CAERN_TERRITORIO = 30
        PONTOS_EQUIPAMENTO = 20
        PONTOS_EFEITO_VIAVEL = 15
        PONTOS_DUPLICATA = -20
        PONTOS_SEM_EFEITO = -30
        PONTOS_LIXO = -100

        # IDs de cartas que sao totems permanentes
        TOTEM_IDS_LOCAL = {214, 215, 817, 818, 821, 824, 826, 830, 836, 838,
                           850, 852, 855, 867, 868, 872, 877, 880, 892, 895,
                           897, 900, 909, 912, 914, 918, 920, 1633}

        # Cartas que ja estao em jogo (pack, hg, umbra)
        cartas_em_jogo = set()
        for c in me.pack_home + me.hunting_grounds + me.umbra:
            cartas_em_jogo.add(c.card_id)

        scored_cards = []
        for i, c in enumerate(me.hand):
            score = 0
            ct = (c.card_type or '')

            # Cartas que sao de combate: nao descartar
            if ct in ('Combat Action', 'Combat Event'):
                score += PONTOS_MODELO_ID + 30
            else:
                # Cartas de sept
                if c.modelo_id:
                    score += PONTOS_MODELO_ID  # Tem efeito definido
                else:
                    score += PONTOS_SEM_EFEITO  # Carta inutil

                # Tipo de carta
                if 'character' in ct.lower():
                    score += PONTOS_PERSONAGEM
                elif ct in ('Caern', 'Territory'):
                    score += PONTOS_CAERN_TERRITORIO
                elif 'equipment' in ct.lower():
                    score += PONTOS_EQUIPAMENTO

                # Totems permanentes: nunca descartar
                if c.card_id in TOTEM_IDS_LOCAL:
                    score += 80

                # Duplicata: ja tem uma igual em jogo
                if c.card_id in cartas_em_jogo:
                    score += PONTOS_DUPLICATA

                # Carta sem stats uteis (tudo 0)
                if (c.rage == 0 and c.gnosis == 0 and c.health == 0
                    and not c.modelo_id):
                    score += PONTOS_LIXO

                # Carta cara sem personagem para pagar
                if c.gnosis > 0:
                    tem_pagador = any(
                        p.gnosis >= c.gnosis
                        for p in me.pack_home
                    )
                    if not tem_pagador:
                        score -= 15

            scored_cards.append((i, score, c))

        # Ordena por pontuacao (piores primeiro)
        scored_cards.sort(key=lambda x: x[1])

        # Indices para descartar: piores cartas, enquanto mao estiver cheia
        sept_count = len(me._cartas_sept())
        descartar_indices = []
        for i, score, c in scored_cards:
            # Nao descarta cartas de combate
            if c.card_type in ('Combat Action', 'Combat Event'):
                continue
            # So descarta se mao estiver cheia ou carta for ruim
            if sept_count > me.hand_size_sept or score < 0:
                descartar_indices.append(i)
                sept_count -= 1
                if sept_count <= me.hand_size_sept and score >= 0:
                    break  # Ja tem espaco, para de descartar boas cartas

        if descartar_indices:
            descartadas = me.descartar_da_mao(descartar_indices)
            self.game.add_log(
                f'[BOT] {me.name} descartou {len(descartadas)} carta(s) '
                f'(redraw seletivo)')
            drawn = me.redraw_sept(descartar_primeiro=False)
            if drawn:
                self.game.add_log(
                    f'[BOT] {me.name} comprou {len(drawn)} carta(s) de sept')
            return f'redraw_descarte_{len(descartadas)}'

        self._pass_turn()
        return 'pass_redraw'

    # ── Tags/chaves que indicam utilidade na Umbra ──
    _UMBRA_TAGS = {
        'umbra', 'umbra-synergy', 'umbra-regen', 'umbral',
        'spirit', 'class-spirit', 'sideways',
    }
    _UMBRA_TIPO = {
        'class-spirit',  # Criaturas espirituais existem em ambos mundos
    }

    @staticmethod
    def _carta_tem_utilidade_umbra(card) -> bool:
        """Verifica se uma carta tem utilidade na Umbra.

        Analisa tags, tipo e texto da carta para detectar
        se ela e mais eficaz ou so funciona na Umbra.
        """
        # Tags explicitas
        tags = (card.tags or '').lower()
        for kw in PriorityBot._UMBRA_TAGS:
            if kw in tags:
                return True
        # Tipo espiritual
        tipo = (card.card_type or '').lower()
        for kw in PriorityBot._UMBRA_TIPO:
            if kw in tipo:
                return True
        # Texto da carta
        texto = (card.text or '').lower()
        if 'umbra' in texto:
            return True
        return False

    def _pontuacao_utilidade_umbra(self) -> int:
        """Calcula pontuacao de utilidade na Umbra baseada na mao.

        Retorna 0-5: quantas cartas uteis na Umbra o bot tem na mao.
        Usado para decidir se vale a pena entrar na Umbra.
        """
        score = 0
        for card in self.player.hand:
            if self._carta_tem_utilidade_umbra(card):
                score += 1
        return score

    def _oponente_pode_seguir_umbra(self) -> bool:
        """Verifica se algum oponente pode seguir para a Umbra.

        Se NENHUM oponente tem Caern + personagem com Gnosis alta,
        entrar na Umbra e uma vantagem enorme (ataque unilateral).
        """
        for p in self.game.players:
            if p.id == self.player_id:
                continue
            from rage_web.game_engine.rules import encontrar_caern, GAUNTLET_DEFAULT
            caern = encontrar_caern(p)
            if caern is None:
                continue  # Sem Caern, nao pode seguir
            gauntlet = getattr(caern, 'damage', GAUNTLET_DEFAULT)
            try:
                gauntlet = int(gauntlet) if gauntlet else GAUNTLET_DEFAULT
            except (ValueError, TypeError):
                gauntlet = GAUNTLET_DEFAULT
            # Tem personagem com Gnosis >= Gauntlet?
            for c in p.pack_home:
                if 'Character' in (c.card_type or '') and c.gnosis >= gauntlet:
                    return True  # Este oponente PODE seguir
        return False

    def _agir_umbra(self) -> str:
        """Age na fase de Umbra: stepping sideways.

        Regra (2.2.4):
        - Character so pode step usando Caern no pack OU card ability.
        - Step simultaneo em Closed Play.
        - Um personagem nao pode entrar E sair na mesma fase.

        Estrategia:
        1. Se tem carta util na Umbra na mao, prioriza entrar.
        2. Se oponente nao pode seguir, prioriza entrar (vantagem).
        3. Volta personagens uteis para combate se precisar.
        4. Alpha fica no Pack Home se possivel.
        5. Uma acao por fase (entrar OU sair, nunca ambos).
        """
        podem_ir, podem_voltar = self.player.personagens_que_podem_step()

        # Regra: UMA acao de Umbra por fase (Closed Play simultaneo)
        if getattr(self, '_umbra_agiu', False):
            self._pass_turn()
            return 'pass_umbra'
        self._umbra_agiu = True

        utilidade_umbra = self._pontuacao_utilidade_umbra()
        oponente_pode_seguir = self._oponente_pode_seguir_umbra()

        # ── Se tem personagens na Umbra, decide se volta ──
        if self.player.umbra:
            # Identifica quem seria o alpha (maior poder de combate no pack)
            candidatos_alpha = [
                c for c in self.player.pack_home
                if 'Character' in (c.card_type or '') or 'Ally' in (c.card_type or '')
            ]
            possivel_alpha_id = None
            if candidatos_alpha:
                possivel_alpha = max(candidatos_alpha,
                                     key=lambda c: c.effective_rage * c.effective_health)
                possivel_alpha_id = str(possivel_alpha.card_id)

            # Traz o alpha se ele estiver na Umbra
            for c in self.player.umbra[:]:
                if str(c.card_id) == possivel_alpha_id and c.rage >= 1:
                    self.player.step_back(c)
                    self.game.add_log(
                        f'[BOT] {self.player.name}: {c.name} '
                        f'voltou da Umbra (alpha prioritario)')
                    return f'umbra_back_{c.card_id}'

            # Se oponente NAO pode seguir, combate sera no mundo fisico.
            # Melhor trazer combatentes com Rage >= 3.
            if not oponente_pode_seguir:
                for c in self.player.umbra[:]:
                    if c.rage >= 3:
                        self.player.step_back(c)
                        self.game.add_log(
                            f'[BOT] {self.player.name}: {c.name} '
                            f'voltou da Umbra (combatente)')
                        return f'umbra_back_{c.card_id}'

            self._pass_turn()
            return 'pass_umbra'

        # ── Decidir se vale a pena entrar ──
        # Prioridade: utilidade na mao (0-5) * 2 + vantagem vs oponente
        # Se nao tem carta util E oponente pode seguir: baixa prioridade
        if utilidade_umbra == 0 and oponente_pode_seguir:
            self._pass_turn()
            return 'pass_umbra'

        if podem_ir:
            # Quem enviar?
            candidatos_alpha = [
                c for c in self.player.pack_home
                if 'Character' in (c.card_type or '') or 'Ally' in (c.card_type or '')
            ]
            possivel_alpha_id = None
            if candidatos_alpha:
                possivel_alpha = max(candidatos_alpha,
                                     key=lambda c: c.effective_rage * c.effective_health)
                possivel_alpha_id = str(possivel_alpha.card_id)

            # Filtra quem enviar: prioriza Gnosis alta, evita alpha
            if possivel_alpha_id:
                personagens_sem_alpha = [
                    c for c in podem_ir
                    if str(c.card_id) != possivel_alpha_id
                ]
            else:
                personagens_sem_alpha = podem_ir

            if personagens_sem_alpha:
                personagem = max(personagens_sem_alpha,
                                 key=lambda c: c.gnosis)
            else:
                # So tem alpha disponivel
                if oponente_pode_seguir:
                    # Oponente segue — alpha precisa estar no pack
                    self._pass_turn()
                    return 'pass_umbra'
                personagem = max(podem_ir, key=lambda c: c.gnosis)

            self.player.step_sideways(personagem)
            self.game.add_log(
                f'[BOT] {self.player.name}: {personagem.name} '
                f'entrou na Umbra'
                + (' (vantagem: oponente nao segue)' if not oponente_pode_seguir else '')
                + (f' (+{utilidade_umbra} cartas uteis)' if utilidade_umbra else ''))
            return f'umbra_step_{personagem.card_id}'

        self._pass_turn()
        return 'pass_umbra'

    def _agir_moot(self) -> str:
        """Age na fase de Moot: votar em Juntas.

        Regra (2.2.5):
        - Personagens tem votos = Renome.
        - Votacao em ordem de Renome.
        - Se aprovado, resolve imediatamente.

        Caern of the Crescent Moon (582): pode dobrar Renown de um
        membro do pack durante Moot. Esse membro nao pode ser alpha
        no combate seguinte.
        """
        g = self.game

        # Ativa Caern of the Crescent Moon se disponivel
        if g.has_modifier('crescent_moon_caern'):
            self._ativar_crescent_moon_moot()

        # Se tem uma Junta ativa, vota
        if g.moot_atual and not g.moot_atual.resolvido:
            # Estrategia de voto para N jogadores:
            # - SIM se for propria junta
            # - SIM se for de oponente que NAO e o lider (alianca implicita)
            #   (assume que nao-lideres estao mirando no lider)
            # - NAO se for do lider ou de oponente qualquer
            a_favor = self._moot_voto_estrategico(g.moot_atual)
            g.votar_moot(self.player_id, a_favor=a_favor)
            g.resolver_moot()
            return f'moot_voto_{g.moot_atual.nome}'

        # Tenta chamar uma Junta (Moot ou Board Meeting)
        for i, card in enumerate(self.player.hand):
            ct = (card.card_type or '').lower()
            if ct in ('moot', 'board meeting'):
                is_board = (ct == 'board meeting')
                modelo_id = card.modelo_id or ''
                g.chamar_moot(self.player_id, nome=card.name,
                              modelo_id=modelo_id, card_uid=id(card),
                              is_board_meeting=is_board)
                card.zone = Zone.DISCARD_SEPT
                self.player.discard_sept.append(
                    self.player.hand.pop(i))
                return f'moot_chamar_{card.name}'

        self._pass_turn()
        return 'pass_moot'

    def _ativar_crescent_moon_moot(self):
        """Ativa Caern of the Crescent Moon (582): dobra Renown de
        um membro do pack durante Moot. Esse membro nao pode ser
        alpha no combate seguinte.

        Salva o Renown original em game.combat_triggers para
        restauracao ao fim do turno.
        """
        me = self.player
        # Verifica se o Caern esta no pack
        tem_caern = any(
            c.card_id == 582
            for c in me.pack_home + me.hunting_grounds
        )
        if not tem_caern:
            return

        # Ja ativou este turno?
        if self.game.combat_triggers.get('crescent_moon_used'):
            return

        # Escolhe o personagem com maior Renown para dobrar
        chars = [c for c in me.pack_home if c.health_current > 0]
        if not chars:
            return

        alvo = max(chars, key=lambda c: c.renown)
        if alvo.renown == 0:
            return  # Nao dobra Renown 0

        renown_original = alvo.renown
        alvo.renown *= 2
        # Marca para nao poder ser alpha no proximo combate
        if 'nao_pode_ser_alpha' not in alvo.restricoes:
            alvo.restricoes.append('nao_pode_ser_alpha')

        # Salva para restauracao
        self.game.combat_triggers['crescent_moon_used'] = True
        self.game.combat_triggers['crescent_moon_restore'] = {
            'player_id': me.id,
            'card_id': alvo.card_id,
            'renown_original': renown_original,
        }

        self.game.add_log(
            f'[Caern] Lua Crescente: Renown de {alvo.name} '
            f'dobrado ({renown_original} -> {alvo.renown}) '
            f'para Moot. Nao podera ser Alpha no combate.')

    def _agir_combate(self) -> str:
        """Age na fase de Combat: acao alfa + cartas + atacar."""
        me = self.player
        g = self.game
        lento = self._is_slow_deck()

        # ── ACAO ALFA ──
        alfa_atual = g.combat.current_alpha
        meu_alpha = g.combat.alphas.get(self.player_id)

        if alfa_atual and meu_alpha and alfa_atual == meu_alpha:
            action = self._agir_alpha()
            if action:
                g.combat.current_alpha_index += 1
                return action
            # Alpha nao pode agir (sem alvos, etc) — avanca o index
            # para evitar loop infinito no match.py
            g.combat.current_alpha_index += 1

        # ── RESTO DO COMBATE (cartas, eliminar, atacar) ──
        # Se o combate esta ativo, declarar acoes de combate
        if g.combat.is_active:
            return self._decide_combat()

        # Acoes de ataque/eliminar sempre sao permitidas (sem limite).
        # So jogar cartas da mao tem limite de 3 por turno.

        # Se deck lento, inverte prioridades: atacar > sobreviver
        if lento:
            # Lento: eliminar > atacar > sobreviver
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action

        # 1. SOBREVIVER
        action = self._try_survive()
        if action:
            return action

        # 2. Usar cartas de efeito (limite 3)
        if self._cards_played_this_turn < 3:
            for i, card in enumerate(me.hand):
                if card.modelo_id and card.card_type:
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    if self._pode_pagar_custos(card):
                        self._cards_played_this_turn += 1
                        return self._usar_carta_efeito(i, modo_idx, card)

        # 3. Outros efeitos (limite 3)
        if self._cards_played_this_turn < 3:
            action = self._try_develop_board()
            if action:
                self._cards_played_this_turn += 1
                return action

        # 3.5 GIFTS PARA PRESA (se nao for o atacante)
        if self._cards_played_this_turn < 3:
            action = self._try_prey_gift()
            if action:
                self._cards_played_this_turn += 1
                return action

        # 4. ELIMINAR AMEACA (sempre permitido)
        if not lento:
            action = self._try_eliminate_threat()
            if action:
                return action

            # 5. ATACAR (sempre permitido)
            action = self._try_attack()
            if action:
                return action

        # Tenta cartas genéricas se ainda nao passou
        if self._cards_played_this_turn < 3:
            for i, card in enumerate(me.hand):
                ct = card.card_type or ''
                eh_recurso = ct in ('Character', 'Equipment', 'Territory',
                                    'Caern')
                if (card.modelo_id
                    and ct not in ('Combat Action', 'Combat Event',
                                   'Combat Action', 'Moot',
                                   'Board Meeting')
                    and not eh_recurso):
                    if self._pode_pagar_custos(card):
                        from rage_web.game_engine.effects import CARTAS_EXEMPLO
                        modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                        if modelo and modelo.modos:
                            modo_idx = self._escolher_melhor_modo(card.modelo_id)
                            self._cards_played_this_turn += 1
                            return self._usar_carta_efeito(i, modo_idx, card)

        # 6. Passa
        self._pass_turn()
        return 'pass_combat'

    def _agir_combat_fallback(self) -> str:
        """Fallback quando alpha ja avancou — so ataca/passa."""
        action = self._try_eliminate_threat()
        if action:
            return action
        action = self._try_attack()
        if action:
            return action
        self._pass_turn()
        return 'pass_combat'

    def _agir_combat_fallback(self) -> str:
        """Fallback quando alpha ja avancou — so ataca/passa."""
        action = self._try_eliminate_threat()
        if action:
            return action
        action = self._try_attack()
        if action:
            return action
        self._pass_turn()
        return 'pass_combat'

    def _get_opponents(self) -> list[PlayerState]:
        """Retorna todos os oponentes (N players).

        Regra 2.3: jogadores eliminados nao sao considerados oponentes.
        """
        return [p for p in self.game.players
                if p.id != self.player_id and not p.eliminado]

    def _moot_voto_estrategico(self, moot) -> bool:
        """Decide o voto em Moot baseado em estrategia para N jogadores.

        Returns:
            True se vota a favor, False se contra.
        """
        # Propria junta: sempre a favor
        if moot.dono_id == self.player_id:
            return True

        # Encontra o lider (maior VP) entre todos os jogadores
        lider = max(self.game.players,
                    key=lambda p: p.victory_points / max(p.renown_level, 1))

        # Se o dono da junta NAO e o lider, e o lider nao e o proprio bot,
        # vota SIM (alianca implicita contra o lider)
        if moot.dono_id != lider.id and lider.id != self.player_id:
            return True

        # Cenario padrao: vota contra
        return False

    def _agir_alpha(self) -> Optional[str]:
        """Acao alfa: o alpha do jogador age.

        Com N jogadores, prioriza alphas de oponentes
        com mais VP (alianca implicita contra o lider).
        So podem ser alpha Characters e Allies.
        """
        me = self.player
        opponents = self._get_opponents()
        meu_alpha_id = self.game.combat.alphas.get(self.player_id)
        if not meu_alpha_id:
            return None

        alpha_card = None
        for c in me.pack_home:
            if str(c.card_id) == meu_alpha_id:
                alpha_card = c
                break

        if not alpha_card:
            return None
        if not self._pode_atacar(alpha_card):
            return None

        from rage_web.game_engine.combat_queue import start_combat

        # Marca que este alpha vai atacar (evita loop infinito)
        self._ataques_feitos.add(meu_alpha_id)

        # Avalia se estrategicamente e melhor atacar Presa agora
        alvo_hg = self._melhor_alvo_hg()
        deve_atacar_presa = self._deve_atacar_presa_estrategicamente(
            alpha_card, alvo_hg)

        if deve_atacar_presa and alvo_hg:
            # Ataca Presa direto (pula inimigos)
            start_combat(self.game, [meu_alpha_id],
                         [str(alvo_hg.card_id)])
            self.game.add_log(
                f'[BOT] Alpha {alpha_card.name} atacou '
                f'{alvo_hg.name} no Hunting Grounds (estrategico)')
            return f'alpha_attack_hg_{meu_alpha_id}'

        # 1. Tenta desafiar nao-alfa de alto valor (6.5.2)
        # P1: Antes de desafiar, calcula chance de aceitacao
        # (so desafia se prob >= 50% e threat alto)
        from rage_web.game_engine.combat_queue import _tentar_desafio
        melhores_nao_alfa = []
        for opp in opponents:
            for c in opp.pack_home:
                if c.health_current <= 0:
                    continue
                if str(c.card_id) in self.game.combat.alphas.values():
                    continue  # so nao-alfa
                ct = (c.card_type or '').lower()
                if not any(t in ct for t in ('character', 'ally')):
                    continue
                if not self.prioritizer.pode_eliminar(alpha_card, c):
                    continue
                threat = self.prioritizer.rate_threat(c)
                melhores_nao_alfa.append((c, threat, opp))

        desafio_tentado = False
        if melhores_nao_alfa:
            melhores_nao_alfa.sort(key=lambda x: x[1], reverse=True)
            melhor_c, melhor_threat, melhor_opp = melhores_nao_alfa[0]
            if melhor_threat > 0:
                # P1: calcula chance de aceitacao ANTES de desafiar
                prob_aceita = self._calcular_chance_aceitacao_desafio(
                    alpha_card, melhor_c)
                if prob_aceita >= 0.5:
                    desafio_tentado = True
                    aceito = _tentar_desafio(
                        self.game, meu_alpha_id, str(melhor_c.card_id))
                    if aceito:
                        self.game.add_log(
                            f'[BOT] Alpha {alpha_card.name} desafiou '
                            f'{melhor_c.name} ({melhor_opp.name})')
                        return f'alpha_challenge_{meu_alpha_id}'
                    else:
                        # P2: recusado -> NAO termina acao alpha.
                        # Cai para ataque direto (alpha ou criatura).
                        self.game.add_log(
                            f'[BOT] Alpha {alpha_card.name} desafiou '
                            f'{melhor_c.name}, mas foi RECUSADO. '
                            'Segue para ataque direto...')
                else:
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} ignorou '
                        f'{melhor_c.name} (chance de aceitar desafio: '
                        f'{prob_aceita:.0%} — muito baixa). '
                        'Segue para ataque direto...')

        # P2: Se desafio nao foi tentado ou foi recusado,
        # cai para ataque direto em vez de terminar a acao alpha.
        # (Regra 6.5.2: desafio recusado encerra acao alpha,
        #  mas ataque direto NAO e desafio — inicia combate normal)

        # 2. Tenta atacar alpha inimigo (prioriza lider em VP)
        alphas_inimigos = []
        for pid, cid in self.game.combat.alphas.items():
            if pid != self.player_id:
                for opp in opponents:
                    if opp.id == pid:
                        for c in opp.pack_home:
                            if str(c.card_id) == cid:
                                alphas_inimigos.append((opp, c))
                                break

        # Ordena por VP do dono (maior primeiro = lider)
        alphas_inimigos.sort(
            key=lambda x: x[0].victory_points / max(x[0].renown_level, 1),
            reverse=True)

        for opp, alpha_inimigo in alphas_inimigos:
            if (alpha_inimigo.health_current > 0
                    and self.prioritizer.pode_eliminar(alpha_card,
                                                       alpha_inimigo)):
                start_combat(self.game, [meu_alpha_id],
                             [str(alpha_inimigo.card_id)])
                self.game.add_log(
                    f'[BOT] Alpha {alpha_card.name} atacou alpha '
                    f'{alpha_inimigo.name} ({opp.name})')
                return f'alpha_attack_alpha_{meu_alpha_id}'

        # 2. Agrega ameacas de TODOS os oponentes, ordenadas por
        #    threat rating (que ja inclui VP weight)
        todas_ameacas = []
        for opp in opponents:
            for c in opp.pack_home:
                if c.health_current > 0:
                    todas_ameacas.append(c)

        if todas_ameacas:
            ameacas = sorted(todas_ameacas,
                             key=self.prioritizer.rate_threat,
                             reverse=True)
            for alvo in ameacas:
                if self.prioritizer.pode_eliminar(alpha_card, alvo):
                    start_combat(self.game, [meu_alpha_id],
                                 [str(alvo.card_id)])
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'{alvo.name}')
                    return f'alpha_attack_{meu_alpha_id}_vs_{alvo.card_id}'

        # 3. Tenta atacar Territory inimigo (6.5.4)
        for opp in opponents:
            for c in opp.pack_home:
                ct = (c.card_type or '').lower()
                if 'territory' in ct or 'realm' in ct:
                    start_combat(self.game, [meu_alpha_id],
                                 [str(c.card_id)],
                                 attack_type='territory',
                                 target_card_id=str(c.card_id))
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'Territory {c.name} ({opp.name})')
                    return f'alpha_attack_territory_{meu_alpha_id}'

        # 4. Tenta atacar Battlefield inimigo (6.5.3)
        for opp in opponents:
            for c in opp.pack_home + opp.hunting_grounds:
                ct = (c.card_type or '').lower()
                if 'battlefield' in ct:
                    start_combat(self.game, [meu_alpha_id],
                                 [str(c.card_id)],
                                 attack_type='battlefield',
                                 target_card_id=str(c.card_id))
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'Battlefield {c.name} ({opp.name})')
                    return f'alpha_attack_battlefield_{meu_alpha_id}'

        # 5. Tenta vincular Spirit no Hunting Grounds (6.5.5)
        # So disponivel se o alpha esta na Umbra
        if alpha_card.zone == Zone.UMBRA:
            for opp in opponents:
                for c in opp.hunting_grounds:
                    ct = (c.card_type or '').lower()
                    if 'spirit' in ct:
                        # Spirit no HG pode ser vinculado
                        start_combat(self.game, [meu_alpha_id],
                                     [str(c.card_id)],
                                     attack_type='bind',
                                     target_card_id=str(c.card_id))
                        self.game.add_log(
                            f'[BOT] Alpha {alpha_card.name} tentou '
                            f'vincular Spirit {c.name} ({opp.name})')
                        return f'alpha_attack_bind_{meu_alpha_id}'

        # 6. Fallback: ataca Presa no Hunting Grounds
        if alvo_hg:
            start_combat(self.game, [meu_alpha_id], [str(alvo_hg.card_id)])
            self.game.add_log(
                f'[BOT] Alpha {alpha_card.name} atacou '
                '{alvo_hg.name} no Hunting Grounds')
            return f'alpha_attack_hg_{meu_alpha_id}'
        return None

    def _decide_easy(self) -> str:
        """Modo facil: acoes aleatorias."""
        g = self.game
        if g.combat.is_active:
            return self._decide_combat_random()

        if g.current_player.id != self.player_id:
            return 'wait'

        actions = []
        if self.player.hand:
            actions.append('play')
        if self.player.pack_home:
            actions.append('attack')
        if self.player.deck_combat:
            actions.append('draw')
        actions.append('pass')

        choice = self.game.rng.choice(actions)
        if choice == 'play':
            idx = self.game.rng.randrange(len(self.player.hand))
            self._play_card(idx)
            return f'play_{idx}'
        elif choice == 'attack':
            # Modo facil: alpha ataca um alvo no HG se houver
            meu_alpha_id = self.game.combat.alphas.get(self.player_id)
            alvo_hg = self._melhor_alvo_hg()
            if meu_alpha_id and alvo_hg:
                start_combat(self.game, [meu_alpha_id],
                             [str(alvo_hg.card_id)])
                return f'attack_{meu_alpha_id}'
        elif choice == 'draw':
            self._draw()
            return 'draw'

        self._pass_turn()
        return 'pass'

    def _decide_combat(self) -> str:
        """Age durante o combate.

        Suporta tanto steps antigos (declare, reveal, resolve, end)
        quanto novos (declaration, play_card, targeting, reveal,
        bluff, resolution, withdrawal, between_rounds).

        Regra (4.4.2): qualquer jogador exceto o atacante pode declarar
        acoes de combate por uma Presa (Victim/Enemy/Battlefield) no HG.
        """
        from rage_web.game_engine.combat_queue import _find_card, \
            _eh_prey_no_hg, _eh_atacante_da_presa, advance_combat_step

        g = self.game
        step = g.combat.step

        # ---- NOVOS STEPS ----

        if step == 'declaration':
            # Declaration Step: ja foi configurado em start_combat
            # Avanca para pre_combat
            advance_combat_step(g)
            return 'combat_progress'

        if step in ('pre_combat', 'beginning_of_combat'):
            # Auto-advance (sem pack actions por enquanto)
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'play_card':
            # Play Card Step: jogar combat cards face-down
            # (mesma logica do antigo 'declare')
            self._feinted_ids.clear()
            all_cids = get_combatants(g)
            for cid in all_cids:
                if cid in g.combat.played_cards:
                    continue

                card = _find_card(g, cid)
                if card:
                    if card.owner_id != self.player_id:
                        continue
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue

                    # 6.6.6c: Random Play — escolhe carta aleatoria
                    # da mao de combate do jogador.
                    if g.combat.has_random_play(cid):
                        mao_combate = self.player.combat_hand
                        if mao_combate:
                            carta_rand = g.rng.choice(mao_combate)
                            # Tenta usar o nome da carta como acao
                            nome_acao = (carta_rand.name or '').lower().replace(' ', '_')
                            # Mapeia nomes de cartas para acoes conhecidas
                            from rage_web.game_engine.combat_queue import (
                                COMBAT_ACTIONS, COMBAT_ACTION_PROPS)
                            if nome_acao in COMBAT_ACTIONS:
                                result = declare_action(g, cid, nome_acao)
                                if result:
                                    return f'play_{cid}_{nome_acao}'
                            # Fallback: acao aleatoria viavel
                            acoes = list(COMBAT_ACTIONS)
                            g.rng.shuffle(acoes)
                            for a in acoes:
                                result = declare_action(g, cid, a)
                                if result:
                                    return f'play_{cid}_{a}'
                        self._pass_turn()
                        return 'combat_wait'

                    # Tenta jogar CE face-down como blefe
                    from rage_web.game_engine.combat_queue import \
                        _jogar_ce_face_down
                    ce_jogado = self._tentar_ce_face_down(card)
                    if ce_jogado:
                        return ce_jogado

                    # P4: Tenta usar carta da mao de combate como acao
                    # antes de cair em acoes basicas (strike/claw/bite).
                    carta_acao, carta_combate = self._escolher_carta_combate_como_acao(card)
                    if carta_acao and carta_combate:
                        result = declare_action(g, cid, carta_acao)
                        if result:
                            # Consome a carta da mao de combate
                            if carta_combate in self.player.combat_hand:
                                self.player.combat_hand.remove(carta_combate)
                                carta_combate.zone = Zone.DISCARD_COMBAT
                                self.player.discard_combat.append(carta_combate)
                            self._usou_carta_combate = True
                            g.add_log(f'{self.player.name} usou carta de combate '
                                      f'{carta_combate.name} como {carta_acao}')
                            return f'play_{cid}_{carta_acao}'

                    action = self._choose_combat_action(card, card.owner_id)
                    result = declare_action(g, cid, action)
                    if not result:
                        # Fallback: tenta acoes mais seguras
                        for fallback in ('strike', 'claw', 'bite', 'block', 'dodge'):
                            if fallback in COMBAT_ACTIONS:
                                result = declare_action(g, cid, fallback)
                                if result:
                                    action = fallback
                                    break
                    # 6.6.6b: Forced Play — se tem carta e nao conseguiu,
                    # tenta qualquer acao viavel (mesmo ilegal)
                    if not result and g.combat.has_forced_play(cid):
                        for acao_forcada in COMBAT_ACTIONS:
                            result = declare_action(g, cid, acao_forcada)
                            if result:
                                action = acao_forcada
                                break
                    if not result:
                        # Ainda falhou: passa a vez
                        self._pass_turn()
                        return 'combat_wait'
                    return f'play_{cid}_{action}'

            # Todos os combatentes do bot jogaram
            combatants = get_combatants(g)
            if all(c in g.combat.played_cards for c in combatants):
                # Avanca para targeting
                g.combat.step = 'targeting'
                return 'combat_targeting'

            # Verifica se so presas nao declaradas (auto-declare)
            pendentes = [c for c in combatants
                         if c not in g.combat.played_cards]
            if pendentes and all(_eh_prey_no_hg(g, c) for c in pendentes):
                reveal_all(g)
                return 'reveal'

            self._pass_turn()
            return 'combat_wait'

        if step == 'targeting':
            # Targeting Step: cada combatente escolhe um alvo
            # (pack combat: cada criatura pode mirar em qualquer oponente)
            for cid in g.combat.attackers + g.combat.defenders:
                if cid in g.combat.targets:
                    continue
                # So atribui alvo para criaturas do proprio bot
                card = _find_card(g, cid)
                if not card or card.owner_id != self.player_id:
                    continue
                acao = g.combat.declarations.get(cid, 'strike')
                if acao in ('block', 'dodge', 'flee'):
                    continue  # defensivas nao precisam de alvo
                # Escolhe alvo: oponente
                alvo = self._escolher_alvo_pack(cid)
                if alvo:
                    g.combat.targets[cid] = alvo
                    return f'target_{cid}_{alvo}'
            g.combat.step = 'reveal'
            return 'combat_progress'

        if step == 'reveal':
            return self._handle_reveal_step()

        if step == 'feint':
            return self._handle_feint_step()

        if step == 'bluff':
            # Bluff Step: verificar requisitos
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'resolution':
            # Resolution Step: aplicar dano
            resolve_combat(g)
            return 'combat_resolve'

        if step == 'withdrawal':
            # Withdrawal Step: verificar se atacante retira
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'between_rounds':
            # Between-rounds: verificar se continua
            if not g.combat.attackers or not g.combat.defenders:
                g.combat.step = 'end'
                return 'combat_end'
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'end':
            end_combat(g)
            return 'end_combat'

        # ---- STEPS ANTIGOS (backward compat) ----

        if step == 'declare':
            self._feinted_ids.clear()  # Novo round de combate
            all_cids = get_combatants(g)
            for cid in all_cids:
                if cid in g.combat.declarations:
                    continue

                card = _find_card(g, cid)
                if card:
                    if card.owner_id != self.player_id:
                        continue
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue
                    action = self._choose_combat_action(card, card.owner_id)
                    declare_action(g, cid, action)
                    return f'declare_{cid}_{action}'

                for p in g.players:
                    for c in p.pack_home:
                        if str(c.card_id) == cid:
                            if c.owner_id != self.player_id:
                                continue
                            action = self._choose_combat_action(c, c.owner_id)
                            declare_action(g, cid, action)
                            return f'declare_{cid}_{action}'

            combatants = get_combatants(g)
            if g.combat.all_declared(combatants):
                reveal_all(g)
                return 'reveal'

            pendentes = [c for c in combatants
                         if c not in g.combat.declarations]
            if pendentes and all(
                _eh_prey_no_hg(g, c) for c in pendentes
            ):
                reveal_all(g)
                return 'reveal'

            self._pass_turn()
            return 'combat_wait'

        if step == 'reveal':
            return self._handle_reveal_step()

        if step in ('resolve',):
            resolve_combat(g)
            end_combat(g)
            return 'end_combat'

        return 'combat_unknown'

    def _handle_reveal_step(self) -> str:
        """Reveal Step: avanca para Feint Step.

        As cartas ja foram reveladas pela etapa de targeting.
        O Feint Step (6.8) cuidara das decisoes de feint.
        """
        g = self.game
        g.combat.step = 'feint'
        return 'combat_progress'

    def _handle_feint_step(self) -> str:
        """Feint Step (6.8.1): decide se alguma criatura deve feintar.

        O ultimo a declarar pode trocar sua acao apos ver
        as revelacoes. Se nenhum feint for desejado/possivel,
        avanca para Bluff Step.
        """
        g = self.game
        opp = self._get_opponent()
        combatants = get_combatants(g)

        for cid in combatants:
            criatura = None
            for p in g.players:
                for c in p.pack_home:
                    if str(c.card_id) == cid and c.owner_id == self.player_id:
                        criatura = c
                        break
            if not criatura:
                continue
            if cid in self._feinted_ids:
                continue
            if not can_feint(g, cid):
                continue

            current = g.combat.declarations.get(cid, '')
            if not current:
                continue

            oponentes_acoes = {}
            for cid2 in combatants:
                if cid2 == cid:
                    continue
                acao = g.combat.declarations.get(cid2, '')
                dono = None
                for p in g.players:
                    for c in p.pack_home:
                        if str(c.card_id) == cid2:
                            dono = c.owner_id
                            break
                if dono and dono != self.player_id:
                    oponentes_acoes[cid2] = acao

            melhor_acao = self._melhor_acao_feint(
                criatura, current, oponentes_acoes, opp)

            if melhor_acao and melhor_acao != current:
                if feint_action(g, cid, melhor_acao):
                    self._feinted_ids.add(cid)
                    return f'feint_{cid}_{melhor_acao}'

        # Nenhum feint desejado/possivel -> avanca para bluff
        g.combat.step = 'bluff'
        return 'combat_progress'

    def _melhor_acao_feint(self, criatura: CardInstance,
                           acao_atual: str,
                           oponentes: dict[str, str],
                           opp: PlayerState) -> Optional[str]:
        """Decide qual acao seria melhor apos ver as revelacoes."""
        OFENSIVAS = {'strike', 'claw', 'bite', 'weapon_strike',
                     'ranged_strike'}
        DEFENSIVAS = {'block', 'dodge', 'flee'}

        # Se todos oponentes agiram defensivamente, ataca
        todos_defensivos = all(
            a in DEFENSIVAS for a in oponentes.values())
        if todos_defensivos and acao_atual in DEFENSIVAS:
            return 'strike'

        # Se ha ameaca maior que o esperado, defende
        for cid_op, acao_op in oponentes.items():
            if acao_op in OFENSIVAS:
                # Encontra a criatura oponente
                for c in opp.pack_home:
                    if str(c.card_id) == cid_op:
                        if c.rage > criatura.rage * 1.3:
                            if acao_atual in OFENSIVAS:
                                return 'dodge'
                        break

        # Se esta com saude critica, foge
        if (criatura.health > 0
                and criatura.health_current < criatura.health * 0.2):
            if acao_atual not in DEFENSIVAS:
                return 'dodge'

        # Se o oponente fugiu, ataca
        if any(a == 'flee' for a in oponentes.values()):
            if acao_atual in DEFENSIVAS:
                return 'strike'

        return None  # Mantem acao atual

    def _decide_combat_random(self) -> str:
        """Acoes aleatorias em combate (modo facil)."""
        from rage_web.game_engine.combat_queue import _find_card, \
            _eh_prey_no_hg, _eh_atacante_da_presa, advance_combat_step

        g = self.game
        combatants = get_combatants(g)
        step = g.combat.step

        # ---- STEPS ANTIGOS ----
        if step == 'declare':
            for cid in combatants:
                if cid not in g.combat.declarations:
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue
                    action = self.game.rng.choice(list(COMBAT_ACTIONS))
                    declare_action(g, cid, action)
                    return f'declare_{cid}_{action}'
            pendentes = [c for c in combatants
                         if c not in g.combat.declarations]
            if pendentes and all(
                _eh_prey_no_hg(g, c) for c in pendentes
            ):
                reveal_all(g)
                return 'reveal'
            if g.combat.all_declared(combatants):
                reveal_all(g)

            resolve_combat(g)
            end_combat(g)
            return 'combat_end'

        # ---- NOVOS STEPS ----
        if step in ('declaration', 'pre_combat', 'beginning_of_combat'):
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'play_card':
            for cid in combatants:
                if cid not in g.combat.played_cards:
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue
                    # 20% de chance de jogar CE face-down
                    if self.game.rng.random() < 0.2:
                        from rage_web.game_engine.combat_queue import \
                            _jogar_ce_face_down
                        ce_card = None
                        for c in self.player.combat_hand:
                            ct = (c.card_type or '').lower()
                            if 'combat event' in ct or ct == 'combat_event':
                                ce_card = c
                                break
                        if ce_card and _jogar_ce_face_down(
                                g, cid, str(ce_card.card_id)):
                            return f'play_{cid}_ce_{ce_card.card_id}'
                    # P4: Tenta usar carta da mao de combate como acao
                    card = _find_card(g, cid)
                    if card and card.owner_id == self.player_id:
                        carta_acao, carta_combate = self._escolher_carta_combate_como_acao(card)
                        if carta_acao and carta_combate and self.game.rng.random() < 0.5:
                            result = declare_action(g, cid, carta_acao)
                            if result:
                                if carta_combate in self.player.combat_hand:
                                    self.player.combat_hand.remove(carta_combate)
                                    carta_combate.zone = Zone.DISCARD_COMBAT
                                    self.player.discard_combat.append(carta_combate)
                                return f'play_{cid}_{carta_acao}'
                    action = self.game.rng.choice(list(COMBAT_ACTIONS))
                    result = declare_action(g, cid, action)
                    if not result:
                        for fallback in ('strike', 'claw', 'bite', 'block', 'dodge'):
                            if fallback in COMBAT_ACTIONS:
                                result = declare_action(g, cid, fallback)
                                if result:
                                    action = fallback
                                    break
                    if not result:
                        self._pass_turn()
                        return 'combat_wait'
                    return f'play_{cid}_{action}'
            g.combat.step = 'targeting'
            return 'combat_progress'

        if step == 'targeting':
            # Random: atribui alvos aleatorios
            for cid in g.combat.attackers + g.combat.defenders:
                if cid in g.combat.targets:
                    continue
                card = _find_card(g, cid)
                if not card or card.owner_id != self.player_id:
                    continue
                acao = g.combat.declarations.get(cid, 'strike')
                if acao in ('block', 'dodge', 'flee'):
                    continue  # defensivas nao precisam de alvo
                # Escolhe alvo aleatorio do lado oposto
                if cid in g.combat.attackers:
                    alvos = [d for d in g.combat.defenders if d != 'hg']
                else:
                    alvos = [a for a in g.combat.attackers if a != 'hg']
                if alvos:
                    alvo = self.game.rng.choice(alvos)
                    g.combat.targets[cid] = alvo
                    return f'target_{cid}_{alvo}'
            g.combat.step = 'reveal'
            return 'combat_progress'

        if step == 'reveal':
            return self._handle_reveal_step()

        if step == 'feint':
            g.combat.step = 'bluff'
            return 'combat_progress'
        if step in ('bluff', 'withdrawal', 'between_rounds'):
            advance_combat_step(g)
            return 'combat_progress'

        if step == 'resolution':
            resolve_combat(g)
            return 'combat_resolve'

        if step == 'end':
            end_combat(g)
            return 'end_combat'

        return 'combat_unknown'

    # ------------------------------------------------------------------
    # Sub-arvores de decisao
    # ------------------------------------------------------------------

    def _pode_pagar_custos(self, card: CardInstance) -> bool:
        """Verifica se o bot pode pagar os custos de Rage e Gnosis.

        Regras (2.2.4/2.2.5):
        - Rage: personagem destapped com Rage >= custo.
        - Gnosis: personagem destapped com Gnosis >= custo.

        Para Gifts (Rage FOO Rule): tambem verifica se algum
        personagem atende os requisitos de keyword do Gift.
        """
        from rage_web.game_engine.rules import (parse_custo_rage, pode_usar_gift,
                                                   validar_timing_gift,
                                                   validar_opponent_gift,
                                                   pode_usar_rite,
                                                   validar_timing_rite,
                                                   TOTEM_IDS)

        # Se for Event (Totem), verifica requisitos de keyword
        if card.card_type == 'Event' and card.card_id in TOTEM_IDS:
            from rage_web.game_engine.rules import validar_totem_evento
            if not validar_totem_evento(self.player, card):
                return False

        # Se for Territory/Realm, verifica requisitos de keyword + Realm rules
        if card.card_type in ('Territory', 'Realm'):
            from rage_web.game_engine.rules import pode_jogar_territory
            if not pode_jogar_territory(self.player, card):
                return False
        elif card.card_type and ('territory' in card.card_type.lower()
                                 or 'realm' in card.card_type.lower()):
            from rage_web.game_engine.rules import pode_jogar_territory
            if not pode_jogar_territory(self.player, card):
                return False

        # Se for Combat Event, verifica requisitos de keyword (requires)
        ct = (card.card_type or '').lower()
        if 'combat event' in ct or ct == 'combat event':
            requires = (card.requires or '').strip()
            if requires:
                from rage_web.game_engine.rules import (
                    _char_atende_requisitos, _info_char)
                opcoes = [p.strip() for p in requires.split(' - ')]
                tem_char = any(
                    _char_atende_requisitos(
                        _info_char(c), c.gnosis or 0, opcoes,
                        self.player, c
                    )
                    for c in self.player.pack_home
                    if 'Character' in (c.card_type or '')
                )
                if not tem_char:
                    return False

        # Se for Rite, verifica requisitos de Renown + timing
        if card.card_type == 'Rite':
            if not validar_timing_rite(card, self.game.phase):
                return False
            if not pode_usar_rite(self.player, card):
                return False

        # Se for Gift, verifica requisitos de keyword + timing
        if card.card_type == 'Gift':
            # Valida timing
            if not validar_timing_gift(card, self.game.phase):
                return False
            # Valida 'opponent' = combat only
            if not validar_opponent_gift(card, self.game.phase):
                return False
            # Valida requisitos de keyword (Rage FOO Rule)
            if not pode_usar_gift(self.player, card):
                return False

        # Caern: verificacoes especiais
        if card.card_type == 'Caern':
            from rage_web.game_engine.rules import pode_jogar_caern
            if not pode_jogar_caern(self.player, card, self.game):
                return False

        # Rage
        custo_rage = parse_custo_rage(card.damage)
        if custo_rage is not None and custo_rage > 0:
            tem_rage = any(c.rage >= custo_rage
                          for c in self.player.pack_home)
            if not tem_rage:
                return False
        # Gnosis (apenas para equipamentos Fetish, nao Caern)
        # Caern.gnosis = Gauntlet rating, nao custo
        if card.card_type != 'Caern' and card.gnosis and card.gnosis > 0:
            tem_gnosis = any(c.gnosis >= card.gnosis
                            for c in self.player.pack_home)
            if not tem_gnosis:
                return False
        return True

    def _try_survive(self) -> Optional[str]:
        """Prioridade 1: Sobreviver.

        Se alguma criatura tem saude critica (< 30%),
        tenta jogar carta de cura ou bloqueio.
        """
        me = self.player

        for c in me.pack_home:
            if c.health > 0 and (c.health_current / c.health) < 0.3:
                logger.info(f'[BOT] {c.name} com saude critica '
                            f'({c.health_current}/{c.health})')
                # Tenta passar a vez para evitar ataque
                # (futuro: curar com gift/equipamento)
                return None  # Ainda nao ha mecanica de cura

        return None

    # -------------------------------------------------------------------
    # P1: Calcular chance de aceitacao de desafio (6.5.2)
    # -------------------------------------------------------------------
    def _calcular_chance_aceitacao_desafio(
        self, desafiante: CardInstance,
        alvo: CardInstance) -> float:
        """Calcula a probabilidade do alvo aceitar um desafio.

        Reusa a mesma logica de _desafiado_aceita_desafio()
        para prever a decisao do oponente.

        Args:
            desafiante: Carta que esta desafiando.
            alvo: Carta que seria desafiada.

        Returns:
            Float entre 0.0 e 1.0 representando a chance
            de aceitacao.
        """
        rage_alvo = alvo.effective_rage
        rage_des = desafiante.effective_rage
        hp_alvo = alvo.health_current or alvo.health
        dano_esperado = rage_des

        # Score entre 0-100 (mesma logica de _desafiado_aceita_desafio)
        score = 50  # Neutro

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
        dono = None
        for p in self.game.players:
            if p.id == alvo.owner_id:
                dono = p
                break
        if dono:
            for card in dono.combat_hand:
                nome = (card.name or '').lower()
                ct = (card.card_type or '').lower()
                if ('block' in nome or 'dodge' in nome
                    or 'defend' in nome or 'evasion' in nome
                    or 'flee' in nome
                    or 'block and strike' in nome):
                    score += 30
                    break
                if 'combat action' in ct or 'combat event' in ct:
                    texto = (card.text or '').lower()
                    if any(p in texto for p in ('block', 'dodge', 'flee',
                                                  'evasion', 'defend')):
                        score += 30
                        break

        # 4. Fator aleatorio (previsivel via seed)
        score += self.game.rng.randint(-20, 20)

        # 5. Desafiante com Rage muito alta: medo extra
        if rage_des >= 7:
            score -= 10
        if rage_des >= 9:
            score -= 10

        # Converte para probabilidade (score 0-100)
        prob = max(0.0, min(1.0, score / 100.0))
        return prob

    # -------------------------------------------------------------------

    def _pode_atacar(self, card: CardInstance) -> bool:
        """Verifica se uma carta pode atacar/combater.

        Regra: apenas Characters e Allies podem entrar em combate.
        Equipment, Gift, Event, Action, Territory, Caern, etc. nao.
        Cada criatura so pode atacar uma vez por fase de combate.
        """
        ct = (card.card_type or '').lower()
        if 'character' not in ct and 'ally' not in ct:
            return False
        # Verifica se ja atacou nesta fase de combate
        if hasattr(self, '_ataques_feitos'):
            if str(card.card_id) in self._ataques_feitos:
                return False
        return True

    def _melhor_alvo_hg(self) -> Optional[CardInstance]:
        """Encontra o melhor alvo no Hunting Grounds considerando alinhamento.

        Regra 6.4.3:
        - Gaia packs ganham 0 VP por matar Victims.
        - Wyrm packs ganham 0 VP por matar Enemies.

        Prioridades:
        1. Presas que dao VP cheio (alinhamento correto)
        2. Presas que dao 0 VP (ataque de negacao, se valer a pena)
        3. Melhor relacao renown/health dentro de cada grupo

        Returns:
            A melhor carta para atacar, ou None se nenhuma viavel.
        """
        from rage_web.game_engine.combat_queue import _eh_pack_gaia, _eh_pack_wyrm

        TIPOS_HG = {'victim', 'enemy', 'battlefield'}
        candidatos = []
        # HG global
        for c in self.game.hunting_grounds_cards:
            ct = (c.card_type or '').lower()
            if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                # Nao ataca propria presa
                if c.owner_id and c.owner_id != self.player_id:
                    candidatos.append(c)
        # HG de cada jogador
        for p in self.game.players:
            if p.id == self.player_id:
                continue  # Nao ataca proprias cartas
            for c in p.hunting_grounds:
                ct = (c.card_type or '').lower()
                if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                    candidatos.append(c)
        if not candidatos:
            return None

        # Verifica alinhamento do pack
        eh_gaia = _eh_pack_gaia(self.player)
        eh_wyrm = _eh_pack_wyrm(self.player)

        def _vp_real(c: CardInstance) -> int:
            """Calcula VP real que esta presa renderia."""
            ct = (c.card_type or '').lower()
            vp_base = c.renown if c.renown > 0 else 1
            if eh_gaia and 'victim' in ct:
                return 0
            if eh_wyrm and 'enemy' in ct:
                return 0
            return vp_base

        def _chave_ordenacao(c: CardInstance) -> tuple:
            """Chave de ordenacao: (vp>0?, eficiencia_vp, renown)."""
            vp = _vp_real(c)
            eficiencia = vp / max(c.health_current, 1)
            return (vp > 0, eficiencia, c.renown or 0)

        # Ordena: primeiro as que dao VP, depois por eficiencia
        candidatos.sort(key=_chave_ordenacao, reverse=True)

        melhor = candidatos[0]
        vp_melhor = _vp_real(melhor)

        if vp_melhor == 0:
            self.game.add_log(
                f'[BOT] {self.player.name}: so ha alvos que dao 0 VP '
                f'no HG ({melhor.name})'
            )

        return melhor

    def _deve_atacar_presa_estrategicamente(
            self, alpha_card: CardInstance,
            alvo_hg: Optional[CardInstance]) -> bool:
        """Decide se e estrategicamente melhor atacar Presa agora.

        A estrategia considera:
        1. Dificuldade: se o alpha e fraco, atacar inimigo e arriscado
        2. VP urgency: se esta muito atras em VP, precisa de pontos
        3. Eficiencia da Presa: VP por health vale a pena?
        4. Deck lento: precisa de VP rapido
        5. Nenhum alvo inimigo viavel

        Returns:
            True se atacar Presa e melhor que atacar inimigo.
        """
        if not alvo_hg:
            return False

        me = self.player
        lento = self._is_slow_deck()

        # 1. Nenhum inimigo viavel: ataca Presa
        opponents = self._get_opponents()
        tem_inimigo_viavel = any(
            c.health_current > 0
            for opp in opponents
            for c in opp.pack_home
        )
        if not tem_inimigo_viavel:
            return True

        # 2. Deck lento sempre prioriza Presa (precisa de VP)
        if lento:
            return True

        # 3. Alpha esta muito fraco para atacar inimigos
        alpha_rage = alpha_card.rage
        max_enemy_health = max(
            (c.health for opp in opponents
             for c in opp.pack_home if c.health_current > 0),
            default=0
        )
        if alpha_rage < max_enemy_health * 0.5:
            return True

        # 4. Verifica VP gap
        max_vp_inimigo = max(
            (p.victory_points for p in opponents),
            default=0
        )
        vp_gap = max_vp_inimigo - me.victory_points
        # Se atrasado por mais de 5 VP, precisa de pontos
        if vp_gap >= 5:
            return True

        # 5. Presa oferece VP alto e e facil de matar
        from rage_web.game_engine.combat_queue import (_eh_pack_gaia,
                                                        _eh_pack_wyrm)
        eh_gaia = _eh_pack_gaia(me)
        eh_wyrm = _eh_pack_wyrm(me)
        ct = (alvo_hg.card_type or '').lower()
        vp_presa = alvo_hg.renown if alvo_hg.renown > 0 else 1
        if eh_gaia and 'victim' in ct:
            vp_presa = 0
        if eh_wyrm and 'enemy' in ct:
            vp_presa = 0

        # Presa com VP >= 3 que pode ser morta em 1 golpe
        if vp_presa >= 3 and alpha_rage >= alvo_hg.health_current:
            return True

        # 6. Cenario normal: tenta matar inimigo primeiro
        return False

    def _try_eliminate_threat(self) -> Optional[str]:
        """Prioridade 2: Eliminar ameaca.

        Com N jogadores, avia ameacas de TODOS os oponentes,
        priorizando criaturas do lider em VP.
        """
        me = self.player
        opponents = self._get_opponents()
        lento = self._is_slow_deck()

        if not me.pack_home:
            return None

        available = [c for c in me.pack_home
                     if self._pode_atacar(c)]
        if not available:
            return None

        # Agrega ameacas de todos os oponentes
        todas_ameacas = []
        for opp in opponents:
            for c in opp.pack_home:
                if c.health_current > 0:
                    todas_ameacas.append(c)

        if not todas_ameacas:
            return None

        # rate_threat ja inclui VP weight -> lider sai primeiro
        ameacas = sorted(todas_ameacas,
                         key=self.prioritizer.rate_threat,
                         reverse=True)

        for alvo in ameacas:
            atacante = self.prioritizer.best_attacker_for(alvo, available)
            if atacante:
                pode = self.prioritizer.pode_eliminar(atacante, alvo,
                                                       modo_lento=lento)
                if pode:
                    self._attack(str(atacante.card_id), str(alvo.card_id))
                    return f'eliminate_{atacante.card_id}_vs_{alvo.card_id}'

        return None

    def _try_develop_board(self) -> Optional[str]:
        """Prioridade 3: Desenvolver mesa.

        Joga personagens primeiro, depois efeitos viaveis.
        """
        me = self.player

        if not me.hand:
            return None

        # 1. Joga personagens
        for i, card in enumerate(me.hand):
            if card.card_type == 'Character':
                self._play_card(i)
                return f'play_character_{card.card_id}'

        # 2. Joga cartas de HG (Victim/Enemy/Battlefield + subtipos)
        for i, card in enumerate(me.hand):
            from rage_web.game_engine.rules import zona_da_carta
            if zona_da_carta(card.card_type or '') == 'hunting_grounds':
                self._play_card(i)
                return f'play_hg_{card.card_id}'

        # 3. Joga Ally (incluindo subtipos), Equipment, Territory, Caern
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            eh_ally = ('Ally' in ct and zona_da_carta(ct) == 'pack_home')
            if (eh_ally
                or ct in ('Equipment', 'Territory', 'Caern')
                or ct == 'Equipment - Fetish - Bane Fetish'):
                self._play_card(i)
                return f'play_{card.card_type.lower()}_{card.card_id}'

        # 3.5 Joga Rites
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            if ct == 'Rite':
                from rage_web.game_engine.rules import (pode_usar_rite,
                                                         validar_timing_rite)
                if (validar_timing_rite(card, self.game.phase)
                    and pode_usar_rite(me, card)
                    and self._pode_pagar_custos(card)):
                    if card.modelo_id:
                        modo_idx = self._escolher_melhor_modo(card.modelo_id)
                        return self._usar_carta_efeito(i, modo_idx, card)
                    else:
                        self._play_card(i)
                        return f'play_rite_{card.card_id}'

        # 4. Joga Quest / Past Life
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            if ct in ('Quest', 'Past Life'):
                if card.modelo_id and self._pode_pagar_custos(card):
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    return self._usar_carta_efeito(i, modo_idx, card)

        # 5. Efeitos nao-stub
        TIPOS_STUB = {'combar_acao'}
        for i, card in enumerate(me.hand):
            if card.modelo_id and self._pode_pagar_custos(card):
                from rage_web.game_engine.effects import CARTAS_EXEMPLO
                modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                if modelo and modelo.modos and modelo.modos[0].efeitos:
                    tem_stub = any(e.tipo in TIPOS_STUB
                                   for e in modelo.modos[0].efeitos)
                    if not tem_stub:
                        modo_idx = self._escolher_melhor_modo(card.modelo_id)
                        return self._usar_carta_efeito(i, modo_idx, card)

        return None

    def _escolher_melhor_modo(self, modelo_id: str) -> int:
        """Escolhe o melhor modo para uma carta de efeito.

        Analisa o estado do tabuleiro e seleciona o modo
        mais vantajoso.
        """
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        modelo = CARTAS_EXEMPLO.get(modelo_id)
        if not modelo or not modelo.modos:
            return 0

        opp = self._get_opponent()
        me = self.player

        # Preferencias por id de carta
        preferencias = {
            'golpe_misericordia': self._modo_golpe_misericordia(me, opp),
            'toque_curativo': self._modo_toque_curativo(me),
        }

        return preferencias.get(modelo_id, 0)

    def _modo_golpe_misericordia(self, me, opp) -> int:
        """Escolhe modo do Golpe de Misericordia.

        Modo 0: destruir ferido (se oponente tem criatura ferida)
        Modo 1: descarte (se oponente tem mao grande)
        Modo 2: dano (padrao)
        """
        # Modo 0: destruir criatura inimiga ferida
        for c in opp.pack_home:
            if c.health > 0 and c.health_current < c.health:
                return 0

        # Modo 1: descarte se oponente tem mao grande
        if len(opp.hand) >= 5:
            return 1

        # Modo 2: dano
        return 2

    def _modo_toque_curativo(self, me) -> int:
        """Escolhe modo do Toque Curativo.

        Modo 0: curar 3 (se tem criatura ferida)
        """
        for c in me.pack_home:
            if c.health > 0 and c.health_current < c.health:
                return 0
        return 0

    def _usar_carta_efeito(self, hand_index: int, modo_idx: int,
                            card) -> str:
        """Usa uma carta de efeito da mao.

        Valida custo de Rage antes de usar.
        """
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        from rage_web.game_engine.rules import parse_custo_rage

        modelo = CARTAS_EXEMPLO.get(card.modelo_id)
        if not modelo:
            self._play_card(hand_index)
            return f'play_{card.card_id}'

        # Pagar custos (ja validado por _pode_pagar_custos)
        custo_rage = parse_custo_rage(card.damage)
        if custo_rage is not None and custo_rage > 0:
            pagador = self.player.pagar_custo_rage(custo_rage)
            if pagador:
                self.game.add_log(
                    f'[BOT] {self.player.name} pagou Rage {custo_rage} '
                    f'com {pagador} para {card.name}')
        if card.gnosis and card.gnosis > 0:
            pagador = self.player.pagar_custo_gnosis(card.gnosis)
            if pagador:
                self.game.add_log(
                    f'[BOT] {self.player.name} pagou Gnosis {card.gnosis} '
                    f'com {pagador} para {card.name}')

        # Remove da mao e aplica (passa card real para equipamentos)
        card_real = self.player.hand.pop(hand_index)
        logs = aplicar_carta(self.game, modelo, self.player_id,
                              modo_idx=modo_idx, card_origem=card_real)

        modo = modelo.modos[modo_idx]
        desc = f'use_{card.modelo_id}_modo{modo_idx}'
        self.game.add_log(
            f'[BOT] {self.player.name} usou {card.name} ({modo.descricao})')
        return desc

    def _try_prey_gift(self) -> Optional[str]:
        """Tenta jogar Gifts para Presa em combate.

        Regra: Prey pode usar Gifts que correspondam ao seu tipo
        de criatura. Qualquer jogador exceto o atacante pode pagar
        Gifts para a Presa. So funciona durante combate.
        """
        g = self.game
        me = self.player

        # So durante combate
        if not g.combat or not g.combat.is_active:
            return None

        # Nao pode ser o atacante
        if g.combat.prey_attackers.get(self.player_id, False):
            return None

        # Busca Gifts na mao
        from rage_web.game_engine.rules import pode_usar_gift_para_presa

        for i, card in enumerate(me.hand):
            if card.card_type != 'Gift':
                continue
            if not card.modelo_id:
                continue
            if not self._pode_pagar_custos(card):
                continue

            # Verifica se alguma Presa atacada pode usar este Gift
            for c in g.hunting_grounds_cards:
                if c.health_current <= 0:
                    continue
                ct = (c.card_type or '').lower()
                if 'victim' not in ct and 'enemy' not in ct:
                    continue
                if str(c.card_id) not in g.combat.defenders:
                    continue

                if pode_usar_gift_para_presa(c, card):
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    self._cards_played_this_turn += 1
                    return self._usar_carta_efeito(i, modo_idx, card)

        return None

    def _try_attack(self) -> Optional[str]:
        """Prioridade 4: Atacar.

        Com N jogadores, ataca criaturas do lider em VP primeiro.
        Regra 6.5.1: apenas o Alpha pode iniciar ataque; ataque
        de nao-Alpha requer card ability.
        """
        me = self.player
        opponents = self._get_opponents()
        lento = self._is_slow_deck()

        available = [c for c in me.pack_home
                     if self._pode_atacar(c)]
        if not available:
            return None

        # Agrega alvos de todos os oponentes
        # Sky River Caern: nao-alfas imunes a challenge/sneak attack
        sky_river_packs = set()
        for p in self.game.players:
            if p.id != self.player_id:
                for mod in self.game.game_modifiers:
                    if mod.modifier == 'sky_river_caern':
                        for c in p.pack_home + p.hunting_grounds:
                            if id(c) == mod.card_uid:
                                sky_river_packs.add(p.id)
                                break

        todas_ameacas = []
        for opp in opponents:
            # Sky River: so pode atacar o Alpha (maior Renown)
            if opp.id in sky_river_packs:
                alvos_permitidos = []
                # Alpha = maior renown ou primeiro char
                alpha = max(
                    [c for c in opp.pack_home if c.health_current > 0],
                    key=lambda x: x.renown,
                    default=None
                )
                if alpha:
                    alvos_permitidos.append(alpha)
                # Tambem pode atacar criaturas no HG (Enemy/Victim)
                for c in self.game.hunting_grounds_cards:
                    if c.health_current > 0:
                        alvos_permitidos.append(c)
                todas_ameacas.extend(alvos_permitidos)
            else:
                for c in opp.pack_home:
                    if c.health_current > 0:
                        todas_ameacas.append(c)

        if todas_ameacas:
            ameacas = sorted(todas_ameacas,
                             key=self.prioritizer.rate_threat,
                             reverse=True)
            for alvo in ameacas:
                atacante = self.prioritizer.best_attacker_for(alvo, available)
                if atacante:
                    if self.prioritizer.pode_eliminar(atacante, alvo,
                                                       modo_lento=lento):
                        self._attack(str(atacante.card_id), str(alvo.card_id))
                        return (f'eliminate_{atacante.card_id}'
                                f'_vs_{alvo.card_id}')

        return None

    # ------------------------------------------------------------------
    # Utilitarios
    # ------------------------------------------------------------------

    def _get_opponent(self) -> PlayerState:
        for p in self.game.players:
            if p.id != self.player_id:
                return p
        raise ValueError('Nenhum oponente')

    def _escolher_carta_combate_como_acao(self, card: CardInstance) -> tuple[Optional[str], Optional[CardInstance]]:
        """P4: Tenta usar carta da mao de combate como acao declarada.

        Percorre a mao de combate do jogador e verifica se alguma
        carta tem nome que corresponde a uma COMBAT_ACTION conhecida
        (ex: 'Head Butt' -> 'head_butt', 'Dodge' -> 'dodge').

        So retorna cartas OFENSIVAS (com dano > 0) que sejam
        melhores que a melhor acao basica. Defensivas (block/dodge)
        sao deixadas para _choose_combat_action.

        Returns:
            (action_name, card_instance) ou (None, None) se nenhuma
            carta viavel foi encontrada.
        """
        if not self.player.combat_hand:
            return None, None

        from rage_web.game_engine.combat_queue import (
            COMBAT_ACTION_PROPS, COMBAT_ACTION_VALIDATORS)

        nivel_restrito = self.game.combat.get_restricted_level(
            str(card.card_id))

        # Calcula o dano da melhor acao basica para comparacao
        melhor_dano_basico = card.effective_rage  # 'strike' = Rage
        for acao_basica in ('head_butt', 'anatomy_lesson',
                            'savage_beatdown', 'tail_lash',
                            'submission_hold', 'claw', 'bite'):
            props = COMBAT_ACTION_PROPS.get(acao_basica, {})
            req = props.get('rage_requirement', 0)
            if card.effective_rage < req:
                continue
            if nivel_restrito is not None and req > nivel_restrito:
                continue
            acao_dano = props.get('damage')
            if acao_dano is None:
                acao_dano = card.effective_rage
            if acao_basica == 'tail_lash':
                keywords = (card.keywords or '').lower()
                if 'rokea' in keywords or 'mokole' in keywords:
                    acao_dano += props.get('bonus_dano', 0)
            if acao_dano > melhor_dano_basico:
                melhor_dano_basico = acao_dano

        ACES_DEFENSIVAS = {'block', 'dodge', 'flee', 'ranged_strike'}

        melhor_acao = None
        melhor_carta = None
        melhor_dano = -1

        for carta_combate in self.player.combat_hand:
            # Converte nome da carta para slug
            nome_slug = (carta_combate.name or '').lower().replace(' ', '_').replace('-', '_')

            # Mapeia nomes de cartas comuns
            MAPA_NOMES_CARTA_PARA_ACAO = {
                'evasion': 'dodge',
                'block_and_strike': 'block',
            }
            if nome_slug in MAPA_NOMES_CARTA_PARA_ACAO:
                nome_slug = MAPA_NOMES_CARTA_PARA_ACAO[nome_slug]

            if nome_slug not in COMBAT_ACTION_PROPS:
                continue

            # Pula acoes defensivas (deixa _choose_combat_action decidir)
            if nome_slug in ACES_DEFENSIVAS:
                continue

            props = COMBAT_ACTION_PROPS.get(nome_slug, {})
            req = props.get('rage_requirement', 0)

            if card.effective_rage < req:
                continue
            if nivel_restrito is not None and req > nivel_restrito:
                continue

            # Validadores especificos
            validators = COMBAT_ACTION_VALIDATORS.get(nome_slug, [])
            rejeitada = False
            for validador in validators:
                erro = validador(self.game, card)
                if erro:
                    rejeitada = True
                    break
            if rejeitada:
                continue

            # Calcula dano esperado
            acao_dano = props.get('damage')
            if acao_dano is None:
                acao_dano = card.effective_rage

            # Bonus de Tail Lash
            if nome_slug == 'tail_lash':
                keywords = (card.keywords or '').lower()
                if 'rokea' in keywords or 'mokole' in keywords:
                    acao_dano += props.get('bonus_dano', 0)

            # So retorna se dano > 0 E pelo menos tao bom quanto a melhor basica
            # (>= para usar cartas com propriedades especiais tipo head_butt bounce)
            if acao_dano > 0 and acao_dano >= melhor_dano_basico and acao_dano > melhor_dano:
                melhor_acao = nome_slug
                melhor_carta = carta_combate
                melhor_dano = acao_dano

        return melhor_acao, melhor_carta

    def _choose_combat_action(self, card: CardInstance,
                                owner_id: str) -> str:
        """Escolhe a melhor acao de combate para uma criatura.

        Considera dano de cada acao (COMBAT_ACTION_PROPS), requisito
        de Rage, e condicao da criatura.

        P4: Fallback quando _escolher_carta_combate_como_acao()
        nao encontra carta viavel na mao de combate.

        Se for criatura do oponente, escolhe acao defensiva ou
        previsivel (block/dodge/strike). Se for do proprio bot,
        escolhe a acao ofensiva de maior dano viavel.
        """
        me = self.player

        if owner_id != self.player_id:
            # Criatura do oponente: reage de forma defensiva
            if card.health_current < card.health * 0.4:
                return 'dodge'
            if card.rage >= 3:
                max_atk_rage = 0
                if me and me.pack_home:
                    max_atk_rage = max(c.rage for c in me.pack_home)
                if max_atk_rage > card.rage * 1.5:
                    return 'block'
                return 'strike'
            return 'block'

        # Criatura propria: escolhe acao ofensiva de maior dano viavel
        from rage_web.game_engine.combat_queue import COMBAT_ACTION_PROPS

        # 6.6.6a: Restricted Play — filtra por nivel maximo de Rage
        nivel_restrito = self.game.combat.get_restricted_level(
            str(card.card_id))

        opp = self._get_opponent()
        melhor_acao = 'strike'
        melhor_dano = -1

        for acao in ('anatomy_lesson', 'head_butt', 'savage_beatdown',
                     'tail_lash', 'submission_hold', 'strike', 'claw', 'bite'):
            props = COMBAT_ACTION_PROPS.get(acao, {})
            req = props.get('rage_requirement', 0)
            if card.effective_rage < req:
                continue  # Nao atende requisito de Rage
            # 6.6.6a: Restricted Play
            if nivel_restrito is not None and req > nivel_restrito:
                continue  # Restricao impede esta acao
            # Verifica validadores especificos (ex: Tail Lash so Rokea/Mokole)
            from rage_web.game_engine.combat_queue import COMBAT_ACTION_VALIDATORS
            validators = COMBAT_ACTION_VALIDATORS.get(acao, [])
            if validators:
                # Pula acao se algum validador rejeitar
                rejeitada = False
                for validador in validators:
                    erro = validador(self.game, card)
                    if erro:
                        rejeitada = True
                        break
                if rejeitada:
                    continue

            # Calcula dano esperado
            acao_dano = props.get('damage')
            if acao_dano is None:
                acao_dano = card.effective_rage  # Fallback: Rage da criatura

            # Bonus de Tail Lash
            if acao == 'tail_lash':
                keywords = (card.keywords or '').lower()
                if 'rokea' in keywords or 'mokole' in keywords:
                    acao_dano += props.get('bonus_dano', 0)

            if acao_dano > melhor_dano:
                melhor_acao = acao
                melhor_dano = acao_dano

        # Dodge so em situacao critica
        opp_pack = opp.pack_home if opp else []
        if opp_pack:
            max_opp_rage = max(c.rage for c in opp_pack)
            if (max_opp_rage > card.rage * 2.0
                    and card.health_current < card.health * 0.5):
                return 'dodge'

        return melhor_acao

    def _tentar_ce_face_down(self, card: CardInstance) -> Optional[str]:
        """Tenta jogar um Combat Event face-down como blefe.

        Joga CE face-down quando a criatura esta em desvantagem
        (Rage baixa vs oponente forte) e tem um CE na mao.
        O CE sera descartado como ilegal no Bluff Step.

        Returns:
            String de acao (play_<cid>_ce_<ce_id>) ou None.
        """
        g = self.game
        from rage_web.game_engine.combat_queue import _jogar_ce_face_down

        # Verifica se a criatura esta fraca para jogar CA normal
        opp = self._get_opponent()
        if opp and opp.pack_home:
            max_opp_rage = max(c.rage for c in opp.pack_home)
            if max_opp_rage <= card.rage * 1.2:
                return None  # Nao esta em desvantagem

        # Encontra CE na mao de combate
        ce_card = None
        for c in self.player.combat_hand:
            ct = (c.card_type or '').lower()
            if 'combat event' in ct or ct == 'combat_event':
                ce_card = c
                break
        if not ce_card:
            # Tenta na mao principal
            for c in self.player.hand:
                ct = (c.card_type or '').lower()
                if 'combat event' in ct or ct == 'combat_event':
                    ce_card = c
                    break
        if not ce_card:
            return None

        # Joga CE face-down
        if _jogar_ce_face_down(g, str(card.card_id),
                                str(ce_card.card_id)):
            g.add_log(f'[BOT] {self.player.name} jogou {ce_card.name} '
                      f'face-down como blefe')
            return f'play_{card.card_id}_ce_{ce_card.card_id}'
        return None

    def _escolher_alvo_pack(self, cid: str) -> Optional[str]:
        """Escolhe um alvo para uma criatura em pack combat.

        Se a criatura e atacante, mira em um defensor.
        Se e defensora, mira em um atacante.
        Prefere alvos com menor HP para eliminar rapido.
        """
        from rage_web.game_engine.combat_queue import _find_card
        g = self.game
        card = _find_card(g, cid)
        if not card:
            return None

        # Determina lado oposto
        if cid in g.combat.attackers:
            oponentes = g.combat.defenders
        elif cid in g.combat.defenders:
            oponentes = g.combat.attackers
        else:
            return None

        # Escolhe o melhor alvo entre os oponentes
        melhor_alvo = None
        melhor_score = -999

        for oid in oponentes:
            if oid == 'hg':
                continue
            o_card = _find_card(g, oid)
            if not o_card or o_card.health_current <= 0:
                continue
            if oid in g.combat.targets.values():
                # Ja esta sendo atacado - pode ser bom (foco) ou ruim
                pass

            # Score: prefere alvos com HP baixo e Rage alta
            hp_ratio = o_card.health_current / max(o_card.health, 1)
            score = -hp_ratio * 10  # Quanto menos HP, melhor
            score += min(o_card.effective_rage / 10, 1)  # Rage alta = ameaca
            score += o_card.renown / 10  # Renome alto = mais VP

            if score > melhor_score:
                melhor_score = score
                melhor_alvo = oid

        return melhor_alvo

    def _draw(self):
        """Compra carta do deck de combate."""
        self.player.draw_combat(1)
        self.game.add_log(f'[BOT] {self.player.name} comprou uma carta')

    def _play_card(self, hand_index: int):
        """Joga carta da mao.

        Regra (1.2): Enemy, Victim e Battlefield vao
        para o Hunting Grounds, nao para o Pack Home.
        Spirit cards com 'existe_apenas_umbra' vao para a Umbra.
        """
        if 0 <= hand_index < len(self.player.hand):
            card = self.player.hand.pop(hand_index)
            # Verifica se e uma criatura que existe apenas na Umbra
            if 'existe_apenas_umbra' in card.restricoes:
                card.zone = Zone.UMBRA
                card.health_current = card.health
                self.player.umbra.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} jogou {card.name} na Umbra')
                # Registra passivas especiais
                self.game.register_card_passives(card, self.player)
                return
            from rage_web.game_engine.rules import zona_da_carta
            ct = (card.card_type or '').lower()
            if 'combat event' in ct or ct == 'combat_event':
                # Combat Events vao para o descarte de combate
                card.zone = Zone.DISCARD_COMBAT
                self.player.discard_combat.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} jogou {card.name} '
                    f'(descartado)')
                return
            zona = zona_da_carta(card.card_type or '')
            if zona == 'hunting_grounds':
                card.zone = Zone.HUNTING_GROUNDS
                card.health_current = card.health
                self.player.hunting_grounds.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} jogou {card.name} '
                    f'no Hunting Grounds')
                self.game.register_card_passives(card, self.player)
            else:
                card.zone = Zone.PACK_HOME
                card.health_current = card.health
                self.player.pack_home.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} jogou {card.name}')
                self.game.register_card_passives(card, self.player)
                # Equipment: tenta equipar a uma criatura do pack
                if 'equipment' in (card.card_type or '').lower():
                    self._equip_card_to_pack(card)

    def _equip_card_to_pack(self, card):
        """P5: Equipa um Equipment na criatura mais adequada do pack.

        Analisa o tipo de equipamento (Weapon, Armor, Fetish) e
        escolhe a criatura mais beneficiada:
        - Weapon: maior Rage (mais dano por ataque)
        - Armor: maior HP ou mais danificada (reducao de dano)
        - Fetish generico: maior Gnosis (pode pagar custo)

        Considera equipamentos existentes para nao stackar armas.
        Usa _validar_restricoes_equipamento para restricoes de
        forma/requisito.
        """
        from rage_web.game_engine.state import Zone
        candidates = [
            c for c in self.player.pack_home
            if c.card_id != card.card_id
            and hasattr(c, 'attached_equipment')
        ]
        if not candidates:
            return

        from rage_web.game_engine.effects import ResolvedorEfeitos
        resolvedor = ResolvedorEfeitos(self.game)

        # Analisa o tipo de equipamento pelas keywords
        kw = (card.keywords or '').lower()
        eh_weapon = 'weapon' in kw
        eh_armor = 'armor' in kw
        eh_fetish = 'fetish' in kw and 'non-fetish' not in kw

        # Pontua cada candidato
        def score(c):
            s = 0

            # Verifica se ja tem equipamento similar
            tem_weapon = False
            tem_armor = False
            for eq in (c.attached_equipment or []):
                eq_kw = (eq.keywords or '').lower()
                if 'weapon' in eq_kw:
                    tem_weapon = True
                if 'armor' in eq_kw:
                    tem_armor = True

            if eh_weapon:
                if tem_weapon:
                    return -100  # Nao stackar duas armas
                s += c.rage * 10  # Maior Rage = mais dano
            elif eh_armor:
                if tem_armor:
                    s -= 30
                hp_perdido = (c.health or 0) - (c.health_current or c.health or 0)
                s += hp_perdido * 8  # Quem mais precisa de protecao
                s += (c.health or 0) * 3  # Tanques se beneficiam mais
            elif eh_fetish:
                s += c.gnosis * 8  # Maior Gnosis = melhor para Fetish
            else:
                s += c.rage * 3 + c.gnosis * 3 + c.health * 2

            # Penalidade: Gnosis insuficiente para requisito
            gnosis_req = card.gnosis or 0
            if gnosis_req > 0 and c.gnosis < gnosis_req:
                s -= 50

            # Penalidade: criatura morta/ferida grave
            hp_atual = c.health_current or c.health or 0
            if hp_atual <= 0:
                s -= 100

            return s

        # Ordena por pontuacao decrescente
        candidates.sort(key=score, reverse=True)

        for alvo in candidates:
            if resolvedor._validar_restricoes_equipamento(card, alvo):
                if card in self.player.pack_home:
                    self.player.pack_home.remove(card)
                card.zone = Zone.OUT_OF_PLAY
                alvo.attached_equipment.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} equipou '
                    f'{card.name} em {alvo.name}')
                return

        self.game.add_log(
            f'[BOT] {self.player.name} nao achou alvo para '
            f'{card.name}, deixou no pack')

    def _attack(self, attacker_id: str, defender_id: str):
        """Inicia combate entre atacante e defensor."""
        start_combat(self.game, [attacker_id], [defender_id])
        self._ataques_feitos.add(attacker_id)
        self.game.add_log(
            f'[BOT] {self.player.name} atacou {defender_id} com {attacker_id}')

    def _pass_turn(self):
        """Passa a vez.

        Durante combate com step machine ativo, passar a vez NAO
        avanca a fase — apenas rotaciona o jogador atual.
        A fase de combate so termina quando end_combat() for chamado
        e todos os jogadores passarem.
        """
        me = self.player
        me.pass_turn()
        all_passed = all(p.has_passed for p in self.game.players)
        # Durante combate ativo: nao avanca fase (so rotaciona)
        if all_passed and self.game.combat.is_active:
            self.game.next_player()
            return True
        if all_passed:
            self.game.next_phase()
            for p in self.game.players:
                p.reset_pass()
            self.game.add_log(f'Todos passaram. Fase: {self.game.phase}')
        else:
            self.game.next_player()
            self.game.add_log(
                f'[BOT] {me.name} passou. Vez de {self.game.current_player.name}')
