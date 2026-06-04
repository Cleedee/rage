#!/usr/bin/env python3
"""Simulador de partida entre dois bots Rage CCG.

Uso:
    python3 match.py                # hard vs hard
    python3 match.py --p1 easy --p2 easy
    python3 match.py --seed 123 --max-turns 10
"""

import argparse
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.combat_queue import get_declaration_summary, get_combatants
from rage_web.game_engine.state import GameState


def print_separator(char='━', width=60):
    print(char * width)


def print_board(game: GameState):
    """Exibe o estado de forma compacta."""
    for p in game.players:
        pack = ', '.join(f'{c.name}({c.health_current}/{c.health})'
                        for c in p.pack_home) or '—'
        hand = len(p.hand)
        hg = ', '.join(c.name for c in p.hunting_grounds) or '—'
        vp = f'VP {p.victory_points}/{p.renown_level}'
        print(f'  {p.name:16s} │ Mao:{hand:2d} │ Pack: {pack}')
        print(f'  {" " * 16} │ VP:{p.victory_points:2d} │ HG:  {hg}')
    if game.combat.is_active:
        atk = ', '.join(game.combat.attackers)
        dfd = ', '.join(game.combat.defenders)
        print(f'  ⚔️  COMBATE [{game.combat.step}] {atk} vs {dfd}')
        summary = get_declaration_summary(game)
        if 'declarations' in summary:
            for cid, action in summary['declarations'].items():
                print(f'     {cid}: {action}')
    print(f'  Fase: {game.phase.upper()} | Turno {game.turn_number}')


def run_match(seed: int = 42, max_turns: int = 30,
              difficulty_p1: str = 'hard',
              difficulty_p2: str = 'hard',
              delay: float = 0.3) -> str:
    """Roda uma partida entre dois bots.

    Returns:
        'p1' | 'p2' | 'draw' | 'timeout'
    """
    game = create_sample_game(seed=seed)
    bots = {
        'p1': PriorityBot(game, 'p1', difficulty=difficulty_p1),
        'p2': PriorityBot(game, 'p2', difficulty=difficulty_p2),
    }
    col1 = '\033[1;36m'  # Cyan
    col2 = '\033[1;33m'  # Yellow
    reset = '\033[0m'

    print_separator()
    print(f'  RAGE CCG — PARTIDA ENTRE BOTS')
    print(f'  P1: {difficulty_p1.upper()} | P2: {difficulty_p2.upper()} | Max: {max_turns}t')
    print_separator()
    print_board(game)

    step = 0
    action_count = 0
    stale_steps = 0
    last_turn = game.turn_number
    last_phase = game.phase
    max_steps = max_turns * 50  # limite de seguranca

    while step < max_steps:
        cp = game.current_player
        bot = bots[cp.id]
        color = col1 if cp.id == 'p1' else col2

        action = bot.decide()
        action_count += 1

        # Detecta progresso: turno ou fase mudou
        if game.turn_number != last_turn or game.phase != last_phase:
            stale_steps = 0
            last_turn = game.turn_number
            last_phase = game.phase
        else:
            stale_steps += 1

        # Se 50 steps sem mudanca de turno/fase, algo travou
        if stale_steps > 50:
            print(f'  ⚠️  TRAVOU ({stale_steps} steps sem progresso)')
            print_separator()
            print_board(game)
            return 'stuck'

        # Mostra a acao
        if action and not action.startswith('wait'):
            if action.startswith('combat'):
                print(f'  {color}{cp.name}: {action}{reset}')
            elif action.startswith('play_'):
                print(f'  {color}{cp.name}: 🃏 {action.replace("play_", "")}{reset}')
            elif action.startswith('attack_') or action.startswith('eliminate_'):
                print(f'  {color}{cp.name}: ⚔️  {action}{reset}')
            elif action.startswith('declare_'):
                print(f'  {color}{cp.name}: 🗣️  {action}{reset}')
            elif action.startswith('feint_'):
                print(f'  {color}{cp.name}: 🎭 {action}{reset}')
            elif action == 'reveal':
                print(f'  {color}{cp.name}: 👁️  REVELAR{reset}')
            elif action == 'end_combat':
                print(f'  {color}{cp.name}: 🏁 FIM COMBATE{reset}')
            elif action == 'draw':
                print(f'  {color}{cp.name}: 📥 COMPRAR{reset}')
            elif action.startswith('pass'):
                if delay:
                    print(f'  {color}{cp.name}: ⏭️  PASSAR{reset}')

        # A cada 4 acoes (fora de combate), mostra o tabuleiro
        if action_count % 4 == 0 and not game.combat.is_active and delay:
            print_separator('-')
            print_board(game)
            time.sleep(delay * 2)

        # Verifica condicoes de fim
        if game.turn_number > max_turns:
            print_separator()
            print(f'⏰ LIMITE DE TURNOS ({max_turns}) ATINGIDO')
            return 'timeout'

        # Vitoria por VP
        for p in game.players:
            if p.victory_points >= p.renown_level:
                print_separator()
                print(f'🏆 {p.name} VENCEU! ({p.victory_points}/{p.renown_level} VP)')
                return p.id

        # Mostra tabuleiro na mudanca de fase
        if game.phase != last_phase or game.turn_number != last_turn:
            print_separator()
            print_board(game)
            time.sleep(delay)

        step += 1

    print_separator()
    print(f'⏰ STEPS EXCEDIDOS ({max_steps})')
    return 'timeout'


def main():
    parser = argparse.ArgumentParser(description='Simulador de partida Rage CCG')
    parser.add_argument('--p1', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--p2', default='hard',
                        choices=['easy', 'medium', 'hard'])
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-turns', type=int, default=30)
    parser.add_argument('--delay', type=float, default=0.3,
                        help='Delay entre acoes (segundos)')
    parser.add_argument('--watch', action='store_true',
                        help='Assiste a partida com delay')
    args = parser.parse_args()

    if args.watch:
        delay = args.delay
    else:
        delay = 0  # sem delay = rapido

    result = run_match(
        seed=args.seed,
        max_turns=args.max_turns,
        difficulty_p1=args.p1,
        difficulty_p2=args.p2,
        delay=delay,
    )

    print()
    print(f'Resultado: {result}')
    print()


if __name__ == '__main__':
    main()
