"""
Cria o deck "Os Ratos de Rua" — Bone Gnawers Ren30.

Tematica: Escoria urbana, espertos, resilientes.
5 personagens = resistencia numerica.
Equipment-heavy (Bannion da .38 Special gratis).
Combate de baixo custo (Rg0-Rg2).
"""
import sys
sys.path.insert(0, '/workspace')

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

app = create_app()
with app.app_context():
    deck_id = 735
    deck_name = "Os Ratos de Rua"
    
    # Check if deck already exists
    existing = Deck.query.get(deck_id)
    if existing:
        print(f'Deck {deck_id} ja existe: {existing.name}')
        # Clear it
        db.session.execute(deck_cards.delete().where(deck_cards.c.deck_id == deck_id))
        existing.name = deck_name
        existing.description = (
            'Bone Gnawers Ren30 — 5 personagens espertos e resilientes. '
            'Grandfather Bannion da .38 Special gratis para todos. '
            'Buggerhead filtra mao de sept todo turno. '
            'Combat cards de baixo custo (Rg0-Rg2) com Sap Spirit e Blood Atami de dano eficiente. '
            'Equipment-heavy com Flak Jacket, Gooshy Gooze, Improvised Weapon. '
            'Estrategia: atrito, numbers advantage, equipamento versatil.'
        )
    else:
        deck = Deck(id=deck_id, name=deck_name)
        db.session.add(deck)
        db.session.flush()
    
    def adicionar(card_id, qty):
        card = db.session.get(Card, card_id)
        existing = db.session.execute(
            db.select(deck_cards).where(
                deck_cards.c.deck_id == deck_id,
                deck_cards.c.card_id == card_id
            )
        ).first()
        
        if existing:
            nova_qty = existing.quantity + qty
            db.session.execute(
                deck_cards.update().where(
                    deck_cards.c.deck_id == deck_id,
                    deck_cards.c.card_id == card_id
                ).values(quantity=nova_qty)
            )
            print(f'  ADD    {card.name:35s} +{qty} (total {nova_qty})')
        else:
            db.session.execute(
                deck_cards.insert().values(deck_id=deck_id, card_id=card_id, quantity=qty)
            )
            print(f'  ADD    {card.name:35s} x{qty}')
    
    print(f'Criando deck {deck_id}: {deck_name}')
    print()
    
    # === PERSONAGENS (Ren30) ===
    print('PERSONAGENS:')
    # Grandfather Bannion (Ren9) — da .38 Special gratis
    adicionar(131, 1)
    # Mother Larissa (Ren8) — resiliente, desenha combat cards
    adicionar(195, 1)
    # Buggerhead (Ren6) — filtra sept deck todo turno
    adicionar(1, 1)
    # Crick Rumwrangler (Ren4) — Amazon Wyrm fighter
    adicionar(19, 1)
    # Quari Filth (Ren3) — busca combat card do descarte
    adicionar(1469, 1)
    
    print()
    
    # === COMBATE (min 30) ===
    print('COMBATE:')
    # Dodge (Rg1, esquiva basica)
    adicionar(312, 3)
    # Evasion (Rg2, esquiva)
    adicionar(317, 3)
    # Block and Roll (Rg0, Fast Striking Block)
    adicionar(288, 3)
    # Flicker (Rg0, dodge-damage 2)
    adicionar(324, 2)
    # Lucky Blow (Rg2, dmg3)
    adicionar(1279, 3)
    # Off-balanced Attack (Rg1, dmg2)
    adicionar(1286, 3)
    # Overextended Attack (Rg2, dmg4)
    adicionar(1289, 2)
    # Reckless Swing (Rg2, dmg3)
    adicionar(1296, 3)
    # Sap Spirit (Rg0, dmg3 Unblockable)
    adicionar(1305, 3)
    # Stinging Wound (Rg1, dmg2)
    adicionar(1312, 2)
    # Blood Atami (Rg0, dmg4)
    adicionar(1720, 3)
    # Surprise Attack (Rg2, dmg1)
    adicionar(1319, 2)
    
    print()
    
    # === SEPT (min 40) ===
    print('SEPT:')
    # .38 Special x3 — Bannion da gratis pra todos!
    adicionar(610, 3)
    # Flak Jacket — armadura
    adicionar(272, 1)
    # Gooshy Gooze — debuff oponente
    adicionar(305, 2)
    # Improvised Weapon — tematico Bone Gnawer!
    adicionar(311, 2)
    # Blood Dagger — +2 Rage
    adicionar(622, 1)
    # Friends in High Places — fuga
    adicionar(790, 2)
    # City Father — declinar ataques
    adicionar(825, 1)
    # Grandfather Thunder — -1 Rage oponentes
    adicionar(867, 1)
    # Mass Pollution — controle Umbra
    adicionar(885, 2)
    # The Green Dragon — dano agravado
    adicionar(914, 1)
    # Spirit of the Fray — Strike first
    adicionar(1056, 2)
    # Clawstorm — draw combat cards
    adicionar(1426, 2)
    # Inspiration — buff combate
    adicionar(988, 2)
    # Battle Song — +Rage buff
    adicionar(932, 2)
    # Messenger's Fortitude — fuga pre-combate
    adicionar(1003, 2)
    # Caern of the Crescent Moon
    adicionar(582, 1)
    # Sky River Caern
    adicionar(597, 3)
    # Ka Spirit
    adicionar(413, 2)
    # Kinfolk Small Town Cop
    adicionar(418, 2)
    # Flame Spirit
    adicionar(402, 2)
    # Sneak Attack
    adicionar(807, 2)
    # Firebomb — territorio
    adicionar(271, 1)
    
    db.session.commit()
    
    # === VERIFY ===
    rows = db.session.execute(
        db.select(deck_cards.c.card_id, deck_cards.c.quantity)
        .where(deck_cards.c.deck_id == deck_id)
    ).all()
    
    total = 0
    ren = 0
    combat = 0
    sept = 0
    chars = 0
    
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if not card: continue
        q = row.quantity
        total += q
        if 'Character' in (card.tipo or ''):
            ren += (card.renown or 0) * q
            chars += q
        elif 'combat' in (card.tipo or '').lower() or card.tipo in ('Combat Action', 'Combat Event'):
            combat += q
        elif 'Character' not in (card.tipo or ''):
            sept += q
    
    print(f'\n{"="*50}')
    print(f'RESUMO:')
    print(f'  Personagens: {chars} (Renome {ren}/30)')
    print(f'  Combate: {combat} (min 30)')
    print(f'  Sept: {sept} (min 40)')
    print(f'  Total: {total}')
    
    ok = True
    if ren > 30: print(f'  ERRO: Renome {ren} > 30'); ok = False
    if combat < 30: print(f'  ERRO: Combate {combat} < 30'); ok = False
    if sept < 40: print(f'  ERRO: Sept {sept} < 40'); ok = False
    if ok: print(f'\n  ✅ DECK VALIDO!')
    
    print(f'\nPersonagens:')
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if card and 'Character' in (card.tipo or ''):
            print(f'  {card.name} (Ren{card.renown}, Rg{card.rage} Gn{card.gnosis} H{card.health})')
    
    print(f'\nContagem por tipo:')
    tipos = {}
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if card:
            t = card.tipo or 'Unknown'
            if 'Character' in t:
                t = 'Character'
            elif 'Combat' in t:
                t = 'Combat'
            tipos[t] = tipos.get(t, 0) + row.quantity
    for t, q in sorted(tipos.items()):
        print(f'  {t}: {q}')
PYEOF