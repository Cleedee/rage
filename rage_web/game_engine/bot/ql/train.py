"""CLI de treinamento Q-Learning para o Rage CCG.

Roda partidas bot-vs-bot (usando run_match) onde o jogador p1 é um
QLearningBot. Cada deck que o bot joga (o primeiro de cada par/episódio)
tem o SEU PRÓPRIO LinearQLearner persistido em um arquivo separado —
isso permite usar os modelos em partidas com mais de 2 decks, onde cada
jogador carrega o modelo do seu próprio deck. O adversário é um
PriorityBot com dificuldade configurável (--opponent).

Uso:
    rage-train --episodes 200 --opponent easy
    rage-train --sample --episodes 50 --eval-freq 10
    rage-train --pairs "7-90,1050-90" --episodes 100 --opponent hard
    rage-train --pairs "7,90,1050" --episodes 100   # partidas N-player
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from rage_web.game_engine.bot.ql.actions import N_ACTIONS
from rage_web.game_engine.bot.ql.agent import QLearningBot
from rage_web.game_engine.bot.ql.features import n_features
from rage_web.game_engine.bot.ql.qlearner import LinearQLearner
from rage_web.game_engine.match import run_match

logger = logging.getLogger('rage_train')

DEFAULT_PAIRS = [(7, 90), (1050, 90), (484, 7), (90, 465)]
DEFAULT_OUT = 'data/ql'
SAMPLE_KEY = 'sample'


def _parse_pairs(text: str | None) -> list[tuple[int, ...]]:
    """Converte a especificação de partidas em grupos de decks.

    Seções separadas por ';' são partidas independentes; dentro de uma
    seção, decks são separados por ','. Cada token 'a-b' (retrocompat)
    é uma partida de 2 decks. O primeiro deck de cada grupo é o que o
    QLearningBot treina.

    Exemplos:
        '7-90,1050-90'        → [(7,90), (1050,90)]
        '7,90,1050'           → [(7,90,1050)]
        '7,90,1050;4,5,6'     → [(7,90,1050), (4,5,6)]
        '7-90;1050-90'        → [(7,90), (1050,90)]
    """
    if not text:
        return DEFAULT_PAIRS
    pairs = []
    for section in text.split(';'):
        plain = []
        for tok in section.split(','):
            tok = tok.strip()
            if not tok:
                continue
            if '-' in tok:
                a, b = tok.split('-')
                pairs.append((int(a.strip()), int(b.strip())))
            else:
                plain.append(int(tok))
        if len(plain) >= 2:
            pairs.append(tuple(plain))
        elif len(plain) == 1:
            pairs.append((plain[0], plain[0]))
    return pairs or DEFAULT_PAIRS


def _learner_path(out_dir: str, key: int | str) -> str:
    return os.path.join(out_dir, f'deck{key}.npz')


def _save_learners(learners: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for key, learner in learners.items():
        learner.save(_learner_path(out_dir, key))


def _load_learners(learners: dict, load_dir: str) -> list[tuple]:
    """Carrega o npz de cada deck que existir em load_dir."""
    loaded = []
    for key, learner in learners.items():
        path = _learner_path(load_dir, key)
        if learner.load(path):
            loaded.append((key, path, learner))
    return loaded


def _play_episode(seed: int, pair: tuple[int, ...], learners: dict,
                  sample: bool, opponent: str, max_turns: int,
                  greedy: bool, agents: dict) -> str:
    """Roda uma partida. p1 (primeiro deck) é QLearningBot; os demais são
    PriorityBots com dificuldade `opponent`. Retorna o vencedor."""
    agents.clear()
    if sample:
        deck_key = SAMPLE_KEY
    else:
        deck_key = pair[0]
    learner = learners[deck_key]

    def factory(game, player_id, deck_id=None):
        if player_id == 'p1':
            ag = QLearningBot(game, player_id, learner=learner, greedy=greedy)
            agents[player_id] = ag
            return ag
        return None

    if sample:
        return run_match(
            seed=seed, max_turns=max_turns,
            difficulty_p1='hard', difficulty_p2=opponent,
            delay=0, verbose=-1, bot_factory=factory)
    if len(pair) == 2:
        return run_match(
            seed=seed, max_turns=max_turns,
            difficulty_p1='hard', difficulty_p2=opponent,
            deck1_id=pair[0], deck2_id=pair[1],
            delay=0, verbose=-1, bot_factory=factory)
    return run_match(
        seed=seed, max_turns=max_turns,
        deck_ids=list(pair),
        difficulties=['hard'] + [opponent] * (len(pair) - 1),
        delay=0, verbose=-1, bot_factory=factory)


def _run_eval(args, learners: dict, pairs: list, agents: dict,
              eval_eps: int = 10) -> float:
    wins = 0
    total = 0
    for i in range(eval_eps):
        pair = pairs[i % len(pairs)]
        result = _play_episode(args.seed + 10_000 + i, pair, learners,
                               args.sample, args.opponent, args.max_turns,
                               True, agents)
        agent = agents.get('p1')
        if agent is not None:
            agent.finish_episode(result)
        total += 1
        if result == 'p1':
            wins += 1
    return wins / total if total else 0.0


def _run_training(args, learners: dict, pairs: list) -> None:
    agents: dict = {}
    ep = 0
    wins = losses = draws = timeouts = 0
    per_deck: dict = {}
    t0 = time.time()

    while ep < args.episodes:
        pair = pairs[ep % len(pairs)]
        deck_key = SAMPLE_KEY if args.sample else pair[0]
        seed = args.seed + ep
        result = _play_episode(seed, pair, learners, args.sample,
                               args.opponent, args.max_turns, False, agents)
        agent = agents.get('p1')
        if agent is not None:
            agent.finish_episode(result)

        w, l, d, t = per_deck.setdefault(deck_key, [0, 0, 0, 0])
        if result == 'p1':
            wins += 1
            w += 1
        elif result == 'p2':
            losses += 1
            l += 1
        elif result == 'draw':
            draws += 1
            d += 1
        else:
            timeouts += 1
            t += 1
        per_deck[deck_key] = [w, l, d, t]

        ep += 1
        if args.verbose and (ep % args.log_every == 0 or ep == args.episodes):
            elapsed = time.time() - t0
            print(f'[ep {ep:4d}] ε={learners[deck_key].epsilon:.3f} '
                  f'deck={deck_key} W={wins} L={losses} D={draws} T={timeouts} '
                  f'({elapsed:.0f}s)')

        if args.eval_freq and ep % args.eval_freq == 0:
            winrate = _run_eval(args, learners, pairs, agents,
                                eval_eps=args.eval_episodes)
            print(f'    → eval winrate vs {args.opponent}: {winrate:.1%}')

        if args.out and ep % args.save_freq == 0:
            _save_learners(learners, args.out)

    if args.out:
        _save_learners(learners, args.out)
        print(f'Pesos salvos em {args.out}/')
        for key, (w, l, d, t) in sorted(per_deck.items()):
            print(f'  deck{key}: W={w} L={l} D={d} T={t}')


def make_deck_aware_factory(models_dir: str = DEFAULT_OUT,
                            greedy: bool = True, seed: int | None = None):
    """Factory que carrega/cacheia um modelo por deck (partidas N-player).

    Uso:
        from rage_web.game_engine.bot.ql.train import make_deck_aware_factory
        run_match(deck_ids=[7, 90, 1050], max_turns=30,
                  bot_factory=make_deck_aware_factory())
    """
    cache: dict = {}

    def factory(game, player_id, deck_id=None):
        key = deck_id or SAMPLE_KEY
        if key not in cache:
            learner = LinearQLearner(
                n_features=n_features(), n_actions=N_ACTIONS, seed=seed)
            learner.load(_learner_path(models_dir, key))
            cache[key] = learner
        return QLearningBot(game, player_id, learner=cache[key], greedy=greedy)

    return factory


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description='Treinamento Q-Learning do bot Rage CCG',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--episodes', type=int, default=200)
    parser.add_argument('--pairs', type=str, default=None,
                        help='Grupos de decks por partida "a-b,c-d" ou '
                             '"a,b,c" (default: rotacao conhecida)')
    parser.add_argument('--opponent', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--max-turns', type=int, default=30)
    parser.add_argument('--alpha', type=float, default=0.01)
    parser.add_argument('--gamma', type=float, default=0.95)
    parser.add_argument('--epsilon', type=float, default=0.3)
    parser.add_argument('--epsilon-decay', type=float, default=0.9995)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', default=DEFAULT_OUT,
                        help='Diretório com um modelo por deck '
                             '(deck{id}.npz)')
    parser.add_argument('--load', default=None,
                        help='Diretório de modelos para retomar treino')
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
        pairs = _parse_pairs(args.pairs)
        keys = [SAMPLE_KEY] if args.sample else sorted({p[0] for p in pairs})

        learners = {key: LinearQLearner(
            n_features=n_features(), n_actions=N_ACTIONS,
            alpha=args.alpha, gamma=args.gamma, epsilon=args.epsilon,
            epsilon_min=0.02, epsilon_decay=args.epsilon_decay,
            seed=args.seed) for key in keys}

        load_dir = args.load or args.out
        if load_dir:
            for key, path, learner in _load_learners(learners, load_dir):
                print(f'Pesos carregados de {path} '
                      f'(steps={learner.steps}, ε={learner.epsilon:.3f})')

        _run_training(args, learners, pairs)
    finally:
        if ctx is not None:
            ctx.pop()


if __name__ == '__main__':
    main()
