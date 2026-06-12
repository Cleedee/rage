#!/usr/bin/env python3
"""Cria JSONs de efeito para as cartas do deck 'Os Ratos de Rua'."""

import os, json

DECK_ID = 735

os.environ['ENVIRONMENT'] = 'default'
import sys
sys.path.insert(0, '/workspace')
from rage_web import create_app
from rage_web.models.card import Card

JSONS = {
    # Characters
    1: {  # Buggerhead
        "id": "buggerhead",
        "nome": "Buggerhead",
        "tipo": "Character - Gaia",
        "modos": [{
            "descricao": "Filtra redraw do sept deck",
            "efeitos": [{
                "tipo": "filtrar_redraw",
                "condicao_alvo": "jogador_aliado",
                "params": {
                    "descricao": "Descarta e compra 1 carta sept extra no fim do Redraw"
                }
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1,
            "texto_original": "While in play, Buggerhead allows you to discard and redraw any 1 sept card at the end of your normal Redraw Phase.",
            "precisa_revisao": False, "slug": "buggerhead"}
    },
    19: {  # Crick Rumwrangler
        "id": "crick-rumwrangler",
        "nome": "Crick Rumwrangler",
        "tipo": "Character - Gaia",
        "modos": [{
            "descricao": "R1 G6, sem efeito especial de carta",
            "efeitos": []
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 19,
            "texto_original": "Crick has gained notoriety for battling the Wyrm in the Amazon jungle.",
            "precisa_revisao": False, "slug": "crick-rumwrangler"}
    },
    131: {  # Grandfather Bannion
        "id": "grandfather-bannion",
        "nome": "Grandfather Bannion",
        "tipo": "Character - Gaia",
        "modos": [{
            "descricao": "Pack comeca com .38 Special equipada",
            "efeitos": [{
                "tipo": "equipar_inicial",
                "condicao_alvo": "packmates",
                "params": {
                    "tipo_equipamento": "firearm",
                    "descricao": "Pack members comecam com .38 Special"
                }
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 131,
            "texto_original": "Members of Bannion's pack may begin the game equipped with .38 Special",
            "precisa_revisao": False, "slug": "grandfather-bannion"}
    },
    195: {  # Mother Larissa
        "id": "mother-larissa",
        "nome": "Mother Larissa",
        "tipo": "Character - Gaia",
        "modos": [{
            "descricao": "Compra 2 cartas de combate extra quando atacada",
            "efeitos": [{
                "tipo": "comprar_quando_atacado",
                "condicao_alvo": "criatura_aliada",
                "params": {
                    "valor": 2,
                    "descricao": "Compra 2 cartas combat quando Larissa e alvo de ataque"
                }
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 195,
            "texto_original": "You may draw 2 extra combat cards whenever she is the target of an attack.",
            "precisa_revisao": False, "slug": "mother-larissa"}
    },
    1469: {  # Quari Filth
        "id": "quari-filth",
        "nome": "Quari Filth",
        "tipo": "Character - Rogue",
        "modos": [{
            "descricao": "Busca carta de combate no descarte",
            "efeitos": [{
                "tipo": "remover_do_descarte",
                "condicao_alvo": "jogador_aliado",
                "params": {
                    "tipo": "Combat Action",
                    "descricao": "Quari busca 1 Combat Action no descarte na fase Resource"
                }
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1469,
            "texto_original": "During the Resource Phase, he may target a combat card in a discard pile and add it to his hand.",
            "precisa_revisao": False, "slug": "quari-filth"}
    },
    # Characters sem JSON mas que já tinham foram cobertos acima
    448: {  # A Bus Full of People (Victim)
        "id": "a-bus-full-of-people",
        "nome": "A Bus Full of People",
        "tipo": "Victim",
        "modos": [],
        "_metadata": {"fonte": "deck_ratos", "card_id": 448,
            "texto_original": "",
            "precisa_revisao": False, "slug": "a-bus-full-of-people"}
    },
    542: {  # Sidhe Knight (Victim)
        "id": "sidhe-knight",
        "nome": "Sidhe Knight",
        "tipo": "Victim",
        "modos": [],
        "_metadata": {"fonte": "deck_ratos", "card_id": 542,
            "texto_original": "At the end of each Combat Phase, this fey spirit attacks the highest Renown Wyrm character.",
            "precisa_revisao": False, "slug": "sidhe-knight"}
    },
    # Ally
    402: {  # Flame Spirit
        "id": "flame-spirit",
        "nome": "Flame Spirit",
        "tipo": "Ally",
        "modos": [{
            "descricao": "Ataque de dano 3 agravado, depois morre",
            "efeitos": [{
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "params": {"valor": 3, "tipo": "agravado", "auto_destruir": True,
                          "descricao": "Flame Spirit ataca com dano 3 agravado e se queima"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 402,
            "texto_original": "The Flame Spirit can burn itself out in one damage 3 attack (aggravated).",
            "precisa_revisao": False, "slug": "flame-spirit"}
    },
    413: {  # Ka Spirit
        "id": "ka-spirit",
        "nome": "Ka Spirit",
        "tipo": "Ally",
        "modos": [{
            "descricao": "Imortal — retorna ao deck quando morto",
            "efeitos": [{
                "tipo": "registrar_trigger_combate",
                "condicao_alvo": "criatura_aliada",
                "params": {"trigger": "morte", "acao": "retornar_ao_deck",
                          "descricao": "Ka Spirit retorna ao deck quando morto"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 413,
            "texto_original": "The Ka Spirit is truly immortal and can never be destroyed. If the Ka Spirit is killed, place it back in the deck.",
            "precisa_revisao": False, "slug": "ka-spirit"}
    },
    418: {  # Kinfolk Small Town Cop
        "id": "kinfolk-small-town-cop",
        "nome": "Kinfolk Small Town Cop",
        "tipo": "Ally",
        "modos": [{
            "descricao": """ + """
                "Prende personagem em Homid",
            "efeitos": [{
                "tipo": "impedir_acoes",
                "condicao_alvo": "criatura_inimiga",
                "params": {"duracao": "1_turno", "forma": "homid",
                          "descricao": "Cop prende 1 personagem em Homid por 1 turno"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 418,
            "texto_original": "Once per turn, just before alphas are selected, the Cop can select any 1 character in Homid form to put in jail.",
            "precisa_revisao": False, "slug": "kinfolk-small-town-cop"}
    },
    1381: {  # Mosquito Swarm
        "id": "mosquito-swarm",
        "nome": "Mosquito Swarm",
        "tipo": "Ally",
        "modos": [{
            "descricao": "Busca todas as copias no deck e joga",
            "efeitos": [{
                "tipo": "buscar_copias",
                "condicao_alvo": "jogador_aliado",
                "params": {"nome": "Mosquito Swarm",
                          "descricao": "Busca todas as copias de Mosquito Swarm no deck"}
            }]
        }, {
            "descricao": "Auto pack attack/defend",
            "efeitos": [{
                "tipo": "auto_pack_attack",
                "condicao_alvo": "criatura_aliada",
                "params": {"descricao": "Mosquito Swarm faz pack attack/defend automatico"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1381,
            "texto_original": "When you play Mosquito Swarm you may search your deck for all copies of Mosquito Swarm and play them.",
            "precisa_revisao": False, "slug": "mosquito-swarm"}
    },
    # Equipment
    272: {  # Flak Jacket
        "id": "flak-jacket",
        "nome": "Flak Jacket",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "Para 1 ataque de ate 4 dano",
            "efeitos": [{
                "tipo": "modificar_reducao_dano",
                "condicao_alvo": "criatura_aliada",
                "params": {"valor": 4, "duracao": "proximo_ataque",
                          "descricao": "Flak Jacket para 1 ataque de ate 4 dano"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 272,
            "texto_original": "The Flak Jacket stops any one attack of up to 4 damage.",
            "precisa_revisao": False, "slug": "flak-jacket"}
    },
    305: {  # Gooshy Gooze
        "id": "gooshy-gooze",
        "nome": "Gooshy Gooze",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "Oponentes perdem 1 Rage e 1 Gnosis em combate",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_inimiga",
                "params": {"atributos": ["rage", "gnosis"], "valor": -1,
                          "duracao": "ate_fim_combate",
                          "descricao": "Gooshy Gooze: oponentes -1 Rage e -1 Gnosis"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 305,
            "texto_original": "Opponents facing a character equipped with Gooshy Gooze lose 1 Rage and 1 Gnosis for the duration of the current combat.",
            "precisa_revisao": False, "slug": "gooshy-gooze"}
    },
    610: {  # .38 Special
        "id": "38-special",
        "nome": ".38 Special",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "Firearm, so Homid, permite jogar combat cards",
            "efeitos": [{
                "tipo": "equipar",
                "condicao_alvo": "criatura_aliada",
                "params": {"slot": "weapon", "tipo": "firearm",
                          "requer_forma": "homid", "bonus_rage": 0,
                          "descricao": ".38 Special: Firearm para Homid"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 610,
            "texto_original": "Only usable by creatures in Homid form. This Firearm allows this creature to play combat cards of Rage 0.",
            "precisa_revisao": False, "slug": "38-special"}
    },
    622: {  # Blood Dagger
        "id": "blood-dagger",
        "nome": "Blood Dagger",
        "tipo": "Equipment",
        "modos": [{
            "descricao": "+1 Rage em combate",
            "efeitos": [{
                "tipo": "equipar",
                "condicao_alvo": "criatura_aliada",
                "params": {"slot": "weapon", "bonus_rage": 1,
                          "descricao": "Blood Dagger: +1 Rage"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 622,
            "texto_original": "A character equipped with the Blood Dagger acts at +1 Rage.",
            "precisa_revisao": False, "slug": "blood-dagger"}
    },
    # Caern
    582: {  # Caern of the Crescent Moon
        "id": "caern-of-the-crescent-moon",
        "nome": "Caern of the Crescent Moon",
        "tipo": "Caern",
        "modos": [{
            "descricao": "Dobra Renome de 1 pack member no Moot",
            "efeitos": [{
                "tipo": "moot_restricao_global",
                "condicao_alvo": "jogador_aliado",
                "params": {"votos_extras_por_personagem": 2,
                          "descricao": "Dobra Renome de 1 personagem no Moot"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 582,
            "texto_original": "You may choose one pack member and double her Renown during any Moot Phase.",
            "precisa_revisao": False, "slug": "caern-of-the-crescent-moon"}
    },
    597: {  # Sky River Caern
        "id": "sky-river-caern",
        "nome": "Sky River Caern",
        "tipo": "Caern",
        "modos": [{
            "descricao": "Nao-alfas imunes a challenge/sneak attack",
            "efeitos": [{
                "tipo": "modifier",
                "condicao_alvo": "packmates",
                "params": {"modifier": "sky_river_caern",
                          "descricao": "Nao-alfas nao podem ser desafiados ou sneak attacked"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 597,
            "texto_original": "Non-alpha members of your pack cannot be challenged or sneak attacked.",
            "precisa_revisao": False, "slug": "sky-river-caern"}
    },
    # Action
    790: {  # Friends in High Places
        "id": "friends-in-high-places",
        "nome": "Friends in High Places",
        "tipo": "Action",
        "modos": [{
            "descricao": "Encerra qualquer combate (sem frenzy)",
            "efeitos": [{
                "tipo": "fugir",
                "condicao_alvo": "todas_criaturas",
                "params": {"descricao": "Encerra combate atual (exceto frenzy)"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 790,
            "texto_original": "You may end any one combat that does not involve a frenzy.",
            "precisa_revisao": False, "slug": "friends-in-high-places"}
    },
    807: {  # Sneak Attack
        "id": "sneak-attack",
        "nome": "Sneak Attack",
        "tipo": "Action",
        "modos": [{
            "descricao": "Ataca qualquer personagem/aliado em jogo",
            "efeitos": [{
                "tipo": "iniciar_combate",
                "condicao_alvo": "criatura_qualquer",
                "params": {"descricao": "Sneak Attack: ataca qualquer alvo em jogo"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 807,
            "texto_original": "The character can circumvent the normal combat protocol and engage any character, ally or enemy in play.",
            "precisa_revisao": False, "slug": "sneak-attack"}
    },
    # Event
    825: {  # City Father
        "id": "city-father",
        "nome": "City Father",
        "tipo": "Event",
        "modos": [{
            "descricao": "Pack pode recusar ataques de Prey e Animal forms",
            "efeitos": [{
                "tipo": "modifier",
                "condicao_alvo": "packmates",
                "params": {"modifier": "pode_recusar_ataques_pre_animal",
                          "descricao": "Pack pode recusar ataques de Prey/Animal forms"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 825,
            "texto_original": "Your pack members may decline attacks from Prey and from Animal form characters as if they were challenges.",
            "precisa_revisao": False, "slug": "city-father"}
    },
    867: {  # Grandfather Thunder
        "id": "grandfather-thunder",
        "nome": "Grandfather Thunder",
        "tipo": "Event",
        "modos": [{
            "descricao": "Oponentes jogam Combat Actions a -1 Rage",
            "efeitos": [{
                "tipo": "modifier",
                "condicao_alvo": "criatura_inimiga",
                "params": {"modifier": "combate_minus_1_rage",
                          "descricao": "Oponentes: -1 Rage em Combat Actions"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 867,
            "texto_original": "All opponents play Combat Actions at -1 Rage when fighting any member of your pack.",
            "precisa_revisao": False, "slug": "grandfather-thunder"}
    },
    885: {  # Mass Pollution
        "id": "mass-pollution",
        "nome": "Mass Pollution",
        "tipo": "Event",
        "modos": [{
            "descricao": "Wyrm +1 Gnosis, nao-Wyrm -1 Gnosis",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "todas_criaturas",
                "params": {"atributos": ["gnosis"], "valor": 1,
                          "filtro_tipo": "Wyrm",
                          "descricao": "Wyrm +1 Gnosis"}
            }, {
                "tipo": "modificar_atributo",
                "condicao_alvo": "todas_criaturas",
                "params": {"atributos": ["gnosis"], "valor": -1,
                          "filtro_tipo": "non_Wyrm",
                          "descricao": "Nao-Wyrm -1 Gnosis"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 885,
            "texto_original": "All Wyrm characters gain 1 Gnosis. Non-Wyrm characters lose 1 Gnosis.",
            "precisa_revisao": False, "slug": "mass-pollution"}
    },
    914: {  # The Green Dragon
        "id": "the-green-dragon",
        "nome": "The Green Dragon",
        "tipo": "Event",
        "modos": [{
            "descricao": "Alpha faz dano agravado +2 Rage, ignora restricoes de forma",
            "efeitos": [{
                "tipo": "modifier",
                "condicao_alvo": "criatura_aliada",
                "params": {"modifier": "green_dragon_alpha",
                          "descricao": "Alpha: dano agravado +2 Rage, ignora forma"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 914,
            "texto_original": "This pack's alpha does aggravated damage and is +2 Rage. Your pack members can ignore form restrictions on combat cards.",
            "precisa_revisao": False, "slug": "the-green-dragon"}
    },
    # Gift
    932: {  # Battle Song
        "id": "battle-song",
        "nome": "Battle Song",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Pack joga Combat Actions a +2 Rage neste turno",
            "efeitos": [{
                "tipo": "modificar_atributo_passivo",
                "condicao_alvo": "packmates",
                "params": {"atributos": ["rage"], "valor": 2,
                          "duracao": "1_turno",
                          "descricao": "Battle Song: pack +2 Rage neste turno"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 932,
            "texto_original": "The Galliard's pack plays Combat Actions at +2 Rage for the current turn.",
            "precisa_revisao": False, "slug": "battle-song"}
    },
    988: {  # Inspiration
        "id": "inspiration",
        "nome": "Inspiration",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Pack +1 Rage e +1 Gnosis na proxima rodada",
            "efeitos": [{
                "tipo": "modificar_atributo_passivo",
                "condicao_alvo": "packmates",
                "params": {"atributos": ["rage", "gnosis"], "valor": 1,
                          "duracao": "1_rodada",
                          "descricao": "Inspiration: pack +1 R/G proxima rodada"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 988,
            "texto_original": "The user and his packmates are +1 Rage and +1 Gnosis for the following round of combat.",
            "precisa_revisao": False, "slug": "inspiration"}
    },
    1003: {  # Messenger's Fortitude
        "id": "messengers-fortitude",
        "nome": "Messenger's Fortitude",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Foge do combate antes de comecar, -1 Renome",
            "efeitos": [{
                "tipo": "fugir",
                "condicao_alvo": "criatura_aliada",
                "params": {"descricao": "Messenger foge antes do combate, -1 Renome"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1003,
            "texto_original": "The user outruns his opponent(s) before combat begins. The character acts at -1 Renown until he engages in combat.",
            "precisa_revisao": False, "slug": "messengers-fortitude"}
    },
    1426: {  # Clawstorm
        "id": "clawstorm",
        "nome": "Clawstorm",
        "tipo": "Gift",
        "modos": [{
            "descricao": "Compra 2 combat cards, joga ate 3 combat actions",
            "efeitos": [{
                "tipo": "comprar",
                "condicao_alvo": "jogador_aliado",
                "params": {"valor": 2, "descricao": "Clawstorm: compra 2 combat cards"}
            }, {
                "tipo": "acao_extra_por_rodada",
                "condicao_alvo": "criatura_aliada",
                "params": {"valor": 3, "descricao": "Clawstorm: ate 3 combat actions"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1426,
            "texto_original": "Play between rounds of combat. Draw 2 combat cards. You may play up to 3 combat actions.",
            "precisa_revisao": False, "slug": "clawstorm"}
    },
    # Combat Actions
    317: {  # Evasion
        "id": "evasion",
        "nome": "Evasion",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Esquiva todos os ataques nesta rodada",
            "efeitos": [{
                "tipo": "anular",
                "condicao_alvo": "ataques_recebidos",
                "params": {"duracao": "rodada_atual",
                          "descricao": "Evasion: esquiva todos os ataques"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 317,
            "texto_original": "Avoids (dodges) all attacks during the current combat round.",
            "precisa_revisao": False, "slug": "evasion"}
    },
    324: {  # Flicker
        "id": "flicker",
        "nome": "Flicker",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "So na Umbra. Esquiva todos os ataques.",
            "efeitos": [{
                "tipo": "anular",
                "condicao_alvo": "ataques_recebidos",
                "params": {"duracao": "rodada_atual", "requer_zona": "umbra",
                          "descricao": "Flicker: esquiva todos os ataques (so Umbra)"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 324,
            "texto_original": "Only usable in the Umbra. Dodge all attacks played against you this round.",
            "precisa_revisao": False, "slug": "flicker"}
    },
    1279: {  # Lucky Blow
        "id": "lucky-blow",
        "nome": "Lucky Blow",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Ataque basico de sorte",
            "efeitos": [{
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "params": {"valor": 1, "descricao": "Lucky Blow: dano 1"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1279,
            "texto_original": "Your opponent takes a turn for the worse.",
            "precisa_revisao": False, "slug": "lucky-blow"}
    },
    1286: {  # Off-balanced Attack
        "id": "off-balanced-attack",
        "nome": "Off-balanced Attack",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "-1 Rage na proxima rodada",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_aliada",
                "params": {"atributos": ["rage"], "valor": -1,
                          "duracao": "proxima_rodada",
                          "descricao": "Off-balanced: -1 Rage proxima rodada"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1286,
            "texto_original": "The character playing this card plays Combat Actions at -1 Rage for the next round of combat.",
            "precisa_revisao": False, "slug": "off-balanced-attack"}
    },
    1289: {  # Overextended Attack
        "id": "overextended-attack",
        "nome": "Overextended Attack",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Nao pode jogar Combat Action na proxima rodada",
            "efeitos": [{
                "tipo": "impedir_acoes",
                "condicao_alvo": "criatura_aliada",
                "params": {"duracao": "proxima_rodada",
                          "descricao": "Overextended: sem combat action proxima rodada"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1289,
            "texto_original": "Your character may not play a Combat Action next round.",
            "precisa_revisao": False, "slug": "overextended-attack"}
    },
    1296: {  # Reckless Swing
        "id": "reckless-swing",
        "nome": "Reckless Swing",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Se esquivado, sem combat action na proxima rodada",
            "efeitos": [{
                "tipo": "impedir_acoes",
                "condicao_alvo": "criatura_aliada",
                "params": {"duracao": "proxima_rodada",
                          "condicao": "se_esquivado",
                          "descricao": "Reckless: se esquivado, sem action proxima rodada"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1296,
            "texto_original": "If this attack is dodged your character cannot play a combat action during the next round of combat.",
            "precisa_revisao": False, "slug": "reckless-swing"}
    },
    1305: {  # Sap Spirit
        "id": "sap-spirit",
        "nome": "Sap Spirit",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "So Umbra. Nao pode ser bloqueado.",
            "efeitos": [{
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "params": {"valor": 1, "nao_pode_ser_bloqueado": True,
                          "requer_zona": "umbra",
                          "descricao": "Sap Spirit: dano 1, so Umbra, unblockable"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1305,
            "texto_original": "Sap Spirit cannot be Blocked. This combat action is only playable in the Umbra.",
            "precisa_revisao": False, "slug": "sap-spirit"}
    },
    1312: {  # Stinging Wound
        "id": "stinging-wound",
        "nome": "Stinging Wound",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Se danificar, oponente +1 Rage proxima rodada",
            "efeitos": [{
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_inimiga",
                "params": {"atributos": ["rage"], "valor": 1,
                          "duracao": "proxima_rodada",
                          "condicao": "se_dano_aplicado",
                          "descricao": "Stinging Wound: oponente +1 R se danificado"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1312,
            "texto_original": "If your opponent is damaged by this attack, he may play Combat Actions at +1 Rage for the next round.",
            "precisa_revisao": False, "slug": "stinging-wound"}
    },
    1319: {  # Surprise Attack
        "id": "surprise-attack",
        "nome": "Surprise Attack",
        "tipo": "Combat Action",
        "modos": [{
            "descricao": "Se danificar na 1a rodada, vitima nao causa dano",
            "efeitos": [{
                "tipo": "impedir_acoes",
                "condicao_alvo": "criatura_inimiga",
                "params": {"duracao": "rodada_atual",
                          "condicao": "se_dano_1a_rodada",
                          "descricao": "Surprise: vitima nao causa dano se atingida na 1a rodada"}
            }]
        }],
        "_metadata": {"fonte": "deck_ratos", "card_id": 1319,
            "texto_original": "If this card damages an opponent during the first round of combat, the victim will inflict no damage this round.",
            "precisa_revisao": False, "slug": "surprise-attack"}
    },
    # Equipment - Improvised Weapon (ja existe com revisao=True, vou atualizar)
    317: {  # Improvised Weapon - ja existe, pular
    },
}

def main():
    app = create_app()
    with app.app_context():
        from rage_web.models.deck import Deck
        d = Deck.query.filter(Deck.name.like('%Ratos%')).first()
        if not d:
            print('Deck nao encontrado!')
            return
        
        criados = 0
        for card in d.cards:
            if card.id not in JSONS:
                continue
            data = JSONS[card.id]
            
            # Verificar se ja existe
            import glob
            slug = card.slug or f'card_{card.id}'
            exists = False
            for p in [f'data/cards/auto_*_{card.id}.json', f'data/cards/{slug}.json']:
                if glob.glob(p):
                    exists = True
                    break
            
            if exists:
                print(f'  JA EXISTE: {card.name}')
                continue
            
            fname = f'data/cards/auto_deckrua_{card.id}.json'
            with open(fname, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            criados += 1
            print(f'  CRIADO: {card.name}')
        
        print(f'\nTotal: {criados} JSONs criados')

if __name__ == '__main__':
    main()
