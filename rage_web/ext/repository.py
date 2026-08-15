
import hashlib
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
                 tags: str = '', limit: int = 100, offset: int = 0) -> list[Card]:
    """Busca cartas com filtros opcionais."""
    q = Card.query
    if query:
        q = q.filter(Card.name.ilike(f'%{query}%'))
    if tipo:
        q = q.filter(Card.tipo == tipo)
    if expansion:
        q = q.filter(Card.expansion == expansion)
    if tags:
        # Suporta múltiplas tags separadas por vírgula (AND logic)
        for tag in tags.split(','):
            tag = tag.strip()
            if tag:
                q = q.filter(Card.tags.ilike(f'%{tag}%'))
    return q.order_by(Card.name).offset(offset).limit(limit).all()

def count_cards(query: str = '', tipo: str = '', expansion: str = '',
                tags: str = '') -> int:
    """Conta cartas com filtros."""
    q = Card.query
    if query:
        q = q.filter(Card.name.ilike(f'%{query}%'))
    if tipo:
        q = q.filter(Card.tipo == tipo)
    if expansion:
        q = q.filter(Card.expansion == expansion)
    if tags:
        for tag in tags.split(','):
            tag = tag.strip()
            if tag:
                q = q.filter(Card.tags.ilike(f'%{tag}%'))
    return q.count()

def get_all_tags() -> list[str]:
    """Retorna lista de todas as tags únicas usadas."""
    from sqlalchemy import func
    result = db.session.query(Card.tags).filter(Card.tags != '').distinct().all()
    tags = set()
    for (tags_str,) in result:
        for t in tags_str.split(','):
            t = t.strip()
            if t:
                tags.add(t)
    return sorted(tags)

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

# --- Conteúdo do deck (hash canônico) ---

def hash_conteudo(cartas: list[tuple[int, int]]) -> str:
    """SHA-256 canônico do conteúdo: pares (card_id, quantidade) ordenados.

    Independe da ordem de inserção e do nome/descrição do deck.
    """
    payload = '|'.join(f'{c}x{q}' for c, q in sorted(cartas))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def deck_content_hash(deck_id: int) -> str:
    """Calcula o content_hash do deck atual no banco (não persiste)."""
    stmt = select(deck_cards.c.card_id, deck_cards.c.quantity).where(
        deck_cards.c.deck_id == deck_id)
    pairs = [(r[0], r[1]) for r in db.session.execute(stmt).all()]
    return hash_conteudo(pairs)


def recalcular_content_hash(deck: Deck) -> None:
    """Recomputa e atualiza deck.content_hash (chamar antes do commit)."""
    deck.content_hash = deck_content_hash(deck.id)

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
    recalcular_content_hash(deck)
    db.session.commit()


def deck_remove_card(deck: Deck, card: Card):
    """Remove uma carta de um deck."""
    db.session.execute(
        deck_cards.delete().where(
            deck_cards.c.deck_id == deck.id,
            deck_cards.c.card_id == card.id,
        )
    )
    recalcular_content_hash(deck)
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
    recalcular_content_hash(deck)
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


def find_decks_with_card(card: Card) -> list[Deck]:
    """Retorna todos os decks que contêm uma determinada carta."""
    stmt = select(Deck).join(deck_cards).where(
        deck_cards.c.card_id == card.id
    ).order_by(Deck.name)
    return list(db.session.scalars(stmt).all())


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
}


def grupo_carta(tipo: str) -> str:
    """Retorna o grupo de uma carta: 'characters', 'sept' ou 'combat'.

    Regras:
      - Characters → 'characters'
      - Combat Actions/Events + Equipment → 'combat'
      - Todo o resto (Gift, Ally, Victim, Enemy, Action, Event, ...) → 'sept'
    """
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


def get_original_image_url(card: Card) -> str | None:
    """Retorna URL apenas da imagem original (LackeyCCG), ignorando fan art."""
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


def get_card_image_url(card: Card) -> str | None:
    """Retorna URL da imagem a ser exibida para uma carta.

    Prioridade:
    1. Fan image (upload do usuário) em /instance/fan_images/
    2. Primeira imagem original do LackeyCCG em /instance/images/
    """
    from flask import current_app
    instance_path = current_app.instance_path

    # 1. Fan image
    if card.fan_image:
        local_path = os.path.join(instance_path, 'fan_images', card.fan_image)
        if os.path.exists(local_path):
            return f'/instance/fan_images/{card.fan_image}'

    # 2. Original image
    if not card.image_file:
        return None
    first_img = card.image_file.split(',')[0].strip()
    if not first_img:
        return None
    local_path = os.path.join(instance_path, 'images', first_img + '.jpg')
    if os.path.exists(local_path):
        return f'/instance/images/{first_img}.jpg'
    return None


def get_card_image_url_by_id(card_id: int) -> str | None:
    """Retorna URL da imagem para um card_id (consulta DB)."""
    from rage_web.models.card import Card
    card = Card.query.get(card_id)
    if not card:
        return None
    return get_card_image_url(card)


def get_back_image_url(card: Card) -> str | None:
    """Retorna URL da imagem de VERSO (Crinos/alternate form) de uma carta.

    O campo image_file pode conter multiplas imagens separadas por virgula.
    A primeira e a imagem da frente (standard form), a segunda e o verso
    (Crinos/alternate form para personagens, ou imagem secundaria).
    """
    if not card.image_file:
        return None
    parts = [p.strip() for p in card.image_file.split(',')]
    if len(parts) < 2:
        return None
    back_img = parts[1]
    if not back_img:
        return None
    from flask import current_app
    instance_path = current_app.instance_path
    local_path = os.path.join(instance_path, 'images', back_img + '.jpg')
    if os.path.exists(local_path):
        return f'/instance/images/{back_img}.jpg'
    return None
