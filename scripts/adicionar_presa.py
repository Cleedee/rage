#!/usr/bin/env python3
"""Adiciona Presa (Enemies/Victims) aos 4 decks e testa partidas."""

import json, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

# Gaia decks (Bastet, Ajaba, Kitsune) levam ENEMIES — dão VP cheio para Gaia
# Wyrm deck leva VICTIMS — dão VP cheio para Wyrm
PREY_FOR_DECK = {
    1043: [  # Bastet (Gaia) -> Enemy
        (454, 2, 'Bane Morphling', 'Enemy'),    # Ren6 H7
        (468, 2, 'Drattosi', 'Enemy'),           # Ren7 H5
        (471, 2, 'Elder Vampire', 'Enemy'),      # Ren9 H9
    ],
    1044: [  # Ajaba (Gaia) -> Enemy
        (450, 2, 'Anaconda Gafflings', 'Enemy'), # Ren3 H2
        (452, 1, 'Arkady', 'Enemy'),             # Ren9 H8
        (470, 2, 'El Guapo', 'Enemy'),           # Ren5 H5
    ],
    1045: [  # Kitsune (Gaia) -> Enemy
        (463, 2, 'Corrupt Kinfolk', 'Enemy'),    # Ren3 H3
        (469, 2, 'Drunken Vandals', 'Enemy'),    # Ren4 H3
        (460, 2, 'Bunyip Spirit', 'Enemy'),      # Ren5 H4
    ],
    1049: [  # Wyrm -> Victim
        (462, 2, 'Cityboy Kinfolk', 'Victim'),   # Ren2 H3
        (456, 2, 'Beat Cop', 'Victim'),          # Ren3 H2
        (490, 1, 'Granola Pete', 'Victim'),      # Ren1 H1
        (481, 2, 'Family Pet', 'Victim'),        # Ren2 H2
    ],
}

def criar_jsons():
    prey_ids = set()
    for deck_id, prey_list in PREY_FOR_DECK.items():
        for cid, qty, name, ptype in prey_list:
            prey_ids.add(cid)
    
    template = {
        "id": "", "nome": "", "tipo": "",
        "modos": [{"descricao": "Presa para VP",
                    "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga"}]}],
        "_metadata": {}
    }
    
    for cid in sorted(prey_ids):
        fname = f'data/cards/auto_presa_{cid}.json'
        if not os.path.exists(fname):
            # Find card info
            from rage_web.models.card import Card
            with app.app_context():
                card = Card.query.get(cid)
                if card:
                    t = card.tipo or 'Prey'
                    n = card.name
                    template['id'] = f'prey_{cid}'
                    template['nome'] = n
                    template['tipo'] = t
                    template['_metadata'] = {
                        "fonte": "adicionar_presa", "card_id": cid,
                        "texto_original": (card.text or '')[:200],
                        "precisa_revisao": True, "slug": n.lower().replace(' ', '-')
                    }
                    with open(fname, 'w') as f:
                        json.dump(template, f, indent=2, ensure_ascii=False)
                    print(f'  JSON: {fname}')
        else:
            print(f'  JSON existe: {fname}')

def adicionar():
    from rage_web.ext.database import db
    from rage_web.models.deck import Deck
    from rage_web.models.card import Card
    import rage_web.ext.repository as rep
    
    for deck_id, prey_list in PREY_FOR_DECK.items():
        with app.app_context():
            deck = Deck.query.get(deck_id)
            if not deck:
                print(f'  Deck {deck_id} nao encontrado!')
                continue
            print(f'  [{deck.id}] {deck.name}:')
            for cid, qty, name, ptype in prey_list:
                card = Card.query.get(cid)
                if not card:
                    print(f'    Carta {cid} nao encontrada!')
                    continue
                rep.deck_add_card(deck, card, qty)
                print(f'    +{qty}x [{cid}] {name} ({ptype})')

def testar():
    from rage_web.game_engine.match import run_match
    
    matchups = [
        (1043, 1044, 42, 'Bastet vs Ajaba'),
        (1043, 1045, 43, 'Bastet vs Kitsune'),
        (1043, 1049, 44, 'Bastet vs Wyrm'),
        (1044, 1045, 45, 'Ajaba vs Kitsune'),
        (1044, 1049, 46, 'Ajaba vs Wyrm'),
        (1045, 1049, 47, 'Kitsune vs Wyrm'),
    ]
    
    print()
    header = '{:25s} {:5s} {:10s} {:6s}'.format('Matchup', 'VP', 'Result', 'Turnos')
    print(header)
    print('-' * 48)
    
    for d1, d2, seed, label in matchups:
        for vp_target in [12, 16, 20]:
            old = sys.stdout
            sys.stdout = io.StringIO()
            result = run_match(seed=seed, max_turns=30, difficulty_p1='medium',
                             difficulty_p2='medium', deck1_id=d1, deck2_id=d2,
                             delay=0.0, vp_to_win=vp_target)
            output = sys.stdout.getvalue()
            sys.stdout = old
            
            n_turns = sum(1 for l in output.split('\n') if 'Turno' in l and 'REDRAW' in l)
            print('{:25s} {:<5d} {:10s} {:<6d}'.format(label, vp_target, str(result), n_turns))

if __name__ == '__main__':
    print('=== ADICIONANDO PRESA AOS DECKS ===')
    print()
    print('--- JSONs ---')
    criar_jsons()
    print()
    print('--- Adicionando ---')
    adicionar()
    print()
    print('=== TESTANDO ===')
    testar()
