from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db
from rage_web.models.card import deck_cards


class Deck(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
    renown_cap: Mapped[int] = mapped_column(default=20)

    # ── Galeria social ──
    is_public: Mapped[bool] = mapped_column(default=False, server_default='0')
    telegram_owner_id: Mapped[int | None] = mapped_column(nullable=True)
    usage_count: Mapped[int] = mapped_column(default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    # Relacionamento muitos-para-muitos com Card
    cards: Mapped[List['Card']] = relationship(
        secondary=deck_cards,
        back_populates='decks',
    )
