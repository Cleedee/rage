"""Agente Q-Learning que decide macro-ações.

Herda o PriorityBot (reutiliza todas as heurísticas de execução)
e substitui `decide()` pela escolha ε-greedy de uma macro-ação.
Aprendizado: Q-Learning linear com memoria de uma transição
pendente, flusheada no próximo `decide()` (bootstrap) ou no fim
da partida (terminal).
"""

from __future__ import annotations

import logging

from rage_web.game_engine.bot.evaluator import BoardEvaluator
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.bot.ql.actions import (ALL_MACROS,
                                                 execute_macro, legal_mask)
from rage_web.game_engine.bot.ql.features import encode_state
from rage_web.game_engine.bot.ql.qlearner import LinearQLearner
from rage_web.game_engine.state import GameState

logger = logging.getLogger(__name__)

STEP_PENALTY = 0.01
SHAPING_WEIGHT = 0.5


def _opponent_id(game: GameState, player_id: str) -> str:
    for p in game.players:
        if p.id != player_id:
            return p.id
    return player_id


def shaping_reward(game: GameState, player_id: str) -> float:
    """Avalia a posição do jogador (usada como reward shaping)."""
    me = None
    opp = None
    for p in game.players:
        if p.id == player_id:
            me = p
        else:
            opp = p
    if me is None:
        return 0.0
    if opp is None:
        return 0.0
    vp_adv = (me.victory_points - opp.victory_points) / max(me.renown_level, 1)
    try:
        ev = BoardEvaluator(game, player_id)
        board = ev.composite_score() / 10.0
    except Exception:
        board = 0.0
    return vp_adv * 1.5 + board


class QLearningBot(PriorityBot):
    """Bot com aprendizado Q-Learning linear sobre macro-ações."""

    def __init__(self, game: GameState, player_id: str,
                 learner: LinearQLearner | None = None,
                 greedy: bool = False,
                 seed: int | None = None):
        super().__init__(game, player_id, difficulty='hard')
        from rage_web.game_engine.bot.ql.actions import N_ACTIONS
        from rage_web.game_engine.bot.ql.features import n_features

        nf = learner.n_features if learner else n_features()
        self.learner = learner or LinearQLearner(
            n_features=nf, n_actions=N_ACTIONS, seed=seed)
        self.greedy = greedy
        self._pending: list[tuple] = []
        self._last_turn_ql = game.turn_number
        self._decisions = 0

    # ── API do bot ──

    def decide(self) -> str:
        g = self.game

        # Reseta heurísticas herdadas por turno
        if g.turn_number > self._last_turn_ql:
            self._cards_played_this_turn = 0
            self._last_turn_ql = g.turn_number
            self._umbra_agiu = False
            self._ataques_feitos.clear()

        if getattr(self.player, 'eliminado', False):
            self._flush_pending(terminal=False)
            self._pass_turn()
            return 'pass_eliminated'

        if g.current_player.id != self.player_id:
            return 'wait'

        # 1) Bootstrap da transição pendente (estado atual = s')
        self._flush_pending(terminal=False)

        # 2) Codifica estado e escolhe macro-ação
        s = encode_state(g, self.player_id)
        mask = legal_mask(self)
        if not mask.any():
            return self._fallback_decision()

        a = int(self.learner.choose_action(s, mask=mask, greedy=self.greedy))
        macro = ALL_MACROS[a]

        shape_before = shaping_reward(g, self.player_id)
        result = execute_macro(self, macro)
        if not result:
            result = self._fallback_decision()
        shape_after = shaping_reward(g, self.player_id)

        r = SHAPING_WEIGHT * (shape_after - shape_before) - STEP_PENALTY
        self._pending.append((s, a, r))
        self._decisions += 1
        if self._decisions % 4 == 0:
            self.learner.decay_epsilon()

        return result

    def finish_episode(self, result: str | None) -> None:
        """Fim de partida: atualiza transição pendente com recompensa final.

        Args:
            result: 'p1'/'p2' (vencedor), ou 'draw'/'stuck'/'timeout'/'error'.
        """
        if result == self.player_id:
            r_terminal = 1.0
        elif result in (None, 'draw', 'stuck', 'timeout', 'error'):
            r_terminal = 0.0
        else:
            r_terminal = -1.0

        if not self._pending:
            return
        s_now = encode_state(self.game, self.player_id)
        mask_now = legal_mask(self)
        last_s, last_a, last_r = self._pending[-1]
        # A última transição recebe a recompensa terminal
        self.learner.terminal_update(last_s, last_a, last_r + r_terminal)
        # Transições anteriores (se houver): terminal sem recompensa extra
        for s, a, r in self._pending[:-1]:
            self.learner.terminal_update(s, a, r)
        self._pending.clear()

    # ── Internos ──

    def _flush_pending(self, terminal: bool = False) -> None:
        if not self._pending:
            return
        s_now = encode_state(self.game, self.player_id)
        mask_now = legal_mask(self)
        if not mask_now.any():
            mask_now = None
        for s, a, r in self._pending:
            if terminal:
                self.learner.terminal_update(s, a, r)
            else:
                self.learner.update(s, a, r, s_now, mask_next=mask_now)
        self._pending.clear()

    def _fallback_decision(self) -> str:
        """Ação segura quando nenhuma macro é viável/legal."""
        self._pass_turn()
        return 'pass'
