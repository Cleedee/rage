"""Bot com arvore de decisao baseada em prioridades.

Arvore de decisao:
1. SOBREVIVER - Curar, bloquear, fugir
2. ELIMINAR AMEACA - Atacar maior threat
3. DESENVOLVER MESA - Jogar personagens, equipamentos
4. ATACAR - Buscar VP, atacar vulneravel
"""

from __future__ import annotations

import logging
import random
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
        """Age na fase de Resource."""
        me = self.player

        # Heuristica: max 3 cartas por turno (nao queimar mao)
        if self._cards_played_this_turn >= 3:
            self._pass_turn()
            return 'pass_resource_limit'

        TIPOS_NAO_RECURSO = {'Combat Action', 'Combat Event', 'Moot', 'Board Meeting'}
        TIPOS_STUB = {'quest_check', 'combar_acao'}
        # Cartas que vao para o Hunting Grounds (precisam ser jogadas cedo)
        TIPOS_HG_CARD = {'Victim', 'Enemy', 'Battlefield'}

        # 1. Prioridade maxima: jogar personagens
        for i, card in enumerate(me.hand):
            if card.card_type == 'Character':
                if self._pode_pagar_custos(card):
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_character_{card.card_id}'

        # 2. Jogar cartas de HG (Victim/Enemy/Battlefield) — essenciais
        #    para ter alvos no Hunting Grounds
        for i, card in enumerate(me.hand):
            if card.card_type in TIPOS_HG_CARD:
                if self._pode_pagar_custos(card):
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_{card.card_type.lower()}_{card.card_id}'

        # 3. Tenta jogar Ally, Equipment, Territory, Caern
        for i, card in enumerate(me.hand):
            if card.card_type in ('Ally', 'Equipment', 'Territory', 'Caern'):
                if self._pode_pagar_custos(card):
                    self._play_card(i)
                    self._cards_played_this_turn += 1
                    return f'play_{card.card_type.lower()}_{card.card_id}'

        # 4. Tenta jogar efeitos de Gifts/Events/Actions
        for i, card in enumerate(me.hand):
            if (card.modelo_id
                and card.card_type not in TIPOS_NAO_RECURSO
                and card.card_type not in TIPOS_HG_CARD):
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
        - O bot descarta cartas que nao sao da sua cor (tipo).
        """
        if self.game.turn_number == 1 and self.player.is_first_turn:
            # Primeiro turno: mao inicial ja foi dada
            self._pass_turn()
            return 'pass_redraw'

        me = self.player

        # Verifica se tem cartas de sept que podem ser descartadas
        # (sem modelo_id = sem efeito definido = carta inutil)
        sept_indices = []
        for i, c in enumerate(me.hand):
            eh_sept = c.card_type not in ('Combat Action', 'Combat Event', '')
            sem_efeito = not c.modelo_id
            if eh_sept and sem_efeito:
                sept_indices.append(i)

        # Se mao de sept esta cheia e tem cartas sem efeito, descarta
        sept_count = len(me._cartas_sept())
        if sept_indices and sept_count >= me.hand_size_sept:
            descartadas = me.descartar_da_mao(sept_indices)
            self.game.add_log(
                f'[BOT] {me.name} descartou {len(descartadas)} carta(s) de sept')
            # Depois do descarte, redraw completa
            drawn = me.redraw_sept(descartar_primeiro=False)
            if drawn:
                self.game.add_log(
                    f'[BOT] {me.name} comprou {len(drawn)} carta(s) de sept')
            return f'redraw_descarte_{len(descartadas)}'

        self._pass_turn()
        return 'pass_redraw'

    def _agir_umbra(self) -> str:
        """Age na fase de Umbra: stepping sideways.

        Regra (2.2.4):
        - So pode tomar UMA acao de stepping por Umbra phase.
        - Step para Umbra se tiver personagens com Gnosis alta.
        - Step de volta se tiver personagem na Umbra com Rage >= 3.
        """
        podem_ir, podem_voltar = self.player.personagens_que_podem_step()

        # So uma acao de Umbra por fase
        if getattr(self, '_umbra_agiu', False):
            self._pass_turn()
            return 'pass_umbra'
        self._umbra_agiu = True

        # Prioridade: voltar da Umbra se tiver guerreiro util
        if self.player.umbra:
            for c in self.player.umbra[:]:
                if c.rage >= 3:
                    self.player.step_back(c)
                    self.game.add_log(
                        f'[BOT] {self.player.name}: {c.name} '
                        f'voltou da Umbra')
                    return f'umbra_back_{c.card_id}'
            self._pass_turn()
            return 'pass_umbra'

        # Entrar na Umbra
        if podem_ir:
            personagem = max(podem_ir, key=lambda c: c.gnosis)
            self.player.step_sideways(personagem)
            self.game.add_log(
                f'[BOT] {self.player.name}: {personagem.name} '
                f'entrou na Umbra')
            return f'umbra_step_{personagem.card_id}'

        self._pass_turn()
        return 'pass_umbra'

    def _agir_moot(self) -> str:
        """Age na fase de Moot: votar em Juntas.

        Regra (2.2.5):
        - Personagens tem votos = Renome.
        - Votacao em ordem de Renome.
        - Se aprovado, resolve imediatamente.
        """
        g = self.game

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

        # Tenta chamar uma Junta (so se tiver carta de Moot na mao)
        for i, card in enumerate(self.player.hand):
            if card.card_type == 'Moot':
                modelo_id = card.modelo_id or ''
                g.chamar_moot(self.player_id, nome=card.name,
                              modelo_id=modelo_id, card_uid=id(card))
                card.zone = Zone.DISCARD_SEPT
                self.player.discard_sept.append(
                    self.player.hand.pop(i))
                return f'moot_chamar_{card.name}'

        self._pass_turn()
        return 'pass_moot'

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

        # ── RESTO DO COMBATE (cartas, eliminar, atacar) ──
        # Heuristica: max 3 cartas por turno
        if self._cards_played_this_turn >= 3:
            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action
            self._pass_turn()
            return 'pass_combat_limit'

        # Se deck lento, inverte prioridades: atacar > sobreviver
        # (nao adianta proteger criaturas se nunca ganha VP)
        if lento:
            # Lento: eliminar > atacar > sobreviver
            # Tenta usar cartas de combate primeiro
            for i, card in enumerate(me.hand):
                if card.modelo_id and card.card_type in (
                        'Combat Action', 'Combat Event', 'Action'):
                    modo_idx = self._escolher_melhor_modo(card.modelo_id)
                    if self._pode_pagar_custos(card):
                        self._cards_played_this_turn += 1
                        return self._usar_carta_efeito(i, modo_idx, card)

            action = self._try_eliminate_threat()
            if action:
                return action
            action = self._try_attack()
            if action:
                return action
            # Pula sobreviver em deck lento — agressivo
            action = self._try_survive()
            if action:
                return action
            self._pass_turn()
            return 'pass_combat'

        # ── NORMAL (hard) ──
        # 1. SOBREVIVER
        action = self._try_survive()
        if action:
            return action

        # 2. Usar cartas de efeito de COMBATE
        for i, card in enumerate(me.hand):
            if card.modelo_id and card.card_type in (
                    'Combat Action', 'Combat Event', 'Action'):
                modo_idx = self._escolher_melhor_modo(card.modelo_id)
                if self._pode_pagar_custos(card):
                    self._cards_played_this_turn += 1
                    return self._usar_carta_efeito(i, modo_idx, card)

        # 3. Outros efeitos
        action = self._try_develop_board()
        if action:
            self._cards_played_this_turn += 1
            return action

        # 4. ELIMINAR AMEACA
        action = self._try_eliminate_threat()
        if action:
            return action

        # 5. ATACAR
        action = self._try_attack()
        if action:
            return action

        # 6. Passa
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

        if not alpha_card or alpha_card.is_tapped:
            return None
        if not self._pode_atacar(alpha_card):
            return None

        from rage_web.game_engine.combat_queue import start_combat

        # 1. Tenta atacar alpha inimigo (prioriza lider em VP)
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
                alpha_card.is_tapped = True
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
                    alpha_card.is_tapped = True
                    self.game.add_log(
                        f'[BOT] Alpha {alpha_card.name} atacou '
                        f'{alvo.name}')
                    return f'alpha_attack_{meu_alpha_id}_vs_{alvo.card_id}'

        # 3. Ataca uma presa especifica no Hunting Grounds
        alvo_hg = self._melhor_alvo_hg()
        if alvo_hg:
            start_combat(self.game, [meu_alpha_id], [str(alvo_hg.card_id)])
            alpha_card.is_tapped = True
            self.game.add_log(
                f'[BOT] Alpha {alpha_card.name} atacou '
                f'{alvo_hg.name} no Hunting Grounds')
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

        choice = random.choice(actions)
        if choice == 'play':
            idx = random.randrange(len(self.player.hand))
            self._play_card(idx)
            return f'play_{idx}'
        elif choice == 'attack':
            # Modo facil: alpha ataca um alvo no HG se houver
            meu_alpha_id = self.game.combat.alphas.get(self.player_id)
            alvo_hg = self._melhor_alvo_hg()
            if meu_alpha_id and alvo_hg:
                start_combat(self.game, [meu_alpha_id],
                             [str(alvo_hg.card_id)])
                for c in self.player.pack_home:
                    if str(c.card_id) == meu_alpha_id:
                        c.is_tapped = True
                        break
                return f'attack_{meu_alpha_id}'
        elif choice == 'draw':
            self._draw()
            return 'draw'

        self._pass_turn()
        return 'pass'

    def _decide_combat(self) -> str:
        """Age durante o combate.

        Declara acoes para TODOS os combatentes (incluindo oponentes)
        para simplificar o ciclo sem necessidade de alternancia.
        """
        g = self.game

        if g.combat.step == 'declare':
            self._feinted_ids.clear()  # Novo round de combate
            all_cids = get_combatants(g)
            for cid in all_cids:
                if cid in g.combat.declarations:
                    continue
                # Encontra a criatura em qualquer jogador
                for p in g.players:
                    for c in p.pack_home:
                        if str(c.card_id) == cid:
                            action = self._choose_combat_action(c, c.owner_id)
                            declare_action(g, cid, action)
                            return f'declare_{cid}_{action}'
            # Todos ja declararam
            if g.combat.all_declared(get_combatants(g)):
                reveal_all(g)
                return 'reveal'
            return 'combat_wait'

        elif g.combat.step == 'reveal':
            return self._handle_reveal_step()

        elif g.combat.step in ('resolve', 'end'):
            resolve_combat(g)
            end_combat(g)
            return 'end_combat'

        return 'combat_unknown'

    def _handle_reveal_step(self) -> str:
        """Lida com o Reveal Step: Feint unico por criatura, depois resolve.

        Cada criatura pode usar Feint no maximo uma vez por round de
        combate (controlado por _feinted_ids).
        """
        g = self.game
        opp = self._get_opponent()
        combatants = get_combatants(g)

        OFENSIVAS = {'strike', 'claw', 'bite', 'weapon_strike',
                     'ranged_strike'}
        DEFENSIVAS = {'block', 'dodge', 'flee'}

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

        resolve_combat(g)
        end_combat(g)
        self._feinted_ids.clear()
        return 'end_combat'

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
        g = self.game
        combatants = get_combatants(g)

        if g.combat.step == 'declare':
            for cid in combatants:
                if cid not in g.combat.declarations:
                    action = random.choice(list(COMBAT_ACTIONS))
                    declare_action(g, cid, action)
                    return f'declare_{cid}_{action}'
            if g.combat.all_declared(combatants):
                reveal_all(g)

        resolve_combat(g)
        end_combat(g)
        return 'combat_end'

    # ------------------------------------------------------------------
    # Sub-arvores de decisao
    # ------------------------------------------------------------------

    def _pode_pagar_custos(self, card: CardInstance) -> bool:
        """Verifica se o bot pode pagar os custos de Rage e Gnosis.

        Regras (2.2.4/2.2.5):
        - Rage: personagem destapped com Rage >= custo.
        - Gnosis: personagem destapped com Gnosis >= custo.
        """
        from rage_web.game_engine.rules import parse_custo_rage
        # Rage
        custo_rage = parse_custo_rage(card.damage)
        if custo_rage is not None and custo_rage > 0:
            tem_rage = any(not c.is_tapped and c.rage >= custo_rage
                          for c in self.player.pack_home)
            if not tem_rage:
                return False
        # Gnosis
        if card.gnosis and card.gnosis > 0:
            tem_gnosis = any(not c.is_tapped and c.gnosis >= card.gnosis
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

    def _pode_atacar(self, card: CardInstance) -> bool:
        """Verifica se uma carta pode atacar/combater.

        Regra: apenas Characters e Allies podem entrar em combate.
        Equipment, Gift, Event, Action, Territory, Caern, etc. nao.
        """
        ct = (card.card_type or '').lower()
        return 'character' in ct or 'ally' in ct

    def _melhor_alvo_hg(self) -> Optional[CardInstance]:
        """Encontra o melhor alvo no Hunting Grounds.

        Retorna a carta Victim/Enemy/Battlefield com maior
        relacao renown/health (facil de matar, muito VP).
        Apenas o Alpha pode atacar Prey no HG (regra 6.5.1).
        """
        TIPOS_HG = {'victim', 'enemy', 'battlefield'}
        candidatos = []
        # HG global
        for c in self.game.hunting_grounds_cards:
            ct = (c.card_type or '').lower()
            if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                candidatos.append(c)
        # HG de cada jogador
        for p in self.game.players:
            for c in p.hunting_grounds:
                ct = (c.card_type or '').lower()
                if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                    candidatos.append(c)
        if not candidatos:
            return None
        # Melhor relacao renown/health (VP rapido)
        candidatos.sort(key=lambda c: (c.renown or 1) / max(c.health_current, 1),
                        reverse=True)
        return candidatos[0]

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

        available = [c for c in me.pack_home if not c.is_tapped
                     and self._pode_atacar(c)]
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
                pode = self.prioritizer.pode_eliminar(atacante, alvo)
                # Deck lento: ataca mesmo sem garantia de eliminar
                if pode or (lento and atacante.rage >= alvo.rage * 0.5):
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

        # 2. Joga Ally, Equipment, Territory, Caern
        for i, card in enumerate(me.hand):
            if card.card_type in ('Ally', 'Equipment', 'Territory', 'Caern'):
                self._play_card(i)
                return f'play_{card.card_type.lower()}_{card.card_id}'

        # 3. Efeitos nao-stub
        TIPOS_STUB = {'quest_check', 'combar_acao'}
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

    def _try_attack(self) -> Optional[str]:
        """Prioridade 4: Atacar.

        Com N jogadores, ataca criaturas do lider em VP primeiro.
        Regra 6.5.1: apenas o Alpha pode iniciar ataque; ataque
        de nao-Alpha requer card ability.
        """
        me = self.player
        opponents = self._get_opponents()
        lento = self._is_slow_deck()

        available = [c for c in me.pack_home if not c.is_tapped
                     and self._pode_atacar(c)]
        if not available:
            return None

        # Agrega alvos de todos os oponentes
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
                atacante = self.prioritizer.best_attacker_for(alvo, available)
                if atacante:
                    if self.prioritizer.pode_eliminar(atacante, alvo) or (
                            lento and atacante.rage >= alvo.rage * 0.5):
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

    def _choose_combat_action(self, card: CardInstance,
                                owner_id: str) -> str:
        """Escolhe a melhor acao de combate para uma criatura.

        Se for criatura do oponente, escolhe acao defensiva ou
        previsivel (block/dodge/strike). Se for do proprio bot,
        escolhe acao ofensiva (strike/claw/bite).
        """
        if owner_id != self.player_id:
            # Criatura do oponente: reage de forma defensiva
            if card.health_current < card.health * 0.4:
                return 'dodge'
            if card.rage >= 3:
                return 'strike'
            return 'block'

        # Criatura propria: age de forma ofensiva
        opp = self._get_opponent()
        if opp.pack_home:
            max_opp_rage = max(c.rage for c in opp.pack_home)
            if max_opp_rage > card.rage * 1.5:
                return 'dodge'

        if card.rage >= 3:
            return 'strike'
        if card.health_current < card.health * 0.3:
            return 'dodge'
        return random.choice(['strike', 'claw', 'bite', 'strike'])

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

    def _attack(self, attacker_id: str, defender_id: str):
        """Inicia combate e tapa a criatura atacante."""
        start_combat(self.game, [attacker_id], [defender_id])
        # Tapa a criatura (nao pode atacar de novo neste turno)
        for c in self.player.pack_home:
            if str(c.card_id) == attacker_id:
                c.is_tapped = True
                break
        self.game.add_log(
            f'[BOT] {self.player.name} atacou {defender_id} com {attacker_id}')

    def _pass_turn(self):
        """Passa a vez."""
        me = self.player
        me.pass_turn()
        all_passed = all(p.has_passed for p in self.game.players)
        if all_passed:
            self.game.next_phase()
            for p in self.game.players:
                p.reset_pass()
            self.game.add_log(f'Todos passaram. Fase: {self.game.phase}')
        else:
            self.game.next_player()
            self.game.add_log(
                f'[BOT] {me.name} passou. Vez de {self.game.current_player.name}')
