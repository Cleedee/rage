from typing import Optional

from redis_om import HashModel, Field

class Card(HashModel):
    name: str = Field(index=True)
    tipo: str = Field(index=True)
    rage: Optional[int] = None
    gnosis: Optional[int] = None
    health: Optional[int] = None
    requires: str = ''
    keyword: str = ''
    text: str = ''

