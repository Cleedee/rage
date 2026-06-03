
import os
from typing import List, Optional
from sqlalchemy import select, func

from rage_web.models.card import Card, deck_cards
from rage_web.models.deck import Deck
from rage_web.models.picture import Picture
from rage_web.ext.database import db


def find_picture_by_id(id):
    return Picture.query.filter(Picture.id == id).one_or_none()

def find_all_pictures():
    stmt = select(Picture)
    return db.session.scalars(stmt).all()

# --- Card ---

def find_card_by_id(id):
    return Card.query.filter(Card.id == id).one_or_none()

def find_all_cards():
    stmt = select(Card)
    return db.session.scalars(stmt).all()

def search_cards(query: str = '', tipo: str = '', expansion: str = '',
                 limit: int = 100, offset: int = 0) -> list[Card]:
    """Busca cartas com filtros opcionais."""
    q = Card.query
    if query:
        q = q.filter(Card.name.ilike(f'%{query}%'))
    if tipo:
        q = q.filter(Card.tipo == tipo)
    if expansion:
        q = q.filter(Card.expansion == expansion)
    return q.order_by(Card.name).offset(offset).limit(limit).all()

def count_cards(query: str = '', tipo: str = '', expansion: str = '') -> int:
    """Conta cartas com filtros."""
    q = Card.query
    if query:
        q = q.filter(Card.name.ilike(f'%{query}%'))
    if tipo:
        q = q.filter(Card.tipo == tipo)
    if expansion:
        q = q.filter(Card.expansion == expansion)
    return q.count()

def save_card(card: Card):
    db.session.add(card)
    db.session.commit()

def delete_card(card: Card):
    db.session.delete(card)
    db.session.commit()

# --- Deck ---

def find_deck_by_id(id) -> Optional[Deck]:
    return Deck.query.filter(Deck.id == id).one_or_none()

def find_all_decks() -> list[Deck]:
    stmt = select(Deck)
    return db.session.scalars(stmt).all()

def save_deck(deck: Deck):
    db.session.add(deck)
    db.session.commit()

def delete_deck(deck: Deck):
    db.session.delete(deck)
    db.session.commit()

# --- Deck <-> Card ---

def deck_add_card(deck: Deck, card: Card, quantity: int = 1):
    """Adiciona uma carta a um deck."""
    # Verifica se já existe
    stmt = select(deck_cards).where(
        deck_cards.c.deck_id == deck.id,
        deck_cards.c.card_id == card.id,
    )
    existing = db.session.execute(stmt).one_or_none()
    if existing:
        # Atualiza quantidade
        db.session.execute(
            deck_cards.update().where(
                deck_cards.c.deck_id == deck.id,
                deck_cards.c.card_id == card.id,
            ).values(quantity=existing.quantity + quantity)
        )
    else:
        db.session.execute(
            deck_cards.insert().values(
                deck_id=deck.id,
                card_id=card.id,
                quantity=quantity,
            )
        )
    db.session.commit()


def deck_remove_card(deck: Deck, card: Card):
    """Remove uma carta de um deck."""
    db.session.execute(
        deck_cards.delete().where(
            deck_cards.c.deck_id == deck.id,
            deck_cards.c.card_id == card.id,
        )
    )
    db.session.commit()


def deck_update_quantity(deck: Deck, card: Card, quantity: int):
    """Atualiza a quantidade de uma carta no deck."""
    if quantity <= 0:
        return deck_remove_card(deck, card)
    db.session.execute(
        deck_cards.update().where(
            deck_cards.c.deck_id == deck.id,
            deck_cards.c.card_id == card.id,
        ).values(quantity=quantity)
    )
    db.session.commit()


def deck_get_cards(deck: Deck) -> list[dict]:
    """Retorna lista de cartas do deck com quantidade."""
    stmt = select(
        Card,
        deck_cards.c.quantity,
    ).join(
        deck_cards,
        Card.id == deck_cards.c.card_id,
    ).where(
        deck_cards.c.deck_id == deck.id,
    ).order_by(Card.tipo, Card.name)
    results = db.session.execute(stmt).all()
    return [
        {'card': card, 'quantity': quantity}
        for card, quantity in results
    ]


def get_expansions() -> list[str]:
    """Retorna lista de expansões disponíveis."""
    stmt = select(Card.expansion).distinct().order_by(Card.expansion)
    return [r[0] for r in db.session.execute(stmt).all() if r[0]]

def get_tipos() -> list[str]:
    """Retorna lista de tipos de carta disponíveis."""
    stmt = select(Card.tipo).distinct().order_by(Card.tipo)
    return [r[0] for r in db.session.execute(stmt).all() if r[0]]


def count_cards_by_tipo(limit: int = 10) -> list[tuple[str, int]]:
    """Conta cartas agrupadas por tipo."""
    stmt = select(
        Card.tipo, func.count(Card.id)
    ).group_by(Card.tipo).order_by(func.count(Card.id).desc()).limit(limit)
    return [(r[0], r[1]) for r in db.session.execute(stmt).all() if r[0]]


def count_cards_by_expansion(limit: int = 10) -> list[tuple[str, int]]:
    """Conta cartas agrupadas por expansão."""
    stmt = select(
        Card.expansion, func.count(Card.id)
    ).group_by(Card.expansion).order_by(func.count(Card.id).desc()).limit(limit)
    return [(r[0], r[1]) for r in db.session.execute(stmt).all() if r[0]]

# --- Picture ---

def save_picture(picture: Picture):
    db.session.add(picture)
    db.session.commit()

def delete_picture(picture: Picture):
    db.session.delete(picture)
    db.session.commit()


# --- Agrupamento de cartas para decks ---

CHARACTER_TYPES = {
    'Character',
    'Character - Gaia', 'Character - Wyrm', 'Character - Rogue',
    'Character (Rogue)', 'Character (Wyrm)',
    'Character-Gaia', 'Character-Wyrm',
}

COMBAT_TYPES = {
    'Combat Action', 'Combat Event',
    'Equipment', 'Equipment - Fetish - Bane Fetish',
    'Gift',
    'Ally', 'Ally - Caern', 'Ally - Enemy', 'Ally - Victim',
    'Enemy', 'Enemy - Victim',
    'Victim',
}

SEPT_TYPES = {
    'Action', 'Battlefield', 'Board Meeting', 'Caern', 'Event',
    'Moot', 'Past Life', 'Quest', 'Realm', 'Rite',
    'Territory', 'Territory - Realm',
    'combat Event', 'quest',
}


def grupo_carta(tipo: str) -> str:
    """Retorna o grupo de uma carta: 'characters', 'sept' ou 'combat'."""
    if tipo in CHARACTER_TYPES:
        return 'characters'
    if tipo in COMBAT_TYPES:
        return 'combat'
    return 'sept'


def agrupar_cartas_do_deck(cards: list[dict]) -> dict[str, list[dict]]:
    """Agrupa cartas de um deck nas categorias Characters, Sept, Combat."""
    grupos = {'characters': [], 'sept': [], 'combat': []}
    for entry in cards:
        g = grupo_carta(entry['card'].tipo)
        grupos[g].append(entry)
    return grupos


def get_card_image_url(card: Card) -> str | None:
    """Retorna URL da primeira imagem disponível para uma carta.

    Verifica primeiro localmente, depois retorna None se não existir.
    """
    if not card.image_file:
        return None
    first_img = card.image_file.split(',')[0].strip()
    if not first_img:
        return None
    from flask import current_app
    instance_path = current_app.instance_path
    local_path = os.path.join(instance_path, 'images', first_img + '.jpg')
    if os.path.exists(local_path):
        return f'/instance/images/{first_img}.jpg'
    return None
