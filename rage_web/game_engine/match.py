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

from rage_web.game_engine.cli import create_sample_game, build_game_from_decks
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.combat_queue import get_declaration_summary, get_combatants
from rage_web.game_engine.state import GameState


FASE_NOMES = {
    'redraw': 'REDRAW (Compra)',
    'regeneration': 'REGENERACAO',
    'resource': 'RECURSO (Jogar cartas)',
    'umbra': 'UMBRA (Step Sideways)',
    'moot': 'MOOT (Junta)',
    'combat': 'COMBATE',
}

def _log_fase(game, turno, fase):
    """Loga mudanca de fase com destaque e lista HG."""
    nome = FASE_NOMES.get(fase, fase.upper())
    print(f'\n  ── [{turno}] {nome} ──\n')
    # Mostra Hunting Grounds no inicio de cada fase
    hg_cards = []
    for p in game.players:
        for c in p.hunting_grounds:
            hg_cards.append(f'{c.name}(dono:{p.name})')
    hg_global = getattr(game, 'hunting_grounds_cards', [])
    for c in hg_global:
        hg_cards.append(f'{c.name}(global)')
    if hg_cards:
        print(f'    🎯 Hunting Grounds: {", ".join(hg_cards)}')


def print_separator(char='━', width=60):
    print(char * width)


def print_board(game: GameState):
    """Exibe o estado de forma compacta e colorida."""
    fase_icone = {
        'redraw': '🔄', 'regeneration': '💚', 'resource': '🛠️',
        'umbra': '🌙', 'moot': '🗳️', 'combat': '⚔️',
    }
    icone = fase_icone.get(game.phase, '?')
    print(f'  ═══ Turno {game.turn_number} {icone} {game.phase.upper()} ═══')
    for p in game.players:
        pack = ', '.join(
            f'{c.name}({c.health_current}/{c.health}{"🔒" if c.is_tapped else ""})'
            for c in p.pack_home
        ) or '—'
        hand = len(p.hand)
        deck_c = len(p.deck_combat)
        deck_s = len(p.deck_sept)
        hg_local = ', '.join(f'{c.name}({c.health_current}/{c.health})' if hasattr(c,'health') and c.health else c.name[:15] for c in p.hunting_grounds) or '—'
        print(f'  {p.name:20s} 🃏{hand:2d} 📚C{deck_c:2d} S{deck_s:2d} '
              f'🏆{p.victory_points}')
        print(f'  {" "*20} 🏠 {pack}')
        if p.hunting_grounds:
            print(f'  {" "*20} 🎯 {hg_local}')
    # Global Hunting Grounds
    hg_global = getattr(game, 'hunting_grounds_cards', [])
    if hg_global:
        hg_names = ', '.join(
            f'{c.name}({c.health_current}/{c.health})' if hasattr(c,'health') and c.health
            else c.name[:15] for c in hg_global
        )
        print(f'  {" "*20} 🌍 HG Global: {hg_names}')
    if game.combat.is_active:
        atk = ', '.join(game.combat.attackers)
        dfd = ', '.join(game.combat.defenders)
        print(f'  ⚔️  COMBATE [{game.combat.step}] {atk} vs {dfd}')
        summary = get_declaration_summary(game)
        if 'declarations' in summary:
            for cid, action in summary['declarations'].items():
                print(f'     {cid}: {action}')


def run_match(seed: int = 42, max_turns: int = 30,
              difficulty_p1: str = 'hard',
              difficulty_p2: str = 'hard',
              deck1_id: int | None = None,
              deck2_id: int | None = None,
              delay: float = 0.3) -> str:
    """Roda uma partida entre dois bots.

    Returns:
        'p1' | 'p2' | 'draw' | 'timeout'
    """
    if deck1_id and deck2_id:
        try:
            game = build_game_from_decks(deck1_id, deck2_id, seed=seed)
        except ValueError as e:
            print(f'Erro ao carregar decks: {e}')
            return 'error'
    else:
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
    deck_info = ''
    if deck1_id and deck2_id:
        deck_info = f' | Decks: {deck1_id} vs {deck2_id}'
    print(f'  P1: {difficulty_p1.upper()} | P2: {difficulty_p2.upper()}{deck_info} | Max: {max_turns}t')
    print_separator()
    print_board(game)

    step = 0
    action_count = 0
    stale_steps = 0
    last_turn = game.turn_number
    last_phase = game.phase
    max_steps = max_turns * 50  # limite de seguranca
    _log_fase(game, last_turn, last_phase)

    while step < max_steps:
        # ── Alpha actions (seguem ordem de Renome, nao current_player) ──
        if game.phase == 'combat' and game.combat.alpha_order:
            if game.combat.current_alpha_index < len(game.combat.alpha_order):
                cid_atual = game.combat.current_alpha
                # Encontra o jogador dono deste alpha
                dono_id = None
                for pid, cid in game.combat.alphas.items():
                    if cid == cid_atual:
                        dono_id = pid
                        break
                if dono_id:
                    cp = next(p for p in game.players if p.id == dono_id)
                    game.current_player_index = game.players.index(cp)
                else:
                    cp = game.current_player
            else:
                cp = game.current_player
        else:
            cp = game.current_player

        bot = bots[cp.id]
        color = col1 if cp.id == 'p1' else col2

        action = bot.decide()
        action_count += 1

        # Detecta progresso: turno ou fase mudou
        if game.turn_number != last_turn or game.phase != last_phase:
            stale_steps = 0
        else:
            stale_steps += 1

        # Se 200 steps sem mudanca de turno/fase, algo travou
        if stale_steps > 200:
            print(f'  ⚠️  TRAVOU ({stale_steps} steps sem progresso)')
            print_separator()
            print_board(game)
            return 'stuck'

        # Mostra a acao com nome da carta quando possivel
        if action and not action.startswith('wait'):
            # Tenta extrair nome da carta do ultimo log do jogo
            nome_carta = ''
            ultimo_log = game.log[-1] if game.log else ''
            if ultimo_log and 'jogou' in ultimo_log:
                # "[BOT] Jogador jogou NomeDaCarta" ou "[T1 ...] Jogador jogou NomeDaCarta"
                partes = ultimo_log.split('jogou ')
                if len(partes) > 1:
                    nome_carta = partes[1].strip()
            elif ultimo_log and 'usou' in ultimo_log:
                partes = ultimo_log.split('usou ')
                if len(partes) > 1:
                    nome_carta = partes[1].replace(' (', ' (').strip()

            if action.startswith('combat'):
                print(f'  {color}{cp.name}: ⚔️  {action}{reset}')
            elif action.startswith('play_'):
                label = nome_carta or action.replace('play_', '')
                print(f'  {color}{cp.name}: 🃏 Jogou {label}{reset}')
            elif action.startswith('use_'):
                label = nome_carta or action
                print(f'  {color}{cp.name}: 🎴 Usou {label}{reset}')
            elif action.startswith('attack_') or action.startswith('eliminate_'):
                print(f'  {color}{cp.name}: ⚔️  {action}{reset}')
            elif action.startswith('declare_'):
                print(f'  {color}{cp.name}: 🗣️  {action}{reset}')
            elif action.startswith('feint_'):
                print(f'  {color}{cp.name}: 🎭 {action}{reset}')
            elif action.startswith('umbra_'):
                print(f'  {color}{cp.name}: 🌙 {action}{reset}')
            elif action.startswith('alpha_'):
                print(f'  {color}{cp.name}: 👑 {action}{reset}')
            elif action.startswith('redraw_'):
                print(f'  {color}{cp.name}: 🔄 {action}{reset}')
            elif action.startswith('moot_'):
                print(f'  {color}{cp.name}: 🗳️ {action}{reset}')
            elif action == 'reveal':
                print(f'  {color}{cp.name}: 👁️  REVELAR{reset}')
            elif action in ('end_combat', 'combat_end'):
                print(f'  {color}{cp.name}: 🏁 FIM COMBATE{reset}')
            elif action == 'combat_wait':
                print(f'  {color}{cp.name}: ⏳ AGUARDANDO{reset}')
            elif action == 'draw':
                print(f'  {color}{cp.name}: 📥 COMPRAR{reset}')
            elif action.startswith('pass'):
                if delay:
                    fase_alvo = action.replace('pass_', '').upper() if action != 'pass' else ''
                    label = f'⏭️  PASSAR {fase_alvo}' if fase_alvo else '⏭️  PASSAR'
                    print(f'  {color}{cp.name}: {label}{reset}')

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

        # Mostra tabuleiro na mudanca de fase/turno
        if game.phase != last_phase or game.turn_number != last_turn:
            if game.turn_number != last_turn:
                print(f'\n  ════ TURNO {game.turn_number} ════\n')
            _log_fase(game, game.turn_number, game.phase)
            print_separator('-', 40)
            print_board(game)
            time.sleep(delay)
            last_turn = game.turn_number
            last_phase = game.phase

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
    parser.add_argument('--deck1', type=int, default=None,
                        help='ID do deck do Jogador 1 (usa sample se vazio)')
    parser.add_argument('--deck2', type=int, default=None,
                        help='ID do deck do Jogador 2 (usa sample se vazio)')
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
        deck1_id=args.deck1,
        deck2_id=args.deck2,
        delay=delay,
    )

    print()
    print(f'Resultado: {result}')
    print()


if __name__ == '__main__':
    main()
