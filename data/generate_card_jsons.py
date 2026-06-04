#!/usr/bin/env python3
"""Gera arquivos JSON de efeitos para cartas de decks do banco.

Uso:
    python3 data/generate_card_jsons.py 7 90
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.deck import Deck, deck_cards
from rage_web.models.card import Card as CardModel

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'cards')


def gerar_json_carta(card: CardModel) -> dict:
    """Gera JSON de efeitos basico para uma carta do banco.

    O JSON gerado e um template inicial. Cada carta precisa
    ser revisada manualmente para preencher os modos e efeitos
    corretos de acordo com o texto da carta.
    """
    tipo_efeito = _mapear_tipo_para_efeito(card.tipo)
    
    return {
        'id': f'card_{card.id}',
        'nome': card.name,
        'tipo': card.tipo,
        'custo_acoes': 1,
        'modos': [
            {
                'descricao': f'Usar {card.name}',
                'efeitos': [
                    {
                        'tipo': tipo_efeito,
                        'condicao_alvo': 'qualquer_alvo',
                    }
                ],
            }
        ],
        '_metadata': {
            'fonte': 'gerado automaticamente',
            'card_id': card.id,
            'texto_original': card.text,
            'keywords': card.keyword,
            'damage': card.damage,
            'rage': card.rage,
            'gnosis': card.gnosis,
            'health': card.health,
            'precisa_revisao': True,
        }
    }


def _mapear_tipo_para_efeito(tipo: str) -> str:
    """Mapeia tipo de carta para tipo de efeito padrao."""
    mapping = {
        'Combat Action': 'dano',
        'Combat Event': 'dano',
        'Event': 'dano',
        'Gift': 'dano',
        'Equipment': 'modificar_rage',
        'Ally': 'dano',
        'Victim': 'dano',
        'Enemy': 'dano',
        'Action': 'dano',
        'Territory': 'dano',
        'Quest': 'dano',
        'Battlefield': 'dano',
        'Rite': 'dano',
        'Moot': 'dano',
    }
    return mapping.get(tipo, 'dano')


def gerar_jsons_do_deck(deck_id: int):
    """Gera arquivos JSON para todas as cartas de um deck."""
    flask_app = create_app()
    cartas_geradas = 0
    
    with flask_app.app_context():
        d = db.session.get(Deck, deck_id)
        if not d:
            print(f'Erro: Deck {deck_id} nao encontrado')
            return cartas_geradas
        
        print(f'\n=== Gerando JSONs para deck {deck_id}: {d.name} ===')
        
        stmt = db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
        rows = db.session.execute(stmt).fetchall()
        
        for row in rows:
            card = db.session.get(CardModel, row.card_id)
            if not card:
                continue
            
            # Gera o JSON da carta
            dados = gerar_json_carta(card)
            fname = f'deck{deck_id}_{card.id}_{_slug(card.name)}.json'
            path = os.path.join(OUTPUT_DIR, fname)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
            
            print(f'  Criado: {fname}')
            cartas_geradas += 1
    
    return cartas_geradas


def _slug(nome: str) -> str:
    """Converte nome para slug basico."""
    return (nome.lower()
            .replace(' ', '_')
            .replace("'", '')
            .replace('-', '_')
            .replace(':', '')
            .replace('(', '')
            .replace(')', '')
            .replace('/', '_')
            [:40])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    deck_ids = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else [7, 90]
    
    total = 0
    for did in deck_ids:
        total += gerar_jsons_do_deck(did)
    
    print(f'\nTotal: {total} JSONs gerados em {OUTPUT_DIR}/')


if __name__ == '__main__':
    main()
