#!/usr/bin/env python3
"""Cria deck Bastet (werecats) Renown 20 com cartas inéditas + JSONs de efeito."""

import glob
import json
import os
import sys

import_path = os.path.join(os.path.dirname(__file__), '..')
if import_path not in sys.path:
    sys.path.insert(0, import_path)

os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

# -------------------------------------------------------------------
# Cartas selecionadas
# -------------------------------------------------------------------

CHARACTERS = [
    # (card_id, quantity)
    (44, 1),    # Black Claw — Ren10 Bastet leader
    (1391, 1),  # Treerose — Ren3 alpha support
    (1396, 1),  # Zari — Ren3 quest VP bonus
    (1386, 1),  # Mapute — Ren1 Bastet pack buffer
    (1398, 1),  # Blood-of-Witches — Ren2 ally recruiter
    (1397, 1),  # Tongue-Biter — Ren1 Bastet voting manip
]

# Support cards from the unused pool, picked for Bastet theme
# Equipment/Gifts/Events that we'll create JSONs for
SUPPORT = [
    # Equipment
    (273, 1),   # Flamethrower — weapon, play combat actions at +2 rage
    (613, 1),   # Bane Arrow — weapon, discard for 3 damage to enemy
    (302, 1),   # Flower of Aphrodite — prevents attacks until owner attacks
    
    # Gifts
    (1025, 2),  # Razor Claws — +2 damage on next claw attack
    (1044, 2),  # Second Sight — can step sideways
    (1074, 1),  # Toxic Claws — +1 aggravated on claw
    (1093, 2),  # Feral Grin — remove opponent from combat for 1 round
    
    # Combat Actions
    (291, 2),   # Body Slam — +2 damage if no action last round
    (322, 2),   # Fetal Position — blocks 1 attack of damage 6 or less
    (326, 2),   # Forceful Wind — kailindo, ends combat after damage
    
    # Combat Events
    (294, 2),   # Bum Rush — packmates can attack before combat actions
    
    # Events
    (856, 2),   # Gaia's Breath — heal all damage to a character
    (908, 2),   # Spiritual Revelation — draw cards based on gnosis
]

# -------------------------------------------------------------------
# JSON templates for each card
# -------------------------------------------------------------------

JSON_TEMPLATES = {
    # --- Characters ---
    44: {  # Black Claw — double gnosis for gifts as alpha action
        "id": "black-claw",
        "nome": "Black Claw",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Dobrar Gnosis para Gifts (ação alpha)",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["gnosis"],
                            "valor": None,
                            "duracao": "ate_fim_turno"
                        }
                    }
                ],
                "condicao_uso": "alpha_action"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 44,
            "texto_original": "Black Claw is practised in many mystical Rites. As his alpha action he may double his Gnosis for the purposes of using Gifts.",
            "precisa_revisao": True,
            "slug": "black-claw"
        }
    },
    1386: {  # Mapute — Bastet packmates +2 rage, can pack attack
        "id": "mapute",
        "nome": "Mapute",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Bastet no pack +2 Rage e pack attack",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["rage"],
                            "valor": 2,
                            "filtro": "tipo=Bastet"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1386,
            "texto_original": "Mapute petitioned his tribe to form a war party. Bastet in his pack have +2 Rage and may pack attack with anyone.",
            "precisa_revisao": True,
            "slug": "mapute"
        }
    },
    1391: {  # Treerose — target reveals alpha attack
        "id": "treerose",
        "nome": "Treerose",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Forçar revelação de alpha alheio",
                "efeitos": [
                    {
                        "tipo": "forcar_bluff",
                        "condicao_alvo": "jogador_inimigo",
                        "quantidade": 1
                    }
                ],
                "condicao_uso": "antes_combate"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1391,
            "texto_original": "If another Bastet is your Alpha, target a player. The target must state whom his Alpha will attack during that Combat Phase.",
            "precisa_revisao": True,
            "slug": "treerose"
        }
    },
    1396: {  # Zari — quests worth +1 VP
        "id": "zari",
        "nome": "Zari",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Quests +1 VP",
                "efeitos": [
                    {
                        "tipo": "quest_check",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "valor_extra": 1
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1396,
            "texto_original": "Quests played on Zari are worth +1 VP when placed in your Victory Pile. Loyalty: Bastet.",
            "precisa_revisao": True,
            "slug": "zari"
        }
    },
    1398: {  # Blood-of-Witches — recruit Uktena allies
        "id": "blood-of-witches",
        "nome": "Blood-of-Witches",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Recrutar aliados Uktena",
                "efeitos": [
                    {
                        "tipo": "buscar_copias",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "filtro": "tipo=Ally&keyword=Uktena"
                        }
                    }
                ],
                "condicao_uso": "uma_vez_por_turno"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1398,
            "texto_original": "Blood-of-Witches may recruit allies with Uktena prerequisites. Rivalry: Black Spiral Dancers.",
            "precisa_revisao": True,
            "slug": "blood-of-witches"
        }
    },
    1397: {  # Tongue-Biter — Bastet lose 2 renown for voting
        "id": "tongue-biter",
        "nome": "Tongue-Biter",
        "tipo": "Character - Bastet",
        "modos": [
            {
                "descricao": "Bastet perde 2 Renome para votação",
                "efeitos": [
                    {
                        "tipo": "moot_restricao_global",
                        "condicao_alvo": "jogador_inimigo",
                        "params": {
                            "filtro": "tipo=Bastet",
                            "penalidade_renown": 2
                        }
                    }
                ],
                "condicao_uso": "uma_vez_por_turno"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1397,
            "texto_original": "Once per turn, Tongue-Biter can cause a Bastet to lose 2 Renown for voting purposes.",
            "precisa_revisao": True,
            "slug": "tongue-biter"
        }
    },

    # --- Equipment ---
    273: {
        "id": "flamethrower",
        "nome": "Flamethrower",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Usar Flamethrower",
                "efeitos": [
                    {
                        "tipo": "equipar",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "boni": {"rage": 2},
                            "allow_combat_actions": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 273,
            "texto_original": "Weapon. While equipped with the Flamethrower, the user may play Combat Actions at +2 Rage.",
            "precisa_revisao": True,
            "slug": "flamethrower"
        }
    },
    613: {
        "id": "bane-arrow",
        "nome": "Bane Arrow",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Descartar para 3 de dano em Enemy",
                "efeitos": [
                    {
                        "tipo": "dano",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 3,
                        "params": {
                            "filtro": "tipo=Enemy",
                            "auto_descarte": True
                        }
                    }
                ],
                "condicao_uso": "during_withdrawal"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 613,
            "texto_original": "Weapon. During the Withdrawal step the owner of the Bane Arrow may discard Bane Arrow to do 3 damage to an Enemy she is fighting.",
            "precisa_revisao": True,
            "slug": "bane-arrow"
        }
    },
    302: {
        "id": "flower-of-aprhodite",
        "nome": "Flower of Aphrodite",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Protege de ataques",
                "efeitos": [
                    {
                        "tipo": "impedir_acoes",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "tipo_impedido": "ataques_desafios"
                        }
                    }
                ],
                "condicao_uso": "enquanto_nao_atacar"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 302,
            "texto_original": "No one may challenge or attack the owner of this fetish. The Flower of Aphrodite is discarded the moment its owner attacks.",
            "precisa_revisao": True,
            "slug": "flower-of-aprhodite"
        }
    },

    # --- Gifts ---
    1025: {
        "id": "razor-claws",
        "nome": "Razor Claws",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "+2 dano no próximo ataque de garra",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["dano_proximo_ataque"],
                            "valor": 2,
                            "duracao": "proximo_ataque"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1025,
            "texto_original": "The character's next claw attack that connects does +2 damage.",
            "precisa_revisao": True,
            "slug": "razor-claws"
        }
    },
    1044: {
        "id": "second-sight",
        "nome": "Second Sight",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Step sideways",
                "efeitos": [
                    {
                        "tipo": "fugir",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 1
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1044,
            "texto_original": "This user can step sideways.",
            "precisa_revisao": True,
            "slug": "second-sight"
        }
    },
    1074: {
        "id": "toxic-claws",
        "nome": "Toxic Claws",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Próximo ataque de garra +1 dano agravado",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["dano_proximo_ataque"],
                            "valor": 1,
                            "agravado": True,
                            "duracao": "proximo_ataque"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1074,
            "texto_original": "The character's next claw attack that damages an opponent does +1 aggravated damage.",
            "precisa_revisao": True,
            "slug": "toxic-claws"
        }
    },
    1093: {
        "id": "feral-grin",
        "nome": "Feral Grin",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Remover oponente do combate por 1 round",
                "efeitos": [
                    {
                        "tipo": "remover_do_combate",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 1
                    }
                ],
                "condicao_uso": "antes_revelar"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 1093,
            "texto_original": "Play on an opponent in combat with less Rage than the Gift user. The target is removed from play for one round of combat.",
            "precisa_revisao": True,
            "slug": "feral-grin"
        }
    },

    # --- Combat Actions ---
    291: {
        "id": "body-slam",
        "nome": "Body Slam",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "Body Slam (+2 se sem ação no round anterior)",
                "efeitos": [
                    {
                        "tipo": "dano",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 2,
                        "params": {
                            "bônus_sem_acao_anterior": 2
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 291,
            "texto_original": "If the creature playing Body Slam did not play a combat action last round, Body Slam does +2 damage.",
            "precisa_revisao": True,
            "slug": "body-slam"
        }
    },
    322: {
        "id": "fetal-position",
        "nome": "Fetal Position",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "Bloqueia 1 ataque de dano 6 ou menos",
                "efeitos": [
                    {
                        "tipo": "anular",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 1,
                        "params": {
                            "filtro_dano_max": 6
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 322,
            "texto_original": "This action blocks 1 attack of damage 6 or less.",
            "precisa_revisao": True,
            "slug": "fetal-position"
        }
    },
    326: {
        "id": "forceful-wind",
        "nome": "Forceful Wind",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "Kailindo: combate termina após dano",
                "efeitos": [
                    {
                        "tipo": "combar_acao",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 2
                    }
                ],
                "params": {"kailindo": True}
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 326,
            "texto_original": "Kailindo. Combat immediately ends after both sides have dealt damage.",
            "precisa_revisao": True,
            "slug": "forceful-wind"
        }
    },

    # --- Combat Events ---
    294: {
        "id": "bum-rush",
        "nome": "Bum Rush",
        "tipo": "Combat Event",
        "modos": [
            {
                "descricao": "Packmates atacam antes das ações de combate",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 3,
                        "params": {"antes_acoes": True}
                    }
                ],
                "condicao_uso": "inicio_round_combate"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 294,
            "texto_original": "Play at the beginning of any combat round before combat action cards are exchanged. Each member of character's pack may make a single attack.",
            "precisa_revisao": True,
            "slug": "bum-rush"
        }
    },

    # --- Events ---
    856: {
        "id": "gaias-breath",
        "nome": "Gaia's Breath",
        "tipo": "Event",
        "modos": [
            {
                "descricao": "Curar todo dano de um personagem",
                "efeitos": [
                    {
                        "tipo": "curar",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 99  # all damage
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 856,
            "texto_original": "Heal all damage to a single character.",
            "slug": "gaias-breath"
        }
    },
    908: {
        "id": "spiritual-revelation",
        "nome": "Spiritual Revelation",
        "tipo": "Event",
        "modos": [
            {
                "descricao": "Comprar cartas igual ao Gnosis",
                "efeitos": [
                    {
                        "tipo": "comprar",
                        "condicao_alvo": "jogador_aliado",
                        "quantidade": None,  # = gnosis of target
                        "params": {"valor_equal_gnosis": True}
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_bastet",
            "card_id": 908,
            "texto_original": "Draw a number of sept cards equal to your character's Gnosis.",
            "slug": "spiritual-revelation"
        }
    },
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def criar_json(card_id: int):
    """Cria arquivo JSON para uma carta, se não existir."""
    json_path = f'data/cards/auto_deckbastet_{card_id}.json'
    if os.path.exists(json_path):
        print(f'  JSON já existe: {json_path}')
        return
    
    template = JSON_TEMPLATES.get(card_id)
    if not template:
        print(f'  [AVISO] Sem template JSON para card_id={card_id}')
        return
    
    with open(json_path, 'w') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f'  JSON criado: {json_path}')


def criar_deck():
    with app.app_context():
        from rage_web.ext.database import db
        from rage_web.models.deck import Deck
        from rage_web.models.card import Card
        import rage_web.ext.repository as rep
        
        # Verifica se deck já existe
        existing = Deck.query.filter_by(name="Bastet — Garras da Noite").first()
        if existing:
            print(f'Deck já existe: [{existing.id}] {existing.name}')
            return existing.id
        
        # Cria o deck
        deck = Deck()
        deck.name = "Bastet — Garras da Noite"
        deck.description = "Bastet (werecats) Renown 20. Foco em garras, pack attacks e manipulação de votação. Cartas 100% inéditas."
        deck.renown_cap = 20
        db.session.add(deck)
        db.session.flush()
        
        total_renown = 0
        
        # Adiciona personagens
        for cid, qty in CHARACTERS:
            card = Card.query.get(cid)
            if not card:
                print(f'  [ERRO] Carta {cid} não encontrada!')
                continue
            rep.deck_add_card(deck, card, qty)
            total_renown += (card.renown or 0) * qty
        
        # Adiciona suporte
        for cid, qty in SUPPORT:
            card = Card.query.get(cid)
            if not card:
                print(f'  [ERRO] Carta {cid} não encontrada!')
                continue
            rep.deck_add_card(deck, card, qty)
        
        print(f'=== DECK CRIADO ===')
        print(f'ID: {deck.id}')
        print(f'Nome: {deck.name}')
        print(f'Renown total: {total_renown}/{deck.renown_cap}')
        
        # Mostra cartas
        cards = rep.deck_get_cards(deck)
        for entry in sorted(cards, key=lambda x: x['card'].name):
            c = entry['card']
            print(f'  {entry["quantity"]}x [{c.id}] {c.name} ({c.tipo})')
        
        return deck.id


def gerar_jsons():
    """Cria JSONs para todas as cartas do deck que não têm."""
    all_ids = [cid for cid, _ in CHARACTERS] + [cid for cid, _ in SUPPORT]
    for cid in sorted(set(all_ids)):
        criar_json(cid)


def rodar_checklist(deck_id):
    """Roda o checklist no deck."""
    print()
    print('=== CHECKLIST ===')
    cmd = f'python3 scripts/gerar_checklist.py {deck_id}'
    os.system(cmd)


if __name__ == '__main__':
    print('=== CRIANDO DECK BASTET ===')
    print()
    
    # 1. Cria JSONs
    print('--- Gerando JSONs de efeito ---')
    gerar_jsons()
    print()
    
    # 2. Cria o deck no banco
    print('--- Criando deck no banco ---')
    deck_id = criar_deck()
    print()
    
    if deck_id:
        # 3. Roda checklist
        rodar_checklist(deck_id)
