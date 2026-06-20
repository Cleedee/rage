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
from rage_web.game_engine.bot.strategy_engine import StrategyEngine
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
        # Motor de estrategia (carrega config do deck se disponivel)
        deck_id = getattr(self.player, 'deck_id', 0)
        self.strategy = StrategyEngine(deck_id=deck_id)
        self._has_strategy = self.strategy.is_loaded()
        if self._has_strategy:
            logger.info(f'[Bot] Estrategia carregada para {self.player.name}')

        # Heuristicas do bot
        self._cards_played_this_turn = 0
        self._umbra_agiu = False  # So uma acao de Umbra por fase
        self._feinted_ids = set()  # IDs que ja usaram Feint neste combate
        # Slow deck detection
        self._vp_history: list[float] = []  # VP total ao final de cada turno
        self._vp_rate: float = 0.0  # VP/turn medio
        # Ataques por fase de combate
        self._ataques_feitos: set[str] = set()
        self._turno_ultimo_kill: int = 0
        self._ataques_sem_morte: int = 0

    @property
    def player(self) -> PlayerState:
        for p in self.game.players:
            if p.id == self.player_id:
                return p
        raise ValueError(f'Jogador {self.player_id} nao encontrado')

    @property
    def _deck_strategy(self) -> str:
        """Retorna a estrategia do deck deste bot."""
        return self.player.deck_strategy or 'midrange'

    def _is_strategy(self, strategy: str) -> bool:
        """Verifica se a estrategia do bot corresponde."""
        return self._deck_strategy == strategy

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
            # Se passou turno sem matar ninguem, incrementa contador
            if g.turn_number > self._turno_ultimo_kill + 1:
                self._ataques_sem_morte += 1
            else:
                self._ataques_sem_morte = 0

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
            # Atualiza turno do ultimo kill
            if self._vp_history and len(self._vp_history) >= 2:
                if self._vp_history[-1] > self._vp_history[-2]:
                    self._turno_ultimo_kill = g.turn_number
            # Tenta jogar Bully's Quest (carta do tipo Quest que pode ser
            # jogada na Regeneration Phase para matar vitima de Renown <= 3)
            from rage_web.game_engine.effects import CARTAS_EXEMPLO
            for i, card in enumerate(self.player.hand):
                ct = card.card_type or ''
                if ct == 'Quest' and card.modelo_id:
                    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                    if modelo and modelo.modos:
                        for mi, modo in enumerate(modelo.modos):
                            for ef in modo.efeitos:
                                if ef.tipo.value == 'matar_vitima':
                                    if self._pode_pagar_custos(card):
                                        return self._usar_carta_efeito(i, mi, card)
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

        # TIPOS que NAO sao de recurso (nao podem ser jogados na fase Resource)
        TIPOS_NAO_RECURSO = {'Combat Action', 'Combat Event', 'Moot', 'Board Meeting', 'Action'}

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

            # ── Strategy Engine: gift_priorities sobrescreve pontuacao ──
            if ct == 'Gift' and self._has_strategy:
                gifted = self.strategy.sorted_gifts(
                    me.hand, self.game, me, self)
                for prio, gc in gifted:
                    if gc.card_id == card.card_id:
                        score = max(score, prio)
                        break

            # ── Strategy Engine: event_priorities (ex: Rewards of Leadership) ──
            if ct == 'Event' and self._has_strategy:
                events = self.strategy.sorted_events(
                    me.hand, self.game, me, self)
                for prio, ec in events:
                    if ec.card_id == card.card_id:
                        score = max(score, prio)
                        break

            # 10. Gift / Event: util se tem personagens
            elif ct == 'Gift':
                if tem_character:
                    score += 35
                else:
                    score -= 10
            elif ct in ('Event',):
                score += 20
            # Action cards sao para combate, nao recurso

            # 11. Cartas sem modelo_id: inuteis
            if not card.modelo_id and score < 50:
                score -= 30

            scored.append((i, score, card))

        # ── Strategy Engine: resource_play_order ajusta ordem ──
        if self._has_strategy and self.strategy.resource_play_order():
            ordem = self.strategy.resource_play_order()
            def _ordem_key(item):
                _, s, card = item
                ct = (card.card_type or '').lower()
                # Encontra a posicao na ordem configurada
                for pos, tipo in enumerate(ordem):
                    if tipo.lower() in ct:
                        # Prioridade: posicao na ordem (menor = melhor)
                        return (0, pos, -s)
                return (1, 0, -s)  # Nao configurado: depois dos configurados
            scored.sort(key=_ordem_key)
        else:
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
                    # ── Allies Below: so joga se tem inimigos no HG ──
                    if card.modelo_id == 'allies-below':
                        hg_vals = [
                            c for c in me.hunting_grounds
                            if c.health_current > 0]
                        if not hg_vals:
                            continue  # Pula, nao ha alvos
                    # Verifica condicao_uso (ex: Rewards of Leadership)
                    from rage_web.game_engine.effects import (
                        CARTAS_EXEMPLO, _validar_condicao_uso)
                    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                    if modelo and modelo.modos:
                        cond_ok = all(
                            not m.condicao_uso
                            or _validar_condicao_uso(
                                self.game, self.player, m.condicao_uso)
                            for m in modelo.modos
                        )
                        if not cond_ok:
                            continue  # Condicao nao atendida, pula
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
                                # Verifica condicao_uso
                                if modo.condicao_uso:
                                    from rage_web.game_engine.effects import _validar_condicao_uso
                                    if not _validar_condicao_uso(
                                            self.game, self.player, modo.condicao_uso):
                                        continue
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

            # ── Strategy Engine: redraw_rules sobrescreve score ──
            if self._has_strategy:
                keep = self.strategy.should_keep_in_redraw(c)
                if keep is True:
                    score += 200  # Nunca descarta
                elif keep is False:
                    score -= 200  # Sempre descarta se possivel

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
            # Passa a vez apos descartar+comprar para evitar ciclo
            # onde o bot descarta 1 carta, compra 1, e a engine o chama
            # novamente para descartar mais.
            self._pass_turn()
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

            # ── Strategy Engine: personagens preferidos para Umbra ──
            if self._has_strategy:
                umbra_cfg = self.strategy.get('umbra_strategy', {})
                enter_chars = umbra_cfg.get('enter_characters', [])
                save_chars = umbra_cfg.get('save_for_combat', [])

                # Se ha personagens especificos para entrar, prioriza
                for entry in enter_chars:
                    for c in podem_ir:
                        if entry.lower() in (c.name or '').lower():
                            self.player.step_sideways(c)
                            self.game.add_log(
                                f'[BOT] {self.player.name}: {c.name} '
                                f'entrou na Umbra (estratégia)')
                            return f'umbra_step_{c.card_id}'

                # Se ha personagens para preservar para combate, exclui
                if save_chars:
                    podem_ir = [
                        c for c in podem_ir
                        if not any(s.lower() in (c.name or '').lower()
                                  for s in save_chars)
                    ]
                    if not podem_ir:
                        self._pass_turn()
                        return 'pass_umbra'

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

        # ── REWARDS OF LEADERSHIP: janela pre-alpha ──
        # Se o jogador tem o modifier, joga Equipment/Ally/Territory da mao
        if any(m.modifier == 'rewards_leadership_play' and m.card_uid == id(me)
               for m in g.game_modifiers):
            # Remove o modifier (uso unico)
            g.game_modifiers = [m for m in g.game_modifiers
                                if not (m.modifier == 'rewards_leadership_play'
                                       and m.card_uid == id(me))]
            for i, card in enumerate(me.hand):
                ct = (card.card_type or '').lower()
                if 'equipment' in ct or ct == 'ally' or ct == 'territory':
                    if self._pode_pagar_custos(card):
                        from rage_web.game_engine.rules import zona_da_carta
                        zona = zona_da_carta(card.card_type or '')
                        if card.modelo_id:
                            modo_idx = self._escolher_melhor_modo(card.modelo_id)
                            self._cards_played_this_turn += 1
                            g.add_log(f'[BOT] {me.name}: Rewards — jogando {card.name}')
                            return self._usar_carta_efeito(i, modo_idx, card)
                        else:
                            self._play_card(i)
                            self._cards_played_this_turn += 1
                            g.add_log(f'[BOT] {me.name}: Rewards — jogando {card.name}')
                            return f'rewards_play_{card.card_id}'
            # Nao havia cartas elegiveis ou viaveis; continua
            g.add_log(f'[BOT] {me.name}: Rewards — nenhuma carta viavel na mao')

        lento = self._is_slow_deck()

        # ── ACAO ALFA ──
        alfa_atual = g.combat.current_alpha
        meu_alpha = g.combat.alphas.get(self.player_id)

        if alfa_atual and meu_alpha and alfa_atual == meu_alpha:
            # 🛑 Regra 6.3: se ja atacamos e combate encerrou, alpha nao ataca de novo
            if not g.combat.is_active and self._ataques_feitos:
                g.combat.current_alpha_index += 1
                g.add_log(f'[BOT] {me.name}: alpha passou (ja atacou - regra 6.3)')
            else:
                action = self._agir_alpha()
                if action:
                    g.combat.current_alpha_index += 1
                    return action
                # Alpha nao agiu (sem alvos). Remove de _ataques_feitos
                # para permitir que _try_attack() funcione.
                meu_alpha_id = g.combat.alphas.get(self.player_id)
                if meu_alpha_id and meu_alpha_id in self._ataques_feitos:
                    self._ataques_feitos.discard(meu_alpha_id)
                g.combat.current_alpha_index += 1

        # ── RESTO DO COMBATE (cartas, eliminar, atacar) ──
        # Se o combate esta ativo, declarar acoes de combate
        if g.combat.is_active:
            return self._decide_combat()

        # 🛑 Regra 6.3: apos o combate encerrar, o defensor pode
        # selecionar um novo alpha e declarar ataque — nao o mesmo
        # atacante. Se este bot ja atacou nesta fase, passa a vez.
        if self._ataques_feitos:
            self._pass_turn()
            return 'pass_pos_combate'

        # Acoes de ataque/eliminar sempre sao permitidas (sem limite).
        # So jogar cartas da mao tem limite de 3 por turno.

        # ── ORDEM DE PRIORIDADES POR ESTRATEGIA ──
        strategy = self._deck_strategy

        if strategy == 'control':
            # Control: sobreviver > eliminar > desenvolver > atacar
            action = self._try_survive()
            if action:
                return action
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_develop_board() if self._cards_played_this_turn < 3 else None
            if action:
                self._cards_played_this_turn += 1
                return action
            action = self._try_attack()
            if action:
                return action

        elif strategy == 'aggro':
            # Aggro: eliminar > atacar > desenvolver > sobreviver
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action
            action = self._try_develop_board() if self._cards_played_this_turn < 3 else None
            if action:
                self._cards_played_this_turn += 1
                return action
            action = self._try_survive()
            if action:
                return action

        elif strategy == 'vp_race':
            # VP Race: desenvolver (quests/VP) > sobreviver > eliminar > atacar
            action = self._try_develop_board() if self._cards_played_this_turn < 3 else None
            if action:
                self._cards_played_this_turn += 1
                return action
            action = self._try_survive()
            if action:
                return action
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action

        elif lento or strategy == 'swarm':
            # Lento/Swarm: eliminar > atacar > sobreviver > desenvolver
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action
            action = self._try_survive()
            if action:
                return action
            action = self._try_develop_board() if self._cards_played_this_turn < 3 else None
            if action:
                self._cards_played_this_turn += 1
                return action

        else:
            # midrange / default: sobreviver > desenvolver > eliminar > atacar
            action = self._try_survive()
            if action:
                return action
            action = self._try_develop_board() if self._cards_played_this_turn < 3 else None
            if action:
                self._cards_played_this_turn += 1
                return action
            action = self._try_eliminate_threat()
            if action:
                return action
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
        # 🛑 Regra 6.3: nao atacar de novo apos combate encerrar
        if self._ataques_feitos:
            self._pass_turn()
            return 'pass_pos_combate'
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
            self.game.add_log(
                f'[BOT] Alpha {alpha_card.name} atacou '
                f'{alvo_hg.name} no Hunting Grounds (estrategico)')
            start_combat(self.game, [meu_alpha_id],
                         [str(alvo_hg.card_id)])
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
                self.game.add_log(
                    f'[BOT] Alpha {alpha_card.name} atacou alpha '
                    f'{alpha_inimigo.name} ({opp.name})')
                start_combat(self.game, [meu_alpha_id],
                             [str(alpha_inimigo.card_id)])
                return f'alpha_attack_alpha_{meu_alpha_id}'

        # 2. Ataca personagens que dao VP (Character) primeiro.
        #    Prioriza menor HP para kills faceis.
        alvos_character = []
        alvos_outros = []
        for opp in opponents:
            for c in opp.pack_home:
                if c.health_current > 0:
                    ct = (c.card_type or '').lower()
                    if 'character' in ct:
                        alvos_character.append(c)
                    else:
                        alvos_outros.append(c)

        # Characters: menor HP primeiro (kills faceis = VP rapido)
        if alvos_character:
            alvos_character.sort(key=lambda c: c.health_current)
            for alvo in alvos_character:
                if self.prioritizer.pode_eliminar(alpha_card, alvo):
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'personagem {alvo.name} (HP {alvo.health_current})')
                    start_combat(self.game, [meu_alpha_id],
                                 [str(alvo.card_id)])
                    return f'alpha_attack_{meu_alpha_id}_vs_{alvo.card_id}'

        # Fallback: ataca nao-Characters (nao dao VP, mas eliminam ameacas)
        if alvos_outros:
            alvos_outros.sort(key=self.prioritizer.rate_threat,
                              reverse=True)
            for alvo in alvos_outros:
                if self.prioritizer.pode_eliminar(alpha_card, alvo):
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'{alvo.name} (nao-Character)')
                    start_combat(self.game, [meu_alpha_id],
                                 [str(alvo.card_id)])
                    return f'alpha_attack_{meu_alpha_id}_vs_{alvo.card_id}'

        # 3. Tenta atacar Territory inimigo (6.5.4)
        for opp in opponents:
            for c in opp.pack_home:
                ct = (c.card_type or '').lower()
                if 'territory' in ct or 'realm' in ct:
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'Territory {c.name} ({opp.name})')
                    start_combat(self.game, [meu_alpha_id],
                                 [str(c.card_id)],
                                 attack_type='territory',
                                 target_card_id=str(c.card_id))
                    return f'alpha_attack_territory_{meu_alpha_id}'

        # 4. Tenta atacar Battlefield inimigo (6.5.3)
        for opp in opponents:
            for c in opp.pack_home + opp.hunting_grounds:
                ct = (c.card_type or '').lower()
                if 'battlefield' in ct:
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'Battlefield {c.name} ({opp.name})')
                    start_combat(self.game, [meu_alpha_id],
                                 [str(c.card_id)],
                                 attack_type='battlefield',
                                 target_card_id=str(c.card_id))
                    return f'alpha_attack_battlefield_{meu_alpha_id}'

        # 5. Tenta vincular Spirit no Hunting Grounds (6.5.5)
        # So disponivel se o alpha esta na Umbra
        if alpha_card.zone == Zone.UMBRA:
            for opp in opponents:
                for c in opp.hunting_grounds:
                    ct = (c.card_type or '').lower()
                    if 'spirit' in ct:
                        # Spirit no HG pode ser vinculado
                        self.game.add_log(
                            f'[BOT] Alpha {alpha_card.name} tentou '
                            f'vincular Spirit {c.name} ({opp.name})')
                        start_combat(self.game, [meu_alpha_id],
                                     [str(c.card_id)],
                                     attack_type='bind',
                                     target_card_id=str(c.card_id))
                        return f'alpha_attack_bind_{meu_alpha_id}'

        # 6. Fallback: ataca Presa no Hunting Grounds
        if alvo_hg:
            self.game.add_log(
                f'[BOT] Alpha {alpha_card.name} atacou '
                '{alvo_hg.name} no Hunting Grounds')
            start_combat(self.game, [meu_alpha_id], [str(alvo_hg.card_id)])
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
            return f'combat_to_{g.combat.step}'

        if step in ('pre_combat', 'beginning_of_combat'):
            # Pre-Combat: stepping in for Prey, gifts, pack actions
            # Processado via advance_combat_step (auto-advance) que
            # chama _preparar_stepping_in para stepping in.
            # Gifts para Presa sao tratados em _tentar_stepping_prey
            # durante a fase resource (quando combat esta ativo).
            advance_combat_step(g)
            return f'combat_to_{g.combat.step}'

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
                    # Se for Presa no HG: qualquer jogador exceto o atacante pode declarar
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue  # Atacante nao pode declarar pela Presa
                        # Verifica se este jogador e o designado (6.6.3)
                        desig = g.combat.prey_player.get(cid)
                        if desig and desig != self.player_id:
                            continue  # Nao e o jogador designado para esta presa
                    else:
                        # Criatura normal: so o dono declara
                        if card.owner_id != self.player_id:
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
                            if nome_acao in COMBAT_ACTIONS:
                                result = declare_action(g, cid, nome_acao)
                                if result:
                                    return f'declare_{cid}_{nome_acao}'
                            # Fallback: acao aleatoria viavel
                            acoes = list(COMBAT_ACTIONS)
                            g.rng.shuffle(acoes)
                            for a in acoes:
                                result = declare_action(g, cid, a)
                                if result:
                                    return f'declare_{cid}_{a}'
                        self._pass_turn()
                        return 'combat_wait'

                    # Se for Presa e nao-atacante: tenta jogar Gift para ela
                    # Regra: Prey pode usar Gifts que correspondam ao seu tipo
                    if _eh_prey_no_hg(g, cid) and not _eh_atacante_da_presa(g, cid, self.player_id):
                        # Verifica se este jogador e o designado (6.6.3)
                        desig = g.combat.prey_player.get(cid)
                        if desig and desig != self.player_id:
                            pass  # Gift nao tem restricao de jogador unico
                        from rage_web.game_engine.rules import pode_usar_gift_para_presa
                        for i, gift_card in enumerate(self.player.hand):
                            ct = (gift_card.card_type or '').lower()
                            if 'gift' not in ct and ct != 'gift':
                                continue
                            if not gift_card.modelo_id:
                                continue
                            if not self._pode_pagar_custos(gift_card):
                                continue
                            if pode_usar_gift_para_presa(card, gift_card):
                                modo_idx = self._escolher_melhor_modo(gift_card.modelo_id)
                                g.add_log(
                                    f'[BOT] {self.player.name} usou '
                                    f'{gift_card.name} para {card.name}'
                                )
                                return self._usar_carta_efeito(i, modo_idx, gift_card)

                    # P4+P8: Tenta usar carta da mao de combate como acao
                    # ANTES de tentar blefe (primeiro carta valida, depois ilegal)
                    carta_acao, carta_combate = self._escolher_carta_combate_como_acao(card)
                    if carta_acao and carta_combate:
                        # ── Passa a carta de combate original (regra 6.4) ──
                        # A carta sera anexada ao alvo como dano na resolucao,
                        # em vez de criar uma damage card copia.
                        result = declare_action(g, cid, carta_acao,
                                                carta_combate=carta_combate)
                        if result:
                            # P8: acao virtual 'dano_' ja consumiu a carta
                            if not carta_acao.startswith('dano_'):
                                # P4: remove a carta da mao de combate
                                # (ela sera anexada ao alvo na resolucao)
                                if carta_combate in self.player.hand:
                                    self.player.hand.remove(carta_combate)
                                    carta_combate.zone = Zone.OUT_OF_PLAY
                            self._usou_carta_combate = True
                            g.add_log(f'{self.player.name} usou carta de combate '
                                      f'{carta_combate.name} como {carta_acao}')
                            return f'declare_{cid}_{carta_acao}'

                    owner = card.owner_id or self.player_id
                    action = self._choose_combat_action(card, owner)
                    result = declare_action(g, cid, action)
                    if not result:
                        # 6.6.6b: Forced Play — se tem carta e nao conseguiu,
                        # tenta qualquer acao viavel (mesmo ilegal/bluff)
                        if g.combat.has_forced_play(cid):
                            for acao_forcada in COMBAT_ACTIONS:
                                result = declare_action(g, cid, acao_forcada)
                                if result:
                                    action = acao_forcada
                                    break
                    if not result:
                        # Tenta jogar CE face-down (Combat Events sao jogados
                        # face-down por natureza — acao legitima, nao blefe)
                        from rage_web.game_engine.combat_queue import \
                            _jogar_ce_face_down
                        ce_jogado = self._tentar_ce_face_down(card)
                        if ce_jogado:
                            return ce_jogado

                    if not result:
                        # Ainda falhou: marca como passou (impede loop)
                        g.combat.played_cards[cid] = ''
                        self._pass_turn()
                        return 'combat_wait'
                    return f'declare_{cid}_{action}'

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
                if card is None:
                    continue
                # Presa: qualquer jogador (exceto atacante) pode escolher alvo
                if _eh_prey_no_hg(g, cid):
                    if _eh_atacante_da_presa(g, cid, self.player_id):
                        continue
                elif card.owner_id != self.player_id:
                    continue
                acao = g.combat.declarations.get(cid, '')
                if acao in ('block', 'dodge', 'flee'):
                    continue  # defensivas nao precisam de alvo
                # Escolhe alvo: oponente
                alvo = self._escolher_alvo_pack(cid)
                if alvo:
                    g.combat.targets[cid] = alvo
                    return f'target_{cid}_{alvo}'
            g.combat.step = 'reveal'
            return f'combat_to_{g.combat.step}'

        if step == 'reveal':
            return self._handle_reveal_step()

        if step == 'feint':
            return self._handle_feint_step()

        if step == 'bluff':
            # Bluff Step: verificar requisitos
            advance_combat_step(g)
            return f'combat_to_{g.combat.step}'

        if step == 'resolution':
            # Resolution Step: aplicar dano
            resolve_combat(g)
            return 'combat_resolve'

        if step == 'withdrawal':
            # Withdrawal Step: verificar se atacante retira
            advance_combat_step(g)
            return f'combat_to_{g.combat.step}'

        if step == 'between_rounds':
            # Between-rounds: verificar se continua
            if not g.combat.attackers or not g.combat.defenders:
                g.combat.step = 'end'
                return 'combat_end'
            advance_combat_step(g)
            return f'combat_to_{g.combat.step}'

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
                    # Se for Presa no HG: qualquer jogador exceto o atacante pode declarar
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue  # Atacante nao pode declarar pela Presa
                    else:
                        if card.owner_id != self.player_id:
                            continue
                    owner = card.owner_id or self.player_id
                    action = self._choose_combat_action(card, owner)
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
        return f'combat_to_{g.combat.step}'

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
        return f'combat_to_{g.combat.step}'

    def _melhor_acao_feint(self, criatura: CardInstance,
                           acao_atual: str,
                           oponentes: dict[str, str],
                           opp: PlayerState) -> Optional[str]:
        """Decide qual acao seria melhor apos ver as revelacoes.

        Nota: acoes sinteticas (strike, dodge, block) foram removidas.
        Toda acao requer uma Combat Action real.
        O feint so pode substituir por outra carta que a criatura
        tenha na mao de combate.
        """
        # Sem acao atual, nao ha o que substituir
        if not acao_atual:
            return None

        # Tenta encontrar carta de combate viavel na mao
        # (delega para _escolher_carta_combate_como_acao se disponivel)
        return None  # Por ora: mantem acao atual

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
            return f'combat_to_{g.combat.step}'

        if step == 'play_card':
            for cid in combatants:
                if cid not in g.combat.played_cards:
                    if _eh_prey_no_hg(g, cid):
                        if _eh_atacante_da_presa(g, cid, self.player_id):
                            continue
                    # P4+P8: Tenta usar carta da mao de combate como acao
                    # (carta valida primeiro, CE ilegal como ultimo recurso)
                    card = _find_card(g, cid)
                    if card and card.owner_id == self.player_id:
                        carta_acao, carta_combate = self._escolher_carta_combate_como_acao(card)
                        if carta_acao and carta_combate and self.game.rng.random() < 0.5:
                            result = declare_action(g, cid, carta_acao,
                                                    carta_combate=carta_combate)
                            if result:
                                # P8: acao virtual 'dano_' ja consumiu a carta
                                if not carta_acao.startswith('dano_'):
                                    if carta_combate in self.player.hand:
                                        self.player.hand.remove(carta_combate)
                                        carta_combate.zone = Zone.OUT_OF_PLAY
                                return f'declare_{cid}_{carta_acao}'
                    # CE face-down como blefe (ultimo recurso)
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
                    action = self.game.rng.choice(list(COMBAT_ACTIONS))
                    result = declare_action(g, cid, action)
                    if not result:
                        # Sem acao viavel: passa (criatura nao joga carta)
                        self._pass_turn()
                        return 'combat_wait'
                    return f'declare_{cid}_{action}'
            g.combat.step = 'targeting'
            return f'combat_to_{g.combat.step}'

        if step == 'targeting':
            # Random: atribui alvos aleatorios
            for cid in g.combat.attackers + g.combat.defenders:
                if cid in g.combat.targets:
                    continue
                card = _find_card(g, cid)
                if not card or card.owner_id != self.player_id:
                    continue
                acao = g.combat.declarations.get(cid, '')
                if acao in ('block', 'dodge', 'flee') or not acao:
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
            return f'combat_to_{g.combat.step}'

        if step == 'reveal':
            return self._handle_reveal_step()

        if step == 'feint':
            g.combat.step = 'bluff'
            return f'combat_to_{g.combat.step}'
        if step in ('bluff', 'withdrawal', 'between_rounds'):
            advance_combat_step(g)
            return f'combat_to_{g.combat.step}'

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
            # (6.11.1) Frenzied nao pode jogar Gifts
            for c in self.player.pack_home:
                if c.is_frenzied:
                    return False
            # Valida timing
            if not validar_timing_gift(card, self.game.phase, self.game.combat.step):
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

        # 6. Ja tentou atacar 2+ vezes sem sucesso: muda para presa
        #    (evita loop de combates que nao matam ninguem)
        if len(self._ataques_feitos) >= 2:
            return True

        # 7. Cenario normal: tenta matar inimigo primeiro
        return False

    def _try_eliminate_threat(self) -> Optional[str]:
        """Prioridade 2: Eliminar ameaca.

        Com N jogadores, avia ameacas de TODOS os oponentes,
        priorizando criaturas do lider em VP.
        """
        me = self.player
        opponents = self._get_opponents()
        lento = self._is_slow_deck()

        # ── Strategy Engine: FFA diplomacy redireciona alvo ──
        if self._has_strategy and len(opponents) >= 2:
            target_id = self.strategy.get_ffa_target(self.game, me)
            if target_id:
                opponents.sort(key=lambda p: p.id != target_id)

        if not me.pack_home:
            return None

        available = [c for c in me.pack_home
                     if self._pode_atacar(c)]
        if not available:
            return None

        # Agrega ameacas de todos os oponentes
        # Prioriza Characters (dao VP) sobre nao-Characters
        alvos_character = []
        alvos_outros = []
        for opp in opponents:
            for c in opp.pack_home:
                if c.health_current > 0:
                    ct = (c.card_type or '').lower()
                    if 'character' in ct:
                        alvos_character.append(c)
                    else:
                        alvos_outros.append(c)

        # Characters: menor HP primeiro (kill facil = VP rapido)
        if alvos_character:
            alvos_character.sort(key=lambda c: c.health_current)
            for alvo in alvos_character:
                atacante = self.prioritizer.best_attacker_for(alvo, available)
                if atacante:
                    pode = self.prioritizer.pode_eliminar(atacante, alvo,
                                                           modo_lento=lento)
                    if pode:
                        self._attack(str(atacante.card_id), str(alvo.card_id))
                        return f'eliminate_{atacante.card_id}_vs_{alvo.card_id}'

        # Fallback: nao-Characters
        if alvos_outros:
            alvos_outros.sort(key=self.prioritizer.rate_threat, reverse=True)
            for alvo in alvos_outros:
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
        # Pula cartas que sao jogadas exclusivamente na Regeneration Phase
        # (ex: Bully's Quest com efeito matar_vitima)
        QUEST_REGENERATION = {'matar_vitima'}
        for i, card in enumerate(me.hand):
            ct = card.card_type or ''
            if ct in ('Quest', 'Past Life'):
                if card.modelo_id and self._pode_pagar_custos(card):
                    from rage_web.game_engine.effects import CARTAS_EXEMPLO
                    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
                    if modelo and modelo.modos:
                        # Pula se carta so pode ser jogada na Regeneration
                        tem_efeito_regen = any(
                            ef.tipo.value in QUEST_REGENERATION
                            for modo in modelo.modos
                            for ef in modo.efeitos
                        )
                        if tem_efeito_regen:
                            continue
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
        if not modelo or not modelo.modos:
            self._play_card(hand_index)
            return f'play_{card.card_id}'

        # Pagar custos (ja validado por _pode_pagar_custos)
        custo_rage = parse_custo_rage(card.damage)
        if custo_rage is not None and custo_rage > 0:
            pagador = self.player.pagar_custo_rage(custo_rage)
            if pagador:
                self.game.add_log(
                    f'[BOT] {self.player.name} {pagador} (Rage {custo_rage}): '
                    f'{card.name}')
        if card.gnosis and card.gnosis > 0:
            pagador = self.player.pagar_custo_gnosis(card.gnosis)
            if pagador:
                self.game.add_log(
                    f'[BOT] {self.player.name} {pagador} (Gnosis {card.gnosis}): '
                    f'{card.name}')

        # Remove da mao e aplica (passa card real para equipamentos)
        card_real = self.player.hand.pop(hand_index)

        modo = modelo.modos[modo_idx]
        desc = f'use_{card.modelo_id}_modo{modo_idx}'
        # Log do uso ANTES de aplicar o efeito, para que a sequencia
        # fique: pagou → usou → sofreu dano → foi destruido
        self.game.add_log(
            f'[BOT] {self.player.name} usou {card.name} ({modo.descricao})')

        logs = aplicar_carta(self.game, modelo, self.player_id,
                              modo_idx=modo_idx, card_origem=card_real)

        # ── Personal Totems: ficam em jogo anexados a um Character ──
        # Regra (4.5.2B): Personal Totem e jogado em um unico Character
        # e permanece em jogo. O efeito ja foi resolvido, agora precisa
        # registrar as passivas e anexar ao Character.
        ct = (card_real.card_type or '').lower()
        if 'event' in ct and 'personal totem' in (card_real.text or '').lower():
            self.game.register_card_passives(card_real, self.player)
            if card_real.attached_to:
                # Ja foi anexado pelo register_card_passives
                pass
            elif card_real.zone in (Zone.OUT_OF_PLAY, Zone.HAND):
                card_real.zone = Zone.PACK_HOME
                if card_real not in self.player.pack_home:
                    self.player.pack_home.append(card_real)
                self.game.add_log(
                    f'{card_real.name} (Personal Totem) permanece em jogo')
        # Descarta a carta apos o uso, a menos que tenha sido anexada
        # a uma criatura (gift/equipamento persistente)
        elif 'gift' not in ct and getattr(card_real, 'attached_to', None) is None:
            # So descarta se a carta nao estiver em nenhuma zona ativa
            # (ja pode ter sido movida pelo efeito)
            if card_real.zone in (Zone.OUT_OF_PLAY, Zone.HAND):
                card_real.zone = Zone.DISCARD_SEPT
                self.player.discard_sept.append(card_real)

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

        Estrategia:
        - aggro: ataca mesmo com chance menor (50% do Rage)
        - swarm: ataca mesmo sem chance de matar (desgasta)
        - control: so ataca se pode eliminar
        - vp_race: evita combate arriscado
        """
        me = self.player
        opponents = self._get_opponents()
        lento = self._is_slow_deck()
        strategy = self._deck_strategy

        # ── Strategy Engine: FFA diplomacy redireciona alvo ──
        if self._has_strategy and len(opponents) >= 2:
            target_id = self.strategy.get_ffa_target(self.game, me)
            if target_id:
                # Reordena opponents para priorizar o alvo da estrategia
                opponents.sort(key=lambda p: p.id != target_id)

        # Swarm: ataca mesmo sem chance de matar (desgaste)
        if strategy == 'swarm':
            all_attackers = [c for c in me.pack_home
                             if self._pode_atacar(c)]
            if all_attackers:
                atacante = max(all_attackers, key=lambda c: c.rage)
                self.game.add_log(
                    f'[SWARM] {me.name} ataque enxame '
                    f'com {atacante.name} (Rg {atacante.rage})')
                # Ataca o Hunting Grounds se tiver presa
                from rage_web.game_engine.combat_queue import _eh_pack_gaia
                eh_gaia = _eh_pack_gaia(me)
                hg_targets = [c for c in self.game.hunting_grounds_cards
                              if c.health_current > 0]
                for hg in hg_targets:
                    ct = (hg.card_type or '').lower()
                    # Gaia nao ganha VP matando Victim, mas ataca assim mesmo
                    self._attack(str(atacante.card_id), str(hg.card_id))
                    return (f'swarm_hg_{atacante.card_id}'
                            f'_vs_{hg.card_id}')
                # Sem presa no HG, ataca personagem mais fraco do oponente
                for opp in opponents:
                    alvos = sorted(
                        [c for c in opp.pack_home if c.health_current > 0],
                        key=lambda c: c.health_current)
                    if alvos:
                        alvo = alvos[0]
                        self._attack(
                            str(atacante.card_id),
                            str(alvo.card_id))
                        return (f'swarm_attack_'
                                f'{atacante.card_id}'
                                f'_vs_{alvo.card_id}')
            return None

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
        alvos_character = []  # VP-giving targets
        alvos_nao_character = []  # non-VP targets (Allies, etc.)
        for opp in opponents:
            # Sky River: so pode atacar o Alpha (maior Renown)
            if opp.id in sky_river_packs:
                alvos_permitidos = []
                alpha = max(
                    [c for c in opp.pack_home if c.health_current > 0],
                    key=lambda x: x.renown,
                    default=None
                )
                if alpha:
                    alvos_permitidos.append(alpha)
                for c in self.game.hunting_grounds_cards:
                    if c.health_current > 0:
                        alvos_permitidos.append(c)
                todas_ameacas.extend(alvos_permitidos)
            else:
                for c in opp.pack_home:
                    if c.health_current > 0:
                        ct = (c.card_type or '').lower()
                        if 'character' in ct:
                            alvos_character.append(c)
                        else:
                            alvos_nao_character.append(c)

        # Prioriza alvos que dao VP (Characters): menor HP primeiro
        if alvos_character:
            alvos_character.sort(key=lambda c: c.health_current)
            modo_lento_eff = lento or self._is_strategy('aggro')
            for alvo in alvos_character:
                atacante = self.prioritizer.best_attacker_for(alvo, available)
                if atacante:
                    if self.prioritizer.pode_eliminar(atacante, alvo,
                                                       modo_lento=modo_lento_eff):
                        self._attack(str(atacante.card_id), str(alvo.card_id))
                        return (f'eliminate_{atacante.card_id}'
                                f'_vs_{alvo.card_id}')

        # Fallback: ataca nao-Characters (nao dao VP, mas eliminam ameacas)
        if alvos_nao_character:
            alvos_nao_character.sort(key=self.prioritizer.rate_threat,
                              reverse=True)
            for alvo in alvos_nao_character:
                atacante = self.prioritizer.best_attacker_for(alvo, available)
                if atacante:
                    if self.prioritizer.pode_eliminar(atacante, alvo,
                                                       modo_lento=modo_lento_eff):
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
        """P4+P8: Tenta usar carta da mao de combate como acao declarada.

        Duas estrategias:
        P4: Mapeia nome da carta para COMBAT_ACTION conhecida
            (ex: 'Head Butt' -> 'head_butt').
        P8: Para cartas com efeito 'dano' no modelo que nao mapeiam
            para acao conhecida, cria acao virtual 'dano_<uid>'.

        Retorna:
            (action_name, card_instance) ou (None, None) se nenhuma
            carta viavel foi encontrada.
        """
        if not self.player.combat_hand:
            return None, None

        from rage_web.game_engine.combat_queue import (
            COMBAT_ACTION_PROPS, COMBAT_ACTION_VALIDATORS,
            _registrar_acao_dano)
        from rage_web.game_engine.effects import CARTAS_EXEMPLO

        nivel_restrito = self.game.combat.get_restricted_level(
            str(card.card_id))
        # ── Equipamentos que elevam limite de Rage ──
        # Chainsaw (10), Shotgun (7), Rocket Launcher (12)
        # Regra 4.3.2: considera apenas equipamentos ATIVOS
        from rage_web.game_engine.combat_queue import _equipamento_melhor_limite
        eq_rage_limit = _equipamento_melhor_limite(card)
        if eq_rage_limit > 0:
            nivel_restrito = max(nivel_restrito or 0, eq_rage_limit)

        # ── Regra 4.3.2: Bot decide se desativa equipamentos ──
        from rage_web.game_engine.combat_queue import _get_active_equipment
        equipamentos_ativos = _get_active_equipment(card)
        equip_to_disable_bot = []
        for eq in equipamentos_ativos:
            eq_slug = getattr(eq, 'modelo_id', '') or ''
            if eq_slug == 'chainsaw':
                for acao_check in ('head_butt', 'tail_lash', 'submission_hold'):
                    props = COMBAT_ACTION_PROPS.get(acao_check, {})
                    req = props.get('rage_requirement', 0)
                    if req >= 6 and card.effective_rage >= req:
                        equip_to_disable_bot.append(eq)
                        break

        for eq in equip_to_disable_bot:
            eid = id(eq)
            disabled = set(getattr(card, 'equipment_disabled', set()))
            disabled.add(eid)
            card.equipment_disabled = disabled
            self.game.add_log(
                f'[BOT] {self.player.name} desativou '
                f'{eq.name} em {card.name} (regra 4.3.2)')

        # Recalcula limite apos possivel desativacao
        from rage_web.game_engine.combat_queue import _equipamento_melhor_limite
        eq_rage_limit = _equipamento_melhor_limite(card)
        if eq_rage_limit > 0:
            nivel_restrito = max(nivel_restrito or 0, eq_rage_limit)

        # No Rage CCG nao existem acoes basicas intrinsecas
        # (strike, block, dodge, etc). Toda acao de combate
        # requer uma carta de Combat Action real.
        # Portanto nao ha 'melhor dano basico' para comparar.

        melhor_acao = None
        melhor_carta = None
        melhor_dano = -1

        # ── Strategy Engine: actions preferidas por personagem ──
        preferred_actions = []
        if self._has_strategy:
            char_name = card.name or ''
            preferred_actions = self.strategy.preferred_actions(char_name)
            if preferred_actions:
                self.game.add_log(
                    f'[BOT] Preferencias de acao para {char_name}: '
                    f'{preferred_actions}')

        # Converte preferencias para slug
        preferred_slugs = [a.lower().replace(' ', '_').replace('-', '_')
                          for a in preferred_actions]

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

            # ── P4: Checa se nome mapeia para COMBAT_ACTION ──
            # Todas as acoes sao cartas reais; nao ha acoes basicas
            # (block, dodge, etc) para pular.
            if nome_slug in COMBAT_ACTION_PROPS:
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

                # No Rage CCG toda acao requer uma carta real.
                # Usa qualquer carta com dano > 0.
                # ── Strategy Engine: bônus de prioridade ──
                dano_ajustado = acao_dano
                if preferred_slugs and nome_slug in preferred_slugs:
                    dano_ajustado += 20  # Bonus grande para ação preferida
                if dano_ajustado > 0 and dano_ajustado > melhor_dano:
                    melhor_acao = nome_slug
                    melhor_carta = carta_combate
                    melhor_dano = acao_dano  # Armazena dano real (sem bônus)

        # ── P8: Se P4 nao achou nada, busca cartas com efeito 'dano' ──
        # (ex: Telling Blow, Reckless Swing, Lucky Blow)
        if melhor_acao is None:
            for carta_combate in self.player.combat_hand:
                # Pula cartas que ja foram mapeadas (evita duplicacao)
                nome_slug = (carta_combate.name or '').lower().replace(' ', '_').replace('-', '_')
                if nome_slug in MAPA_NOMES_CARTA_PARA_ACAO:
                    nome_slug = MAPA_NOMES_CARTA_PARA_ACAO[nome_slug]
                if nome_slug in COMBAT_ACTION_PROPS:
                    continue  # Ja foi considerada em P4

                # Verifica se o modelo da carta tem efeito 'dano'
                if not carta_combate.modelo_id:
                    continue
                modelo = CARTAS_EXEMPLO.get(carta_combate.modelo_id)
                if not modelo or not modelo.modos:
                    continue

                # Encontra o primeiro efeito de dano
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
                    continue

                # Verifica Rage requirement do card (campo 'rage' no banco)
                rage_card = getattr(carta_combate, 'rage', 0)
                if card.effective_rage < rage_card:
                    continue
                if nivel_restrito is not None and rage_card > nivel_restrito:
                    continue

                # Verifica requisitos especiais (campo 'requires')
                reqs = (getattr(carta_combate, 'requires', '') or '').lower()
                if 'crino' in reqs and not card.is_crinos:
                    continue

                # No Rage CCG nao ha ataque basico — toda acao
                # requer carta real. Qualquer dano > 0 e util.

                # Registra acao virtual
                acao_virtual = _registrar_acao_dano(self.game, carta_combate,
                                                     str(card.card_id))
                if acao_virtual:
                    if dano_valor > melhor_dano:
                        melhor_acao = acao_virtual
                        melhor_carta = carta_combate  # Ja foi consumido
                        melhor_dano = dano_valor

        return melhor_acao, melhor_carta

    def _choose_combat_action(self, card: CardInstance,
                                owner_id: str) -> str:
        """Escolhe a melhor acao de combate para uma criatura.

        Considera dano de cada acao (COMBAT_ACTION_PROPS), requisito
        de Rage, e condicao da criatura.

        P4: Fallback quando _escolher_carta_combate_como_acao()
        nao encontra carta viavel nao mao de combate.

        Se for criatura do oponente, escolhe acao defensiva ou
        previsivel (block/dodge/strike). Se for do proprio bot,
        escolhe a acao ofensiva de maior dano viavel.

        Se for Presa (Enemy/Victim) sem dono, o interventor escolhe
        acao defensiva (block/dodge) para proteger a Presa.
        """
        me = self.player

        ct = (card.card_type or '').lower()

        # Presa em HG: sem carta de combate, nao age
        # (ataques de presa sao controlados por _check_victim_attacks)
        is_prey = any(t in ct for t in ('enemy', 'victim'))
        if is_prey and not card.owner_id:
            return ''

        if owner_id != self.player_id:
            # Criatura do oponente: sem carta de combate, nao age
            return ''

        # Criatura propria: escolhe acao ofensiva de maior dano viavel
        from rage_web.game_engine.combat_queue import COMBAT_ACTION_PROPS

        # 6.6.6a: Restricted Play — filtra por nivel maximo de Rage
        nivel_restrito = self.game.combat.get_restricted_level(
            str(card.card_id))
        # ── Equipamentos que elevam limite de Rage ──
        # Chainsaw (10), Shotgun (7), Rocket Launcher (12)
        # Regra 4.3.2: considera apenas equipamentos ATIVOS
        from rage_web.game_engine.combat_queue import _equipamento_melhor_limite
        eq_rage_limit = _equipamento_melhor_limite(card)
        if eq_rage_limit > 0:
            nivel_restrito = max(nivel_restrito or 0, eq_rage_limit)

        # ── Regra 4.3.2: Bot decide se desativa equipamentos ──
        from rage_web.game_engine.combat_queue import _get_active_equipment
        equipamentos_ativos = _get_active_equipment(card)
        equip_to_disable_bot = []
        for eq in equipamentos_ativos:
            eq_slug = getattr(eq, 'modelo_id', '') or ''
            if eq_slug == 'chainsaw':
                for acao_check in ('tail_lash', 'head_butt', 'submission_hold'):
                    props = COMBAT_ACTION_PROPS.get(acao_check, {})
                    req = props.get('rage_requirement', 0)
                    if req >= 6 and card.effective_rage >= req:
                        equip_to_disable_bot.append(eq)
                        break

        for eq in equip_to_disable_bot:
            eid = id(eq)
            disabled = set(getattr(card, 'equipment_disabled', set()))
            disabled.add(eid)
            card.equipment_disabled = disabled
            self.game.add_log(
                f'[BOT] {self.player.name} desativou '
                f'{eq.name} em {card.name} (regra 4.3.2)')

        # Recalcula limite apos possivel desativacao
        from rage_web.game_engine.combat_queue import _equipamento_melhor_limite
        eq_rage_limit = _equipamento_melhor_limite(card)
        if eq_rage_limit > 0:
            nivel_restrito = max(nivel_restrito or 0, eq_rage_limit)

        opp = self._get_opponent()
        melhor_acao = ''
        melhor_dano = -1

        # Per 6.6/6.9.2: nao existe Strike/Claw/Bite intrinseco.
        # Toda acao de combate requer uma carta de Combat Action real.
        # Nomes como anatomy_lesson, head_butt, tail_lash, etc. sao
        # CARTAS ESPECIFICAS, nao acoes basicas — o bot so pode
        # declara-las se encontrar a carta viavel via P4/P8.
        # Sem carta viavel, a criatura simplesmente nao age.
        return ''  # Criatura nao age sem carta de combate

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

        # Verifica se o CE tem condicao_uso que nao pode ser atendida
        # (ex: Attacking the Wyrm requer alpha atacando HG)
        if ce_card.modelo_id:
            from rage_web.game_engine.effects import (
                CARTAS_EXEMPLO, _validar_condicao_uso)
            modelo = CARTAS_EXEMPLO.get(ce_card.modelo_id)
            if modelo and modelo.modos:
                for modo in modelo.modos:
                    if modo.condicao_uso:
                        if not _validar_condicao_uso(
                                g, self.player, modo.condicao_uso):
                            # Condicao nao atendida: nao vale a pena
                            # desperdicar o CE como blefe
                            return None

        # Joga CE face-down
        if _jogar_ce_face_down(g, str(card.card_id),
                                str(ce_card.card_id)):
            g.add_log(f'[BOT] {self.player.name} jogou {ce_card.name} '
                      f'face-down como blefe')
            return f'play_{card.card_id}_ce_{ce_card.card_id}'
        return None

    def _tentar_stepping_prey(self) -> bool:
        """Tenta intervir (step in) para ajudar uma Presa no pre_combat.

        Regra (6.5.3): qualquer jogador exceto o atacante pode "step in"
        para ajudar uma Presa (Victim/Enemy/Battlefield) no HG que esta
        sendo atacada. O jogador pode:
        - Jogar um CE face-down em defesa da Presa
        - Usar uma carta de combate da mao como acao para a Presa
        - Jogar Gifts que correspondam ao tipo da Presa

        Returns:
            True se interveio com alguma acao.
        """
        from rage_web.game_engine.combat_queue import (_eh_prey_no_hg,
            _eh_atacante_da_presa, _find_card, _jogar_ce_face_down,
            COMBAT_ACTIONS, declare_action)
        from rage_web.game_engine.rules import pode_usar_gift_para_presa
        g = self.game

        if not g.combat.is_active:
            return False
        if g.combat.step not in ('pre_combat', 'beginning_of_combat'):
            return False

        # Verifica se ha Presa sendo atacada
        for dfd in g.combat.defenders:
            if not _eh_prey_no_hg(g, dfd):
                continue
            if _eh_atacante_da_presa(g, dfd, self.player_id):
                continue  # O atacante nao pode intervir

            card = _find_card(g, dfd)
            if not card:
                continue

            # 1. Tenta jogar Gift para a Presa (regra: Prey pode usar Gifts
            #    que correspondam ao seu tipo de criatura)
            for i, gift_card in enumerate(self.player.hand):
                if (gift_card.card_type == 'Gift'
                        and gift_card.modelo_id
                        and self._pode_pagar_custos(gift_card)
                        and pode_usar_gift_para_presa(card, gift_card)):
                    modo_idx = self._escolher_melhor_modo(gift_card.modelo_id)
                    action = self._usar_carta_efeito(i, modo_idx, gift_card)
                    if action:
                        g.add_log(
                            f'[BOT] {self.player.name} interveio: usou '
                            f'{gift_card.name} para {card.name}'
                        )
                        return True

            # 2. Tenta jogar CE face-down em defesa da Presa
            ce_card = None
            for c in self.player.combat_hand:
                ct = (c.card_type or '').lower()
                if 'combat event' in ct or ct == 'combat_event':
                    ce_card = c
                    break
            if not ce_card:
                for c in self.player.hand:
                    ct = (c.card_type or '').lower()
                    if 'combat event' in ct or ct == 'combat_event':
                        ce_card = c
                        break

            if ce_card:
                if _jogar_ce_face_down(g, dfd, str(ce_card.card_id)):
                    g.add_log(
                        f'[BOT] {self.player.name} interveio: jogou '
                        f'{ce_card.name} face-down para {card.name}'
                    )
                    return True

            # 3. Tenta usar carta de combate da mao como acao
            for c in self.player.combat_hand:
                nome_acao = (c.name or '').lower().replace(' ', '_')
                if nome_acao in COMBAT_ACTIONS:
                    if declare_action(g, dfd, nome_acao,
                                     carta_combate=c):
                        c.zone = Zone.OUT_OF_PLAY
                        if c in self.player.hand:
                            self.player.hand.remove(c)
                        g.add_log(
                            f'[BOT] {self.player.name} interveio: usou '
                            f'{c.name} como {nome_acao} para {card.name}'
                        )
                        return True

            # 4. Intervencao basica: declara block para a Presa
            if dfd not in g.combat.declarations:
                if declare_action(g, dfd, 'block'):
                    g.add_log(
                        f'[BOT] {self.player.name} interveio: '
                        f'{card.name} usa block'
                    )
                    return True

        return False

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
                # ── Plague Vermin: Ratkin pode recrutar como Ally (Pack Home) ──
                if card.card_id == 524:
                    # Verifica se tem Ratkin character para recrutar como Ally
                    tem_ratkin = any(
                        'ratkin' in (c.keywords or '').lower()
                        and 'Character' in (c.card_type or '')
                        and c.health_current > 0
                        for c in self.player.pack_home
                    )
                    if tem_ratkin:
                        card.zone = Zone.PACK_HOME
                        card.health_current = 1
                        card.card_type = 'Ally - Enemy'
                        self.player.pack_home.append(card)
                        self.game.add_log(
                            f'[BOT] {self.player.name} recrutou {card.name}'
                            f' como Ally (Ratkin)')
                        self.game.register_card_passives(card, self.player)
                        return
                card.zone = Zone.HUNTING_GROUNDS
                card.health_current = card.health if card.health > 0 else 1
                self.player.hunting_grounds.append(card)
                self.game.add_log(
                    f'[BOT] {self.player.name} jogou {card.name} '
                    f'no Hunting Grounds')
                self.game.register_card_passives(card, self.player)
            else:
                card.zone = Zone.PACK_HOME
                card.health_current = card.health
                self.player.pack_home.append(card)
                self.game.register_card_passives(card, self.player)
                # Gift: anexa a um personagem viavel no pack
                ct = (card.card_type or '').lower()
                if 'gift' in ct:
                    receptor = self._encontrar_receptor_gift(card)
                    if receptor:
                        receptor.attached_gifts.append(card)
                        self.game.add_log(
                            f'[BOT] {receptor.name} recebeu '
                            f'{card.name}')
                    else:
                        # Gift sem receptor viavel: log padrao
                        self.game.add_log(
                            f'[BOT] {self.player.name} jogou '
                            f'{card.name}')
                else:
                    self.game.add_log(
                        f'[BOT] {self.player.name} jogou {card.name}')
                # Equipment: tenta equipar a uma criatura do pack
                if 'equipment' in ct:
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

        # ── Strategy Engine: equipment_assignments tem prioridade ──
        if self._has_strategy:
            nome_alvo = self.strategy.equipment_assignment(
                card.name or '', self.game, self.player)
            if nome_alvo:
                for alvo in candidates:
                    if nome_alvo.lower() in (alvo.name or '').lower():
                        if resolvedor._validar_restricoes_equipamento(card, alvo):
                            if card in self.player.pack_home:
                                self.player.pack_home.remove(card)
                            card.zone = Zone.OUT_OF_PLAY
                            alvo.attached_equipment.append(card)
                            self.game.add_log(
                                f'[BOT] {self.player.name} equipou '
                                f'{card.name} em {alvo.name} '
                                f'(estratégia)')
                            return
                        break

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
        # Log ANTES do start_combat para que o intento apareca
        # antes de eventos como Frenar trocar de lugar
        atk_name = attacker_id
        dfd_name = defender_id
        g = self.game
        for p in g.players:
            for zone_list in (p.pack_home, p.hunting_grounds, p.umbra):
                for c in zone_list:
                    if str(c.card_id) == attacker_id:
                        atk_name = c.name
                    if str(c.card_id) == defender_id:
                        dfd_name = c.name
        self.game.add_log(
            f'[BOT] {self.player.name} atacou {dfd_name} com {atk_name}')
        start_combat(self.game, [attacker_id], [defender_id])
        self._ataques_feitos.add(attacker_id)

    def _encontrar_receptor_gift(self, gift: CardInstance) -> Optional[CardInstance]:
        """Encontra o melhor personagem no pack para receber um Gift.

        Regras (4.5.3):
        - O personagem deve ter Gnosis >= requisito do Gift
        - O personagem deve ter keywords que atendam 'requires' do Gift
        - Gift é anexado ao personagem via attached_gifts

        Args:
            gift: A carta Gift.

        Returns:
            CardInstance do personagem receptor, ou None.
        """
        from rage_web.game_engine.rules import parse_custo_rage

        req_gnosis = gift.gnosis or 0
        # 'requires' pode conter keywords separadas por espaco ou virgula
        req_keywords_raw = (gift.requires or '').strip()
        req_keywords = [k.strip().lower() for k in req_keywords_raw.replace(',', ' ').split() if k.strip()]

        candidates = []
        for c in self.player.pack_home:
            if c.card_id == gift.card_id:
                continue
            if c.health_current <= 0:
                continue
            if 'character' not in (c.card_type or '').lower():
                continue

            # Verifica Gnosis
            if c.gnosis < req_gnosis:
                continue

            # Verifica keywords requeridas
            if req_keywords:
                c_kw = (c.keywords or '').lower()
                if not all(kw in c_kw for kw in req_keywords):
                    continue

            candidates.append(c)

        if not candidates:
            return None

        # Escolhe o com maior Gnosis (mais apto a usar Gifts)
        candidates.sort(key=lambda x: x.gnosis, reverse=True)
        return candidates[0]

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
