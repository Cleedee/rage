"""Cria o deck Umbral Wardens e seus JSONs."""
from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.deck import Deck, deck_cards
from rage_web.models.card import Card
from sqlalchemy import select
import json, os

JSON_DIR = 'data/cards'

def salvar_json(card_id, nome, tipo, modos, metadata_extra=None):
    """Cria um JSON padrao para uma carta."""
    from rage_web.ext.database import db
    from rage_web.models.card import Card
    app = create_app()
    with app.app_context():
        c = db.session.get(Card, card_id)
        if not c:
            print(f"  ⚠️ Card {card_id} nao encontrado no DB")
            return None
    
    fname = f"umbral_{card_id}_{nome.lower().replace(' ','_').replace('-','_')}.json"
    fname = fname.replace("'","")
    
    data = {
        "id": f"card_{card_id}",
        "nome": nome,
        "tipo": tipo,
        "modos": modos,
        "_metadata": {
            "deck": "umbral_wardens",
            "card_id": card_id,
            "texto_original": (c.text or '').strip(),
            "keywords": c.keyword or '',
            "damage": c.damage or '',
            "rage": c.rage,
            "gnosis": c.gnosis,
            "health": c.health,
            "renown": c.renown,
            "requires": c.requires or '',
            "expansion": getattr(c, 'expansion', '') or '',
            "precisa_revisao": False
        }
    }
    if metadata_extra:
        data["_metadata"].update(metadata_extra)
    
    path = os.path.join(JSON_DIR, fname)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Criado {fname}")
    return fname

app = create_app()

print("=== Criando JSONs para cartas do Umbral Wardens ===\n")

# ── CHARACTERS ──

# Sees-through-Stars (247)
print("247 - Sees-through-Stars")
salvar_json(247, "Sees-through-Stars", "Character - Gaia", [
    {
        "descricao": "Passiva: usa Gauntlet de qualquer Caern para step sideways",
        "efeitos": [
            {
                "tipo": "modificador_gauntlet",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 0,
                "params": {
                    "usa_qualquer_caern": True,
                    "alvo_card_id": 247
                }
            }
        ]
    }
])

# Fade-To-Black (62)
print("\n62 - Fade-To-Black")
salvar_json(62, "Fade-To-Black", "Character - Gaia", [
    {
        "descricao": "Passiva: +2 Gnosis para step sideways e combat cards com requisito de Gnosis",
        "efeitos": [
            {
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 2,
                "params": {
                    "atributo": "gnosis",
                    "so_para_umbra": True,
                    "restricao": "step_sideways_ou_combat_gnosis",
                    "alvo_card_id": 62
                }
            }
        ]
    }
])

# Tim Rowantree (337)
print("\n337 - Tim Rowantree")
salvar_json(337, "Tim Rowantree", "Character - Gaia", [
    {
        "descricao": "Passiva: se pack tem Caern, +2 Rage +1 Health",
        "efeitos": [
            {
                "tipo": "modificar_atributo",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 0,
                "params": {
                    "se_pack_tem_caern": True,
                    "rage_bonus": 2,
                    "health_bonus": 1,
                    "alvo_card_id": 337
                }
            }
        ]
    }
])

# Rainpuddle (231)
print("\n231 - Rainpuddle")
salvar_json(231, "Rainpuddle", "Character - Gaia", [
    {
        "descricao": "Passiva: ataques afetam qualquer coisa na Umbra",
        "efeitos": [
            {
                "tipo": "modificador_umbra",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 0,
                "params": {
                    "ataca_umbra": True,
                    "alvo_card_id": 231
                }
            }
        ]
    }
])

# Shadow-Weaver (1662)
print("\n1662 - Shadow-Weaver")
salvar_json(1662, "Shadow-Weaver", "Character - Rogue", [
    {
        "descricao": "Passiva: Ananasi agem como Caern Gauntlet 1 para pack step sideways",
        "efeitos": [
            {
                "tipo": "modificador_gauntlet",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "gauntlet_reduction": 3,
                    "funciona_como_caern": True,
                    "alvo_card_id": 1662
                }
            }
        ]
    }
])

# ── ACTIONS (Sept) ──

# Step Sideways (809)
print("\n809 - Step Sideways")
salvar_json(809, "Step Sideways", "Action", [
    {
        "descricao": "Step sideways para Umbra antes dos alfas",
        "efeitos": [
            {
                "tipo": "remover_do_combate",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "destino": "umbra",
                    "volta_proximo_turno": False,
                    "antes_dos_alfas": True,
                    "gauntlet_inicial": 3
                }
            }
        ],
        "condicao_uso": "antes_dos_alfas"
    }
])

# Fast Shift (788)
print("\n788 - Fast Shift")
salvar_json(788, "Fast Shift", "Action", [
    {
        "descricao": "Entra na Umbra imediatamente (ignora Gauntlet)",
        "efeitos": [
            {
                "tipo": "remover_do_combate",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "destino": "umbra",
                    "ignora_gauntlet": True,
                    "qualquer_fase": True
                }
            }
        ]
    }
])

# ── COMBAT ACTIONS ──

# Umbral Flurry (1325)
print("\n1325 - Umbral Flurry")
salvar_json(1325, "Umbral Flurry", "Combat Action", [
    {
        "descricao": "Apenas na Umbra. Dano = Gnosis - oponente Gnosis",
        "efeitos": [
            {
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 0,
                "params": {
                    "apenas_umbra": True,
                    "dano_baseado_em": "gnosis_difference",
                    "minimo_dano": 1
                }
            }
        ]
    }
], {"rage": 0, "gnosis": 4, "health": 0})

# Redirected Attack (1297)
print("\n1297 - Redirected Attack")
salvar_json(1297, "Redirected Attack", "Combat Action", [
    {
        "descricao": "Se Gnosis > oponente, ele sofre propria acao",
        "efeitos": [
            {
                "tipo": "redirecionar_acao",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 1,
                "params": {
                    "apenas_umbra": True,
                    "condicao": "gnosis_maior",
                    "alvo": "atacante"
                }
            }
        ]
    }
], {"rage": 0, "gnosis": 7, "health": 0})

# Flicker (324)
print("\n324 - Flicker")
salvar_json(324, "Flicker", "Combat Action", [
    {
        "descricao": "Apenas na Umbra. Dodga todos ataques este round",
        "efeitos": [
            {
                "tipo": "dodge",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "apenas_umbra": True,
                    "dodge_all": True
                }
            }
        ]
    }
], {"rage": 0, "gnosis": 6, "health": 0})

# Sap Spirit (1305)
print("\n1305 - Sap Spirit")
salvar_json(1305, "Sap Spirit", "Combat Action", [
    {
        "descricao": "Apenas na Umbra. Inbloqueavel. Dano = Rage do atacante",
        "efeitos": [
            {
                "tipo": "dano",
                "condicao_alvo": "criatura_inimiga",
                "quantidade": 0,
                "params": {
                    "apenas_umbra": True,
                    "inbloqueavel": True,
                    "dano_baseado_em": "attacker_rage"
                }
            }
        ]
    }
], {"rage": 0, "gnosis": 6, "health": 0})

# ── EVENTS / GIFTS (Sept) ──
# Walking between Worlds (1082)
print("\n1082 - Walking between Worlds")
salvar_json(1082, "Walking between Worlds", "Gift", [
    {
        "descricao": "Criatura pode entrar/sair da Umbra a vontade ate o fim do turno",
        "efeitos": [
            {
                "tipo": "modificador_umbra",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "livre_transito_umbra": True,
                    "duracao": "fim_do_turno"
                }
            }
        ]
    }
])

# Airt Gateway (921)
print("\n921 - Airt Gateway")
salvar_json(921, "Airt Gateway", "Gift", [
    {
        "descricao": "Teleporta personagem para a Umbra ou vice-versa",
        "efeitos": [
            {
                "tipo": "mover_entre_zonas",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 1,
                "params": {
                    "destino": "umbra_ou_fisico",
                    "pode_trazer_aliado": True
                }
            }
        ]
    }
])

# Airt Mastery (922)
print("\n922 - Airt Mastery")
salvar_json(922, "Airt Mastery", "Gift", [
    {
        "descricao": "Controla movimento via Airt. Personagens nao podem sair da Umbra sem permissao",
        "efeitos": [
            {
                "tipo": "restringir",
                "condicao_alvo": "inimigo",
                "quantidade": 0,
                "params": {
                    "nao_pode_sair_umbra": True,
                    "duracao": "ate_proximo_moot"
                }
            }
        ]
    }
])

# Spiritual Revelation (908)
print("\n908 - Spiritual Revelation")
salvar_json(908, "Spiritual Revelation", "Event", [
    {
        "descricao": "Revelacao espiritual. Compre cartas igual ao numero de Caerns no jogo",
        "efeitos": [
            {
                "tipo": "comprar",
                "condicao_alvo": "jogador",
                "quantidade": 0,
                "params": {
                    "por_caern_em_jogo": True
                }
            }
        ]
    }
])

# Umbral Wave (919)
print("\n919 - Umbral Wave")
salvar_json(919, "Umbral Wave", "Event", [
    {
        "descricao": "Onda umbral. Todos personagens na Umbra sofrem dano igual a diferenca de Gnosis",
        "efeitos": [
            {
                "tipo": "dano",
                "condicao_alvo": "todos_na_umbra",
                "quantidade": 0,
                "params": {
                    "dano_baseado_em": "gnosis_difference_global",
                    "afeta_ambos_lados": True
                }
            }
        ]
    }
])

# Close Gauntlet (829)
print("\n829 - Close Gauntlet")
salvar_json(829, "Close Gauntlet", "Event", [
    {
        "descricao": "Fecha o Gauntlet. Personagens na Umbra ficam presos ate o fim do turno",
        "efeitos": [
            {
                "tipo": "impedir_retirada",
                "condicao_alvo": "todos_na_umbra",
                "quantidade": 0,
                "params": {
                    "apenas_na_umbra": True,
                    "duracao": "fim_do_turno"
                }
            }
        ]
    }
])

# Gaia's Breath (856)
print("\n856 - Gaia's Breath")
salvar_json(856, "Gaia's Breath", "Event", [
    {
        "descricao": "Sopro de Gaia. Cura 2 de dano de todos personagens aliados na Umbra",
        "efeitos": [
            {
                "tipo": "curar",
                "condicao_alvo": "criatura_aliada",
                "quantidade": 2,
                "params": {
                    "apenas_na_umbra": True,
                    "todos_na_umbra": True
                }
            }
        ]
    }
])

print("\n=== JSONs criados ===")

# ── CRIAR DECK ──
print("\n=== Criando deck Umbral Wardens ===")
with app.app_context():
    # Check if deck already exists
    existing = db.session.execute(
        select(Deck).where(Deck.name == "Umbral Wardens")
    ).scalar_one_or_none()
    
    if existing:
        print(f"Deck ja existe (id={existing.id}). Removendo cartas antigas...")
        db.session.execute(deck_cards.delete().where(deck_cards.c.deck_id == existing.id))
        deck_id = existing.id
    else:
        deck = Deck(name="Umbral Wardens", description="Guardioes do Gauntlet. Usam Caerns e mobilidade Umbral para controlar o campo.",
                    renown_cap=20)
        db.session.add(deck)
        db.session.flush()
        deck_id = deck.id
        print(f"Deck criado (id={deck_id})")
        existing = deck
    
    def add(card_id, qty=1):
        db.session.execute(
            deck_cards.insert().values(deck_id=deck_id, card_id=card_id, quantity=qty)
        )
    
    # ── Characters (5, Ren=19) ──
    add(247, 1)   # Sees-through-Stars, Ren7
    add(62, 1)    # Fade-To-Black, Ren5
    add(337, 1)   # Tim Rowantree, Ren3
    add(231, 1)   # Rainpuddle, Ren2
    add(1662, 1)  # Shadow-Weaver, Ren2
    
    # ── Combat Actions (34 cards, max 2 copies) ──
    # Umbra-only combat actions
    add(324, 2)   # Flicker (Umbra dodge all)
    add(1297, 2)  # Redirected Attack (Umbra reflect)
    add(1305, 2)  # Sap Spirit (Umbra unblockable)
    add(1325, 2)  # Umbral Flurry (Umbra Gnosis damage)
    # Standard combat actions
    add(1324, 2)  # Umbral Escape (step to Umbra)
    add(312, 2)   # Dodge
    add(317, 2)   # Evasion
    add(321, 2)   # Feint
    add(289, 2)   # Block and Strike
    add(1272, 2)  # Disarm
    add(1278, 2)  # Low Blow (R2 D3)
    add(1279, 2)  # Lucky Blow (R2 D3)
    add(1296, 2)  # Reckless Swing (R2 D3)
    add(1326, 2)  # Vital Blow (R6 D4)
    add(283, 2)   # Battle Fervor
    add(112, 2)   # Frenzy
    
    # ── Sept Cards (30 cards, max 3 copies) ──
    # Umbra actions
    add(809, 3)   # Step Sideways
    add(788, 2)   # Fast Shift
    # Caerns
    add(579, 2)   # Caern of Rytthiku
    add(586, 2)   # Caern of the Unwashed Child
    add(609, 2)   # Lake Nasser Wallow
    add(599, 2)   # Trinity Hive Caern
    # Umbra events
    add(910, 2)   # Stuck Sideways
    add(908, 2)   # Spiritual Revelation
    add(919, 2)   # Umbral Wave
    add(829, 2)   # Close Gauntlet
    add(856, 2)   # Gaia's Breath
    # Umbra gifts
    add(1082, 2)  # Walking between Worlds
    add(921, 2)   # Airt Gateway
    add(922, 2)   # Airt Mastery
    # Support gifts
    add(818, 2)   # Beast-of-War
    add(1052, 2)  # Silver Claws
    add(790, 2)   # Friends in High Places
    add(807, 2)   # Sneak Attack
    add(875, 2)   # Iron Will
    
    db.session.commit()
    
    # Verify
    from rage_web.ext.repository import grupo_carta, _validar_deck
    rows = db.session.execute(
        select(deck_cards).where(deck_cards.c.deck_id == deck_id)
    ).all()
    
    total = combat = sept = chars = 0
    for r in rows:
        card = db.session.get(Card, r.card_id)
        if not card:
            continue
        g = grupo_carta(card.tipo or '')
        total += r.quantity
        if g == 'combat':
            combat += r.quantity
        elif g == 'sept':
            sept += r.quantity
        else:
            chars += r.quantity
    
    print(f"\n=== Deck Umbral Wardens (id={deck_id}) ===")
    print(f"  Characters: {chars}")
    print(f"  Combate: {combat}")
    print(f"  Septo: {sept}")
    print(f"  Total: {total}")
    
    erros = _validar_deck(existing)
    if erros:
        print(f"  ❌ Erros de validacao:")
        for e in erros:
            print(f"     {e}")
    else:
        print(f"  ✅ Deck valido!")
