from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column

from rage_web.ext.database import db

class Deck(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    description: Mapped[str] = mapped_column(nullable=True)
