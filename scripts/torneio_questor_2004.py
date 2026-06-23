#!/usr/bin/env python3
"""Torneio de teste: Questor Defence (2004) vs outros decks.

Uso:
    cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py
    cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py --rounds 3
    cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py --matches 20
"""

import sys
import os
import argparse
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.deck import Deck
from rage_web.game_engine.match import run_match, set_verbosity

# Decks para testar contra o 2004
OPONENTES = [
    (465,  "Apocalypse: First Team #21",  "hard"),
    (1044, "Ajaba: Hienas da Savana",     "hard"),
    (1045, "Kitsune: Raposas da Fortuna",  "hard"),
    (2000, "Apocalypse: First Team 28",   "hard"),
    (2001, "Morgans Bully Quest",         "hard"),
    (2002, "Virtual: Gaia Umbra",         "hard"),
    (2003, "Virtual: Ajaba Aggression",   "hard"),
    (2005, "Classic: Wailer special",     "hard"),
    (2006, "Classic: Wyrm Frenzy",        "hard"),
    (2007, "Classic: Gaia Weenie",        "hard"),
    (2008, "Classic: Grimfang Moot",      "hard"),
    (2013, "Passos da Morte (Ren20)",     "hard"),
    (2014, "Drain Team v1 (Ren20)",       "hard"),
    (2015, "Trovao dos Metis v2",         "hard"),
    (2016, "Umbral Wardens",             "hard"),
    (2017, "Furia e Sabedoria",           "hard"),
]

TARGET_DECK = 2004
TARGET_NAME = "Classic: Questor Defence"


def run_tournament(matches_per_opponent: int = 3, max_rounds: int = 0,
                   verbose: int = 0):
    """Roda torneio round-robin: 2004 vs cada oponente."""
    
    set_verbosity(verbose)
    
    app = create_app()
    with app.app_context():
        # Verifica que o deck 2004 existe
        target = db.session.get(Deck, TARGET_DECK)
        if not target:
            print(f"❌ Deck #{TARGET_DECK} não encontrado!")
            return
        
        print(f"{'='*70}")
        print(f"🏆 TORNEIO: {TARGET_NAME} (#{TARGET_DECK})")
        print(f"{'='*70}")
        print(f"Oponentes: {len(OPONENTES)}")
        print(f"Partidas por oponente: {matches_per_opponent}")
        print(f"Total de partidas: {len(OPONENTES) * matches_per_opponent}")
        print(f"{'='*70}\n")
        
        # Resultados
        results = {
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'errors': 0,
            'by_opponent': defaultdict(lambda: {'wins': 0, 'losses': 0, 'draws': 0, 'errors': 0}),
            'vp_scored': 0,
            'vp_received': 0,
            'turns_avg': 0,
            'total_turns': 0,
            'total_games': 0,
        }
        
        start_time = time.time()
        game_num = 0
        
        for deck_id, deck_name, difficulty in OPONENTES:
            oponente = db.session.get(Deck, deck_id)
            if not oponente:
                print(f"⚠️  Deck #{deck_id} ({deck_name}) não encontrado, pulando...")
                continue
            
            print(f"\n🎯 vs #{deck_id}: {deck_name}")
            print(f"   ({len(oponente.cards)} cards vs {len(target.cards)} cards)")
            
            for i in range(matches_per_opponent):
                game_num += 1
                seed = 1000 + game_num * 7 + i * 13
                
                try:
                    result = run_match(
                        seed=seed,
                        deck1_id=TARGET_DECK,
                        deck2_id=deck_id,
                        difficulty_p1='hard',
                        difficulty_p2=difficulty,
                        delay=0,
                        verbose=0,  # Só resultado
                        max_turns=40,
                    )
                    
                    if result == 'p1':
                        results['wins'] += 1
                        results['by_opponent'][deck_name]['wins'] += 1
                        symbol = '✅'
                    elif result == 'p2':
                        results['losses'] += 1
                        results['by_opponent'][deck_name]['losses'] += 1
                        symbol = '❌'
                    elif result == 'draw':
                        results['draws'] += 1
                        results['by_opponent'][deck_name]['draws'] += 1
                        symbol = '🟰'
                    else:
                        results['errors'] += 1
                        results['by_opponent'][deck_name]['errors'] += 1
                        symbol = '⚠️'
                    
                    print(f"   {symbol} Jogo {i+1}/{matches_per_opponent}: {result}")
                    
                except Exception as e:
                    results['errors'] += 1
                    results['by_opponent'][deck_name]['errors'] += 1
                    print(f"   ⚠️  Jogo {i+1}: ERRO - {e}")
        
        elapsed = time.time() - start_time
        
        # Relatório
        print(f"\n{'='*70}")
        print(f"📊 RELATÓRIO FINAL")
        print(f"{'='*70}")
        print(f"Tempo total: {elapsed:.1f}s")
        print(f"Partidas: {game_num}")
        print(f"")
        print(f"Vitórias:  {results['wins']} ({results['wins']/max(game_num,1)*100:.1f}%)")
        print(f"Derrotas:  {results['losses']} ({results['losses']/max(game_num,1)*100:.1f}%)")
        print(f"Empates:   {results['draws']} ({results['draws']/max(game_num,1)*100:.1f}%)")
        print(f"Erros:     {results['errors']}")
        print(f"")
        
        print(f"📋 Por oponente:")
        print(f"{'Oponente':<35} {'V':>3} {'D':>3} {'E':>3} {'WR%':>6}")
        print(f"{'-'*35} {'-'*3} {'-'*3} {'-'*3} {'-'*6}")
        
        for deck_name, stats in sorted(results['by_opponent'].items()):
            total = stats['wins'] + stats['losses'] + stats['draws']
            wr = stats['wins'] / max(total, 1) * 100
            print(f"{deck_name:<35} {stats['wins']:>3} {stats['losses']:>3} {stats['draws']:>3} {wr:>5.1f}%")
        
        print(f"\n{'='*70}")
        
        return results


def run_single_matches(n_matches: int = 10, verbose: int = 0):
    """Roda N partidas aleatórias do 2004 vs oponentes aleatórios."""
    
    set_verbosity(verbose)
    
    app = create_app()
    with app.app_context():
        target = db.session.get(Deck, TARGET_DECK)
        if not target:
            print(f"❌ Deck #{TARGET_DECK} não encontrado!")
            return
        
        print(f"{'='*70}")
        print(f"🎲 PARTIDAS ALEATÓRIAS: {TARGET_NAME}")
        print(f"{'='*70}")
        print(f"Total: {n_matches} partidas")
        print(f"{'='*70}\n")
        
        import random
        
        results = {'wins': 0, 'losses': 0, 'draws': 0, 'errors': 0}
        start_time = time.time()
        
        for i in range(n_matches):
            deck_id, deck_name, diff = random.choice(OPONENTES)
            seed = random.randint(1, 99999)
            
            print(f"[{i+1}/{n_matches}] vs {deck_name} (seed={seed})...", end=' ', flush=True)
            
            try:
                result = run_match(
                    seed=seed,
                    deck1_id=TARGET_DECK,
                    deck2_id=deck_id,
                    difficulty_p1='hard',
                    difficulty_p2=diff,
                    delay=0,
                    verbose=0,
                    max_turns=40,
                )
                
                if result == 'p1':
                    results['wins'] += 1
                    print("✅ VITÓRIA")
                elif result == 'p2':
                    results['losses'] += 1
                    print("❌ DERROTA")
                elif result == 'draw':
                    results['draws'] += 1
                    print("🟰 EMPATE")
                else:
                    results['errors'] += 1
                    print(f"⚠️  {result}")
                    
            except Exception as e:
                results['errors'] += 1
                print(f"⚠️  ERRO: {e}")
        
        elapsed = time.time() - start_time
        total = n_matches
        
        print(f"\n{'='*70}")
        print(f"📊 RESULTADO: {results['wins']}V / {results['losses']}D / {results['draws']}E ({results['wins']/max(total,1)*100:.1f}% WR)")
        print(f"Tempo: {elapsed:.1f}s")
        print(f"{'='*70}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Torneio Questor Defence')
    parser.add_argument('--rounds', type=int, default=0,
                        help='Rodadas do round-robin (0=todos os oponentes)')
    parser.add_argument('--matches', type=int, default=3,
                        help='Partidas por oponente (round-robin) ou total (aleatório)')
    parser.add_argument('--random', action='store_true',
                        help='Modo aleatório em vez de round-robin')
    parser.add_argument('--verbose', '-v', type=int, default=0,
                        help='Verbosidade (0=resultado, 1=narrativa, 2=debug)')
    
    args = parser.parse_args()
    
    if args.random:
        run_single_matches(args.matches, args.verbose)
    else:
        run_tournament(args.matches, args.rounds, args.verbose)
