from typing import Optional

from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db


# Tabela associativa Deck <-> Card (muitos-para-muitos)
deck_cards = Table(
    'deck_cards',
    db.metadata,
    Column('deck_id', ForeignKey('deck.id'), primary_key=True),
    Column('card_id', ForeignKey('card.id'), primary_key=True),
    Column('quantity', db.Integer, default=1),
)


class Card(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(default='', index=True)
    expansion: Mapped[str] = mapped_column(default='')
    image_file: Mapped[str] = mapped_column(default='')
    sealed: Mapped[str] = mapped_column(default='')
    tipo: Mapped[str]  # Type: Character - Gaia, Gift, Equipment, etc.
    notes: Mapped[str] = mapped_column(default='')
    requires: Mapped[str] = mapped_column(default='')
    keyword: Mapped[str] = mapped_column(default='')
    renown: Mapped[int] = mapped_column(default=0)
    rage: Mapped[int] = mapped_column(default=0)
    gnosis: Mapped[int] = mapped_column(default=0)
    health: Mapped[int] = mapped_column(default=0)
    rage_morph: Mapped[int] = mapped_column(default=0)
    gnosis_morph: Mapped[int] = mapped_column(default=0)
    health_morph: Mapped[int] = mapped_column(default=0)
    damage: Mapped[str] = mapped_column(default='')
    text: Mapped[str] = mapped_column(default='')
    errata: Mapped[str] = mapped_column(default='')
    fan_image: Mapped[Optional[str]] = mapped_column(default='', nullable=True)
    tags: Mapped[str] = mapped_column(default='')

    # Relacionamento muitos-para-muitos com Deck
    decks: Mapped[list['Deck']] = relationship(
        secondary=deck_cards,
        back_populates='cards',
    )

    pictures: Mapped[list['Picture']] = relationship(back_populates='card')
