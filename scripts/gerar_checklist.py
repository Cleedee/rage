#!/usr/bin/env python3
"""Gera checklist de deck: cartas, JSONs, efeitos, sistemas."""

import argparse
import glob
import os
import sys
from collections import defaultdict

# -------------------------------------------------------------------
# Mapeamento de decks conhecidos: nome e estrategia
# -------------------------------------------------------------------
DECK_INFO = {
    7: ("Kinfolk Resistance", "Kinfolk + Firearms + Pack combat. Usa humanos armados e vitimas."),
    90: ("Classic: Cliath Ahroun", "Ahroun basico. Strike + dodge + Rage 3-4. Bater ate cair."),
    160: ("Mokole", "Gaia com quests, morte e recrutamento. Sand's Last King + Mnesis Dreams."),
    416: ("Questor", "Vigilante que pontua matando quem matou menor Renome. The Pit + Chronicle."),
    465: ("Apocalypse: First Team 28", "Wyrm squad. 5 personagens, ataque HG em massa."),
    484: ("Ajaba Aggression", "Hienas que fogem de dano alto. Morder e correr."),
    524: ("Classic: Wailer special", "Aliados + pack attack. Wailer flipa e trava Combat Actions."),
}


# -------------------------------------------------------------------
# Efeitos implementados no motor (efeitos.py)
# -------------------------------------------------------------------
EFEITOS_IMPLEMENTADOS = {
    'dano', 'curar', 'destruir', 'descarte', 'comprar', 'tapar', 'destapar',
    'modificar_rage', 'modificar_gnosis', 'modificar_vida', 'mover_para',
    'remover_do_jogo', 'ganhar_vp', 'perder_vp', 'combar_acao', 'redirecionar',
    'anular', 'fugir', 'iniciar_combate', 'restringir', 'comprar_ate', 'equipar',
    'modificar_reducao_dano', 'descartar_metade_mao', 'modificar_atributo',
    'usar_gift', 'quest_check', 'impedir_acoes', 'impedir_retirada',
    'cancelar_acao', 'ataque_imediato', 'remover_do_combate', 'forcar_bluff',
    'impedir_frenzy', 'olhar_topo_deck', 'descartar_mao_combate',
    'registrar_trigger_combate', 'remover_do_jogo',
}


def get_deck_name(deck_id):
    """Retorna nome do deck do banco ou do mapa."""
    if deck_id in DECK_INFO:
        return DECK_INFO[deck_id][0]
    return f"Deck {deck_id}"


def get_deck_strategy(deck_id):
    """Retorna estrategia do deck."""
    if deck_id in DECK_INFO:
        return DECK_INFO[deck_id][1]
    return ""


def load_json_cards():
    """Carrega metadados de todos os JSONs em data/cards/."""
    import re
    jsons = {}
    for f in sorted(glob.glob("data/cards/*.json")):
        if '_checklist' in f:
            continue
        try:
            import json
            with open(f) as fh:
                data = json.load(fh)
            meta = data.get('_metadata', {})
            cid = meta.get('card_id')
            # Fallback: extrair card_id do nome do arquivo (ex: deck7_122_hunting_party.json)
            if not cid:
                m = re.search(r'_(\d+)_', os.path.basename(f))
                if m:
                    cid = int(m.group(1))
            if cid:
                deck_src = os.path.basename(f).split('_')[0]
                jsons[cid] = {
                    'file': os.path.basename(f),
                    'deck': deck_src,
                    'nome': data['nome'],
                    'tipo': data['tipo'],
                    'efeitos': sum(len(m.get('efeitos', [])) for m in data.get('modos', [])),
                }
        except Exception as exc:
            pass
    return jsons


def get_tipos_efeito_no_json(json_data):
    """Extrai tipos de efeito usados num JSON."""
    tipos = set()
    for modo in json_data.get('modos', []):
        for efeito in modo.get('efeitos', []):
            tipos.add(efeito.get('tipo', ''))
        for p in modo.get('passivas', []):
            tipos.add(f"passiva:{p.get('tipo', '')}")
        for r in modo.get('restricoes', []):
            tipos.add(f"restricao:{r.get('tipo', '')}")
    return tipos


def check_engine_gap(efeito_tipo):
    """Verifica se um tipo de efeito tem resolvedor implementado."""
    if efeito_tipo.startswith('passiva:') or efeito_tipo.startswith('restricao:'):
        return '⚠️ passiva'  # Passivas/restricoes precisam de registro manual
    return '✅' if efeito_tipo in EFEITOS_IMPLEMENTADOS else '❌'


def gerar_checklist(deck_id):
    """Gera o checklist completo para um deck."""
    from rage_web import create_app
    from rage_web.ext.database import db
    from rage_web.models.card import Card, deck_cards
    from rage_web.models.deck import Deck

    app = create_app()
    with app.app_context():
        deck = db.session.get(Deck, deck_id)
        if not deck:
            print(f"Deck {deck_id} nao encontrado no banco.")
            return

        results = db.session.execute(
            db.select(Card, deck_cards.c.quantity)
            .join(deck_cards, Card.id == deck_cards.c.card_id)
            .where(deck_cards.c.deck_id == deck_id)
            .order_by(Card.id)
        ).all()

        jsons = load_json_cards()
        nome = get_deck_name(deck_id)
        estrategia = get_deck_strategy(deck_id)

        # Agrupa cartas por categoria
        categories = defaultdict(list)
        unique_cards = 0
        jsons_novos = 0
        jsons_reaproveitados = 0
        sem_json = 0
        efeitos_usados = set()
        gaps = set()

        for card, qty in results:
            unique_cards += 1
            tipo_base = card.tipo.split(' - ')[0] if ' - ' in card.tipo else card.tipo
            categories[tipo_base].append((card, qty))

            # Verifica JSON
            cid = card.id
            if cid in jsons:
                j = jsons[cid]
                if j['deck'] == f'deck{deck_id}':
                    jsons_novos += qty
                else:
                    jsons_reaproveitados += qty
            else:
                sem_json += qty

            # Tenta ler o JSON para extrair efeitos
            json_paths = glob.glob(f"data/cards/*_{cid}_*.json")
            if json_paths:
                import json
                try:
                    with open(json_paths[0]) as fh:
                        jdata = json.load(fh)
                    tipos = get_tipos_efeito_no_json(jdata)
                    efeitos_usados.update(tipos)
                    for t in tipos:
                        status = check_engine_gap(t)
                        if status != '✅':
                            gaps.add((t, status))
                except Exception:
                    pass

        # --- GERA OUTPUT ---
        lines = []
        lines.append(f"# Deck {deck_id} — {nome}")
        lines.append("")
        if estrategia:
            lines.append(f"**Estratégia:** {estrategia}")
            lines.append("")
        lines.append(f"Gerado automaticamente em {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append("## Checklist de Cartas")
        lines.append("")
        lines.append("| ID | Nome | Tipo | Qty | JSON | Deck fonte | Efeitos no JSON |")
        lines.append("|---|---|---|---|---|---|---|")

        for cat_name in sorted(categories.keys()):
            lines.append(f"| **{cat_name}** | | | | | | |")
            for card, qty in categories[cat_name]:
                cid = card.id
                if cid in jsons:
                    j = jsons[cid]
                    status = '✅' if j['deck'] == f'deck{deck_id}' else '✅'
                    deck_src = j['deck']
                    n_efeitos = j.get('efeitos', 0)
                else:
                    status = '❌'
                    deck_src = '-'
                    n_efeitos = 0
                lines.append(
                    f"| {cid} | {card.name} | {card.tipo} | {qty} | {status} | {deck_src} | {n_efeitos} |"
                )

        lines.append("")
        lines.append(f"**Total:** {unique_cards} cartas unicas ({jsons_novos} novas + {jsons_reaproveitados} reaproveitadas, {sem_json} sem JSON)")
        lines.append("")

        # --- SISTEMAS E GAPS ---
        lines.append("## Efeitos Utilizados vs Motor")
        lines.append("")
        lines.append("| Tipo de Efeito | Status no Motor |")
        lines.append("|---|---|")
        for t in sorted(efeitos_usados):
            status = check_engine_gap(t)
            if status == '✅':
                lines.append(f"| `{t}` | ✅ Implementado |")
            elif status == '⚠️ passiva':
                lines.append(f"| `{t}` | ⚠️ Passiva (registro manual em `register_card_passives`) |")
            else:
                lines.append(f"| `{t}` | ❌ **Nao implementado** |")

        if gaps:
            lines.append("")
            lines.append("### Gaps Identificados")
            lines.append("")
            for tipo, status in sorted(gaps):
                lines.append(f"- **{tipo}**: {status}")

        # --- SUGESTOES DE TESTES ---
        lines.append("")
        lines.append("## Sugestoes de Testes")
        lines.append("")
        for card, qty in sorted(results, key=lambda x: x[0].id):
            cid = card.id
            if cid in jsons:
                j = jsons[cid]
                lines.append(f"- **{j['nome']}** ({cid}): teste de {j['tipo']}")
            else:
                lines.append(f"- **{card.name}** ({cid}): ❌ sem JSON — criar primeiro")

        return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gera checklist de deck')
    parser.add_argument('deck_id', type=int, help='ID do deck')
    args = parser.parse_args()

    texto = gerar_checklist(args.deck_id)
    print(texto)

    # Salva em arquivo
    out = f'data/cards/deck{args.deck_id}_checklist.md'
    with open(out, 'w') as f:
        f.write(texto)
    print(f'\n---\nSalvo em: {out}')
