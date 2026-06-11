#!/usr/bin/env python3
"""Simula torneio entre os 4 novos decks e analisa resultados."""

import os, sys, subprocess, json, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
from rage_web.game_engine.match import run_match

DECKS = {
    1043: "Bastet",
    1044: "Ajaba",
    1045: "Kitsune",
    1049: "Wyrm",
}

MATCHUPS = [
    # (deck1_id, deck2_id, seed)
    (1043, 1044, 42),   # Bastet vs Ajaba
    (1043, 1045, 43),   # Bastet vs Kitsune
    (1043, 1049, 44),   # Bastet vs Wyrm
    (1044, 1045, 45),   # Ajaba vs Kitsune
    (1044, 1049, 46),   # Ajaba vs Wyrm
    (1045, 1049, 47),   # Kitsune vs Wyrm
    # Same matchup different seeds to check consistency
    (1043, 1044, 142),  # Bastet vs Ajaba (seed alt)
    (1043, 1049, 144),  # Bastet vs Wyrm (seed alt)
    (1045, 1049, 147),  # Kitsune vs Wyrm (seed alt)
]

results = []

print("=" * 70)
print("  SIMULAÇÃO DE PARTIDAS — 4 NOVOS DECKS")
print("=" * 70)

for d1, d2, seed in MATCHUPS:
    name1 = DECKS[d1]
    name2 = DECKS[d2]
    label = f"{name1} vs {name2} (seed={seed})"
    
    print(f"\n{'─' * 70}")
    print(f"  ▶ {label}")
    print(f"{'─' * 70}")
    
    # Redirect stdout to capture verbose output
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        result = run_match(
            seed=seed,
            max_turns=20,
            difficulty_p1='medium',
            difficulty_p2='medium',
            deck1_id=d1,
            deck2_id=d2,
            delay=0.0,
        )
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    
    # Parse result
    if result == 'timeout':
        winner = "⏰ TIME OUT"
        detail = ""
    elif result == 'error':
        winner = "💥 ERRO"
        detail = ""
    elif result == 'draw':
        winner = "🤝 EMPATE"
        detail = ""
    else:
        winner = f"🏆 {name1 if result == '0' else name2}" if result in ('0', '1') else f"🏆 J{result}"
        detail = ""
    
    # Extract final turn and VP from output
    final_turn = ""
    vps = ""
    for line in output.split('\n'):
        if 'Turno' in line and 'FINAL' in line:
            final_turn = line.strip()
        if 'Vitória' in line:
            winner_line = line.strip()
        if 'VP:' in line and 'J' in line:
            vps = line.strip()
    
    print(f"  Resultado: {winner}")
    if final_turn:
        print(f"  {final_turn}")
    if vps:
        print(f"  {vps}")
    
    results.append({
        'match': label,
        'd1': d1, 'd2': d2, 'seed': seed,
        'result': result,
        'winner': winner,
        'output': output,
    })

print("\n" + "=" * 70)
print("  RESUMO DAS PARTIDAS")
print("=" * 70)
print(f"{'Matchup':40s} {'Resultado':20s}")
print(f"{'─' * 40} {'─' * 20}")
for r in results:
    d1n = DECKS[r['d1']]
    d2n = DECKS[r['d2']]
    label = f"{d1n} vs {d2n} (s={r['seed']})"
    print(f"{label:40s} {r['winner']:20s}")

print("\n" + "=" * 70)
print("  ANÁLISE")
print("=" * 70)

# Analyze win rates
wins = {name: 0 for name in DECKS.values()}
draws = 0
timeouts = 0
errors = 0
for r in results:
    if 'TIME OUT' in r['winner']:
        timeouts += 1
    elif 'EMPATE' in r['winner']:
        draws += 1
    elif 'ERRO' in r['winner']:
        errors += 1
    else:
        for name in DECKS.values():
            if name in r['winner']:
                wins[name] += 1
                break

print(f"\n  Vitórias: {wins}")
print(f"  Empates: {draws}")
print(f"  Timeouts: {timeouts}")
print(f"  Erros: {errors}")

# Detail analysis
print(f"\n{'─' * 70}")
print(f"  DETALHES TÉCNICOS")
print(f"{'─' * 70}")
for r in results:
    out = r['output']
    problems = []
    
    # Check for errors
    if 'KeyError' in out or 'ValueError' in out or 'TypeError' in out:
        problems.append("⚠️ Exceção Python")
    if 'discard' in out.lower() and 'error' in out.lower():
        problems.append("⚠️ Erro de descarte")
    if 'AttributeError' in out:
        problems.append("⚠️ AttributeError")
    
    if problems:
        print(f"\n  {r['match']}:")
        for p in problems:
            print(f"    {p}")

print("\n  ✅ Simulação concluída")
