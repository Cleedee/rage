#!/usr/bin/env python3
"""Reconstroi os decks clássicos perdidos na recriação do banco.

Os decks 160, 629, 90, 619, 705 e 1052 são usados pelos testes do motor
de jogo (build_game_from_decks). Eles sumiram quando o database.db foi
recriado. As checklists em git (data/cards/deck*_checklist.md) contêm a
lista fiel de cartas dos decks originais.

Uso:
    PYTHONPATH=. .venv/bin/python3 scripts/reconstruir_decks.py
"""

import os
import re
import sys

import_path = os.path.join(os.path.dirname(__file__), '..')
if import_path not in sys.path:
    sys.path.insert(0, import_path)

os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app  # noqa: E402
from rage_web.ext.database import db  # noqa: E402
from rage_web.ext.repository import (  # noqa: E402
    recalcular_content_hash,
)
from rage_web.models.deck import Deck, deck_cards  # noqa: E402
from rage_web.models.card import Card  # noqa: E402

app = create_app('default')

CHECKLIST_DIR = os.path.join('data', 'cards')

# Decks reconstruídos a partir das checklists (fontes autoritativas).
CHECKLISTS = {
    'deck160_checklist.md': {
        'name': 'Mokole',
        'description': 'Gaia com quests, morte e recrutamento. '
                       'Sand\'s Last King + Mnesis Dreams.',
        'renown_cap': 20,
        'strategy': 'midrange',
    },
    'deck90_checklist.md': {
        'name': 'Classic: Cliath Ahroun',
        'description': 'Ahroun básico. Strike + dodge + Rage 3-4. '
                       'Bater até cair.',
        'renown_cap': 20,
        'strategy': 'aggro',
    },
    'deck629_checklist.md': {
        'name': 'Umbral Wardens',
        'description': 'Deck Caern + Umbra. Caerns para fortalecer o '
                       'pack e mobilidade da Umbra.',
        'renown_cap': 20,
        'strategy': 'control',
    },
}

# Decks sem checklist — construídos a partir de decks reais existentes.
# 705 = Classic: Gaia Weenie (cópia do deck 2007, que tem Carleson Ruah
# e Flame Spirit). 1052 = pack Wyrm (Assombração). 619 = deck genérico
# (só precisa ser válido para build_game_from_decks).
DECK_705_FONTE = 2007  # Classic: Gaia Weenie
DECK_1052_CARDS = [
    # Wyrm characters
    (17, 1),    # Corinna
    (18, 1),    # Count Vladimir Rustovitch
    (12, 1),    # Chirox the Unfeeling
    (33, 1),    # Amelia
    # Combat actions (sem requisitos altos de Rage)
    (286, 2),   # Bite
    (285, 2),   # Bitch Slap
    (312, 2),   # Dodge
    (1323, 2),  # Telling Blow
    (1286, 2),  # Off-balanced Attack
    # Combat events
    (122, 2),   # Hunting Party
    # Gifts / Events / Equipment
    (890, 2),   # New Moon
    (790, 2),   # Friends in High Places
    (621, 2),   # Bivouac (Equipment)
]
DECK_619_CARDS = [
    (46, 1),    # Blood-on-the-Wind
    (207, 1),   # Old Storm-Chaser
    (349, 1),   # Whispers-in-Pines
    (123, 2),   # Instinctive Attack
    (320, 2),   # Fast Strike
    (1279, 2),  # Lucky Blow
    (944, 2),   # Catfeet
    (546, 2),   # Street Bum
    (1115, 2),  # Bully's Quest
]


def parse_checklist(fpath):
    """Extrai pares (card_id, qty) do markdown de checklist."""
    pares = []
    for line in open(fpath, encoding='utf-8'):
        m = re.match(r'^\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*(\d+)\s*\|', line)
        if m:
            pares.append((int(m.group(1)), int(m.group(4))))
    return pares


def criar_deck(deck_id, nome, descricao, pares, renown_cap=20,
               strategy='midrange', is_public=True):
    """Cria (ou recria) um deck com os pares (card_id, qty) dados."""
    app.app_context().push()

    existing = db.session.get(Deck, deck_id)
    if existing:
        db.session.execute(
            deck_cards.delete().where(deck_cards.c.deck_id == deck_id))
        db.session.delete(existing)
        db.session.commit()

    deck = Deck(
        id=deck_id,
        name=nome,
        description=descricao,
        renown_cap=renown_cap,
        strategy=strategy,
        is_public=is_public,
    )
    db.session.add(deck)
    db.session.flush()

    ausentes = []
    for cid, qty in pares:
        if db.session.get(Card, cid) is None:
            ausentes.append(cid)
            continue
        db.session.execute(deck_cards.insert().values(
            deck_id=deck_id, card_id=cid, quantity=qty))

    recalcular_content_hash(deck)
    db.session.commit()

    total = sum(q for _, q in pares)
    status = f' (⚠️ ausentes: {ausentes})' if ausentes else ''
    print(f'  ✅ Deck {deck_id} — {nome}: {len(pares)} únicas, '
          f'{total} cartas{status}')


def main():
    app.app_context().push()

    print('🃏 Reconstruindo decks das checklists...')
    for fname, meta in CHECKLISTS.items():
        fpath = os.path.join(CHECKLIST_DIR, fname)
        if not os.path.exists(fpath):
            print(f'  ⚠️ Checklist ausente: {fpath} (restaurar do git)')
            continue
        pares = parse_checklist(fpath)
        criar_deck(
            int(re.search(r'deck(\d+)_checklist', fname).group(1)),
            meta['name'], meta['description'], pares,
            meta['renown_cap'], meta['strategy'],
        )

    print('🃏 Deck 705 — Classic: Gaia Weenie (cópia do deck 2007)...')
    rows = db.session.execute(
        db.select(deck_cards.c.card_id, deck_cards.c.quantity)
        .where(deck_cards.c.deck_id == DECK_705_FONTE)
    ).fetchall()
    criar_deck(705, 'Classic: Gaia Weenie',
               'Gaia weenie com Carleson Ruah (deck 2007 reconstruído).',
               [(r[0], r[1]) for r in rows], 20, 'aggro')

    print('🃏 Deck 1052 — Assombração (Wyrm)...')
    criar_deck(1052, 'Assombração',
               'Pack Wyrm — Assombração (deck de suporte dos testes).',
               DECK_1052_CARDS, 20, 'aggro')

    print('🃏 Deck 619 — Deck genérico de suporte...')
    criar_deck(619, 'Deck de Suporte',
               'Deck genérico de oposição para testes.',
               DECK_619_CARDS, 20, 'midrange', is_public=False)

    print('✅ Concluído!')


if __name__ == '__main__':
    main()
