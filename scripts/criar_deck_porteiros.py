"""
Cria deck Os Porteiros (The Gatekeepers) - Gaia pack de 30 renome
que usa presas de ambos os tipos por suas habilidades especiais.

Tema: Um pack Gaia que "coleciona" criaturas poderosas
independente de alinhamento, usando o Hunting Grounds como
um menagerie estrategico.
"""
import sqlite3, sys

sys.path.insert(0, '/workspace')
conn = sqlite3.connect('/workspace/rage_web/database.db')

sept_types = {'Event', 'Action', 'Territory', 'Caern', 'Quest',
              'Battlefield', 'Rite', 'Moot', 'Board Meeting',
              'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
              'Victim', 'Enemy',
              'Equipment', 'Equipment - Fetish - Bane Fetish'}

deck_config = {
    # ═══════════════════════════════════════════════════════════
    # PERSONAGENS (4) — 9+9+7+5 = 30 renome
    # ═══════════════════════════════════════════════════════════
    191: 1,  # Modi Votishal — rn9, Silver Fang Galliard, rage 7, health 10, gnosis 8
             # ALPHA — o "Colecionador", guerreiro poderoso
     34: 1,  # Anna Kliminski — rn9, Shadow Lord Ahroun, rage 3, health 4, gnosis 8
             # A "Caçadora", rastreia presas exoticas
      9: 1,  # Charging Bull — rn7, Wendigo Ragabash, rage 3, health 4, gnosis 6
             # O "Rompedor de Véu", atravessa a Gauntlet
     62: 1,  # Fade-To-Black — rn5, Glass Walker Ragabash, rage 4, health 5, gnosis 6
             # A "Sombra", infiltra-se nos dois mundos

    # ═══════════════════════════════════════════════════════════
    # PRESAS POR UTILIDADE (mistas — Victims por habilidade,
    #                        Enemies por VP + habilidade)
    # ═══════════════════════════════════════════════════════════

    # --- VICTIMS (habilidades valem mais que 0 VP pra Gaia) ---
    503: 2,  # Mage of the Celestial Chorus — 🎯 USA QUALQUER GIFT!
             # Renown 8, health 7. Gaia perde VP mas ganha acesso
             # a qualquer Gift do jogo. Inestimavel.
    451: 1,  # Angus, the White Howler — 🎯 VIRA ALLY APOS 3 TURNOS!
             # Renown 12, health 10. Sobreviver 3 turnos no HG
             # e vira Ally permanente. 5o personagem!
    488: 1,  # Glade Child — Remove ALL Mass Pollution.
             # Protecao contra decks Wyrm que usam poluicao.
    546: 1,  # Street Bum — Counteract 1 Mass Pollution.
             # Reforco anti-poluicao.

    # --- ENEMIES (VP cheio pra Gaia + habilidades) ---
    1337: 2, # Ootani Oil Bane — 🎯 Oponente nao pode retirar!
             # Renown 6, health 5. Prende inimigos no combate
             # ate gastarem todas as cartas de combate.
    573: 2,  # Dream Hunter — 🎯 So existe na Umbra!
             # Renown 4, health 4. Defensor umbral gratis.
             # Forca oponente a ir pra Umbra para ataca-lo.
    517: 1,  # Pentex First Team 43 — 2 Combat Actions/round
             # Renown 8, health 8. Combatente poderoso no HG.
    520: 1,  # Pentex Refinery — Previne regeneracao +2 Gauntlet
             # Renown 14, health 15. Negacao de area massiva.

    # ═══════════════════════════════════════════════════════════
    # EQUIPAMENTOS (8)
    # ═══════════════════════════════════════════════════════════
    697: 2,  # Skin of the Hellbound — imunidade rage 6+
    713: 2,  # Vampire Blood — cura
    272: 1,  # Flak Jacket — armadura
    695: 1,  # Shotgun — ranged
    716: 1,  # War Knife — dano agravado se rage <= 4
    700: 1,  # Spiral Boomerang

    # ═══════════════════════════════════════════════════════════
    # ACOES (4)
    # ═══════════════════════════════════════════════════════════
    790: 2,  # Friends in High Places
    807: 2,  # Sneak Attack

    # ═══════════════════════════════════════════════════════════
    # EVENTOS (5) — controle
    # ═══════════════════════════════════════════════════════════
    875: 2,  # Iron Will — protecao
    885: 2,  # Mass Pollution — poluicao (pra usar com Glade Child?)
    829: 1,  # Close Gauntlet — controle umbral

    # ═══════════════════════════════════════════════════════════
    # GIFTS (6) — focados nos personagens
    # ═══════════════════════════════════════════════════════════
    # Nota: Angus e Mage podem usar gifts que os personagens nao tem
    1056: 2, # Spirit of the Fray — Ahroun (Anna)
    1052: 2, # Silver Claws — Ahroun (Anna) — dano +2
    99:  2,  # Command Spirit — qualquer um pode usar

    # ═══════════════════════════════════════════════════════════
    # COMBAT ACTIONS (20)
    # ═══════════════════════════════════════════════════════════
    110:  2, # Disembowelment — rage 5 dmg 3
    1280: 2, # Maim — rage 7 dmg 4 (Modi rage 7 usa!)
    1283: 2, # Massive Wound — rage 7 dmg 5 (Modi rage 7 usa!)
    1326: 2, # Vital Blow — rage 6 dmg 4
    1279: 2, # Lucky Blow — rage 2 dmg 3
    1278: 2, # Low Blow — rage 2 dmg 3
    1286: 2, # Off-balanced Attack
    1328: 2, # Head Butt — rage 3 dmg 4
    289:  1, # Block and Strike
    317:  1, # Evasion
    1324: 2, # Umbral Escape — fuga umbral
    1303: 1, # Run Like Hell
}

# Validate
char_count = 0
sept_count = 0
combat_count = 0
total = 0
renown_total = 0
requires_ally = False

for cid, qty in deck_config.items():
    c = conn.execute('SELECT name, tipo, renown FROM card WHERE id = ?', (cid,)).fetchone()
    if not c:
        print(f'Card #{cid} not found!')
        continue
    total += qty
    if 'Character' in c[1]:
        char_count += qty
        renown_total += c[2] * qty
    elif c[1] in sept_types:
        sept_count += qty
    else:
        combat_count += qty
    if cid == 1335:  # Bitter Hatar
        requires_ally = True

print(f'=== Os Porteiros (The Gatekeepers) ===')
print(f'Total: {total} cards')
print(f'Characters: {char_count}')
print(f'Total Renown: {renown_total} (max 30)')
print(f'Sept deck: {sept_count} (min 30)')
print(f'Combat deck: {combat_count} (min 20)')

valido = (sept_count >= 30 and combat_count >= 20 and renown_total <= 30)
print(f'Valid: {"✅" if valido else "❌"}')

if not valido:
    sys.exit(1)

# Show prey analysis
print(f'\n=== Analise de Presas ===')
prey = [(cid, qty) for cid, qty in deck_config.items() 
        if cid in [503, 451, 488, 546, 569, 1337, 573, 517, 520, 
                   1336, 1344, 553, 1335]]
for cid, qty in prey:
    c = conn.execute('SELECT name, tipo, renown, text FROM card WHERE id = ?', (cid,)).fetchone()
    if c:
        tipo = c[1]
        texto = (c[3] or '')[:120]
        vp_status = '0 VP (Gaia)' if tipo == 'Victim' else 'VP cheio'
        print(f'  #{cid} {c[0]:<35} [{tipo}] renown={c[2]} | {vp_status}')
        print(f'    {texto}')
        print()

# Confirm
print(f'=== CRIAR DECK? ===')
resp = input('Criar deck? (s/N): ').strip().lower()
if resp != 's':
    print('Cancelado.')
    sys.exit(0)

# Find next available deck ID
next_id = conn.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM deck').fetchone()[0]

nome = 'Os Porteiros (The Gatekeepers)'
desc = ('Gaia pack de 30 renome que usa presas de ambos os tipos '
        'por suas habilidades especiais (Mage of the Celestial Chorus, '
        'Angus, Ootani Oil Bane, Dream Hunter). '
        'Personagens: Modi Votishal, Anna Kliminski, '
        'Charging Bull, Fade-To-Black.')

conn.execute('INSERT INTO deck (id, name, description) VALUES (?, ?, ?)',
             (next_id, nome, desc))
for cid, qty in deck_config.items():
    conn.execute('INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)',
                 (next_id, cid, qty))
conn.commit()
print(f'\n✅ Deck {next_id} - {nome} criado com {total} cards, {renown_total} renome!')

print(f'\n=== Deck Completo ===')
for cid, qty in sorted(deck_config.items()):
    c = conn.execute('SELECT name, tipo FROM card WHERE id = ?', (cid,)).fetchone()
    if c:
        zone = 'CHAR' if 'Character' in c[1] else ('SEPT' if c[1] in sept_types else 'COMBAT')
        print(f'  #{cid} {c[0]:<40} x{qty} | {c[1]:<20} | {zone}')
PYEOF