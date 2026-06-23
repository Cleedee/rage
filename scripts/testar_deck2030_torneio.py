#!/usr/bin/env python3
"""Testa deck 2030 (Pack Attack — Fianna v4) em torneio contra decks conhecidos."""

import os, sys, io, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
from rage_web.game_engine.match import run_match

DECKS = {
    2030: "Fianna v4",
    465:  "FirstTeam28",
    1044: "Ajaba",
    1045: "Kitsune",
    1054: "Ratkin",
    1055: "Philodox",
    2005: "Wailer",
    2007: "GaiaWeenie",
    2011: "Hakimu",
    2031: "Indestrutiv",
    2033: "VampLords",
}

OPPONENTS = [465, 1044, 1045, 1054, 2005, 2031]
SEEDS = [42, 142]
DIFFICULTY = 'medium'
MAX_TURNS = 15
VP_TO_WIN = 15

results = []
errors = []

print("=" * 70)
print("  TORNEIO: Pack Attack — Fianna v4 (deck 2030)")
print(f"  {len(OPPONENTS)} oponentes x {len(SEEDS)} seeds = {len(OPPONENTS) * len(SEEDS)} partidas")
print("=" * 70)

for opp_id in OPPONENTS:
    opp_name = DECKS[opp_id]
    for seed in SEEDS:
        label = f"Fianna v4 vs {opp_name} (seed={seed})"
        print(f"\n{'─' * 70}")
        print(f"  ▶ {label}")
        print(f"{'─' * 70}")

        try:
            result = run_match(
                seed=seed,
                max_turns=MAX_TURNS,
                difficulty_p1=DIFFICULTY,
                difficulty_p2=DIFFICULTY,
                deck1_id=2030,
                deck2_id=opp_id,
                vp_to_win=VP_TO_WIN,
                delay=0.0,
                verbose=1,
            )
        except Exception as e:
            result = f'error:{e}'

        # Parse result
        if result == 'timeout':
            winner = "⏰ TIME OUT"
            detail = ""
        elif isinstance(result, str) and result.startswith('error'):
            winner = f"💥 ERRO: {result}"
            errors.append(label)
            detail = ""
        elif result == 'draw':
            winner = "🤝 EMPATE"
            detail = ""
        else:
            winner_idx = result
            if winner_idx == '0':
                winner = f"🏆 Fianna v4"
            elif winner_idx == '1':
                winner = f"🏆 {opp_name}"
            else:
                winner = f"🏆 J{winner_idx}"
            detail = ""

        print(f"  {winner}")
        if 'timeout' in result:
            print(f"  ⚠️ Timeout!")

        results.append({
            'match': label,
            'd1': 2030, 'd2': opp_id, 'seed': seed,
            'result': result,
            'winner': winner,
        })

# ── Resumo ──
print("\n" + "=" * 70)
print("  RESUMO DO TORNEIO")
print("=" * 70)
print(f"{'Matchup':45s} {'Resultado':25s}")
print(f"{'─' * 45} {'─' * 25}")
for r in results:
    label = f"Fianna v4 vs {DECKS[r['d2']]} (s={r['seed']})"
    print(f"{label:45s} {r['winner']:25s}")

# Stats
wins_fianna = 0
wins_opp = {}
for opp_id in OPPONENTS:
    wins_opp[opp_id] = 0
draws = 0
timeouts = 0
err_count = 0

for r in results:
    if 'TIME OUT' in r['winner']:
        timeouts += 1
    elif 'EMPATE' in r['winner']:
        draws += 1
    elif 'ERRO' in r['winner']:
        err_count += 1
    elif 'Fianna v4' in r['winner']:
        wins_fianna += 1
    else:
        for opp_id in OPPONENTS:
            if DECKS[opp_id] in r['winner']:
                wins_opp[opp_id] += 1
                break

print(f"\n  🏆 Fianna v4: {wins_fianna} vitórias ({wins_fianna/max(len(results)-timeouts-err_count,1)*100:.0f}%)")
for opp_id in OPPONENTS:
    w = wins_opp[opp_id]
    total_matchups = len(SEEDS)
    print(f"  vs {DECKS[opp_id]:20s}: {w}/{total_matchups} ({w/total_matchups*100:.0f}%)")
print(f"  🤝 Empates: {draws}")
print(f"  ⏰ Timeouts: {timeouts}")
print(f"  💥 Erros: {err_count}")

# ── Detalhes Técnicos ──
print(f"\n{'─' * 70}")
print("  DETALHES TÉCNICOS")
print(f"{'─' * 70}")
for r in results:
    out = r['output']
    problems = []
    for exc in ['KeyError', 'ValueError', 'TypeError', 'AttributeError', 'IndexError']:
        if exc in out:
            problems.append(f"⚠️ {exc}")
    if problems:
        print(f"\n  {r['match']}:")
        for p in problems:
            print(f"    {p}")

# ── Erros ──
if errors:
    print(f"\n{'─' * 70}")
    print("  PARTIDAS COM ERRO")
    print(f"{'─' * 70}")
    for e in errors:
        print(f"  {e}")

print("\n  ✅ Torneio concluído")
print(f"  Resultados salvos internamente ({len(results)} partidas)")
