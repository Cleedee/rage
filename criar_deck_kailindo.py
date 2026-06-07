"""
Cria o deck Círculo Kailindo — mestres de Kailindo.
Ren30. Combate ágil com Fast Striking + dano eficiente + Gifts.
"""
import sys
sys.path.insert(0, '/workspace')

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

app = create_app()
with app.app_context():
    # Garantir que não há lock
    db.session.rollback()
    
    # Criar deck
    deck = Deck(name='Círculo Kailindo', 
                description='4 mestres de Kailindo (Ren30). Combate ágil: Fast Striking + dano eficiente (Rg0 dmg4-7) + Gifts versáteis. Pack Totem: The Green Dragon.',
                renown_cap=30)
    db.session.add(deck)
    db.session.flush()
    deck_id = deck.id
    print(f'✅ Deck {deck_id}: {deck.name}')
    
    def adicionar(card_id, qty):
        card = db.session.get(Card, card_id)
        if not card:
            print(f'  ❌ [{card_id}] não encontrado')
            return False
        
        # Verificar se já existe
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
        else:
            db.session.execute(
                deck_cards.insert().values(deck_id=deck_id, card_id=card_id, quantity=qty)
            )
        
        tipo_simbolo = {
            'Character': '👤', 'Character - Gaia': '👤', 'Character - Wyrm': '👹', 'Character - Rogue': '👤',
            'Combat Action': '⚔️', 'Combat Event': '💥',
            'Gift': '✨', 'Equipment': '🔧', 'Ally': '🤝', 'Enemy': '👹',
            'Event': '🌟', 'Action': '⚡', 'Caern': '🏔️', 'Territory': '🗺️',
            'Moot': '🗳️', 'Board Meeting': '🏛️', 'Rite': '🔥',
        }
        s = tipo_simbolo.get(card.tipo, '📜')
        print(f'  {s} {card.name[:40]:40s} x{qty} ({card.tipo})')
        return True
    
    # === PERSONAGENS (Ren30) ===
    # 10 + 8 + 8 + 4 = 30
    print('\n--- PERSONAGENS ---')
    adicionar(13, 1)   # Ciran Far-Traveler (Ren10, Rg4 Gn6 H5) — Alpha, Kailindo
    adicionar(154, 1)  # John Hidden-Moon (Ren8, Rg4 Gn7 H5) — Kailindo, Ahroun
    adicionar(194, 1)  # Morihei High-Mountain (Ren8, Rg3 Gn9 H3) — Kailindo, Gn9
    adicionar(331, 1)  # Tanzut (Ren4, Rg1 Gn4 H2) — Kailindo
    
    # === COMBATE (30+) ===
    print('\n--- COMBATE ---')
    # Fast Striking — atacam primeiro
    adicionar(324, 3)  # Flicker — Rg0 dmg2 Dodge Fast Striking
    adicionar(1362, 3) # Umbral Escape — Rg0 Fast Striking
    adicionar(288, 3)  # Block and Roll — Rg0 Block Fast Striking
    adicionar(1527, 3) # Sudden Impediment — Rg3 Block Fast Striking
    
    # Unblockable — não podem ser bloqueados
    adicionar(1305, 3) # Sap Spirit — Rg0 dmg3 Unblockable
    adicionar(1269, 3) # Critical Blow — Rg4 dmg2 Unblockable
    
    # Dodge — esquiva
    adicionar(312, 3)  # Dodge — Rg1
    adicionar(317, 3)  # Evasion — Rg2 Dodge
    
    # Dano eficiente (Rg0-2)
    adicionar(1720, 3) # Blood Atami — Rg0 dmg4! 
    adicionar(1325, 3) # Umbral Flurry — Rg0 dmg2
    adicionar(1286, 2) # Off-balanced Attack — Rg1 dmg2
    adicionar(1312, 2) # Stinging Wound — Rg1 dmg2
    
    # Dano médio (Rg2-3)
    adicionar(1296, 3) # Reckless Swing — Rg2 dmg3
    adicionar(1279, 3) # Lucky Blow — Rg2 dmg3
    adicionar(1289, 3) # Overextended Attack — Rg2 dmg4
    adicionar(1319, 2) # Surprise Attack — Rg2 dmg1
    adicionar(1328, 3) # Head Butt — Rg3 dmg4
    
    # == SEPT (40+) ==
    print('\n--- SEPT ---')
    
    # Pack Totems
    adicionar(914, 1)  # The Green Dragon — alpha +2 Rage, dano agravado, ignora forma!
    adicionar(867, 1)  # Grandfather Thunder — oponentes -1 Rage
    adicionar(825, 1)  # City Father — declinar ataques, +vantagem urbana
    
    # Caerns
    adicionar(597, 3)  # Sky River Caern
    adicionar(582, 1)  # Caern of the Crescent Moon
    
    # Gifts (Morihei Gn9, Ciran Gn6, John Gn7)
    adicionar(988, 2)  # Inspiration — +1 Rage +1 Gnosis no combate (Gn2)
    adicionar(932, 2)  # Battle Song — +2 Rage alcateia (Gn4)
    adicionar(1056, 2) # Spirit of the Fray — strike first (Gn3)
    adicionar(1426, 2) # Clawstorm — compra 2, joga 3 ações (Gn5)
    adicionar(1488, 2) # Arms of the Abyss — carta extra no round 1 (Gn3)
    adicionar(1003, 2) # Messenger's Fortitude — foge do combate antes de começar (Gn3)
    adicionar(1043, 1) # Scream of Gaia — empurra oponentes para longe (Gn5)
    
    # Equipment
    adicionar(622, 2)  # Blood Dagger — +1 Rage
    adicionar(639, 1)  # Dhul Fiqar — imune a Rg1 ou menos (Silent Striders)
    adicionar(305, 2)  # Gooshy Gooze — redução de dano
    adicionar(638, 1)  # Devilwhip — ação extra de dano!
    
    # Aliados
    adicionar(413, 3)  # Ka Spirit — imortal!
    adicionar(402, 2)  # Flame Spirit — ataque de dano 3 agravado (sacrifício)
    adicionar(418, 2)  # Kinfolk Small Town Cop — prende personagem
    
    # Ações
    adicionar(790, 3)  # Friends in High Places — encerra combate
    adicionar(808, 2)  # Stand like a Fool — oponente não joga Combat Actions (só Ragabash)
    
    # Eventos
    adicionar(807, 3)  # Sneak Attack — ataque a qualquer alvo
    adicionar(885, 2)  # Mass Pollution — umbra
    adicionar(218, 1)  # Wyldstorm — shuffle
    
    # === RESUMO ===
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
    
    print(f'\n=== 📊 RESUMO ===')
    print(f'  👤 Personagens: {chars} (Renome {ren}/30)')
    print(f'  ⚔️  Combate: {combat} (mín 30)')
    print(f'  📜 Sept: {sept} (mín 40)')
    print(f'  📦 Total: {total}')
    
    ok = True
    if ren > 30: print(f'  ❌ Renome {ren} > 30'); ok = False
    if combat < 30: print(f'  ❌ Combate {combat} < 30'); ok = False
    if sept < 40: print(f'  ❌ Sept {sept} < 40'); ok = False
    
    if ok:
        print(f'\n  ✅ DECK VÁLIDO!')
    else:
        print(f'\n  ❌ DECK INVÁLIDO')
    
    db.session.commit()
    print(f'\nID do deck: {deck_id}')
