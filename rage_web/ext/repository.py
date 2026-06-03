
from typing import List
from sqlalchemy import select

from rage_web.models.card import Card
from rage_web.models.deck import Deck
from rage_web.models.picture import Picture
from rage_web.ext.database import db

def find_picture_by_id(id):
    return Picture.query.filter(Picture.id == id).one_or_none()

def find_all_pictures():
    stmt = select(Picture)
    return db.session.scalars(stmt).all()

def find_card_by_id(id):
    return Card.query.filter(Card.id == id).one_or_none()

def find_all_cards():
    stmt = select(Card)
    return db.session.scalars(stmt).all()

def find_deck_by_id(id):
    return Deck.query.filter(Deck.id == id).one_or_none()

def find_all_decks():
    stmt = select(Deck)
    return db.session.scalars(stmt).all()

def save_card(card: Card):
    db.session.add(card)
    db.session.commit()

def delete_card(card: Card):
    db.session.delete(card)
    db.session.commit()

def save_deck(deck: Deck):
    db.session.add(deck)
    db.session.commit()

def delete_deck(deck: Deck):
    db.session.delete(deck)
    db.session.commit()

def save_picture(picture: Picture):
    db.session.add(picture)
    db.session.commit()

def delete_picture(picture: Picture):
    db.session.delete(picture)
    db.session.commit()
