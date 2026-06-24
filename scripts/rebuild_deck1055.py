#!/usr/bin/env python3
"""Reconstroi o deck 1055 (O Julgamento — Philodox) para Renome 20."""

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

DECK_ID = 1055

# (card_id, quantity)
CARDS = [
    # === CHARACTERS (Rn:20) ===
    (3, 1),     # Carla Grimsson (Rn:7) - Get of Fenris, Philodox
    (132, 1),   # Grek Twice-Tongue (Rn:6) - Silent Striders, Philodox
    (174, 1),   # Lone Wolf Circles (Rn:4) - Red Talons, Philodox
    (193, 1),   # Morgan the Unworthy (Rn:3) - Fianna, Philodox

    # === COMBAT ACTIONS (18) ===
    # Offense
    (110, 2),   # Disembowelment (Rg:5, Dmg:3)
    (119, 2),   # Head or Gut? (Rg:5, Dmg:3)
    (320, 2),   # Fast Strike (Rg:5, Dmg:2)
    (1313, 2),  # Stunning Strike (Rg:5, Dmg:1)
    (1328, 2),  # Head Butt (Rg:3, Dmg:4)
    (286, 2),   # Bite (Rg:2, Dmg:3)

    # Defense
    (287, 2),   # Block (Rg:1)
    (312, 2),   # Dodge (Rg:1)
    (289, 2),   # Block and Strike (Rg:4)

    # === COMBAT EVENTS (2) ===
    (1290, 2),  # Pack Defense

    # === SEPT CARDS (30) ===
    # Equipment (8)
    (726, 2),   # Assegai - weapon
    (272, 2),   # Flak Jacket - reduce damage
    (621, 2),   # Bivouac - extra health
    (660, 1),   # Lost Map - search utility
    (627, 1),   # Cellular Phone - utility

    # Gifts (12)
    (1021, 3),  # Power of the Ways (Gn:4, Philodox) - cura
    (1029, 2),  # Resist Pain (Gn:3, Get+Philodox) - redução dano
    (1084, 1),  # Wearing the Bear Shirt (Gn:4, Get) - +Rage
    (966, 1),   # Geas (Gn:5, Fianna+Philodox) - força combate
    (1635, 1),  # Odin's Blood (Gn:2, Get) - cura
    (1047, 2),  # Serenity (Gn:3, CoG+Philodox) - utility
    (967, 1),   # Ghost Lance (Gn:4, Silent Striders+Philodox) - utility
    (1003, 1),  # Messenger's Fortitude (Gn:3, Silent Striders) - defense

    # Caern (1)
    (597, 1),   # Sky River Caern

    # Actions (4)
    (790, 2),   # Friends in High Places - end combat
    (807, 2),   # Sneak Attack - bypass combat protocol

    # Rites (1)
    (1618, 1),  # Lone Wolf
]

def rebuild_deck():
    app = create_app()
    with app.app_context():
        deck = db.session.get(Deck, DECK_ID)
        if not deck:
            print(f'Deck {DECK_ID} not found!')
            return

        print(f'Rebuilding deck {DECK_ID}: {deck.name}')

        # Clear existing cards
        db.session.execute(
            deck_cards.delete().where(deck_cards.c.deck_id == DECK_ID)
        )

        # Calculate stats
        total_renown = 0
        char_count = 0
        combat_count = 0
        sept_count = 0
        total = 0

        for card_id, qty in CARDS:
            card = db.session.get(Card, card_id)
            if not card:
                print(f'  WARNING: Card {card_id} not found!')
                continue

            db.session.execute(
                deck_cards.insert().values(
                    deck_id=DECK_ID,
                    card_id=card_id,
                    quantity=qty
                )
            )

            total += qty
            is_char = 'Character' in (card.tipo or '')
            is_combat = 'Combat' in (card.tipo or '')

            if is_char:
                char_count += qty
                total_renown += card.renown * qty
            elif is_combat:
                combat_count += qty
            else:
                sept_count += qty

            print(f'  {qty}x [{card.id}] {card.name} ({card.tipo}) Rn:{card.renown}')

        db.session.commit()

        print(f'\n=== RESUMO ===')
        print(f'Total Renown: {total_renown}')
        print(f'Characters: {char_count}')
        print(f'Combat: {combat_count}')
        print(f'Sept: {sept_count}')
        print(f'Total: {total}')
        print(f'\n=== REQUISITOS Ren20 ===')
        print(f'Combat >= 20: {combat_count} {"✅" if combat_count >= 20 else "❌ FALTAM " + str(20 - combat_count)}')
        print(f'Sept >= 30: {sept_count} {"✅" if sept_count >= 30 else "❌ FALTAM " + str(30 - sept_count)}')

if __name__ == '__main__':
    rebuild_deck()
