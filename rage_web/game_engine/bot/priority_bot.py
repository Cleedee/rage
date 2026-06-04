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
    COMBAT_ACTIONS, declare_action, get_combatants, reveal_all,
    start_combat,
)
from rage_web.game_engine.state import GameState, PlayerState, CardInstance

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

        # Se esta em combate, age no combate
        if g.combat.is_active:
            return self._decide_combat()

        # Se nao e a vez do bot, passa
        if g.current_player.id != self.player_id:
            return 'wait'

        # 1. SOBREVIVER
        action = self._try_survive()
        if action:
            return action

        # 2. ELIMINAR AMEACA
        action = self._try_eliminate_threat()
        if action:
            return action

        # 3. DESENVOLVER MESA
        action = self._try_develop_board()
        if action:
            return action

        # 4. ATACAR
        action = self._try_attack()
        if action:
            return action

        # 5. Fallback: passa
        self._pass_turn()
        return 'pass'

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
            if self.player.pack_home:
                atk = random.choice(self.player.pack_home)
                self._attack(str(atk.card_id), 'hg')
                return f'attack_{atk.card_id}'
        elif choice == 'draw':
            self._draw()
            return 'draw'

        self._pass_turn()
        return 'pass'

    def _decide_combat(self) -> str:
        """Age durante o combate."""
        g = self.game
        my_combatants = []
        for cid in get_combatants(g):
            for p in g.players:
                for c in p.pack_home:
                    if str(c.card_id) == cid:
                        my_combatants.append(c)

        if g.combat.step == 'declare':
            # Declara acao para cada combatente
            for c in my_combatants:
                cid = str(c.card_id)
                if cid not in g.combat.declarations:
                    action = self._choose_combat_action(c)
                    declare_action(g, cid, action)
                    return f'declare_{cid}_{action}'

        elif g.combat.step == 'reveal':
            # Se for o ultimo a declarar, pode Feint
            for c in my_combatants:
                cid = str(c.card_id)
                if cid == g.combat.last_to_declare:
                    # Verifica se deve trocar
                    current = g.combat.declarations.get(cid)
                    if current and current != 'strike':
                        from rage_web.game_engine.combat_queue import feint_action
                        feint_action(g, cid, 'strike')
                        return f'feint_{cid}_strike'
            # Revela se todos declararam
            reveal_all(g)
            return 'reveal'

        elif g.combat.step == 'declare' or g.combat.step == 'resolve':
            from rage_web.game_engine.combat_queue import resolve_combat
            resolve_combat(g)
            from rage_web.game_engine.combat_queue import end_combat
            end_combat(g)
            return 'end_combat'

        return 'combat_unknown'

    def _decide_combat_random(self) -> str:
        """Acoes aleatorias em combate (modo facil)."""
        g = self.game
        my_combatants = []
        for cid in get_combatants(g):
            for p in g.players:
                for c in p.pack_home:
                    if str(c.card_id) == cid:
                        my_combatants.append(c)

        if g.combat.step == 'declare':
            for c in my_combatants:
                cid = str(c.card_id)
                if cid not in g.combat.declarations:
                    action = random.choice(list(COMBAT_ACTIONS))
                    declare_action(g, cid, action)
                    return f'declare_{cid}_{action}'

        reveal_all(g)
        from rage_web.game_engine.combat_queue import resolve_combat, end_combat
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
        """
        me = self.player
        opp = self._get_opponent()

        if not me.pack_home or not opp.pack_home:
            return None

        # Encontra a criatura mais ameacadora do oponente
        top_threat = max(opp.pack_home, key=lambda c: c.rage)

        # Encontra minha criatura mais forte
        my_best = max(me.pack_home, key=lambda c: c.rage)

        if my_best.rage >= top_threat.rage * 0.7:
            self._attack(str(my_best.card_id), str(top_threat.card_id))
            return f'eliminate_{my_best.card_id}_vs_{top_threat.card_id}'

        return None

    def _try_develop_board(self) -> Optional[str]:
        """Prioridade 3: Desenvolver mesa.

        Joga personagens da mao no Pack Home.
        Prefere cartas do tipo Character.
        """
        me = self.player

        if not me.hand:
            return None

        # Procura por personagens na mao
        for i, card in enumerate(me.hand):
            if card.card_type == 'Character':
                self._play_card(i)
                return f'play_character_{card.card_id}'

        # Joga a primeira carta da mao
        self._play_card(0)
        return f'play_{me.hand[0].card_id}'

    def _try_attack(self) -> Optional[str]:
        """Prioridade 4: Atacar.

        Ataca o Hunting Grounds com a criatura mais forte.
        """
        me = self.player

        if not me.pack_home:
            return None

        # Escolhe a criatura com mais Rage
        best = max(me.pack_home, key=lambda c: c.rage)

        if not best.is_tapped:
            self._attack(str(best.card_id), 'hg')
            return f'attack_hg_{best.card_id}'

        return None

    # ------------------------------------------------------------------
    # Utilitarios
    # ------------------------------------------------------------------

    def _get_opponent(self) -> PlayerState:
        for p in self.game.players:
            if p.id != self.player_id:
                return p
        raise ValueError('Nenhum oponente')

    def _choose_combat_action(self, card: CardInstance) -> str:
        """Escolhe a melhor acao de combate para uma criatura."""
        opp = self._get_opponent()

        # Se oponente tem criaturas com rage alto, usa block
        if opp.pack_home:
            max_opp_rage = max(c.rage for c in opp.pack_home)
            if max_opp_rage > card.rage:
                return 'block'

        # Se tem saude baixa, usa dodge
        if card.health_current < card.health * 0.4:
            return 'dodge'

        # Se tem rage alto, ataca
        if card.rage >= 3:
            return 'strike'

        return random.choice(['strike', 'block', 'dodge'])

    def _draw(self):
        """Compra carta do deck de combate."""
        self.player.draw_combat(1)
        self.game.add_log(f'[BOT] {self.player.name} comprou uma carta')

    def _play_card(self, hand_index: int):
        """Joga carta da mao."""
        if 0 <= hand_index < len(self.player.hand):
            card = self.player.hand.pop(hand_index)
            card.zone = 'pack_home'
            card.health_current = card.health
            self.player.pack_home.append(card)
            self.game.add_log(
                f'[BOT] {self.player.name} jogou {card.name}')

    def _attack(self, attacker_id: str, defender_id: str):
        """Inicia combate."""
        start_combat(self.game, [attacker_id], [defender_id])
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
