"""Agente Q-Learning para o Rage CCG.

Pacote com aprendizado por reforço (Q-Learning linear com numpy)
usando macro-ações: o agente escolhe entre categorias de ações
(jogar personagem, atacar, declarar strike, passar...) e os
detalhes concretos (qual carta, qual alvo) são resolvidos por
heurísticas herdadas do PriorityBot.
"""

from rage_web.game_engine.bot.ql.agent import QLearningBot
from rage_web.game_engine.bot.ql.qlearner import LinearQLearner

__all__ = ['QLearningBot', 'LinearQLearner']
