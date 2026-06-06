"""Sistema principal de crafting automatizado de JSON de efeitos.

Orquestra a leitura do banco, parsing do texto e geração do JSON.
"""

from __future__ import annotations
import json
import os
import re
from typing import Any, Optional
from pathlib import Path

from rage_web.ext.database import db
from rage_web.models.card import Card as CardModel
from rage_web import create_app

from rage_web.helpers.auto_json.parsers import (
    parse_combat_action,
    parse_gift,
    parse_equipment,
    parse_event,
    parse_action,
    parse_ally,
    parse_territory,
    parse_rite,
    parse_moot,
    parse_board_meeting,
    parse_caern,
    parse_enemy,
    parse_victim,
    parse_quest,
    parse_battlefield,
    parse_past_life,
    parse_realm,
    parse_character,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'cards'
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _card_has_json(card_id: int) -> bool:
    """Verifica se já existe um JSON para esta carta."""
    modelo_key = f'card_{card_id}'
    from rage_web.game_engine.effects import CARTAS_EXEMPLO
    return modelo_key in CARTAS_EXEMPLO


def _existing_json_path(card_id: int) -> Optional[Path]:
    """Retorna o path do JSON existente, se houver."""
    for f in DATA_DIR.glob(f'*_{card_id}_*.json'):
        return f
    return None


def _filename_for(card_name: str, card_id: int, deck_id: int = 0) -> str:
    """Gera nome de arquivo padronizado."""
    slug = re.sub(r'[^a-z0-9]+', '_', card_name.lower()).strip('_')
    prefix = f'deck{deck_id}' if deck_id else 'auto'
    return f'{prefix}_{card_id}_{slug}.json'


PARSERS = {
    'Combat Action': parse_combat_action,
    'Combat Event': parse_combat_action,
    'Gift': parse_gift,
    'Equipment': parse_equipment,
    'Event': parse_event,
    'Action': parse_action,
    'Ally': parse_ally,
    'Territory': parse_territory,
    'Rite': parse_rite,
    'Moot': parse_moot,
    'Board Meeting': parse_board_meeting,
    'Caern': parse_caern,
    'Enemy': parse_enemy,
    'Victim': parse_victim,
    'Quest': parse_quest,
    'Battlefield': parse_battlefield,
    'Past Life': parse_past_life,
    'Realm': parse_realm,
    'Character': parse_character,
    'Character - Gaia': parse_character,
    'Character - Wyrm': parse_character,
    'Character - Rogue': parse_character,
}


def craft_card(card_id: int, deck_id: int = 0) -> Optional[dict]:
    """Gera o modelo JSON para uma carta do banco.

    Args:
        card_id: ID da carta no banco SQLite.
        deck_id: ID do deck de origem (para nome do arquivo).

    Returns:
        Dicionário com o modelo JSON, ou None se a carta não for encontrada
        ou já tiver JSON.
    """
    if _card_has_json(card_id):
        return None  # Já existe

    flask_app = create_app()
    with flask_app.app_context():
        card = db.session.get(CardModel, card_id)
        if not card:
            return None

        tipo_base = _tipo_base(card.tipo or '')
        parser = PARSERS.get(tipo_base)
        if not parser:
            return None

        modelo = parser(card)
        if not modelo:
            return None

        # Adicionar metadata
        modelo['_metadata'] = {
            'fonte': 'auto_json',
            'card_id': card_id,
            'texto_original': (card.text or '')[:500],
            'keywords': card.keyword or '',
            'damage': card.damage or '',
            'rage': card.rage,
            'gnosis': card.gnosis,
            'health': card.health,
            'requires': card.requires or '',
        }

        # Salvar
        fname = _filename_for(card.name, card_id, deck_id)
        path = DATA_DIR / fname
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(modelo, f, indent=2, ensure_ascii=False)
            f.write('\n')

        return modelo


def craft_deck_cards(deck_id: int) -> list[dict]:
    """Gera JSONs para todas as cartas de um deck que ainda não têm.

    Args:
        deck_id: ID do deck.

    Returns:
        Lista de modelos JSON gerados.
    """
    from rage_web.models.deck import Deck, deck_cards

    flask_app = create_app()
    with flask_app.app_context():
        deck = db.session.get(Deck, deck_id)
        if not deck:
            return []

        rows = db.session.execute(
            db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
        ).all()

        gerados = []
        for row in rows:
            card = db.session.get(CardModel, row.card_id)
            if not card:
                continue
            if _card_has_json(card.id):
                continue
            modelo = craft_card(card.id, deck_id)
            if modelo:
                gerados.append(modelo)

        return gerados


def craft_all_missing(deck_filter: Optional[list[int]] = None) -> int:
    """Gera JSONs para todas as cartas sem modelo no banco.

    Args:
        deck_filter: Se fornecidos, só considera cartas destes decks.

    Returns:
        Número de JSONs gerados.
    """
    flask_app = create_app()
    with flask_app.app_context():
        from rage_web.models.deck import Deck, deck_cards

        if deck_filter:
            decks = [db.session.get(Deck, did) for did in deck_filter]
            decks = [d for d in decks if d]
        else:
            decks = Deck.query.all()

        cids_vistos: set[int] = set()
        for d in decks:
            rows = db.session.execute(
                db.select(deck_cards).where(deck_cards.c.deck_id == d.id)
            ).all()
            for row in rows:
                cids_vistos.add(row.card_id)

        gerados = 0
        for cid in sorted(cids_vistos):
            if _card_has_json(cid):
                continue
            modelo = craft_card(cid)
            if modelo:
                gerados += 1

        return gerados


def _tipo_base(tipo_raw: str) -> str:
    """Normaliza o tipo da carta para o nome da chave no PARSERS."""
    t = tipo_raw.strip()
    # Mapeamentos especiais
    mapping = {
        'Equipment - Fetish - Bane Fetish': 'Equipment',
        'Character - Gaia': 'Character - Gaia',
        'Character - Wyrm': 'Character - Wyrm',
        'Character - Rogue': 'Character - Rogue',
        'Character (Wyrm)': 'Character - Wyrm',
        'Character (Rogue)': 'Character - Rogue',
        'Character-Gaia': 'Character - Gaia',
        'Character-Wyrm': 'Character - Wyrm',
        'Ally - Victim': 'Ally',
        'Ally - Enemy': 'Ally',
        'Ally - Caern': 'Ally',
        'Enemy - Victim': 'Enemy',
        'Territory - Realm': 'Territory',
        'combat Event': 'Combat Event',
        'quest': 'Quest',
        'Character': 'Character',
    }
    if t in mapping:
        return mapping[t]
    return t
