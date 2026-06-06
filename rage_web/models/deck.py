from typing import Optional, List

from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db
from rage_web.models.card import deck_cards


class Deck(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
    renown_cap: Mapped[int] = mapped_column(default=20)

    # Relacionamento muitos-para-muitos com Card
    cards: Mapped[List['Card']] = relationship(
        secondary=deck_cards,
        back_populates='decks',
    )
