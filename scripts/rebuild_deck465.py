#!/usr/bin/env python3
"""Reconstroi o deck 465 (Apocalypse: First Team #21) para Renome 20."""

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

# Deck composition
# Characters: Rn 8+5+4+3 = 20
# Combat: 24 cards (17 CA + 2 CE + 5 defensive CA)
# Sept: 31 cards
# Total: 59 cards

DECK_ID = 465

# (card_id, quantity)
CARDS = [
    # === CHARACTERS (Rn:20) ===
    (329, 1),   # T.F. MacNeil (Rn:8) - Leader, draws 2 extra combat cards
    (270, 1),   # Sybil (Rn:5) - Iliad Fomori, pack attack
    (17, 1),    # Corinna (Rn:4) - Black Spiral Dancer, Galliard
    (229, 1),   # Ragnor the Terror (Rn:3) - Bane, Eater-of-Souls

    # === COMBAT ACTIONS (17) ===
    # Low Rage (Rg:1-3) - usable by all
    (1289, 3),  # Overextended Attack (Rg:2, Dmg:4) - main damage dealer
    (1294, 2),  # Rapid Reload (Rg:3) - utility
    (1523, 2),  # Iron Skin (Rg:1) - defense

    # Medium Rage (Rg:4-5) - usable with Shotgun
    (1520, 2),  # Dismember (Rg:4, Dmg:3)
    (1359, 2),  # Aggressive Bite (Rg:4, Dmg:3)
    (1407, 2),  # Lobotomy (Rg:4, Dmg:3)
    (1531, 2),  # Whirlwind Defense (Rg:4) - defense
    (313, 2),   # Dry Gulch (Rg:5, Dmg:4)

    # === COMBAT EVENTS (2) ===
    (1285, 2),  # No Escape - prevents fleeing

    # === SEPT CARDS (31) ===
    # Equipment (8)
    (695, 3),   # Shotgun - CAs up to Rg:7
    (692, 2),   # Rocket Launcher - 1 CA up to Rg:12
    (644, 2),   # Experimental Cybernetics - +2 Rage, +1 Health
    (626, 1),   # Bureaucratic Blueprints - surprise attack from HG

    # Gifts (4) - limited by character keywords
    (1005, 2),  # Mindspeak (Gn:3, Galliard) - Corinna
    (1041, 1),  # Scent of Distinction (Gn:2, Galliard) - Corinna
    (921, 1),   # Airt Gateway (Gn:2, Bane) - Ragnor

    # Events (12)
    (890, 3),   # New Moon - control lunar phase
    (910, 3),   # Stuck Sideways - trap characters in Umbra
    (219, 2),   # Wyrm Taint - disrupt Glass Walkers
    (917, 2),   # Town Meeting - call Board Meetings
    (833, 1),   # Corporate Take-over - force Pentex discard equipment
    (838, 1),   # Dragon - pack totem for Wyrm

    # Actions (5)
    (790, 2),   # Friends in High Places - end combat / search
    (807, 3),   # Sneak Attack - bypass combat protocol

    # Caern (1)
    (579, 1),   # Caern of Rytthiku - attack Enemies for VP
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

            # Insert
            db.session.execute(
                deck_cards.insert().values(
                    deck_id=DECK_ID,
                    card_id=card_id,
                    quantity=qty
                )
            )

            total += qty
            is_char = 'Character' in (card.tipo or '')
            is_combat = card.tipo in ('Combat Action', 'Combat Event')

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

if __name__ == '__main__':
    rebuild_deck()
