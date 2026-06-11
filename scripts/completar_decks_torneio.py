#!/usr/bin/env python3
"""Completa os decks de torneio ate os minimos oficiais do Rage CCG.

Regras:
- Sept deck: minimo 30 cartas (Event, Gift, Equipment, Enemy, Victim, Ally, etc.)
- Combat deck: minimo 20 cartas (Combat Action, Combat Event, etc.)

Adiciona cartas tematicas para cada deck e cria JSONs de efeito genericos.

Uso:
  python3 scripts/completar_decks_torneio.py           # Executa
  python3 scripts/completar_decks_torneio.py --dry-run # Preview
"""

import os, sys, json, glob

os.environ['ENVIRONMENT'] = 'default'
sys.path.insert(0, '/workspace')

from rage_web.ext.database import db
from rage_web import create_app
from rage_web.models.deck import Deck
from rage_web.models.card import Card
import rage_web.ext.repository as rep

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SEPT_TYPES = {
    'Event', 'Action', 'Territory', 'Caern', 'Quest',
    'Battlefield', 'Rite', 'Moot', 'Board Meeting',
    'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
    'Victim', 'Enemy',
    'Equipment', 'Equipment - Fetish - Bane Fetish',
}

COMBAT_DECK_MIN = 20
SEPT_DECK_MIN = 30

DECK_IDS = [1043, 1044, 1045, 1049]

DECK_PREFIX = {
    1043: 'deckbastet',
    1044: 'deckajaba',
    1045: 'deckkitsune',
    1049: 'deckwyrm',
}

#每条 deck precisa de uma composição balanceada de tipos.
# Definimos quantas cartas de cada tipo adicionar (além das que já existem).
DECK_SEPT_COMPOSITION = {
    # tipo -> quantidade mínima desejada no sept deck
    'Gift': 4,
    'Event': 4,
    'Equipment': 3,
    'Enemy': 3,
    'Victim': 2,
}

DECK_COMBAT_COMPOSITION = {
    'Combat Action': 12,
    'Combat Event': 4,
}

# Palavras para filtrar cartas genéricas/de teste que devem ser evitadas
BLACKLIST_NAMES = {'teste', 'test ', 'test_', 'gift 1', 'gift 2', 'gift 3',
                   'gift 4', 'gift 5', 'gift 6', 'event 1', 'event 2',
                   'event 3', 'event 4', 'event 5', 'event 6',
                   'combat action 1', 'combat action 2', 'combat action 3',
                   'combat action 4', 'combat action 5', 'combat action 6',
                   'banana split', 'enemy 1', 'enemy 2', 'enemy 3',
                   'victim 1', 'victim 2', 'victim 3', 'equipment 1',
                   'equipment 2', 'ally 1', 'ally 2',}

# Nomes que indicam cartas com texto longo demais (truncadas)
BLACKLIST_PARTIAL = ['�', '�']

# Keywords temáticas por deck
DECK_KEYWORDS = {
    1043: {  # Bastet — werecats, claws, moon, night, stealth, spirit
        'sept': ['claw', 'moon', 'night', 'shadow', 'spirit', 'gift',
                 'breath', 'senses', 'vision', 'stealth', 'pack',
                 'healing', 'restore', 'umbra', 'wind', 'fang'],
        'combat': ['claw', 'fang', 'bite', 'strike', 'ambush', 'pack',
                   'dodge', 'block', 'counter', 'parry', 'evade'],
    },
    1044: {  # Ajaba — werehyenas, pack, hunt, savanna, endurance
        'sept': ['pack', 'hunt', 'spirit', 'breath', 'wind', 'healing',
                 'endurance', 'stamina', 'prey', 'savanna', 'fang'],
        'combat': ['fang', 'bite', 'broken', 'limb', 'hamstring', 'pack',
                   'pursue', 'chase', 'dodge', 'block', 'strike'],
    },
    1045: {  # Kitsune — werefoxes, fortune, trick, illusion, spirit
        'sept': ['spirit', 'fortune', 'luck', 'trick', 'illusion', 'moon',
                 'shadow', 'wind', 'senses', 'vision', 'umbra', 'fox'],
        'combat': ['strike', 'dodge', 'counter', 'trick', 'illusion',
                   'shadow', 'swift', 'leap', 'evade', 'rake'],
    },
    1049: {  # Wyrm — Pentex, corporate, corruption, weapon, combat
        'sept': ['corporate', 'pentex', 'defiler', 'corruption', 'taint',
                 'wyrm', 'weapon', 'combat', 'enemy', 'victim', 'rite'],
        'combat': ['strike', 'dodge', 'block', 'combat', 'weapon',
                   'berserk', 'frenzy', 'rage', 'tactical'],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classificar_deck_type(card_type):
    """Retorna 'sept', 'combat' ou 'character'."""
    if not card_type:
        return 'combat'
    ct = card_type.strip()
    if 'Character' in ct or 'character' in ct.lower():
        return 'character'
    if ct in SEPT_TYPES:
        return 'sept'
    return 'combat'


def nome_generico(nome):
    """Retorna True se o nome parece ser carta generica/de teste."""
    n = (nome or '').lower().strip()
    for b in BLACKLIST_NAMES:
        if b in n:
            return True
    # Nomes muito curtos ou só numeros
    if len(n) <= 2:
        return True
    return False


def contar_decks(deck):
    """Retorna (n_sept, n_combat) para um deck."""
    counts = {}
    for card in deck.cards:
        ct = classificar_deck_type(card.tipo)
        counts[ct] = counts.get(ct, 0) + 1
    return counts.get('sept', 0), counts.get('combat', 0)


def contar_tipos(deck):
    """Retorna dict tipo->quantidade para as cartas do deck."""
    counts = {}
    for card in deck.cards:
        ct = classificar_deck_type(card.tipo)
        if ct == 'sept':
            t = card.tipo.strip()
            counts[t] = counts.get(t, 0) + 1
    return counts


def score_tematico(card, keywords):
    """Pontua uma carta baseado em relevancia tematica."""
    s = 0
    nome = (card.name or '').lower()

    # Evitar cartas genéricas
    if nome_generico(card.name):
        return -100

    # Keywords no nome
    for kw in keywords:
        if kw in nome:
            s += 10

    # Bônus para tipos desejados
    tipo = (card.tipo or '').strip()
    if tipo in ['Combat Action', 'Combat Event']:
        s += 5  # Priorizar Combat para o pool de combate
    if tipo in ['Gift', 'Event', 'Equipment', 'Enemy', 'Victim']:
        s += 5  # Priorizar Sept para o pool de sept

    return s


def score_sept(card, keywords, tipo_alvo):
    """Pontua carta para o sept deck — prioriza o tipo alvo."""
    s = score_tematico(card, keywords)
    if (card.tipo or '').strip() == tipo_alvo:
        s += 20
    return s


def score_combat(card, keywords):
    """Pontua carta para o combat deck."""
    s = score_tematico(card, keywords)
    return s


def escolher_pool(pool, keywords, quantidade, tipo_alvo=None):
    """Escolhe N cartas de um pool, ordenadas por relevância."""
    if tipo_alvo:
        scored = sorted(pool, key=lambda c: score_sept(c, keywords, tipo_alvo), reverse=True)
    else:
        scored = sorted(pool, key=lambda c: score_combat(c, keywords), reverse=True)

    escolhidos = []
    for c in scored:
        if len(escolhidos) >= quantidade:
            break
        if c.id not in [x.id for x in escolhidos]:
            escolhidos.append(c)
    return escolhidos


def criar_json_efeito(card, prefix):
    """Cria JSON de efeito generico para uma carta."""
    tipo = (card.tipo or 'Unknown').strip().lower()

    if 'combat action' in tipo:
        efeito_tipo = 'modificar_atributo'
        condicao_alvo = 'criatura_inimiga'
        params = {"atributos": ["rage"], "valor": -1,
                  "duracao": "ate_fim_combate", "condicao": "se_dano_aplicado"}
        descricao = "Reduz Rage da vítima"
    elif 'combat event' in tipo:
        efeito_tipo = 'ataque_imediato'
        condicao_alvo = 'criatura_inimiga'
        params = {"valor": 1}
        descricao = "Ataque imediato"
    elif 'gift' in tipo:
        efeito_tipo = 'modificar_atributo_passivo'
        condicao_alvo = 'criatura_aliada'
        params = {"atributos": ["gnosis"], "valor": 1}
        descricao = "Bênção +1 Gnosis"
    elif 'equipment' in tipo:
        efeito_tipo = 'equipar'
        condicao_alvo = 'criatura_aliada'
        params = {"slot": "weapon", "bonus_rage": 1}
        descricao = "Equipamento de combate"
    elif 'enemy' in tipo:
        efeito_tipo = None
        condicao_alvo = ''
        params = {}
        descricao = "Inimigo sem efeito ativo"
    elif 'victim' in tipo:
        efeito_tipo = None
        condicao_alvo = ''
        params = {}
        descricao = "Vítima passiva"
    elif 'ally' in tipo:
        efeito_tipo = 'modificar_atributo_passivo'
        condicao_alvo = 'criatura_aliada'
        params = {"atributos": ["rage"], "valor": 1, "duracao": "1_rodada"}
        descricao = "Aliado dá +1 Rage"
    elif 'event' in tipo:
        efeito_tipo = 'comprar'
        condicao_alvo = 'jogador_aliado'
        params = {"valor": 2}
        descricao = "Compra cartas"
    elif 'rite' in tipo:
        efeito_tipo = 'modificar_atributo'
        condicao_alvo = 'criatura_aliada'
        params = {"atributos": ["rage"], "valor": 2, "duracao": "1_rodada"}
        descricao = "Rito de fúria"
    else:
        efeito_tipo = 'modificar_atributo_passivo'
        condicao_alvo = 'criatura_aliada'
        params = {"atributos": ["rage"], "valor": 1}
        descricao = "Efeito passivo"

    if efeito_tipo:
        modos = [{
            "descricao": descricao,
            "efeitos": [{"tipo": efeito_tipo, "condicao_alvo": condicao_alvo,
                         "params": params}]
        }]
    else:
        modos = [{"descricao": descricao, "efeitos": []}]

    slug = card.slug or f"card_{card.id}"
    return {
        "id": slug,
        "nome": card.name,
        "tipo": card.tipo,
        "modos": modos,
        "_metadata": {
            "fonte": prefix,
            "card_id": card.id,
            "texto_original": card.text or "",
            "precisa_revisao": True,
            "slug": slug,
        }
    }


def salvar_json(card, prefix):
    """Salva arquivo JSON de efeito. Retorna True se criou novo."""
    fname = f"data/cards/auto_{prefix}_{card.id}.json"
    if os.path.exists(fname):
        return False
    template = criar_json_efeito(card, prefix)
    with open(fname, 'w') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv

    app = create_app()
    with app.app_context():
        total_cartas = 0
        total_jsons = 0

        for deck_id in DECK_IDS:
            d = Deck.query.get(deck_id)
            if not d:
                print(f'[ERRO] Deck {deck_id} nao encontrado!')
                continue

            prefix = DECK_PREFIX[deck_id]
            keywords = DECK_KEYWORDS[deck_id]

            n_sept, n_combat = contar_decks(d)
            faltam_sept = max(0, SEPT_DECK_MIN - n_sept)
            faltam_combat = max(0, COMBAT_DECK_MIN - n_combat)

            print(f'\n{"="*60}')
            print(f'Deck: {d.name} (ID {deck_id})')
            print(f'  Atual:  {n_sept} sept / {n_combat} combat')
            print(f'  Faltam: {faltam_sept} sept / {faltam_combat} combat')

            if faltam_sept == 0 and faltam_combat == 0:
                print(f'  ✓ Deck completo!')
                continue

            used_ids = set(c.id for c in d.cards)

            # Buscar todos os candidatos do banco
            pool_sept_cards = {}  # tipo -> [cards]
            pool_combat_cards = []

            for c in Card.query.filter(
                ~Card.id.in_(list(used_ids)) if used_ids else True
            ).all():
                ct = classificar_deck_type(c.tipo)
                if ct == 'character':
                    continue
                if nome_generico(c.name):
                    continue
                if ct == 'sept':
                    t = c.tipo.strip()
                    if t not in pool_sept_cards:
                        pool_sept_cards[t] = []
                    pool_sept_cards[t].append(c)
                elif ct == 'combat':
                    pool_combat_cards.append(c)

            # --- SEPT DECK: distribuir por tipo ---
            sept_a_adicionar = []
            tipos_sept = list(DECK_SEPT_COMPOSITION.keys())

            # Contar o que já existe de cada tipo
            existing_sept_types = contar_tipos(d)
            # Filtrar só sept types
            existing_sept_types = {k: v for k, v in existing_sept_types.items()
                                   if k.strip() in SEPT_TYPES}

            for tipo_alvo, qtd_desejada in DECK_SEPT_COMPOSITION.items():
                ja_tem = existing_sept_types.get(tipo_alvo, 0)
                faltam_tipo = max(0, qtd_desejada - ja_tem)
                if faltam_tipo <= 0:
                    continue

                tipo_cards = pool_sept_cards.get(tipo_alvo, [])
                # Ordenar por relevancia tematica
                tipo_cards.sort(
                    key=lambda c: score_sept(c, keywords['sept'], tipo_alvo),
                    reverse=True
                )
                for c in tipo_cards[:faltam_tipo]:
                    if c.id not in used_ids and c.id not in [x.id for x in sept_a_adicionar]:
                        sept_a_adicionar.append(c)

            # Completar até o mínimo de 30
            restante_sept = faltam_sept - len(sept_a_adicionar)
            if restante_sept > 0:
                # Pegar de qualquer tipo de sept
                todos_sept = []
                for tipo_list in pool_sept_cards.values():
                    todos_sept.extend(tipo_list)
                todos_sept.sort(
                    key=lambda c: score_sept(c, keywords['sept'], None),
                    reverse=True
                )
                for c in todos_sept:
                    if len(sept_a_adicionar) >= faltam_sept:
                        break
                    if c.id not in used_ids and c.id not in [x.id for x in sept_a_adicionar]:
                        sept_a_adicionar.append(c)

            # --- COMBAT DECK ---
            pool_combat_cards.sort(
                key=lambda c: score_combat(c, keywords['combat']),
                reverse=True
            )
            combat_a_adicionar = []
            for c in pool_combat_cards[:faltam_combat]:
                if c.id not in used_ids:
                    combat_a_adicionar.append(c)

            # --- DRY RUN ou EXECUTAR ---
            if dry_run:
                print(f'  [DRY RUN] Adicionaria {len(sept_a_adicionar)} sept:')
                for c in sept_a_adicionar:
                    print(f'    [SEPT]   {c.name:40s} [{c.tipo}]')
                print(f'  [DRY RUN] Adicionaria {len(combat_a_adicionar)} combat:')
                for c in combat_a_adicionar:
                    print(f'    [COMBAT] {c.name:40s} [{c.tipo}]')
                continue

            # Adicionar ao deck
            for c in sept_a_adicionar + combat_a_adicionar:
                rep.deck_add_card(d, c, 1)
                used_ids.add(c.id)
                total_cartas += 1
                if salvar_json(c, prefix):
                    total_jsons += 1

            db.session.commit()

            n_final_sept, n_final_combat = contar_decks(d)
            n_jsons_criados = sum(1 for c in sept_a_adicionar + combat_a_adicionar
                                  if os.path.exists(f"data/cards/auto_{prefix}_{c.id}.json"))
            print(f'  ✓ Resultado: {n_final_sept} sept / {n_final_combat} combat')
            print(f'    {len(sept_a_adicionar)} sept + {len(combat_a_adicionar)} combat adicionados')
            print(f'    {n_jsons_criados} JSONs criados')

        print(f'\n{"="*60}')
        if not dry_run:
            print(f'TOTAL: {total_cartas} cartas, {total_jsons} JSONs')


if __name__ == '__main__':
    main()
