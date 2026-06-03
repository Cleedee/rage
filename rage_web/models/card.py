from sqlalchemy.orm import Mapped, mapped_column

from rage_web.ext.database import db

class Card(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    tipo: Mapped[str]
    rage: Mapped[int] = mapped_column(default=0)
    gnosis: Mapped[int] = mapped_column(default=0)
    health: Mapped[int] = mapped_column(default=0)
    rage_morph: Mapped[int] = mapped_column(default=0)
    gnosis_morph: Mapped[int] = mapped_column(default=0)
    health_morph: Mapped[int] = mapped_column(default=0)
    requires: Mapped[str] = mapped_column(default='')
    keyword: Mapped[str] = mapped_column(default='')
    text: Mapped[str] = mapped_column(default='')
