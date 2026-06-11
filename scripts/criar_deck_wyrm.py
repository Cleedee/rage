#!/usr/bin/env python3
"""Cria deck Wyrm — Pentex First Team #21."""

import glob, json, os, sys
import_path = os.path.join(os.path.dirname(__file__), '..')
if import_path not in sys.path: sys.path.insert(0, import_path)
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

DECK = {
    "name": "Wyrm — Primeiro Esquadrão #21",
    "description": "Pentex First Team #21 Renown 20. Esquadrão corporativo Wyrm especializado em operações de eliminação. Cartas 100% inéditas.",
    "renown_cap": 20,
    "cards": [
        # Characters — Pentex First Team #21 (sinergia total)
        (229, 1),   # Ragnor the Terror — Ren3, pack with Team #21
        (17, 1),    # Corinna — Ren4, pack with Team #21
        (270, 1),   # Sybil — Ren5, pack with Team #21
        (329, 1),   # T. F. MacNeil — Ren8, leader, pack ALL Team #21
        
        # Equipment
        (644, 2),   # Experimental Cybernetics — +2 Rage, can't be stolen
        (626, 2),   # Bureaucratic Blueprints — discard to cancel board meeting
        
        # Gifts
        (108, 2),   # Devoted Servant — can't be removed from play
        (942, 2),   # Call of the Wyrm — attract Wyrm minions
        
        # Combat Actions
        (296, 2),   # Cleft in Twain — weapon required, can't be dodged
        (292, 2),   # Broken Limb — -2 Rage for combat (já tem JSON)
        
        # Combat Events
        (1285, 2),  # No Escape — attacker can't withdraw
        
        # Events
        (219, 2),   # Wyrm Taint — Glass Walkers lose renown
        (833, 2),   # Corporate Take-over — Pentex discard equipment
        (838, 2),   # Dragon — more Wyrm than Gaia advantage
        (917, 2),   # Town Meeting — Board Meeting with 1 Wyrm
        (836, 2),   # Defiler — take a caern
    ],
}

JSON_TEMPLATES = {
    # == Characters ==
    229: {  # Ragnor the Terror
        "id": "ragnor-the-terror",
        "nome": "Ragnor the Terror",
        "tipo": "Character - Wyrm (Pentex)",
        "modos": [{
            "descricao": "Pack attack/defend com First Team #21",
            "efeitos": [{
                "tipo": "registrar_trigger_combate",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "trigger": "pack_action",
                    "filtro": "keyword=First Team #21"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 229,
            "texto_original": "Ragnor is a member of Pentex First Team #21. He can pack attack or defend with any other member of Team #21 in his pack.",
            "precisa_revisao": True,
            "slug": "ragnor-the-terror"
        }
    },
    17: {  # Corinna
        "id": "corinna",
        "nome": "Corinna",
        "tipo": "Character - Wyrm (Pentex)",
        "modos": [{
            "descricao": "Pack attack/defend com First Team #21",
            "efeitos": [{
                "tipo": "registrar_trigger_combate",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "trigger": "pack_action",
                    "filtro": "keyword=First Team #21"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 17,
            "texto_original": "A member of Pentex First Team #21, Corinna can pack attack or defend with any other members of this team in her pack.",
            "precisa_revisao": True,
            "slug": "corinna"
        }
    },
    270: {  # Sybil
        "id": "sybil",
        "nome": "Sybil",
        "tipo": "Character - Wyrm (Pentex)",
        "modos": [{
            "descricao": "Pack attack/defend com First Team #21",
            "efeitos": [{
                "tipo": "registrar_trigger_combate",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "trigger": "pack_action",
                    "filtro": "keyword=First Team #21"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 270,
            "texto_original": "Sybil can pack attack or defend with any other member of First Team #21 in her pack.",
            "precisa_revisao": True,
            "slug": "sybil"
        }
    },
    329: {  # T. F. MacNeil
        "id": "tf-macneil",
        "nome": "T. F. MacNeil",
        "tipo": "Character - Wyrm (Pentex)",
        "modos": [{
            "descricao": "Pack attack/defend com TODOS Team #21",
            "efeitos": [{
                "tipo": "registrar_trigger_combate",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "trigger": "pack_action",
                    "filtro": "keyword=First Team #21",
                    "incluir_todos": True
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 329,
            "texto_original": "The Leader of First Team #21. He can pack attack or defend with any and all other Team #21 members in his pack.",
            "precisa_revisao": True,
            "slug": "tf-macneil"
        }
    },
    
    # == Equipment ==
    644: {
        "id": "experimental-cybernetics",
        "nome": "Experimental Cybernetics",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "+2 Rage, não pode ser roubado",
            "efeitos": [{
                "tipo": "equipar",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "boni": {"rage": 2},
                    "anti_roubo": True,
                    "filtro": "tipo=Wyrm|Glass Walker"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 644,
            "texto_original": "Only equippable by Wyrm creatures and Glass Walkers. The equipped character gains 2 Rage and the Equipment cannot be stolen.",
            "precisa_revisao": True,
            "slug": "experimental-cybernetics"
        }
    },
    626: {
        "id": "bureaucratic-blueprints",
        "nome": "Bureaucratic Blueprints",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "Descartar para cancelar Board Meeting",
            "efeitos": [{
                "tipo": "anular",
                "condicao_alvo": "jogador_inimigo",
                "quantidade": 1,
                "params": {
                    "filtro": "board_meeting",
                    "auto_descarte": True
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 626,
            "texto_original": "Discard to cancel a Board Meeting being called by a Pentex Alpha.",
            "precisa_revisao": True,
            "slug": "bureaucratic-blueprints"
        }
    },
    
    # == Gifts ==
    108: {
        "id": "devoted-servant",
        "nome": "Devoted Servant",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Não pode ser removido do jogo",
            "efeitos": [{
                "tipo": "impedir_acoes",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "tipo_impedido": "remocao_jogo"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 108,
            "texto_original": "The Wyrm has noticed the Gift user's devotion and his pack. He cannot be removed from play.",
            "precisa_revisao": True,
            "slug": "devoted-servant"
        }
    },
    942: {
        "id": "call-of-the-wyrm",
        "nome": "Call of the Wyrm",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Atrair seguidores Wyrm",
            "efeitos": [{
                "tipo": "ataque_imediato",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 3,
                "params": {
                    "filtro": "tipo=Wyrm",
                    "atrair_minions": True
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 942,
            "texto_original": "The Gift user emits an unholy shout that attracts minions of the Wyrm. Wyrm pack alphas must attack the Gift user or another Wyrm character.",
            "precisa_revisao": True,
            "slug": "call-of-the-wyrm"
        }
    },
    
    # == Combat Actions ==
    296: {
        "id": "cleft-in-twain",
        "nome": "Cleft in Twain",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Ataque com arma, não pode ser esquivado",
            "efeitos": [{
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 3,
                "params": {
                    "requer_arma": True,
                    "ignora_esquiva": True
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 296,
            "texto_original": "The character cleaving his opponent in twain must have a weapon. This Combat Action may not be dodged.",
            "precisa_revisao": True,
            "slug": "cleft-in-twain"
        }
    },
    
    # == Combat Events ==
    1285: {
        "id": "no-escape",
        "nome": "No Escape",
        "tipo": "Combat Event",
        "modos": [{
            "descricao": "Atacante não pode sair do combate",
            "efeitos": [{
                "tipo": "impedir_retirada",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 2
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 1285,
            "texto_original": "Play when attacker announces that he will not continue combat. Your defending Garou has trapped him.",
            "precisa_revisao": True,
            "slug": "no-escape"
        }
    },
    
    # == Events ==
    219: {
        "id": "wyrm-taint-event",
        "nome": "Wyrm Taint",
        "tipo": "Event",
        "modos": [{
            "descricao": "Glass Walkers perdem Renome",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "jogador_inimigo",
                "params": {
                    "atributos": ["renown"],
                    "valor": -2,
                    "duracao": "ate_fim_turno",
                    "filtro": "tipo=Glass Walker"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 219,
            "texto_original": "Evidence surfaces implicating the Glass Walkers tribe in dealings with the Wyrm. All Glass Walkers lose 2 Renown.",
            "precisa_revisao": True,
            "slug": "wyrm-taint-event"
        }
    },
    833: {
        "id": "corporate-takeover",
        "nome": "Corporate Take-over",
        "tipo": "Event",
        "modos": [{
            "descricao": "Pentex descarta equipamento",
            "efeitos": [{
                "tipo": "descarte",
                "condicao_alvo": "jogador_inimigo",
                "quantidade": 1,
                "params": {
                    "filtro": "equipment",
                    "alvo": "pentex_characters"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 833,
            "texto_original": "Each Pentex character in play must discard 1 piece of Equipment.",
            "precisa_revisao": True,
            "slug": "corporate-takeover"
        }
    },
    838: {
        "id": "dragon-event",
        "nome": "Dragon",
        "tipo": "Event",
        "modos": [{
            "descricao": "Mais Wyrm que Gaia = vantagem",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "atributos": ["rage"],
                    "valor": 2,
                    "duracao": "ate_fim_turno",
                    "condicao": "mais_wyrm_que_gaia"
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 838,
            "texto_original": "If there are more Wyrm characters in play than Gaia characters, the Dragon allows packs which contain more Wyrm than Gaia to pack attack.",
            "precisa_revisao": True,
            "slug": "dragon-event"
        }
    },
    917: {
        "id": "town-meeting",
        "nome": "Town Meeting",
        "tipo": "Event",
        "modos": [{
            "descricao": "Board Meeting com 1 Wyrm",
            "efeitos": [{
                "tipo": "moot_restricao_global",
                "condicao_alvo": "jogador_aliado",
                "params": {
                    "board_meeting_min_wyrm": 1
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 917,
            "texto_original": "Play during the Moot phase. Wyrm packs may call Board Meetings even if there is only one Wyrm creature in their pack.",
            "precisa_revisao": True,
            "slug": "town-meeting"
        }
    },
    836: {
        "id": "defiler-event",
        "nome": "Defiler",
        "tipo": "Event",
        "modos": [{
            "descricao": "Tomar um caern",
            "efeitos": [{
                "tipo": "mover_para",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 1,
                "params": {
                    "filtro": "caern",
                    "origem": "inimigo",
                    "destino": "aliado",
                    "descarte_carta": True
                }
            }]
        }],
        "_metadata": {
            "fonte": "novo_deck_wyrm",
            "card_id": 836,
            "texto_original": "You may discard the Defiler to take any 1 caern in play and make it your own. Ignore the territory requirements.",
            "precisa_revisao": True,
            "slug": "defiler-event"
        }
    },
}

# ===================================================================

def criar_json(card_id):
    json_path = f'data/cards/auto_deckwyrm_{card_id}.json'
    if os.path.exists(json_path):
        print(f'  JSON já existe: {json_path}')
        return
    template = JSON_TEMPLATES.get(card_id)
    if not template:
        print(f'  [AVISO] Sem template para card_id={card_id}')
        return
    with open(json_path, 'w') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f'  JSON criado: {json_path}')

def criar_deck():
    from rage_web.ext.database import db
    from rage_web.models.deck import Deck
    from rage_web.models.card import Card
    import rage_web.ext.repository as rep
    with app.app_context():
        existing = Deck.query.filter_by(name=DECK['name']).first()
        if existing:
            print(f'Deck já existe: [{existing.id}] {existing.name}')
            return existing.id
        deck = Deck()
        deck.name = DECK['name']
        deck.description = DECK['description']
        deck.renown_cap = DECK['renown_cap']
        db.session.add(deck)
        db.session.flush()
        total_ren = 0
        for cid, qty in DECK['cards']:
            card = Card.query.get(cid)
            if not card:
                print(f'  [ERRO] Carta {cid} não encontrada!')
                continue
            rep.deck_add_card(deck, card, qty)
            total_ren += (card.renown or 0) * qty
        print(f'  Deck ID: {deck.id}')
        print(f'  Nome: {deck.name}')
        print(f'  Renown: {total_ren}/{deck.renown_cap}')
        print(f'  Cartas: {sum(q for _, q in DECK["cards"])} (únicas: {len(DECK["cards"])})')
        for cid, qty in DECK['cards']:
            c = Card.query.get(cid)
            if c: print(f'    {qty}x [{c.id}] {c.name} ({c.tipo})')
        return deck.id

def rodar_checklist(deck_id):
    cmd = f'python3 scripts/gerar_checklist.py {deck_id}'
    os.system(cmd)

if __name__ == '__main__':
    print('=== WYRM — PRIMEIRO ESQUADRÃO #21 ===')
    print('--- Gerando JSONs ---')
    for cid, _ in DECK['cards']:
        criar_json(cid)
    print()
    print('--- Criando deck ---')
    deck_id = criar_deck()
    if deck_id: rodar_checklist(deck_id)
    print()
    print('=== PRONTO! ===')
