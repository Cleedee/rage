"""
Cria deck refinado baseado nas modificacoes do Questor Defence (D416)
como um novo deck para comparacao.
"""
import sqlite3
import sys

sys.path.insert(0, '/workspace')
conn = sqlite3.connect('/workspace/rage_web/database.db')

sept_types = {'Event', 'Action', 'Territory', 'Caern', 'Quest',
              'Battlefield', 'Rite', 'Moot', 'Board Meeting',
              'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
              'Victim', 'Enemy',
              'Equipment', 'Equipment - Fetish - Bane Fetish'}

deck_config = {
    # === CHARACTERS (5) ===
    47: 1,   # Blossom - Wyrm (rage 1, gnosis 6)
    175: 1,  # Longtooth Soulkiller - ALPHA (rage 8, health 8)
    227: 1,  # Questor (rage 3)
    186: 1,  # Maxmillian (rage 2, health 5)
    166: 1,  # Kills-the-Weak (rage 5, health 7)

    # === VICTIMS (9) ===
    535: 3,  # Renegade Werewolf Hunter
    565: 3,  # Vigilante
    568: 3,  # Wild Animals

    # === EQUIPMENT (11) ===
    697: 3,  # Skin of the Hellbound - imune a rage 6+
    713: 2,  # Vampire Blood - cura
    716: 1,  # War Knife of Benning Simon
    720: 1,  # Whip of the Wicked
    700: 1,  # Spiral Boomerang
    630: 1,  # Chronicle of the Black Labyrinth
    272: 1,  # Flak Jacket - armadura
    695: 1,  # Shotgun - ataque a distancia
    # Tambertail's heart removido (muito nichado)

    # === COMBAT ACTIONS (20) ===
    1280: 2, # Maim - rage 7 dmg 4
    1283: 2, # Massive Wound - rage 7 dmg 5
    110: 2,  # Disembowelment - rage 5 dmg 3
    1326: 2, # Vital Blow
    1279: 1, # Lucky Blow
    1308: 1, # Septum Crushed
    1289: 1, # Overextended Attack
    1286: 2, # Off-balanced Attack
    1270: 1, # Curb Stomp
    289: 1,  # Block and Strike - util (reduzido de 2)
    313: 2,  # Dry Gulch
    # Fancy Footwork, Dodge, Evasion removidos

    # === COMBAT EVENTS (5) ===
    1309: 1, # Shieldmate
    1322: 1, # Taking the Death Blow (Death Blow)
    111: 1,  # Fox Frenzy
    112: 1,  # Frenzy
    1525: 1, # Rally to Battle

    # === ACTIONS (6) ===
    790: 3,  # Friends in High Places x3
    807: 3,  # Sneak Attack x3

    # === GIFTS (3) ===
    964: 3,  # Gaia's Will Corrupted x3

    # === TERRITORY (1) ===
    777: 1,  # The Pit
}

# Validar
char_count = 0
sept_count = 0
combat_count = 0
total = 0
valido = True

for cid, qty in deck_config.items():
    c = conn.execute('SELECT name, tipo FROM card WHERE id = ?', (cid,)).fetchone()
    if not c:
        print(f'❌ Card #{cid} nao encontrado!')
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

if total < 50 or total > 75:
    print(f'❌ Tamanho invalido (50-75 expected, got {total})')
    valido = False

if sept_count < 30:
    print(f'❌ Sept deck insuficiente ({sept_count} < 30)')
    valido = False

if combat_count < 20:
    print(f'❌ Combat deck insuficiente ({combat_count} < 20)')
    valido = False

if not valido:
    sys.exit(1)

# Confirm
nome = 'Questor Defence - Refinado'
desc = 'Deck refinado baseado no Classic: Questor Defence com chars melhores, combat actions ofensivas, combat events e equipment novo.'

print(f'\nCriando deck: {nome}')
conn.execute('INSERT INTO deck (name, description) VALUES (?, ?)', (nome, desc))
deck_id = conn.execute('SELECT MAX(id) FROM deck').fetchone()[0]

for cid, qty in deck_config.items():
    conn.execute('INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)', (deck_id, cid, qty))

conn.commit()
print(f'✅ Deck {deck_id} - {nome} criado com {total} cards!')

# Mostrar deck
print(f'\nDeck {deck_id}:')
for cid, qty in sorted(deck_config.items()):
    c = conn.execute('SELECT name, tipo FROM card WHERE id = ?', (cid,)).fetchone()
    if c:
        zone = 'CHAR' if 'Character' in c[1] else ('SEPT' if c[1] in sept_types else 'COMBAT')
        print(f'  #{cid} {c[0]:<40} x{qty} | {c[1]:<20} | {zone}')
