"""
Importador de decks em formato texto ou XML (.dek LackeyCCG).
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.request import urlopen

from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck
import rage_web.ext.repository as rep

logger = logging.getLogger(__name__)

# Regex para linha de carta: "3 Nome da Carta" ou "1 Nome da Carta"
CARD_LINE_RE = re.compile(r'^\s*(\d+)\s+(.+?)\s*$')


def parse_dek_xml(content: str) -> dict:
    """Analisa arquivo .dek XML do LackeyCCG.

    Retorna:
        dict com 'title', 'author', 'format', 'cards': [(nome, set, qtd)]
    """
    root = ET.fromstring(content)
    meta = root.find('meta')
    result = {
        'title': meta.findtext('title', '').strip() if meta is not None else '',
        'author': meta.findtext('author', '').strip() if meta is not None else '',
        'format': meta.findtext('format', '').strip() if meta is not None else '',
        'cards': [],
    }

    # Agrupa cartas por nome+set
    card_counts = {}
    for superzone in root.findall('superzone'):
        for card_elem in superzone.findall('card'):
            name_elem = card_elem.find('name')
            name = (name_elem.text or '').strip() if name_elem is not None else ''
            # Tenta extrair nome do atributo 'id' se text estiver vazio
            if not name and name_elem is not None:
                name = name_elem.get('id', '').split('.')[-1].replace('_', ' ') or ''
            set_name = card_elem.findtext('set', '').strip() if card_elem is not None else ''
            key = (name, set_name)
            card_counts[key] = card_counts.get(key, 0) + 1

    for (name, set_name), qtd in card_counts.items():
        result['cards'].append((name, set_name, qtd))

    return result


def parse_text_deck(content: str) -> dict:
    """Analisa deck em formato texto livre.

    Formatos aceitos:
      - "3 Nome da Carta"
      - "3x Nome da Carta"
      - Linhas em branco separam seções (ex: Characters, Sept, Combat)
      - Tudo que não casa é ignorado (comentários, explicações)

    Retorna:
        dict com 'cards': [(nome, '', qtd)]
    """
    result = {'cards': []}
    card_counts = {}

    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Pula cabeçalhos de seção (ex: "<u>Characters</u>" ou "Characters:")
        if re.match(r'^<\/?u>|^[A-Z][a-z]+[:]', line):
            continue

        # Tenta extrair quantidade + nome
        m = CARD_LINE_RE.match(line)
        if m:
            qtd = int(m.group(1))
            name = m.group(2).strip()
            # Remove tags HTML
            name = re.sub(r'<[^>]+>', '', name).strip()
            # Remove span leftovers
            name = re.sub(r'\s+', ' ', name).strip()
            if name:
                key = (name, '')
                card_counts[key] = card_counts.get(key, 0) + qtd

    for (name, _), qtd in card_counts.items():
        result['cards'].append((name, '', qtd))

    return result


def find_card_by_name(name: str, set_name: str = '') -> Optional[Card]:
    """Busca carta por nome (e opcionalmente expansão)."""
    if set_name:
        card = Card.query.filter(
            Card.name.ilike(name),
            Card.expansion.ilike(set_name),
        ).first()
        if card:
            return card

    # Busca por nome exato (case insensitive)
    card = Card.query.filter(Card.name.ilike(name)).first()
    if card:
        return card

    # Busca por nome parcial
    cards = Card.query.filter(Card.name.ilike(f'%{name}%')).all()
    if len(cards) == 1:
        return cards[0]
    if len(cards) > 1:
        # Tenta correspondência mais próxima
        name_lower = name.lower()
        for c in cards:
            if c.name.lower() == name_lower:
                return c
        # Retorna None se ambiguo
        logger.warning(f'Nome ambíguo: "{name}" → {len(cards)} correspondências')
        return None

    return None


def import_deck_from_text(content: str, deck_name: str = '',
                          description: str = '') -> dict:
    """Importa cartas de um texto para um novo deck.

    Retorna estatísticas da importação.
    """
    stats = {'total': 0, 'encontradas': 0, 'nao_encontradas': 0, 'cards': []}

    parsed = parse_text_deck(content)
    if not parsed['cards']:
        # Tenta como XML
        parsed = parse_dek_xml(content)

    stats['total'] = len(parsed['cards'])

    if not deck_name:
        deck_name = parsed.get('title', 'Deck Importado')

    deck = Deck(name=deck_name, description=description)
    db.session.add(deck)
    db.session.flush()  # garante deck.id

    for name, set_name, qtd in parsed['cards']:
        card = find_card_by_name(name, set_name)
        if card:
            rep.deck_add_card(deck, card, qtd)
            stats['encontradas'] += 1
            stats['cards'].append({'name': card.name, 'quantity': qtd,
                                    'found': True})
        else:
            stats['nao_encontradas'] += 1
            stats['cards'].append({'name': name, 'quantity': qtd,
                                    'found': False})

    db.session.commit()
    stats['deck_id'] = deck.id
    return stats


def import_deck_from_url(url: str, deck_name: str = '') -> dict:
    """Baixa e importa um deck de uma URL (.dek ou texto)."""
    logger.info(f'Baixando deck de {url}...')
    with urlopen(url, timeout=30) as resp:
        content = resp.read().decode('utf-8', errors='replace')
    return import_deck_from_text(content, deck_name=deck_name)
