from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db

class Picture(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] # nome do arquivo salvo
    side: Mapped[int] = mapped_column(default=0)
    # side 0 = frente, side 1 = verso
    version: Mapped[str] = mapped_column(nullable=True)
    card_id: Mapped[int] = mapped_column(ForeignKey('card.id'))
    card: Mapped['Card']= relationship()
