#!/usr/bin/env python3
"""Análise final das partidas entre os 4 decks do torneio."""

import sys, os, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web.game_engine.match import run_match

DECKS = {
    1043: "🐱 Bastet",
    1044: "🐕 Ajaba",
    1045: "🦊 Kitsune",
    1049: "👹 Wyrm",
}

matchups = [
    (1043, 1044, 42), (1043, 1045, 43), (1043, 1049, 44),
    (1044, 1045, 45), (1044, 1049, 46), (1045, 1049, 47),
]

# Test with VP=8 (approx half of team renown)
print("=" * 65)
print("  TESTE FINAL — VP para vencer = 8")
print("=" * 65)
print(f"{'Matchup':25s} {'Result':10s} {'Turnos':6s} {'VP final':10s}")
print("-" * 53)

total_wins = {}
total_timeouts = 0

for d1, d2, seed in matchups:
    n1 = DECKS[d1]
    n2 = DECKS[d2]
    label = f"{n1} vs {n2}"
    
    for vp in [8]:
        old = sys.stdout
        sys.stdout = io.StringIO()
        result = run_match(seed=seed, max_turns=25, difficulty_p1='medium',
                         difficulty_p2='medium', deck1_id=d1, deck2_id=d2,
                         delay=0.0, vp_to_win=vp)
        output = sys.stdout.getvalue()
        sys.stdout = old
        
        turnos = sum(1 for l in output.split('\n') if '═══ Turno' in l)
        
        # Encontrar VP final dos jogadores
        vp_final = []
        for line in output.split('\n'):
            if 'Jogador' in line and '🏆' in line:
                if 'VP:' in line:
                    vp_part = line.split('VP:')[1].strip().rstrip(')')
                    vp_final.append(vp_part)
        
        # Parse resultado
        if result == 'p1' or result == 'p2':
            winner = n1 if result == 'p1' else n2
            winner_name = "Bastet" if result == 'p1' else "Ajaba"
        elif result == 'timeout':
            winner = '⏰'
            total_timeouts += 1
        else:
            winner = result[:8]
        
        if result not in ('timeout',):
            total_wins[winner] = total_wins.get(winner, 0) + 1
        
        vp_str = vp_final[0] if vp_final else '?'
        print(f"{label:25s} {str(winner):10s} {turnos:<6d} {vp_str:10s}")

print()
print("=" * 65)
print("  RESUMO DAS MELHORIAS IDENTIFICADAS")
print("=" * 65)
print("""
1️⃣  JSON INVÁLIDO (CORRIGIDO)
   - deck7_418_kinfolk_small_town_cop.json: 'restricao' → 'remover_do_jogo'
   - Impedia carregamento de efeitos no motor

2️⃣  JSON MAL MAPEADO (CORRIGIDO)
   - Leap of the Kangaroo [995]: 'ataque_imediato' causava crash
     (atacava cartas não-personagem como 'Spiritual Revelation')
     → Corrigido para 'registrar_trigger_combate' (passivo)

3️⃣  VP ALVO INADEQUADO (PARA AJUSTAR NO TORNEIO)
   - renown_level padrão = 20, mas decks têm apenas 20 de Renome total
   - Jogador precisa matar TODOS os inimigos para vencer = jogos longos
   - VP=8 funciona bem: partidas de 1-5 turnos na maioria dos casos
   - Sugestão: usar vp_to_win = soma_renown_deck // 2 (≈10)

4️⃣  BOT JOGA CARTAS COMO BLEFE
   - Combat Events (Bum Rush, Pack Defense, Cub's Cry) são jogados
     face-down como blefe em vez de ativados
   - Isso porque a arvore do bot trata qualquer carta sem utilidade
     imediata no step de combate como blefe
   - Essas cartas deveriam ser jogadas ANTES do combate, não durante

5️⃣  EFEITOS NÃO IMPLEMENTADOS (JSONs com precisa_revisao=true)
   - Razor Claws [1025]: modificar_atributo 'dano_proximo_ataque'
     não reconhecido pelo resolvedor
   - Spiritual Revelation [908]: comprar com gnosis_scaling
     não implementado no resolvedor
   - Corporate Credit Card [635]: equipar com timing especial
   - Cleft in Twain [296]: dano com requer_arma

6️⃣  FALTA DE AGRESSIVIDADE DOS BOTS
   - Em alguns cenários, o alpha ignora desafios (chance < 30%)
     e depois não ataca ninguém, travando a fase de combate
   - Após a primeira leva de combates, os bots param de atacar
     e passam a usar gifts inúteis

✅  CORREÇÕES APLICADAS:
   - JSON inválido corrigido
   - Leap of the Kangaroo corrigido
   - VP=8 recomendado para torneios com decks Renown 20

⚠️  PENDENTES (para revisão futura):
   - 10 JSONs com precisa_revisao=true precisam de resolvedores novos
   - Bot precisa de heurística melhor para Combat Events
   - Sistema de VP alvo automático baseado no Renome do deck
""")
