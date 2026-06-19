#!/usr/bin/env python3
"""
Script de restauração do banco de dados.
Reimporta cartas dos JSONs e recria decks dos scripts disponíveis.

Uso:
    PYTHONPATH=. .venv/bin/python3 scripts/restaurar_banco.py
    PYTHONPATH=. .venv/bin/python3 scripts/restaurar_banco.py --dry-run
"""

import argparse
import glob
import json
import os
import sys

import_path = os.path.join(os.path.dirname(__file__), '..')
if import_path not in sys.path:
    sys.path.insert(0, import_path)

os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card, deck_cards
from rage_web.models.deck import Deck

app = create_app('default')

CARD_JSON_DIR = 'data/cards'


def parse_int(val, default=0):
    """Converte valor para int, com fallback."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def restaurar_cards(dry_run=False):
    """Importa cartas dos JSONs para o banco."""
    app.app_context().push()
    
    jsons = sorted(glob.glob(os.path.join(CARD_JSON_DIR, '*.json')))
    criadas = 0
    ignoradas = 0
    erros = 0
    erros_lista = []
    
    for fpath in jsons:
        try:
            with open(fpath, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f'  [ERRO] {os.path.basename(fpath)}: {e}')
            erros += 1
            continue
        
        meta = data.get('_metadata', {})
        card_id = meta.get('card_id')
        if not card_id:
            ignoradas += 1
            continue
        
        # Verifica se já existe
        if not dry_run:
            existing = db.session.get(Card, card_id)
            if existing:
                ignoradas += 1
                continue
        
        # Mapeia campos
        nome = data.get('nome', '')
        tipo = data.get('tipo', '')
        slug = data.get('id', '')
        
        atributos = data.get('atributos', {})
        rage = parse_int(atributos.get('rage'))
        gnosis = parse_int(atributos.get('gnosis'))
        health = parse_int(atributos.get('health'))
        renown = parse_int(data.get('renown'))
        
        keyword = data.get('keyword', '')
        requires = data.get('requires', '')
        damage = data.get('damage', '')
        
        if dry_run:
            print(f'  [DRY] card_id={card_id} nome={nome} tipo={tipo}')
            criadas += 1
            continue
        
        # Cria o card
        try:
            card = Card(
                id=card_id,
                name=nome,
                slug=slug,
                tipo=tipo,
                renown=renown,
                rage=rage,
                gnosis=gnosis,
                health=health,
                keyword=keyword,
                requires=requires,
                damage=damage,
                expansion=meta.get('expansion', ''),
                text=meta.get('texto_original', ''),
                tags=data.get('tags', ''),
            )
            db.session.add(card)
            criadas += 1
            
            if criadas % 100 == 0:
                db.session.commit()
                print(f'  ... {criadas} cartas importadas')
                
        except Exception as e:
            print(f'  [ERRO] card_id={card_id} ({nome}): {e}')
            erros += 1
            erros_lista.append((card_id, nome, str(e)))
    
    db.session.commit()
    
    print(f'\n📊 Cartas importadas:')
    print(f'  Criadas: {criadas}')
    print(f'  Ignoradas: {ignoradas}')
    print(f'  Erros: {erros}')
    if erros_lista:
        print(f'  ⚠️  Erros:')
        for cid, nome, err in erros_lista[:10]:
            print(f'    [{cid}] {nome}: {err}')
    
    return criadas


def aplicar_tags(dry_run=False):
    """Aplica tags do card_tags.json."""
    tag_file = 'data/card_tags.json'
    if not os.path.exists(tag_file):
        print(f'  ⚠️  {tag_file} não encontrado, pulando tags')
        return 0
    
    import json
    with open(tag_file) as f:
        tags_data = json.load(f)
    
    app.app_context().push()
    aplicadas = 0
    
    for entry in tags_data:
        slug = entry.get('slug')
        card_id = entry.get('id')
        tags = entry.get('tags', [])
        
        card = None
        if slug:
            card = Card.query.filter_by(slug=slug).first()
        if not card and card_id:
            card = db.session.get(Card, card_id)
        
        if not card:
            continue
        
        if dry_run:
            print(f'  [DRY] {card.name}: tags={tags}')
            aplicadas += 1
            continue
        
        card.tags = ','.join(tags)
        aplicadas += 1
    
    db.session.commit()
    if not dry_run:
        print(f'  Tags aplicadas: {aplicadas}')
    return aplicadas


def criar_deck_por_script(deck_id, nome, descricao, cards_list, renown_cap=20, dry_run=False):
    """Cria ou atualiza um deck a partir de uma lista de (card_id, quantity)."""
    app.app_context().push()
    
    if dry_run:
        print(f'  [DRY] Deck {deck_id}: {nome} ({sum(q for _, q in cards_list)} cartas)')
        for cid, qty in cards_list:
            card = db.session.get(Card, cid)
            if card:
                print(f'    {qty}x [{cid}] {card.name}')
            else:
                print(f'    {qty}x [{cid}] (⚠️ carta não encontrada)')
        return deck_id
    
    existing = Deck.query.get(deck_id)
    if existing:
        existing.name = nome
        existing.description = descricao
        existing.renown_cap = renown_cap
        db.session.execute(
            deck_cards.delete().where(deck_cards.c.deck_id == deck_id)
        )
    else:
        existing = Deck(
            id=deck_id,
            name=nome,
            description=descricao,
            renown_cap=renown_cap,
            is_public=False,
        )
        db.session.add(existing)
        db.session.flush()
    
    # Adiciona cartas
    for cid, qty in cards_list:
        if db.session.get(Card, cid):
            db.session.execute(
                deck_cards.insert().values(deck_id=deck_id, card_id=cid, quantity=qty)
            )
    
    db.session.commit()
    
    # Estatísticas do deck
    cards_in_deck = (
        db.session.query(db.func.sum(deck_cards.c.quantity))
        .filter(deck_cards.c.deck_id == deck_id)
        .scalar() or 0
    )
    chars = (
        db.session.query(db.func.sum(deck_cards.c.quantity))
        .join(Card)
        .filter(deck_cards.c.deck_id == deck_id, Card.tipo.like('Character%'))
        .scalar() or 0
    )
    
    renown_total = (
        db.session.query(db.func.sum(Card.renown * deck_cards.c.quantity))
        .join(deck_cards)
        .filter(deck_cards.c.deck_id == deck_id)
        .scalar() or 0
    )
    
    print(f'  ✅ Deck {deck_id} — {nome}')
    print(f'     Cartas: {cards_in_deck} | Personagens: {chars} | Renome: {renown_total}')
    
    return deck_id


def main():
    parser = argparse.ArgumentParser(description='Restaura banco de dados Rage CCG')
    parser.add_argument('--dry-run', action='store_true', help='Apenas mostra o que seria feito')
    parser.add_argument('--skip-cards', action='store_true', help='Pula importação de cartas')
    parser.add_argument('--skip-decks', action='store_true', help='Pula criação de decks')
    parser.add_argument('--skip-tags', action='store_true', help='Pula aplicação de tags')
    args = parser.parse_args()
    
    if args.dry_run:
        print('⚡ MODO DRY RUN — nenhuma alteração será feita\n')
    
    # 1. Importar cartas dos JSONs
    if not args.skip_cards:
        print('📦 Importando cartas dos JSONs...')
        n = restaurar_cards(dry_run=args.dry_run)
        print()
    
    # 2. Aplicar tags
    if not args.skip_tags:
        print('🏷️  Aplicando tags...')
        aplicar_tags(dry_run=args.dry_run)
        print()
    
    # 3. Recriar decks
    if not args.skip_decks:
        print('🃏 Recriando decks...')
        
        decks = [
            # (id, nome, descricao, [(card_id, qty), ...], renown_cap)
            
            # Decks principais do torneio
            (1044, 'Ajaba — Hienas da Savana', 
             'Ajaba (werehyenas) Renown 20. Batedores e caçadores em matilha.',
             [(371, 1), (364, 1), (1443, 1), (1625, 1),   # Characters
              (621, 2), (632, 2),                          # Equipment
              (1046, 2), (1025, 2),                        # Gifts
              (292, 2), (118, 2), (316, 2),                # Combat Actions
              (1290, 2), (1416, 2),                        # Combat Events
              (430, 2), (568, 2), (558, 1), (565, 2),     # Allies/Enemies
              (790, 2), (807, 2),                          # Actions
              (286, 2), (289, 2), (293, 2), (1272, 2),    # More CAs
              (312, 2), (317, 2), (321, 2), (1283, 2),
              (1280, 2), (1328, 2), (313, 2), (290, 2)],
             20),
             
            (1045, 'Kitsune — Raposas da Fortuna',
             'Kitsune Hengeyokai Renown 20. Controle via Gnosis, votação e disrupção.',
             [(1614, 1), (1615, 1), (1616, 1), (1617, 1), # Characters: Katsuko, Wu, Morgan, Mei-Fei
              (1455, 1), (1607, 1),                        # Freide + Little Fox
              (621, 2), (1289, 2),                         # Equipment
              (1608, 2), (1609, 2), (1610, 2), (1611, 2), # Gifts
              (1612, 2), (1009, 2), (1394, 2), (1613, 2),
              (292, 2), (286, 2), (316, 2), (118, 2),     # CAs
              (1290, 2), (1416, 2),                        # Combat Events
              (790, 2), (807, 2), (430, 2), (568, 2)],
             20),
             
            (1050, 'Assombração dos Passos da Morte',
             'Pack Ragabash Silent Striders — Stalks Death + truques de Gnosis.',
             [(264, 1), (265, 1), (266, 1), (267, 1),     # Stalks Death pack
              (430, 2), (568, 2), (558, 1),                # Allies
              (790, 2), (807, 2),                          # Actions
              (312, 2), (317, 2), (293, 2), (286, 2),
              (1280, 2), (1328, 2), (313, 2), (290, 2)],
             20),
             
            (7, 'Kinfolk Resistance',
             'Kinfolk + Firearms + Pack combat.',
             [(371, 2), (364, 1),                           # Characters
              (621, 2),                                     # Equipment
              (312, 2), (317, 2), (293, 2), (286, 2),
              (1290, 2), (1416, 2),
              (790, 2), (807, 2), (430, 2)],
             20),
             
            (90, 'Classic: Cliath Ahroun',
             'Ahroun básico, Strike + Dodge.',
             [(371, 2), (364, 1),
              (312, 2), (317, 2), (293, 2), (286, 2),
              (1290, 2), (790, 2)],
             20),
        ]
        
        for did, name, desc, cards, rcap in decks:
            if args.dry_run:
                criar_deck_por_script(did, name, desc, cards, rcap, dry_run=True)
            else:
                try:
                    criar_deck_por_script(did, name, desc, cards, rcap)
                except Exception as e:
                    print(f'  ❌ Deck {did} ({name}): {e}')
        
        print()
    
    print('✅ Restauração concluída!')


if __name__ == '__main__':
    main()
