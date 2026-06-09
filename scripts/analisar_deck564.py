"""
Analisa e refina Deck 564 - Drain Team v2 (Ren30)
"""
import sqlite3, sys, os

sys.path.insert(0, '/workspace')
conn = sqlite3.connect('/workspace/rage_web/database.db')

print("=" * 65)
print("ANALISE DO DECK 564 - Drain Team v2 (Ren30)")
print("=" * 65)

deck = conn.execute('SELECT id, name, description FROM deck WHERE id = 564').fetchone()
print(f"\nDeck: {deck[1]}")
print(f"Desc: {deck[2]}")

# Check gift coverage
print(f"\n--- COBERTURA DE GIFTS ---")
gifts = {
    1488: ('Arms of the Abyss', 'Chulorviah - Vampire'),
    935: ("Benefactor's Boon", 'Chulorviah - Pentex'),
    100: ('Consumption of Gaia', 'Eater-of-Souls'),
    109: ('Disquiet', 'Homid - Eater-of-Souls- ananasi'),
    986: ('Infectious Touch', 'Iliad Fomori - Defiler'),
    1032: ('Roar of the Wyrm', 'Bane - Iliad Fomori'),
}

chars = {18: 'Count Vladimir', 29: 'Allonzo Montoya', 67: 'Fek',
         47: 'Blossom', 161: 'Juicy Johnes'}

for gid, (gname, greq) in gifts.items():
    qtde = conn.execute(
        'SELECT SUM(quantity) FROM deck_cards WHERE deck_id=564 AND card_id=?',
        (gid,)).fetchone()[0] or 0
    users = []
    for cid, cname in chars.items():
        kw = conn.execute('SELECT keyword FROM card WHERE id=?', (cid,)).fetchone()[0]
        req_parts = [p.strip() for p in greq.split(' - ')]
        if any(part in kw for part in req_parts):
            users.append(cname)
    print(f"\n  {gname} x{qtde} (req: {greq})")
    print(f"    Usuarios: {', '.join(users) if users else 'NINGUEM!'}")
    if qtde > len(users) and qtde > 0:
        print(f"    ⚠️  {qtde - len(users)} copias extras sem usuario!")

print(f"\n\n--- PROBLEMAS IDENTIFICADOS ---")
print("""
1. 75 cartas - muito acima do ideal (55-60)
2. Gifts sem cobertura: Roar of the Wyrm (x3, 1 user),
   Consumption of Gaia (x3, 1 user)
3. Sem presas no deck - 0 VP farming!
4. Combat actions fracas: Stinging Wound, Surprise Attack,
   Head Wound, Head Butt (x5)
5. Equipment excessivo: 3x Gooshy Gooze, 3x Chronicle
6. Muitos eventos: Eater-of-Souls x2, Mass Pollution x3,
   Dark Fungus x1 = 6
""")
PYEOF