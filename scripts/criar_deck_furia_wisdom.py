"""
Refina Deck 619 - Furia e Sabedoria (Wendigo/Shadow Lord)
Focus: Big Fisher (rage 5, Ahroun) + Margrave (gnosis 7, Theurge)
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
    # === CHARACTERS (5) — Wendigo + Shadow Lords ===
    1671: 1,  # Big Fisher — Wendigo Ahroun, rage 5, ALPHA
    180:  1,  # Margrave Konietzko — Shadow Lord Theurge, gnosis 7
    154:  1,  # John Hidden-Moon — Wendigo Ahroun, rage 4
    46:   1,  # Blood-on-the-Wind — Wendigo Galliard, gnosis 9, renown 9
    34:   1,  # Anna Kliminski — Shadow Lord Ahroun, rage 3

    # === VICTIMS (6) — VP farming ===
    535:  2,  # Renegade Werewolf Hunter
    565:  2,  # Vigilante
    568:  2,  # Wild Animals

    # === EQUIPMENT (6) ===
    697:  2,  # Skin of the Hellbound — imunidade rage 6+
    713:  2,  # Vampire Blood — cura
    272:  1,  # Flak Jacket — armadura
    695:  1,  # Shotgun — ranged attack

    # === ACTIONS (6) ===
    790:  2,  # Friends in High Places
    807:  2,  # Sneak Attack
    809:  2,  # Step Sideways — Umbra

    # === EVENTS (6) — keep best, reduce duplicates ===
    875:  2,  # Iron Will (reduzido de 3)
    885:  2,  # Mass Pollution (reduzido de 3)
    215:  1,  # Wendigo (reduzido de 2)
    867:  1,  # Grandfather Thunder (mantido)
    902:  1,  # Red Alert (mantido)

    # === GIFTS (6) — focus on Ahroun + Shadow Lord ===
    1056: 2,  # Spirit of the Fray — req Ahroun (Big Fisher, John, Anna)
    1052: 2,  # Silver Claws — req Ahroun (Big Fisher, John, Anna)
    1000: 1,  # Luna's Armor — req Shadow Lord (Margrave, Anna)
    988:  1,  # Inspiration — req Ahroun (Big Fisher, John, Anna)
    # Removido: Fatal Flaw (muito nichado)

    # === COMBAT ACTIONS (18) — upgrade damage dealers ===
    # Keep best from original:
    1326: 2,  # Vital Blow — rage 6 dmg 4 — so Big Fisher/rage5+ can use
    1279: 2,  # Lucky Blow — rage 2 dmg 3
    1278: 2,  # Low Blow — rage 2 dmg 3
    1286: 2,  # Off-balanced Attack — util
    317:  1,  # Evasion — util (reduzida de 2)
    289:  1,  # Block and Strike — util (reduzida de 2)
    1303: 1,  # Run Like Hell — util (reduzida de 2)
    # Upgrades:
    110:  2,  # Disembowelment — rage 5 dmg 3 — fits Big Fisher/JHM
    1280: 2,  # Maim — rage 7 dmg 4
    1289: 1,  # Overextended Attack — dmg 4
    1270: 1,  # Curb Stomp — dmg 3
    1308: 1,  # Septum Crushed — dmg 4 — so for rage 5+ chars
    1283: 2,  # Massive Wound — rage 7 dmg 5 — so for rage 5+ chars
    # Removido: Dodge, Feint, Gooshy Gooze, Stinging Wound, Wild Flailing,
    #            Rip Open, Body Blow, Brutal Kick, Jaw Breaker,
    #            Reckless Swing, Head Butt, Disarm, Umbral Escape
}

# Validate
char_count = 0
sept_count = 0
combat_count = 0
total = 0
valido = True

for cid, qty in deck_config.items():
    c = conn.execute('SELECT name, tipo FROM card WHERE id = ?', (cid,)).fetchone()
    if not c:
        print(f'Card #{cid} not found!')
        valido = False
        continue
    total += qty
    if 'Character' in c[1]:
        char_count += qty
    elif c[1] in sept_types:
        sept_count += qty
    else:
        combat_count += qty

print(f'Total: {total} cards')
print(f'Characters: {char_count}')
print(f'Sept deck: {sept_count} (min 30)')
print(f'Combat deck: {combat_count} (min 20)')

if not valido:
    sys.exit(1)

if sept_count < 30:
    print(f'Sept insuficiente ({sept_count} < 30)')
    valido = False
if combat_count < 20:
    print(f'Combat insuficiente ({combat_count} < 20)')
    valido = False

if not valido:
    sys.exit(1)

# Apply
conn.execute('DELETE FROM deck_cards WHERE deck_id = 619')
for cid, qty in deck_config.items():
    conn.execute('INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)', (619, cid, qty))
conn.commit()

print(f'\nDeck 619 (Furia e Sabedoria) atualizado!\n')

# Show deck
for cid, qty in sorted(deck_config.items()):
    c = conn.execute('SELECT name, tipo FROM card WHERE id = ?', (cid,)).fetchone()
    if c:
        zone = 'CHAR' if 'Character' in c[1] else ('SEPT' if c[1] in sept_types else 'COMBAT')
        print(f'  #{cid} {c[0]:<40} x{qty} | {c[1]:<20} | {zone}')
