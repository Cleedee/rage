from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db
from rage_web.models.card import deck_cards


# Estrategias de deck para o bot
ESTRATEGIAS_DECK = {
    'aggro': 'Agressivo: atacar cedo e com frequencia',
    'swarm': 'Enxame: muitas criaturas fracas, sobrecarregar oponente',
    'control': 'Controle: sobreviver, eliminar ameacas',
    'vp_race': 'Corrida de VP: pontuar por quests/vitoria',
    'midrange': 'Equilibrado: desenvolvimento e combate balanceados',
    'combo': 'Combo: usar cartas em sinergia',
    'defensive': 'Defensivo: priorizar bloqueio e esquiva',
}


class Deck(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
    renown_cap: Mapped[int] = mapped_column(default=20)

    # ── Estrategia do deck para o bot ──
    strategy: Mapped[str] = mapped_column(
        String(20), default='midrange', server_default='midrange'
    )

    # ── Galeria social ──
    is_public: Mapped[bool] = mapped_column(default=False, server_default='0')
    telegram_owner_id: Mapped[int | None] = mapped_column(nullable=True)
    usage_count: Mapped[int] = mapped_column(default=0, server_default='0')

    # ── Identificação por conteúdo ──
    # SHA-256 do conteúdo (card_id + quantity), independente de nome/ordem.
    content_hash: Mapped[str] = mapped_column(String(64), default='',
                                              index=True)

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
