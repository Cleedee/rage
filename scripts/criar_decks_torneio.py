#!/usr/bin/env python3
"""Cria 2 decks para torneio: Ajaba (hienas) + Kitsune (raposas)."""

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

# ===================================================================
# DECK 2: AJABA — Hienas da Savana
# ===================================================================
# African werehyenas. Scavengers, bullies, pack hunters.
# Renown 20: Mtupeni(1) + Chuki(3) + Kisasi(6) + Shari(10) = 20

DECK2 = {
    "name": "Ajaba — Hienas da Savana",
    "description": "Ajaba (werehyenas) Renown 20. Batedores e caçadores em matilha. Tema africano, bullying tático, rivalidade com Bastet. Cartas 100% inéditas.",
    "renown_cap": 20,
    "cards": [
        # Characters
        (371, 1),    # Mtupeni — Ren1, +2 Rage vs Renown 1
        (364, 1),    # Chuki — Ren3, auto join pack defense
        (1443, 1),   # Kisasi — Ren6, loyalty to each other
        (1625, 1),   # Shari — Ren10, anti-Bastet
        
        # Equipment — simple, no JSON
        (621, 2),    # Bivouac — heal 1 extra in regen
        (632, 2),    # Concertina Wire — discard when alpha declares battle
        
        # Gifts
        (1046, 2),   # Sense Wyrm — reveal top 5 from sept deck
        (1025, 2),   # Razor Claws — +2 damage next claw
        
        # Combat Actions
        (292, 2),    # Broken Limb — -2 Rage for rest of combat if damaged
        (118, 2),    # Hamstringed — can't withdraw next round
        (316, 2),    # Evade and Strike — Kailindo dodge all attacks
        
        # Combat Events
        (1290, 2),   # Pack Defense — pull members from pack
        (1416, 2),   # Cub's Cry — loyal packmates join
        
        # Events
        (856, 2),    # Gaia's Breath — heal all damage (já tem JSON)
        (214, 2),    # Weasel — totem, agility in battle
    ],
}

# ===================================================================
# DECK 3: KITSUNE — Raposas da Fortuna
# ===================================================================
# Japanese werefoxes. Tricksters, mystics, luck-bringers.
# Renown 19: Mei-Fei(1) + Wu Bingshu(4) + Kim(5) + Katsuko(6) + Ozatu(3) = 19

DECK3 = {
    "name": "Kitsune — Raposas da Fortuna",
    "description": "Kitsune (werefoxes) Hengeyokai Renown 20. Místicos, ilusionistas e estrategistas. Tema asiático, foco em gnosis, votação e cartas de sept. Cartas 100% inéditas.",
    "renown_cap": 20,
    "cards": [
        # Characters
        (1676, 1),   # Mei-Fei Quan — Ren1, hengeyokai +1 Gnosis
        (1685, 1),   # Wu Bingshu — Ren4, extra votes from loyal
        (1716, 1),   # Kim — Ren5, start with Wyrm char
        (1687, 1),   # Katsuko Moon-Saint — Ren6, Philodox/CoG cards
        (1679, 1),   # Ozatu Junichiro — Ren3, discard instead of shuffle
        
        # Equipment
        (627, 2),    # Cellular Phone — pack attack/defend with anyone
        (660, 2),    # Lost Map — act as defending alpha for any battlefield
        (635, 2),    # Corporate Credit Card — equip at start of combat
        
        # Gifts
        (982, 2),    # Heightened Senses — refuse challenges, dodge outside combat
        (1044, 2),   # Second Sight — step sideways (já tem JSON)
        (995, 2),    # Leap of the Kangaroo — join any battlefield
        
        # Combat Actions
        (322, 2),    # Fetal Position — block 1 attack ≤6 (já tem JSON)
        (326, 2),    # Forceful Wind — Kailindo, ends combat (já tem JSON)
        
        # Combat Events
        (1298, 2),   # Reinforcements — add up to 10 Renown after round 3
        (1317, 2),   # Superior Tactics — choose 2 in battlefield
        
        # Events
        (908, 2),    # Spiritual Revelation — draw = gnosis (já tem JSON)
        (221, 2),    # Rewards of Leadership — search deck for Ally/Equipment
        (216, 2),    # Whippoorwill — recycle when Ally/Victim removed
    ],
}

# ===================================================================
# JSON TEMPLATES
# ===================================================================

JSON_TEMPLATES = {
    # ---- DECK 2: AJABA ----
    
    # Mtupeni — +2 Rage vs Renown 1 opponents
    371: {
        "id": "mtupeni",
        "nome": "Mtupeni",
        "tipo": "Character - Ajaba",
        "modos": [
            {
                "descricao": "+2 Rage contra Renome 1",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["rage"],
                            "valor": 2,
                            "condicao": "alvo_renown_1"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 371,
            "texto_original": "Mtupeni is a terrible bully and acts at +2 Rage if she is facing a creature in combat with Renown 1 or less.",
            "precisa_revisao": True,
            "slug": "mtupeni"
        }
    },
    
    # Chuki — auto join Ajaba pack defense
    364: {
        "id": "chuki",
        "nome": "Chuki",
        "tipo": "Character - Ajaba",
        "modos": [
            {
                "descricao": "Auto-defender pack Ajaba",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 1,
                        "params": {
                            "filtro": "tipo=Ajaba",
                            "auto_defesa": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 364,
            "texto_original": "Chuki is dedicated to defending its clan. Chuki may automatically join any Ajaba packmate in pack defense.",
            "precisa_revisao": True,
            "slug": "chuki"
        }
    },
    
    # Kisasi — loyalty between non-Ajaba and Ajaba
    1443: {
        "id": "kisasi",
        "nome": "Kisasi",
        "tipo": "Character - Ajaba",
        "modos": [
            {
                "descricao": "Lealdade entre Ajaba e não-Ajaba no pack",
                "efeitos": [
                    {
                        "tipo": "registrar_trigger_combate",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "trigger": "pack_inicio_jogo",
                            "efeito": "lealdade_mutua"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 1443,
            "texto_original": "If you start with Kisasi in play, Kisasi and non-Ajaba Characters in her pack gain Loyalty to each other.",
            "precisa_revisao": True,
            "slug": "kisasi"
        }
    },
    
    # Shari — anti-Bastet, Iksakku
    1625: {
        "id": "shari",
        "nome": "Shari",
        "tipo": "Character - Ajaba",
        "modos": [
            {
                "descricao": "Anti-Bastet em combate",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["rage", "gnosis"],
                            "valor": 2,
                            "condicao": "contra_bastet"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 1625,
            "texto_original": "Iksakku. Shari harbors great resentment towards the Bastet. When facing Bastet in combat, Shari acts at +2 Rage and +2 Gnosis.",
            "precisa_revisao": True,
            "slug": "shari"
        }
    },
    
    # Bivouac — heal 1 extra in regen
    621: {
        "id": "bivouac",
        "nome": "Bivouac",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Cura +1 na regeneração",
                "efeitos": [
                    {
                        "tipo": "equipar",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "boni": {"regen_extra": 1}
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 621,
            "texto_original": "The equipped character may heal 1 additional damage card per Regeneration Phase.",
            "precisa_revisao": True,
            "slug": "bivouac"
        }
    },
    
    # Concertina Wire — discard when alpha declares
    632: {
        "id": "concertina-wire",
        "nome": "Concertina Wire",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Descartar quando alpha declarar batalha",
                "efeitos": [
                    {
                        "tipo": "restringir",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 1,
                        "params": {
                            "filtro": "battlefield_ignore",
                            "auto_descarte": True
                        }
                    }
                ],
                "condicao_uso": "quando_alpha_declarar_batalha"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 632,
            "texto_original": "A character equipped with Concertina Wire may discard it when any alpha declares a Battlefield conflict, forcing that alpha to ignore one of your Battlefields.",
            "precisa_revisao": True,
            "slug": "concertina-wire"
        }
    },
    
    # Sense Wyrm — reveal top 5 of sept deck
    1046: {
        "id": "sense-wyrm-ajaba",
        "nome": "Sense Wyrm",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Revelar topo do deck Sept",
                "efeitos": [
                    {
                        "tipo": "olhar_topo_deck",
                        "condicao_alvo": "jogador_inimigo",
                        "quantidade": 5,
                        "params": {
                            "deck": "sept",
                            "colocar_enemies_em_jogo": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 1046,
            "texto_original": "Target a player; that player reveals the top five cards from his Sept deck. If any are Enemies, they are immediately placed into play.",
            "precisa_revisao": True,
            "slug": "sense-wyrm-ajaba"
        }
    },
    
    # Broken Limb — -2 Rage if damaged
    292: {
        "id": "broken-limb",
        "nome": "Broken Limb",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "-2 Rage para vítima",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo",
                        "condicao_alvo": "criatura_inimiga",
                        "params": {
                            "atributos": ["rage"],
                            "valor": -2,
                            "duracao": "ate_fim_combate",
                            "condicao": "se_dano_aplicado"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 292,
            "texto_original": "If damaged by this attack, the victim plays all of her Combat Actions at -2 Rage for the duration of the combat.",
            "precisa_revisao": True,
            "slug": "broken-limb"
        }
    },
    
    # Hamstringed — can't withdraw
    118: {
        "id": "hamstringed",
        "nome": "Hamstringed",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "Impedir retirada no próximo round",
                "efeitos": [
                    {
                        "tipo": "impedir_retirada",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 1
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 118,
            "texto_original": "Your opponent cannot withdraw or escape during the next round of combat.",
            "precisa_revisao": True,
            "slug": "hamstringed"
        }
    },
    
    # Evade and Strike — Kailindo dodge
    316: {
        "id": "evade-and-strike",
        "nome": "Evade and Strike",
        "tipo": "Combat Action",
        "modos": [
            {
                "descricao": "Esquivar de todos ataques + contra-atacar",
                "efeitos": [
                    {
                        "tipo": "dano",
                        "condicao_alvo": "criatura_inimiga",
                        "quantidade": 1,
                        "params": {
                            "kailindo": True,
                            "dodge_all": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 316,
            "texto_original": "Kailindo. You can dodge all attacks this round, except those that normally ignore dodges.",
            "precisa_revisao": True,
            "slug": "evade-and-strike"
        }
    },
    
    # Pack Defense — pull members
    1290: {
        "id": "pack-defense",
        "nome": "Pack Defense",
        "tipo": "Combat Event",
        "modos": [
            {
                "descricao": "Puxar membros do pack para defesa",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 3,
                        "params": {"pack_defense": True}
                    }
                ],
                "condicao_uso": "antes_combate_defesa"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 1290,
            "texto_original": "Play before one of your defending characters begins combat. You may pull members from your pack to assist in the defense.",
            "precisa_revisao": True,
            "slug": "pack-defense"
        }
    },
    
    # Cub's Cry — loyal packmates join
    1416: {
        "id": "cubs-cry",
        "nome": "Cub's Cry",
        "tipo": "Combat Event",
        "modos": [
            {
                "descricao": "Leais entram no combate",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 2,
                        "params": {"filtro": "loyal", "entre_rounds": True}
                    }
                ],
                "condicao_uso": "entre_rounds_combate"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 1416,
            "texto_original": "Play between rounds of combat. Each pack member loyal to this creature joins the combat.",
            "precisa_revisao": True,
            "slug": "cubs-cry"
        }
    },
    
    # Weasel — totem, agility
    214: {
        "id": "weasel-totem",
        "nome": "Weasel",
        "tipo": "Event",
        "modos": [
            {
                "descricao": "Agilidade em batalha",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["rage"],
                            "valor": 1,
                            "duracao": "ate_fim_combate"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_ajaba",
            "card_id": 214,
            "texto_original": "Weasel is a cunning totem of war, granting his children agility in battle.",
            "precisa_revisao": True,
            "slug": "weasel-totem"
        }
    },
    
    # ---- DECK 3: KITSUNE ----
    
    # Mei-Fei Quan — hengeyokai +1 Gnosis
    1676: {
        "id": "mei-fei-quan",
        "nome": "Mei-Fei Quan",
        "tipo": "Character - Kitsune",
        "modos": [
            {
                "descricao": "Hengeyokai +1 Gnosis",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["gnosis"],
                            "valor": 1,
                            "filtro": "tipo=Hengeyokai"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1676,
            "texto_original": "Hengeyokai. While Mei-Fei is in play, her hengeyokai packmates gain +1 gnosis.",
            "precisa_revisao": True,
            "slug": "mei-fei-quan"
        }
    },
    
    # Wu Bingshu — extra votes from loyal
    1685: {
        "id": "wu-bingshu",
        "nome": "Wu Bingshu",
        "tipo": "Character - Kitsune",
        "modos": [
            {
                "descricao": "Voto extra por leal no pack",
                "efeitos": [
                    {
                        "tipo": "moot_restricao_global",
                        "condicao_alvo": "jogador_aliado",
                        "params": {
                            "votos_extras_por_leal": 1
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1685,
            "texto_original": "Wu Bingshu has 1 extra vote for each packmate loyal to him.",
            "precisa_revisao": True,
            "slug": "wu-bingshu"
        }
    },
    
    # Kim — start with Wyrm character
    1716: {
        "id": "kim",
        "nome": "Kim",
        "tipo": "Character - Kitsune",
        "modos": [
            {
                "descricao": "Começar com personagem Wyrm Ren5 no pack",
                "efeitos": [
                    {
                        "tipo": "equipar_inicial",
                        "condicao_alvo": "jogador_aliado",
                        "params": {
                            "filtro": "tipo=Wyrm&renown<=5",
                            "tipo_busca": "character"
                        }
                    }
                ],
                "condicao_uso": "inicio_jogo"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1716,
            "texto_original": "Kim has formed unusual Sentai. You can start with a Wyrm Character of Renown 5 or less in your pack.",
            "precisa_revisao": True,
            "slug": "kim"
        }
    },
    
    # Katsuko Moon-Saint — Philodox/CoG
    1687: {
        "id": "katsuko-moon-saint",
        "nome": "Katsuko Moon-Saint",
        "tipo": "Character - Kitsune",
        "modos": [
            {
                "descricao": "Usar cartas Philodox e CoG",
                "efeitos": [
                    {
                        "tipo": "registrar_trigger_combate",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "trigger": "passivo",
                            "filtro_cartas": ["Philodox", "Children of Gaia"]
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1687,
            "texto_original": "Hengeyokai. Katsuko can use Philodox and Children of Gaia cards while Matsuko Sun-Devil is in her pack.",
            "precisa_revisao": True,
            "slug": "katsuko-moon-saint"
        }
    },
    
    # Ozatu Junichiro — discard instead of shuffle
    1679: {
        "id": "ozatu-junichiro",
        "nome": "Ozatu Junichiro",
        "tipo": "Character - Garou (Hakken)",
        "modos": [
            {
                "descricao": "Descartar em vez de embaralhar",
                "efeitos": [
                    {
                        "tipo": "descartar_metade_mao",
                        "condicao_alvo": "jogador_aliado",
                        "params": {
                            "alternativa_embaralhar": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1679,
            "texto_original": "Hengeyokai. If a card would be shuffled into its owner's sept deck, discard it instead.",
            "precisa_revisao": True,
            "slug": "ozatu-junichiro"
        }
    },
    
    # Cellular Phone — pack attack/defend with anyone
    627: {
        "id": "cellular-phone",
        "nome": "Cellular Phone",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Pack attack/defend com qualquer um",
                "efeitos": [
                    {
                        "tipo": "equipar",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "allow_pack_anyone": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 627,
            "texto_original": "A character equipped with a Cellular Phone can pack attack or defend with any other character, regardless of distance or other restrictions.",
            "precisa_revisao": True,
            "slug": "cellular-phone"
        }
    },
    
    # Lost Map — act as defending alpha
    660: {
        "id": "lost-map",
        "nome": "Lost Map",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Alpha defensor em qualquer Battlefield",
                "efeitos": [
                    {
                        "tipo": "equipar",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "any_battlefield_defense": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 660,
            "texto_original": "The character can act as defending alpha for ANY Battlefield in play.",
            "precisa_revisao": True,
            "slug": "lost-map"
        }
    },
    
    # Corporate Credit Card — equip at start of combat
    635: {
        "id": "corporate-credit-card",
        "nome": "Corporate Credit Card",
        "tipo": "Equipment",
        "modos": [
            {
                "descricao": "Equipar no início do combate",
                "efeitos": [
                    {
                        "tipo": "equipar",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "timing": "inicio_combate",
                            "descarte_ao_equipar_novo": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 635,
            "texto_original": "This character can equip at the beginning of the Combat Phase right after alphas are declared, and may discard a previously held piece of equipment.",
            "precisa_revisao": True,
            "slug": "corporate-credit-card"
        }
    },
    
    # Heightened Senses — refuse challenges
    982: {
        "id": "heightened-senses",
        "nome": "Heightened Senses",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Recusar desafios, esquivar fora de combate",
                "efeitos": [
                    {
                        "tipo": "impedir_acoes",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "tipo_impedido": "desafios_ataques_fora_combate"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 982,
            "texto_original": "The user of this Gift can refuse any challenges, even those that normally cannot be refused.",
            "precisa_revisao": True,
            "slug": "heightened-senses"
        }
    },
    
    # Leap of the Kangaroo — join any battlefield
    995: {
        "id": "leap-of-the-kangaroo",
        "nome": "Leap of the Kangaroo",
        "tipo": "Gift",
        "modos": [
            {
                "descricao": "Entrar em qualquer conflito de Battlefield",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "any_battlefield": True,
                            "nao_conta_limite": True
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 995,
            "texto_original": "The Gift user can join her pack in any Battlefield conflict. This character does not count toward the total Battlefield capacity.",
            "precisa_revisao": True,
            "slug": "leap-of-the-kangaroo"
        }
    },
    
    # Reinforcements — add 10 Renown after round 3
    1298: {
        "id": "reinforcements",
        "nome": "Reinforcements",
        "tipo": "Combat Event",
        "modos": [
            {
                "descricao": "Adicionar até 10 Renome em reforços",
                "efeitos": [
                    {
                        "tipo": "ataque_imediato",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 10,
                        "params": {
                            "reforcos": True,
                            "apos_round": 3
                        }
                    }
                ],
                "condicao_uso": "apos_round_3"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1298,
            "texto_original": "Any time after the third round of combat you may add up to 10 Renown worth of characters to the combat.",
            "precisa_revisao": True,
            "slug": "reinforcements"
        }
    },
    
    # Superior Tactics — choose 2 in battlefield
    1317: {
        "id": "superior-tactics",
        "nome": "Superior Tactics",
        "tipo": "Combat Event",
        "modos": [
            {
                "descricao": "Escolher 2 personagens em Battlefield",
                "efeitos": [
                    {
                        "tipo": "restringir",
                        "condicao_alvo": "jogador_inimigo",
                        "quantidade": 2,
                        "params": {
                            "filtro": "battlefield_choice"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 1317,
            "texto_original": "You may choose 2 of your characters involved in a Battlefield conflict. Your opponent can only choose 1 of his.",
            "precisa_revisao": True,
            "slug": "superior-tactics"
        }
    },
    
    # Rewards of Leadership — search deck
    221: {
        "id": "rewards-of-leadership",
        "nome": "Rewards of Leadership",
        "tipo": "Event",
        "modos": [
            {
                "descricao": "Buscar Ally/Equipment no deck",
                "efeitos": [
                    {
                        "tipo": "buscar_copias",
                        "condicao_alvo": "jogador_aliado",
                        "quantidade": 1,
                        "params": {
                            "filtro": "tipo=Ally|Equipment"
                        }
                    }
                ],
                "condicao_uso": "apos_vencer_junta"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 221,
            "texto_original": "Play after you win a Junta you called. You may search your deck for one Ally, Equipment or Fetish card.",
            "precisa_revisao": True,
            "slug": "rewards-of-leadership"
        }
    },
    
    # Whippoorwill — recycle when Ally/Victim removed
    216: {
        "id": "whippoorwill",
        "nome": "Whippoorwill",
        "tipo": "Event",
        "modos": [
            {
                "descricao": "Reciclar Ally ou Victim descartado",
                "efeitos": [
                    {
                        "tipo": "mover_para",
                        "condicao_alvo": "criatura_aliada",
                        "quantidade": 1,
                        "params": {
                            "filtro": "tipo=Ally|Victim",
                            "origem": "discard",
                            "destino": "hand"
                        }
                    }
                ],
                "condicao_uso": "quando_ally_victim_descartado"
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 216,
            "texto_original": "When a Victim or Ally is removed or discarded from play and put in a discard pile, you may take that card into your hand instead.",
            "precisa_revisao": True,
            "slug": "whippoorwill"
        }
    },
}

# ===================================================================
# Helper
# ===================================================================

def criar_json(card_id: int, prefix: str):
    """Cria JSON se não existir."""
    json_path = f'data/cards/auto_{prefix}_{card_id}.json'
    if os.path.exists(json_path):
        print(f'  JSON já existe: {json_path}')
        return True
    
    template = JSON_TEMPLATES.get(card_id)
    if not template:
        print(f'  [AVISO] Sem template para card_id={card_id}')
        return False
    
    with open(json_path, 'w') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f'  JSON criado: {json_path}')
    return True


def criar_deck(config: dict, prefix: str):
    """Cria um deck no banco."""
    from rage_web.ext.database import db
    from rage_web.models.deck import Deck
    from rage_web.models.card import Card
    import rage_web.ext.repository as rep
    
    with app.app_context():
        existing = Deck.query.filter_by(name=config['name']).first()
        if existing:
            print(f'Deck já existe: [{existing.id}] {existing.name}')
            return existing.id
        
        deck = Deck()
        deck.name = config['name']
        deck.description = config['description']
        deck.renown_cap = config['renown_cap']
        db.session.add(deck)
        db.session.flush()
        
        total_renown = 0
        
        for cid, qty in config['cards']:
            card = Card.query.get(cid)
            if not card:
                print(f'  [ERRO] Carta {cid} não encontrada!')
                continue
            rep.deck_add_card(deck, card, qty)
            total_renown += (card.renown or 0) * qty
        
        print(f'  Deck ID: {deck.id}')
        print(f'  Nome: {deck.name}')
        print(f'  Renown: {total_renown}/{deck.renown_cap}')
        print(f'  Cartas: {sum(q for _, q in config["cards"])} (únicas: {len(config["cards"])})')
        
        # List cards
        for cid, qty in config['cards']:
            c = Card.query.get(cid)
            if c:
                print(f'    {qty}x [{c.id}] {c.name} ({c.tipo})')
        
        return deck.id


def gerar_jsons(config: dict, prefix: str):
    all_ids = [cid for cid, _ in config['cards']]
    for cid in sorted(set(all_ids)):
        criar_json(cid, prefix)


def rodar_checklist(deck_id):
    print()
    print('  --- CHECKLIST ---')
    cmd = f'python3 scripts/gerar_checklist.py {deck_id}'
    os.system(cmd)


# ===================================================================
# Main
# ===================================================================

if __name__ == '__main__':
    for i, (config, prefix) in enumerate([
        (DECK2, 'deckajaba'),
        (DECK3, 'deckkitsune'),
    ], 2):
        print(f'\n{"="*60}')
        print(f'DECK {i}: {config["name"]}')
        print(f'{"="*60}')
        
        print('--- Gerando JSONs ---')
        gerar_jsons(config, prefix)
        
        print()
        print('--- Criando deck ---')
        deck_id = criar_deck(config, prefix)
        
        if deck_id:
            rodar_checklist(deck_id)
    
    print()
    print('=== PRONTO! 3 decks para torneio: ===')
