"""
Cria Deck 1034 - Drain Team Refinado (v3)
Versao otimizada do D564 com VP farming, gifts viaveis e 60 cartas.
"""
import sys, sqlite3
sys.path.insert(0, '/workspace')

conn = sqlite3.connect('/workspace/rage_web/database.db')

# === NOVO DECK ===
deck_id = 1034
name = "Drain Team Refinado (Ren30)"
description = """Versao refinada do D564: 60 cartas, gifts que funcionam, Victims para VP.
Foco em controle Wyrm/Pentex com Farming de VP."""

conn.execute('DELETE FROM deck_cards WHERE deck_id = ?', (deck_id,))
conn.execute('DELETE FROM deck WHERE id = ?', (deck_id,))
conn.execute('INSERT INTO deck (id, name, description) VALUES (?, ?, ?)',
             (deck_id, name, description))

cards = [
    # === Personagens (5 = 30 renome) ===
    (18, 1),   # Count Vladimir Rustovitch - rn10, alpha
    (29, 1),   # Allonzo Montoya - rn9, Vampire
    (67, 1),   # Fek - rn6, Defiler/Bane
    (47, 1),   # Blossom - rn4, Pentex/Defiler
    (161, 1),  # Juicy Johnes - rn1, Pentex
    
    # === Aliados (3) ===
    (400, 1),  # Experimental Fomori - Pentex Ally
    (430, 2),  # Pentex Executive and Limousine x2
    
    # === Presas (Victims) para VP farming — Wyrm = VP de Victims (6) ===
    (568, 2),  # Wild Animals x2 - rn5 hp4, simples, 10 VP
    (565, 2),  # Vigilante x2 - rn5 hp5, ataca maior Wyrm fim do turno
    (558, 1),  # Unlucky Lune x2 - rn6 hp4, pode usar Gifts
    (503, 1),  # Mage of the Celestial Chorus - rn8 hp7, usa ANY Gift!
    
    # === Acoes (4) ===
    (790, 2),  # Friends in High Places x2
    (807, 2),  # Sneak Attack x2
    
    # === Combat Actions (22) ===
    (1280, 2),  # Maim x2 - dmg 4 rage 7
    (1326, 2),  # Vital Blow x2 - dmg 4 rage 6
    (313, 2),   # Dry Gulch x2 - dmg 4 rage 5
    (1289, 2),  # Overextended Attack x2 - dmg 4 rage 2
    (1308, 2),  # Septum Crushed x2 - dmg 4 rage 5
    (1283, 2),  # Massive Wound x2 - dmg 5 rage 7!
    (1328, 2),  # Head Butt x2 - dmg 4 rage 3
    (1296, 2),  # Reckless Swing x2 - dmg 3 rage 2
    (312, 2),   # Dodge x2
    (317, 2),   # Evasion x2
    (1303, 2),  # Run Like Hell x2 - req Slow Striking
    
    # === Combat Events (2) ===
    (114, 2),   # Gang Beating x2
    
    # === Equipment (7) ===
    (697, 3),   # Skin of the Hellbound x3
    (720, 1),   # Whip of the Wicked x1
    (630, 1),   # Chronicle of the Black Labyrinth x1
    (305, 1),   # Gooshy Gooze x1
    (1722, 1),  # Combat Reflexes x1 - dmg 4
    
    # === Eventos (4) ===
    (885, 2),   # Mass Pollution x2
    (840, 1),   # Eater-of-Souls x1 - req Pentex
    (913, 1),   # The Dark Fungus x1 - req Defiler
    
    # === Gifts (9) ===
    (100, 1),   # Consumption of Gaia x1 - so Vladimir (Eater-of-Souls)
    (1032, 1),  # Roar of the Wyrm x1 - so Fek (Bane)
    (986, 2),   # Infectious Touch x2 - Fek + Blossom (Defiler)
    (1488, 2),  # Arms of the Abyss x2 - Vladimir + Allonzo (Vampire)
    (935, 1),   # Benefactor's Boon x1 - Pentex chars
    (109, 2),   # Disquiet x2 - Homid chars
]

total_qty = 0
for cid, qty in cards:
    conn.execute('INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)',
                 (deck_id, cid, qty))
    total_qty += qty

# Verify
renown = conn.execute('''
    SELECT SUM(c.renown * dc.quantity)
    FROM deck_cards dc JOIN card c ON c.id = dc.card_id
    WHERE dc.deck_id = ? AND c.tipo LIKE 'Character%'
''', (deck_id,)).fetchone()[0] or 0

sept_cards = conn.execute('''
    SELECT SUM(dc.quantity)
    FROM deck_cards dc JOIN card c ON c.id = dc.card_id
    WHERE dc.deck_id = ? AND c.tipo NOT LIKE 'Character%'
      AND c.tipo NOT IN ('Combat Action', 'Combat Event')
''', (deck_id,)).fetchone()[0] or 0

combat_cards = conn.execute('''
    SELECT SUM(dc.quantity)
    FROM deck_cards dc JOIN card c ON c.id = dc.card_id
    WHERE dc.deck_id = ? AND c.tipo IN ('Combat Action', 'Combat Event')
''', (deck_id,)).fetchone()[0] or 0

char_cards = conn.execute('''
    SELECT SUM(dc.quantity)
    FROM deck_cards dc JOIN card c ON c.id = dc.card_id
    WHERE dc.deck_id = ? AND c.tipo LIKE 'Character%'
''', (deck_id,)).fetchone()[0] or 0

print(f"=== DECK CRIADO: #{deck_id} - {name} ===")
print(f"Total: {total_qty} cartas")
print(f"Personagens: {char_cards} (Renome: {renown}/30)")
print(f"Sept deck: {sept_cards} (min 30)")
print(f"Combat deck: {combat_cards} (min 20)")
print(f"Valido: {'✅' if sept_cards >= 30 and combat_cards >= 20 and renown <= 30 else '❌'}")

conn.commit()
conn.close()
PYEOF