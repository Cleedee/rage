#!/usr/bin/env python3
"""
Aplica tags do arquivo data/card_tags.json ao banco de dados.

As tags são dados curados manualmente que NÃO foram importados
do LackeyCCG. Este script permite restaurá-las caso o banco seja
recriado.

Uso:
    cd /workspace && PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py

Flags:
    --dry-run  Apenas mostra o que seria alterado, sem modificar.
    --slug     Aplica tags de uma carta específica (ex: --slug frenar_r1).
"""

import os
import sys
import json

os.environ['FLASK_APP'] = 'rage_web'

TAG_FILE = 'data/card_tags.json'


def main():
    app = __import__('rage_web', fromlist=['create_app']).create_app()

    dry_run = '--dry-run' in sys.argv
    only_slug = None
    for i, arg in enumerate(sys.argv):
        if arg == '--slug' and i + 1 < len(sys.argv):
            only_slug = sys.argv[i + 1]

    with app.app_context():
        from rage_web.ext.database import db
        from rage_web.models.card import Card as CardModel

        if not os.path.exists(TAG_FILE):
            print(f'❌ Arquivo {TAG_FILE} não encontrado.')
            print('Execute primeiro: scripts/export_tags.py')
            sys.exit(1)

        with open(TAG_FILE, 'r') as f:
            tag_data = json.load(f)

        if only_slug:
            tag_data = [t for t in tag_data if t['slug'] == only_slug]
            if not tag_data:
                print(f'❌ Slug \"{only_slug}\" não encontrado em {TAG_FILE}')
                sys.exit(1)

        applied = 0
        skipped = 0
        not_found = 0

        for entry in tag_data:
            slug = entry.get('slug', '')
            card_id = entry.get('id')
            expected_tags = entry.get('tags', '')

            # Busca por slug primeiro, depois por id
            card = CardModel.query.filter_by(slug=slug).first()
            if not card and card_id:
                card = CardModel.query.get(card_id)

            if not card:
                not_found += 1
                if only_slug:
                    print(f'  ⚠️  Carta não encontrada no banco: slug={slug} id={card_id}')
                continue

            if card.tags == expected_tags:
                skipped += 1
                continue

            if dry_run:
                print(f'  📝 [{card.id}] {card.name}')
                print(f'       Antes: \"{card.tags}\"')
                print(f'       Depois: \"{expected_tags}\"')
            else:
                card.tags = expected_tags
                applied += 1

        if not dry_run:
            db.session.commit()

        print()
        print(f'Resumo:')
        print(f'  Tags aplicadas: {applied}')
        print(f'  Já atualizadas: {skipped}')
        print(f'  Não encontradas: {not_found}')

        if only_slug:
            if dry_run:
                print(f'Modo --dry-run: nenhuma alteração feita.')


if __name__ == '__main__':
    main()
