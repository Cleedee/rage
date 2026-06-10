#!/usr/bin/env python3
"""
Script para gerar slugs estáveis para cartas no banco de dados e JSONs.

Slug format: slugify(name) + renown suffix (se > 0).
Para colisoes (cartas diferentes com mesmo nome+renown), expansion como desambiguador.

Uso:
    .venv/bin/python3 scripts/gerar_slugs.py          # Apenas backfill no banco
    .venv/bin/python3 scripts/gerar_slugs.py --json   # Atualiza JSONs tambem
    .venv/bin/python3 scripts/gerar_slugs.py --dry-run # Preview sem alterar
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from slugify import slugify

# Para execucao standalone, acessa banco direto
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cards')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'rage_web', 'database.db')


def gerar_slug_base(name: str, renown: int = 0) -> str:
    """Gera slug base: slugify do nome + _r{N} se renown > 0."""
    slug = slugify(name)
    if renown and renown > 0:
        slug = f'{slug}_r{renown}'
    return slug


def gerar_slug(name: str, renown: int = 0, expansion: str = '') -> str:
    """Gera slug completo, com expansion como desambiguador final."""
    base = gerar_slug_base(name, renown)
    if expansion:
        exp_slug = slugify(expansion.replace('(', '').replace(')', ''))
        if exp_slug:
            return f'{base}_{exp_slug}'
    return base


def backfill_db(conn, dry_run=False):
    """Preenche campo slug no banco SQLite."""
    cur = conn.cursor()
    
    # Verifica se coluna slug existe
    cur.execute('PRAGMA table_info(card)')
    cols = [r[1] for r in cur.fetchall()]
    if 'slug' not in cols:
        print('ERRO: coluna slug nao existe na tabela card. Execute migration primeiro.')
        return False
    
    # Busca todas as cartas
    cur.execute('SELECT id, name, renown, expansion FROM card ORDER BY id')
    cards = cur.fetchall()
    
    # Primeira pass: gera slugs base
    slug_counts = defaultdict(list)
    for cid, name, renown, expansion in cards:
        base = gerar_slug_base(name, renown or 0)
        slug_counts[base].append((cid, name, renown or 0, expansion or ''))
    
    # Segunda pass: resolve colisoes
    updates = []
    for base, entries in slug_counts.items():
        if len(entries) == 1:
            # Unico, sem colisao
            updates.append((entries[0][0], base))
        else:
            # Colisao: adiciona expansion como desambiguador
            for cid, name, renown, expansion in entries:
                if expansion:
                    slug = gerar_slug(name, renown, expansion)
                else:
                    slug = f'{base}_{cid}'  # Fallback: usa ID
                updates.append((cid, slug))
    
    # Aplica atualizacoes
    if dry_run:
        print(f'[DRY-RUN] {len(updates)} slugs seriam atualizados:')
        for cid, slug in updates[:10]:
            cur.execute('SELECT name, renown, expansion FROM card WHERE id = ?', (cid,))
            card = cur.fetchone()
            print(f'  id={cid}: {card[0]:40s} -> {slug}')
        if len(updates) > 10:
            print(f'  ... e mais {len(updates) - 10}')
    else:
        for cid, slug in updates:
            cur.execute('UPDATE card SET slug = ? WHERE id = ?', (slug, cid))
        conn.commit()
        print(f'✅ {len(updates)} slugs atualizados no banco.')
    
    return True


def update_jsons(conn, dry_run=False):
    """Adiciona slug no _metadata de todos os JSONs."""
    cur = conn.cursor()
    
    # Carrega slugs do banco
    cur.execute('SELECT id, slug FROM card WHERE slug != ""')
    slugs = {row[0]: row[1] for row in cur.fetchall()}
    print(f'  {len(slugs)} slugs carregados do banco.')
    
    if not os.path.isdir(DATA_DIR):
        print(f'  ERRO: diretorio {DATA_DIR} nao encontrado.')
        return False
    
    updated = 0
    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(DATA_DIR, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                dados = json.load(f)
            
            meta = dados.get('_metadata', {})
            card_id = meta.get('card_id') or int(dados.get('id', '0').replace('card_', '0'))
            
            if card_id and card_id in slugs:
                slug = slugs[card_id]
                curr_id = dados.get('id', '')
                target_id = slug
                
                if curr_id != target_id or meta.get('slug') != slug:
                    if dry_run:
                        print(f'  [DRY-RUN] {fname}: id "{curr_id}" -> "{target_id}", slug="{slug}"')
                    else:
                        dados['id'] = target_id
                        if 'slug' not in dados.get('_metadata', {}):
                            if '_metadata' not in dados:
                                dados['_metadata'] = {}
                        dados['_metadata']['slug'] = slug
                        dados['_metadata']['card_id'] = card_id
                        with open(fpath, 'w', encoding='utf-8') as f:
                            json.dump(dados, f, indent=2, ensure_ascii=False)
                            f.write('\n')
                    updated += 1
            else:
                print(f'  ⚠️  {fname}: card_id={card_id} nao encontrado no banco')
                
        except Exception as e:
            print(f'  ❌ {fname}: erro ao processar: {e}')
    
    if not dry_run:
        print(f'✅ {updated} JSONs atualizados com slug.')
    else:
        print(f'  {updated} JSONs seriam atualizados.')
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Gerar slugs para cartas')
    parser.add_argument('--json', action='store_true', help='Atualizar JSONs tambem')
    parser.add_argument('--dry-run', action='store_true', help='Preview sem alterar')
    args = parser.parse_args()
    
    print('=== Gerador de Slugs para Cartas ===')
    
    # Conecta ao banco
    if not os.path.exists(DB_PATH):
        print(f'ERRO: banco {DB_PATH} nao encontrado.')
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    
    # Backfill slugs no banco
    if backfill_db(conn, dry_run=args.dry_run):
        if args.json:
            update_jsons(conn, dry_run=args.dry_run)
    
    conn.close()
    print('=== Concluido ===')


if __name__ == '__main__':
    main()
