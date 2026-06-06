"""CLI para o sistema de crafting automatizado de JSON.

Uso:
    python3 -m rage_web.helpers.auto_json.cli craft-card 1234
    python3 -m rage_web.helpers.auto_json.cli craft-deck 643
    python3 -m rage_web.helpers.auto_json.cli craft-all
    python3 -m rage_web.helpers.auto_json.cli craft-all --decks 643,619,629
    python3 -m rage_web.helpers.auto_json.cli status
"""

import sys
import argparse

from rage_web.helpers.auto_json import craft_card, craft_deck_cards, craft_all_missing


def cmd_status():
    """Mostra status das cartas com/sem JSON."""
    from rage_web.models.card import Card as CardModel
    from rage_web.ext.database import db
    from rage_web import create_app
    from rage_web.game_engine.effects import CARTAS_EXEMPLO

    app = create_app()
    with app.app_context():
        total = CardModel.query.count()
        com_json = len(CARTAS_EXEMPLO)
        sem_json = total - com_json

        print(f'Total de cartas no banco: {total}')
        print(f'Com JSON de efeitos:     {com_json}')
        print(f'Sem JSON de efeitos:     {sem_json}')
        print(f'Cobertura:               {com_json/total*100:.1f}%')

        # Por tipo
        from collections import Counter
        tipos = Counter()
        for c in CardModel.query.all():
            modelo_key = f'card_{c.id}'
            if modelo_key not in CARTAS_EXEMPLO:
                tipos[c.tipo or 'Unknown'] += 1
        print(f'\nTop tipos sem JSON:')
        for t, n in tipos.most_common(10):
            print(f'  {n:4d} x {t}')


def cmd_craft_card(args):
    """Gera JSON para uma carta específica."""
    modelo = craft_card(args.card_id, args.deck_id)
    if modelo is None:
        print(f'Carta {args.card_id}: já existe ou não encontrada')
    else:
        print(f'✅ Gerado JSON para "{modelo["nome"]}" (id={args.card_id})')


def cmd_craft_deck(args):
    """Gera JSONs para todas as cartas de um deck."""
    gerados = craft_deck_cards(args.deck_id)
    print(f'Gerados {len(gerados)} JSONs para deck {args.deck_id}')
    for m in gerados:
        print(f'  ✅ {m["nome"]} (id={m["_metadata"]["card_id"]})')


def cmd_craft_all(args):
    """Gera JSONs para cartas sem modelo (opcionalmente filtrando por decks)."""
    decks = args.decks.split(',') if args.decks else None
    if decks:
        decks = [int(d.strip()) for d in decks]
    total = craft_all_missing(decks)
    print(f'Gerados {total} JSONs no total')


def main():
    parser = argparse.ArgumentParser(description='Craft automatizado de JSONs de efeitos')
    sub = parser.add_subparsers(dest='command')

    p_status = sub.add_parser('status', help='Status das cartas')

    p_card = sub.add_parser('craft-card', help='Craft para uma carta')
    p_card.add_argument('card_id', type=int)
    p_card.add_argument('--deck-id', type=int, default=0)

    p_deck = sub.add_parser('craft-deck', help='Craft para um deck')
    p_deck.add_argument('deck_id', type=int)

    p_all = sub.add_parser('craft-all', help='Craft para todos os decks')
    p_all.add_argument('--decks', type=str, default=None,
                       help='IDs separados por vírgula')

    args = parser.parse_args()

    if args.command == 'status':
        cmd_status()
    elif args.command == 'craft-card':
        cmd_craft_card(args)
    elif args.command == 'craft-deck':
        cmd_craft_deck(args)
    elif args.command == 'craft-all':
        cmd_craft_all(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
