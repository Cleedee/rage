#!/usr/bin/env python3
"""
Importa decks do site Rage CCG Example Decks.
Baixa todos os .dek primeiro, depois importa em lote.

Uso:
    PYTHONPATH=. .venv/bin/python3 scripts/import_decks_weebly.py
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.request import urlopen

import_path = os.path.join(os.path.dirname(__file__), '..')
if import_path not in sys.path:
    sys.path.insert(0, import_path)

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck, deck_cards

BASE_URL = 'https://rageccg.weebly.com'
DEK_DIR = '/uploads/5/7/1/3/57137205/'

DECKS = [
    ('tourney_first_team.dek', 'Apocalypse: First Team 28', 28),
    ('wendgigo_bullies.dek', 'Apocalypse: Wendigo Bullies', 20),
    ('virtual_-_gaia_umbra.dek', 'Fan only: Gaia Umbra', 20),
    ('virtual_-_ajaba_aggression.dek', 'Fan only: Ajaba Aggression', 20),
    ('classic_questor-defence.dek', 'Classic: Questor Defence', 20),
    ('classic-wailer.dek', 'Classic: Wailer special', 20),
    ('classic_wyrm_frenzy.dek', 'Classic: Wyrm Frenzy', 20),
    ('classic_weenie.dek', 'Classic: Gaia Weenie', 20),
    ('classic_grimfang_moot.dek', 'Classic: Grimfang Moot', 20),
]

CRINOS_ALIASES = {
    'Blood-on-the-Wind (Crinos Form)': 'Blood-on-the-Wind',
    'Old Storm-Chaser (Crinos Form)': 'Old Storm-Chaser',
    'Whispers-in-Pines (Crinos Form)': 'Whispers-in-Pines',
    "Sand's Last King (Crinos Form)": 'Sand\'s Last King',
    'Thousand Cubs (Crinos Form)': 'Thousand Cubs',
    'Ironjaw (Crinos Form)': 'Ironjaw',
    'Amber Eyes-Like-Knives (Crinos Form)': 'Amber Eyes-Like-Knives',
    'Njoki Scarface (Crinos Form)': 'Njoki Scarface',
}


def find_card(name):
    if name in CRINOS_ALIASES:
        name = CRINOS_ALIASES[name]
    clean = name.strip('" \'')
    card = Card.query.filter(Card.name.ilike(clean)).first()
    if card:
        return card
    card = Card.query.filter(Card.name.ilike(f'%{clean}%')).first()
    if card:
        return card
    base = re.sub(r'\s*\(.*?\)\s*$', '', clean).strip()
    if base != clean:
        card = Card.query.filter(Card.name.ilike(base)).first()
        if card:
            return card
    return None


def download_dek(fname):
    url = f'{BASE_URL}{DEK_DIR}{fname}'
    with urlopen(url, timeout=30) as resp:
        content = resp.read().decode('utf-8', errors='replace')
    root = ET.fromstring(content)
    meta = root.find('meta')
    title = meta.findtext('title', '').strip() if meta is not None else ''
    cards = []
    for superzone in root.findall('superzone'):
        for card_elem in superzone.findall('card'):
            name_elem = card_elem.find('name')
            name = (name_elem.text or '').strip() if name_elem is not None else ''
            if not name and name_elem is not None:
                name = name_elem.get('id', '').split('.')[-1].replace('_', ' ') or ''
            set_name = card_elem.findtext('set', '').strip() if card_elem is not None else ''
            cards.append((name, set_name))
    return title, Counter((n, s) for n, s in cards)


def main():
    os.environ['ENVIRONMENT'] = 'default'
    app = create_app('default')
    
    print('🌐 Baixando decks de rageccg.weebly.com/exampledecks...\n')
    
    # 1. Download all decks first
    downloaded = []
    for fname, deck_name, renown_cap in DECKS:
        try:
            title, card_counts = download_dek(fname)
            display = title or deck_name
            print(f'  ✅ {display} ({sum(card_counts.values())} cartas)')
            downloaded.append((display, renown_cap, card_counts))
        except Exception as e:
            print(f'  ❌ {fname}: {e}')
    
    # 2. Import all in one batch
    print(f'\n📦 Importando {len(downloaded)} decks...\n')
    
    with app.app_context():
        start_id = 2000
        
        for name, renown_cap, card_counts in downloaded:
            # Resolve cards
            card_entries = []
            missing = []
            for (cname, cset), qty in sorted(card_counts.items(), key=lambda x: -x[1]):
                card = find_card(cname)
                if card:
                    card_entries.append((card.id, qty, card.name))
                else:
                    missing.append(cname)
            
            total = sum(q for _, q, _ in card_entries)
            pct = len(card_entries) * 100 // len(card_counts)
            
            # Create deck with fixed ID
            desc = f'{name} ({renown_cap} Renown). Importado de rageccg.weebly.com'
            
            existing = Deck.query.get(start_id)
            if existing:
                existing.name = name
                existing.description = desc
                existing.renown_cap = renown_cap
                db.session.execute(deck_cards.delete().where(deck_cards.c.deck_id == start_id))
                deck = existing
            else:
                deck = Deck(id=start_id, name=name, description=desc,
                           renown_cap=renown_cap, is_public=False)
                db.session.add(deck)
                db.session.flush()
            
            for cid, qty, cname in card_entries:
                db.session.execute(
                    deck_cards.insert().values(deck_id=start_id, card_id=cid, quantity=qty)
                )
            
            db.session.commit()
            
            # Export JSON
            export_dir = 'data/decks'
            os.makedirs(export_dir, exist_ok=True)
            
            total_ren = sum(
                (db.session.get(Card, cid).renown or 0) * qty
                for cid, qty, _ in card_entries
            )
            
            export = {
                'id': start_id,
                'name': name,
                'description': desc,
                'renown_cap': renown_cap,
                'strategy': 'midrange',
                'is_public': False,
                'total_cards': total,
                'total_renown': total_ren,
                'cards': [
                    {'card_id': cid, 'name': cname, 'quantity': qty}
                    for cid, qty, cname in card_entries
                ],
            }
            
            fpath = os.path.join(export_dir, f'deck{start_id}.json')
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(export, f, indent=2, ensure_ascii=False)
            
            print(f'  ✅ #{start_id} {name} ({total} cartas, {pct}%)')
            if missing:
                print(f'     ⚠️  {len(missing)} nao encontradas: {", ".join(missing[:3])}')
            
            start_id += 1
    
    print(f'\n✅ Pronto!')


if __name__ == '__main__':
    main()
