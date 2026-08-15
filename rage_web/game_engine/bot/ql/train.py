"""CLI de treinamento Q-Learning para o Rage CCG.

Roda partidas bot-vs-bot (usando run_match) onde o jogador p1 é um
QLearningBot compartilhando um LinearQLearner persistido entre
episódios. O adversário é um PriorityBot com dificuldade configurável.

Uso:
    rage-train --episodes 200 --opponent hard
    rage-train --sample --episodes 50 --eval-freq 10
    rage-train --eval --episodes 30 --greedy
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.bot.ql.actions import N_ACTIONS
from rage_web.game_engine.bot.ql.agent import QLearningBot
from rage_web.game_engine.bot.ql.features import n_features
from rage_web.game_engine.bot.ql.qlearner import LinearQLearner
from rage_web.game_engine.match import run_match

logger = logging.getLogger('rage_train')

DEFAULT_PAIRS = [(7, 90), (1050, 90), (484, 7), (90, 465)]
DEFAULT_OUT = 'data/ql/qlinear.npz'


def _parse_pairs(text: str | None) -> list[tuple[int, int]]:
    if not text:
        return DEFAULT_PAIRS
    pairs = []
    for chunk in text.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        if '-' in chunk:
            a, b = chunk.split('-')
            pairs.append((int(a), int(b)))
        else:
            pairs.append((int(chunk), int(chunk)))
    return pairs or DEFAULT_PAIRS


def _play_episode(seed: int, pair: tuple[int, int], learner: LinearQLearner,
                  sample: bool, opponent: str, max_turns: int,
                  greedy: bool, agents: dict) -> str:
    agents.clear()

    def factory(game, player_id):
        agent = QLearningBot(game, player_id, learner=learner, greedy=greedy)
        agents[player_id] = agent
        return agent

    deck1, deck2 = pair if not sample else (None, None)
    return run_match(
        seed=seed,
        max_turns=max_turns,
        difficulty_p1='hard',
        difficulty_p2=opponent,
        deck1_id=deck1,
        deck2_id=deck2,
        delay=0,
        verbose=-1,
        bot_factory=factory,
    )


def _run_training(args, learner: LinearQLearner) -> None:
    pairs = _parse_pairs(args.pairs)
    agents: dict = {}
    ep = 0
    wins = 0
    losses = 0
    draws = 0
    timeouts = 0
    t0 = time.time()

    while ep < args.episodes:
        pair = pairs[ep % len(pairs)]
        seed = args.seed + ep
        result = _play_episode(seed, pair, learner, args.sample,
                               args.opponent, args.max_turns, False, agents)
        agent = agents.get('p1')
        if agent is not None:
            agent.finish_episode(result)

        if result == 'p1':
            wins += 1
        elif result == 'p2':
            losses += 1
        elif result == 'draw':
            draws += 1
        else:
            timeouts += 1

        ep += 1
        if args.verbose and (ep % args.log_every == 0 or ep == args.episodes):
            elapsed = time.time() - t0
            print(f'[ep {ep:4d}] ε={learner.epsilon:.3f} '
                  f'W={wins} L={losses} D={draws} T={timeouts} '
                  f'({elapsed:.0f}s)')

        if args.eval_freq and ep % args.eval_freq == 0:
            winrate = _run_eval(args, learner, agents, eval_eps=args.eval_episodes)
            print(f'    → eval winrate vs {args.opponent}: {winrate:.1%}')

        if args.out and ep % args.save_freq == 0:
            learner.save(args.out)

    if args.out:
        learner.save(args.out)
        print(f'Pesos salvos em {args.out}')


def _run_eval(args, learner: LinearQLearner, agents: dict,
              eval_eps: int = 10) -> float:
    wins = 0
    total = 0
    for i in range(eval_eps):
        pair = DEFAULT_PAIRS[i % len(DEFAULT_PAIRS)]
        result = _play_episode(args.seed + 10_000 + i, pair, learner,
                               args.sample, args.opponent, args.max_turns,
                               True, agents)
        agent = agents.get('p1')
        if agent is not None:
            agent.finish_episode(result)
        total += 1
        if result == 'p1':
            wins += 1
    return wins / total if total else 0.0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description='Treinamento Q-Learning do bot Rage CCG',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--episodes', type=int, default=200)
    parser.add_argument('--pairs', type=str, default=None,
                        help='Pares de decks "a-b,c-d" (default: rotacao conhecida)')
    parser.add_argument('--opponent', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--max-turns', type=int, default=30)
    parser.add_argument('--alpha', type=float, default=0.01)
    parser.add_argument('--gamma', type=float, default=0.95)
    parser.add_argument('--epsilon', type=float, default=0.3)
    parser.add_argument('--epsilon-decay', type=float, default=0.9995)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', default=DEFAULT_OUT)
    parser.add_argument('--load', default=None,
                        help='Caminho dos pesos para retomar treino')
    parser.add_argument('--eval-freq', type=int, default=25,
                        help='Rodar avaliação (greedy) a cada N episódios')
    parser.add_argument('--eval-episodes', type=int, default=10)
    parser.add_argument('--save-freq', type=int, default=50)
    parser.add_argument('--log-every', type=int, default=10)
    parser.add_argument('--sample', action='store_true',
                        help='Usar sample game (sem banco de dados)')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format='%(message)s' if args.verbose else '')
    logging.getLogger('rage_web.game_engine.bot.priority_bot').setLevel(
        logging.WARNING)
    logging.getLogger('rage_web.game_engine.bot.ql').setLevel(
        logging.INFO if args.verbose else logging.WARNING)

    ctx = None
    if not args.sample:
        from rage_web import create_app
        app = create_app()
        ctx = app.app_context()
        ctx.push()

    try:
        learner = LinearQLearner(
            n_features=n_features(), n_actions=N_ACTIONS,
            alpha=args.alpha, gamma=args.gamma, epsilon=args.epsilon,
            epsilon_min=0.02, epsilon_decay=args.epsilon_decay,
            seed=args.seed)

        load_path = args.load or (args.out if os.path.exists(args.out) else None)
        if load_path and learner.load(load_path):
            print(f'Pesos carregados de {load_path} '
                  f'(steps={learner.steps}, ε={learner.epsilon:.3f})')

        _run_training(args, learner)
    finally:
        if ctx is not None:
            ctx.pop()


if __name__ == '__main__':
    main()
