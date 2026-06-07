"""
Ajuste do deck Círculo Kailindo (ID 734).

Problemas identificados:
1. Stand like a Fool x2 — ninguem eh Ragabash (carta morta)
2. So 4 personagens — muito fragil em multijogador
3. Fast Striking inconsistente — precisa de mais cartas

Mudancas:
- Remove Tanzut (Ren4, fragil) → adiciona Shadow-Weaver (Ren2) + Rainpuddle (Ren2) = 5 chars
- Remove Stand like a Fool x2 → adiciona Steel Wall x3 (Fast Striking) + Mass Pollution +1 + Battle Song +1
"""
import sys
sys.path.insert(0, '/workspace')

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

app = create_app()
with app.app_context():
    deck_id = 734
    deck = db.session.get(Deck, deck_id)
    if not deck:
        print(f'Deck {deck_id} nao encontrado')
        exit()
    
    def remover(card_id, qty=1):
        existing = db.session.execute(
            db.select(deck_cards).where(
                deck_cards.c.deck_id == deck_id,
                deck_cards.c.card_id == card_id
            )
        ).first()
        if existing:
            nova_qty = existing.quantity - qty
            if nova_qty <= 0:
                db.session.execute(
                    deck_cards.delete().where(
                        deck_cards.c.deck_id == deck_id,
                        deck_cards.c.card_id == card_id
                    )
                )
                card = db.session.get(Card, card_id)
                print(f'  REMOVE {card.name} x{existing.quantity}')
            else:
                db.session.execute(
                    deck_cards.update().where(
                        deck_cards.c.deck_id == deck_id,
                        deck_cards.c.card_id == card_id
                    ).values(quantity=nova_qty)
                )
                card = db.session.get(Card, card_id)
                print(f'  REMOVE {card.name} {qty} (fica {nova_qty})')
    
    def adicionar(card_id, qty=1):
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
            print(f'  ADD    {card.name} +{qty} (total {nova_qty})')
        else:
            db.session.execute(
                deck_cards.insert().values(deck_id=deck_id, card_id=card_id, quantity=qty)
            )
            print(f'  ADD    {card.name} x{qty}')
    
    print('=== REMOCOES ===')
    # Personagem fragil
    remover(331)  # Tanzut (Ren4)
    # Cartas mortas
    remover(808, 2)  # Stand like a Fool x2
    
    print()
    print('=== ADICOES ===')
    # Novos personagens (Ren2 cada = +4 total = mesmo Ren de Tanzut)
    adicionar(1662)  # Shadow-Weaver (Ren2, step sideways)
    adicionar(231)   # Rainpuddle (Ren2, Stargazer, Umbra)
    
    # Fast Striking consistency
    adicionar(1738, 3)  # Steel Wall (Rg3 Fast Striking Block)
    
    # Preencher slots vagos no sept
    adicionar(885)   # Mass Pollution +1 (agora 3)
    adicionar(932)   # Battle Song +1 (agora 3)
    
    db.session.commit()
    
    # === VERIFICAR ===
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
    
    print(f'\n=== RESUMO ===')
    print(f'  Personagens: {chars} (Renome {ren}/30)')
    print(f'  Combate: {combat} (min 30)')
    print(f'  Sept: {sept} (min 40)')
    print(f'  Total: {total}')
    
    ok = True
    if ren > 30: print(f'  ERRO: Renome {ren} > 30'); ok = False
    if combat < 30: print(f'  ERRO: Combate {combat} < 30'); ok = False
    if sept < 40: print(f'  ERRO: Sept {sept} < 40'); ok = False
    if ok: print(f'\n  DECK VALIDO!')
    
    # Mostrar personagens atualizados
    print(f'\n=== PERSONAGENS ===')
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if card and 'Character' in (card.tipo or ''):
            print(f'  {card.name} (Ren{card.renown}, Rg{card.rage} Gn{card.gnosis} H{card.health})')
PYEOF