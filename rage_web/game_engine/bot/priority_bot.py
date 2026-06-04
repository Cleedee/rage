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

from rage_web.game_engine.bot.evaluator import BoardEvaluator
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
        self._actions_this_turn = 0
        self._last_turn = 0
        # Maximo de acoes por turno antes de passar forcadamente
        # (evita loop infinito ate que o motor de regras lide com
        #  recursos como acoes por turno)
        self.max_actions_per_turn = 6

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

        Returns:
            Descricao da acao escolhida.
        """
        if self.difficulty == 'easy':
            return self._decide_easy()

        g = self.game

        # Reseta contagem de acoes a cada novo turno
        if g.turn_number > self._last_turn:
            self._actions_this_turn = 0
            self._last_turn = g.turn_number

        # Se esta em combate, age no combate (nao conta como acao)
        if g.combat.is_active:
            return self._decide_combat()

        # Se nao e a vez do bot, passa
        if g.current_player.id != self.player_id:
            return 'wait'

        # Limite de acoes por turno
        if self._actions_this_turn >= self.max_actions_per_turn:
            self._pass_turn()
            return 'pass_max_actions'

        # 1. SOBREVIVER
        action = self._try_survive()
        if action:
            self._actions_this_turn += 1
            return action

        # 2. ELIMINAR AMEACA
        action = self._try_eliminate_threat()
        if action:
            self._actions_this_turn += 1
            return action

        # 3. DESENVOLVER MESA
        action = self._try_develop_board()
        if action:
            self._actions_this_turn += 1
            return action

        # 4. ATACAR
        action = self._try_attack()
        if action:
            self._actions_this_turn += 1
            return action

        # 5. Fallback: passa
        self._pass_turn()
        self._actions_this_turn += 1
        return 'pass'

    def _decide_easy(self) -> str:
        """Modo facil: acoes aleatorias."""
        g = self.game
        if g.combat.is_active:
            return self._decide_combat_random()

        if g.current_player.id != self.player_id:
            return 'wait'

        # Reseta contagem
        if g.turn_number > self._last_turn:
            self._actions_this_turn = 0
            self._last_turn = g.turn_number

        if self._actions_this_turn >= self.max_actions_per_turn:
            self._pass_turn()
            return 'pass_max_actions'

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
            self._actions_this_turn += 1
            return f'play_{idx}'
        elif choice == 'attack':
            if self.player.pack_home:
                atk = random.choice(self.player.pack_home)
                self._attack(str(atk.card_id), 'hg')
                self._actions_this_turn += 1
                return f'attack_{atk.card_id}'
        elif choice == 'draw':
            self._draw()
            self._actions_this_turn += 1
            return 'draw'

        self._pass_turn()
        self._actions_this_turn += 1
        return 'pass'

    def _decide_combat(self) -> str:
        """Age durante o combate.

        Declara acoes para TODOS os combatentes (incluindo oponentes)
        para simplificar o ciclo sem necessidade de alternancia.
        """
        g = self.game

        if g.combat.step == 'declare':
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
        """Lida com o Reveal Step: usa Feint se vantajoso e resolve."""
        g = self.game
        if g.combat.last_to_declare:
            cid = g.combat.last_to_declare
            # So usa Feint se for criatura propria
            for p in g.players:
                for c in p.pack_home:
                    if str(c.card_id) == cid and c.owner_id == self.player_id:
                        current = g.combat.declarations.get(cid)
                        if current and current != 'strike':
                            if feint_action(g, cid, 'strike'):
                                return f'feint_{cid}_strike'

        resolve_combat(g)
        end_combat(g)
        return 'end_combat'

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

    def _try_eliminate_threat(self) -> Optional[str]:
        """Prioridade 2: Eliminar ameaca.

        Ataca a criatura do oponente com maior Rage.
        So ataca se a criatura nao estiver tapada.
        """
        me = self.player
        opp = self._get_opponent()

        if not me.pack_home or not opp.pack_home:
            return None

        # Criaturas proprias que ainda podem atacar
        available = [c for c in me.pack_home if not c.is_tapped]
        if not available:
            return None

        # Encontra a criatura mais ameacadora do oponente
        top_threat = max(opp.pack_home, key=lambda c: c.rage)

        # Encontra minha criatura mais forte ainda livre
        my_best = max(available, key=lambda c: c.rage)

        if my_best.rage >= top_threat.rage * 0.7:
            self._attack(str(my_best.card_id), str(top_threat.card_id))
            return f'eliminate_{my_best.card_id}_vs_{top_threat.card_id}'

        return None

    def _try_develop_board(self) -> Optional[str]:
        """Prioridade 3: Desenvolver mesa.

        Usa cartas de efeito, depois joga personagens.
        """
        me = self.player

        if not me.hand:
            return None

        # 1. Usa cartas com efeitos (modelo_id) prioritariamente
        for i, card in enumerate(me.hand):
            if card.modelo_id:
                modo_idx = self._escolher_melhor_modo(card.modelo_id)
                return self._usar_carta_efeito(i, modo_idx, card)

        # 2. Procura por personagens na mao
        for i, card in enumerate(me.hand):
            if card.card_type == 'Character':
                self._play_card(i)
                return f'play_character_{card.card_id}'

        # 3. Joga a primeira carta da mao
        if me.hand:
            card = me.hand[0]
            self._play_card(0)
            return f'play_{card.card_id}'
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
        """Usa uma carta de efeito da mao."""
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        modelo = CARTAS_EXEMPLO.get(card.modelo_id)
        if not modelo:
            self._play_card(hand_index)
            return f'play_{card.card_id}'

        # Remove da mao e aplica
        self.player.hand.pop(hand_index)
        logs = aplicar_carta(self.game, modelo, self.player_id,
                              modo_idx=modo_idx)

        modo = modelo.modos[modo_idx]
        desc = f'use_{card.modelo_id}_modo{modo_idx}'
        self.game.add_log(
            f'[BOT] {self.player.name} usou {card.name} ({modo.descricao})')
        return desc

    def _try_attack(self) -> Optional[str]:
        """Prioridade 4: Atacar.

        Ataca o Hunting Grounds com a criatura mais forte ainda livre.
        """
        me = self.player

        available = [c for c in me.pack_home if not c.is_tapped]
        if not available:
            return None

        # Escolhe a criatura com mais Rage ainda nao tapada
        best = max(available, key=lambda c: c.rage)
        self._attack(str(best.card_id), 'hg')
        return f'attack_hg_{best.card_id}'

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
        """Joga carta da mao."""
        if 0 <= hand_index < len(self.player.hand):
            card = self.player.hand.pop(hand_index)
            card.zone = Zone.PACK_HOME
            card.health_current = card.health
            self.player.pack_home.append(card)
            self.game.add_log(
                f'[BOT] {self.player.name} jogou {card.name}')

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
