#!/usr/bin/env python3
"""Gera checklist de deck: cartas, JSONs, efeitos, sistemas.

ATENCAO: A lista EFEITOS_IMPLEMENTADOS abaixo deve ser mantida em sincronia
com o enum EfeitoTipo em rage_web/game_engine/effects.py.
Sempre que adicionar um novo tipo de efeito no motor, adicione-o aqui tambem.
"""

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
    1050: ("Assombracao dos Passos da Morte", "Pack Ragabash Silent Striders - Stalks Death + truques."),
}


# -------------------------------------------------------------------
# Efeitos implementados no motor (efeitos.py)
# Deve refletir exatamente o enum EfeitoTipo em rage_web/game_engine/effects.py
# -------------------------------------------------------------------
EFEITOS_IMPLEMENTADOS = {
    # Efeitos basicos de combate
    'dano', 'curar', 'destruir', 'descarte', 'comprar',
    'modificar_rage', 'modificar_gnosis', 'modificar_vida',
    'mover_para', 'remover_do_jogo',
    'ganhar_vp', 'perder_vp',
    'combar_acao', 'redirecionar', 'anular', 'fugir',
    'iniciar_combate', 'restringir', 'comprar_ate', 'equipar',
    'modificar_reducao_dano', 'descartar_metade_mao',
    'modificar_atributo', 'usar_gift', 'quest_check',
    'impedir_acoes', 'impedir_retirada', 'cancelar_acao',
    'ataque_imediato', 'remover_do_combate', 'forcar_bluff',
    'impedir_frenzy', 'olhar_topo_deck', 'descartar_mao_combate',
    'registrar_trigger_combate',
    # Efeitos de estado
    'entrar_em_frenesi', 'tapar', 'destapar',
    # Efeitos de setup / passivos
    'equipar_inicial', 'filtrar_redraw',
    'comprar_quando_atacado', 'remover_do_descarte',
    'buscar_copias', 'auto_pack_attack',
    'acao_extra_por_rodada', 'imune_combate_rage',
    'modificar_atributo_passivo', 'modificar_gauntlet',
    'modificar_hand_size', 'adicionar_modifier',
    'matar_vitima',
    # Efeitos de Moot (Juntas)
    'moot_remover_personagem', 'moot_ganhar_vp',
    'moot_restringir', 'moot_rebaixar_forma',
    'moot_construir_caern', 'moot_restricao_global',
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
    """Carrega metadados de todos os JSONs em data/cards/.

    Retorna dict {card_id: info}, onde a chave e o card_id extraido
    do campo _metadata.card_id de cada JSON. JSONs sem card_id sao ignorados.
    """
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
            if cid:
                # deck fonte = prefixo do nome do arquivo ate primeiro '_' (ex: deck7, deck1050)
                # ou 'data/cards/' se nao tiver prefixo numerico
                deck_src = os.path.basename(f)
                jsons[cid] = {
                    'file': deck_src,
                    'deck': deck_src,
                    'nome': data['nome'],
                    'tipo': data['tipo'],
                    'efeitos': sum(len(m.get('efeitos', [])) for m in data.get('modos', [])),
                    'data': data,  # Guarda os dados completos para analise de efeitos
                }
        except Exception:
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

        # Carrega JSONs indexados por card_id
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

            cid = card.id
            if cid in jsons:
                j = jsons[cid]
                # Determina se o JSON foi criado "novo" para este deck
                # (o deck fonte contem o deck_id no nome do arquivo)
                if f'deck{deck_id}' in j['deck'] or j['deck'].startswith(f'deck{deck_id}'):
                    jsons_novos += 1
                else:
                    jsons_reaproveitados += 1

                # Extrai efeitos do JSON (usando os dados completos guardados)
                try:
                    jdata = j['data']
                    tipos = get_tipos_efeito_no_json(jdata)
                    efeitos_usados.update(tipos)
                    for t in tipos:
                        status = check_engine_gap(t)
                        if status != '✅':
                            gaps.add((t, status))
                except Exception:
                    pass
            else:
                sem_json += 1

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
                    status = '✅'
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

        # --- VALIDACAO DE EQUIPAMENTOS vs PERSONAGENS ---
        lines.append("")
        lines.append("## Validacao de Equipamentos vs Personagens")
        lines.append("")
        lines.append("Verifica se os equipamentos do deck sao compativeis com as formas")
        lines.append("e alinhamento dos personagens.")
        lines.append("")

        # Coleta keywords dos personagens
        chars_text = []
        chars_names = []
        for card, qty in results:
            if 'Character' in (card.tipo or ''):
                ct = ((card.tipo or '') + ' ' + (card.keyword or '')).lower()
                chars_text.append(ct)
                chars_names.append(card.name)

        equip_issues = []
        for card, qty in results:
            if card.tipo != 'Equipment':
                continue
            kw = (card.keyword or '').lower()
            req = (card.requires or '').strip()
            issues = []

            # 1. Bane Fetish: requer personagem Wyrm
            eh_bane_fetish = 'bane fetish' in kw or 'bane' in kw.split(' - ')
            if eh_bane_fetish:
                tem_wyrm = any('wyrm' in ct for ct in chars_text)
                if not tem_wyrm:
                    issues.append('Bane Fetish: requer personagem Wyrm, mas nenhum personagem e Wyrm')

            # 2. Gaia Fetish (nao-bane): requer personagem Gaia
            eh_fetish = not eh_bane_fetish and ('fetish' in kw) and 'non-fetish' not in kw
            if eh_fetish:
                tem_gaia = any('gaia' in ct for ct in chars_text)
                if not tem_gaia:
                    issues.append('Gaia Fetish: requer personagem Gaia, mas nenhum personagem e Gaia')

            # 3. Form restrictions via requires field
            if req.startswith('(') and req.endswith(')'):
                req_clean = req.strip('()').strip().lower()
                if req_clean.startswith('not '):
                    forma_negada = req_clean[4:].replace(' form', '').strip()
                    tem_forma = any(forma_negada in ct for ct in chars_text)
                    if tem_forma:
                        issues.append(f'Requer que NAO esteja em forma "{forma_negada}", '
                                      f'mas algum personagem esta nesta forma')
                else:
                    forma_exigida = req_clean.replace(' form', '').strip()
                    tem_forma = any(forma_exigida in ct for ct in chars_text)
                    # Metis sao sempre Crinos — se exigir Homid, Metis nao serve
                    if forma_exigida == 'homid':
                        # Verifica se ha Metis que nao podem virar Homid
                        if not tem_forma:
                            issues.append(f'Requer forma "{forma_exigida}", '
                                          f'mas nenhum personagem esta nela '
                                          f'(personagens Metis sao sempre Crinos)')
                    elif not tem_forma:
                        issues.append(f'Requer forma "{forma_exigida}", '
                                      f'mas nenhum personagem esta nela')

            if issues:
                equip_issues.append((card, issues))

        if equip_issues:
            lines.append("| Carta | Problema |")
            lines.append("|---|---|")
            for card, issues in equip_issues:
                for iss in issues:
                    lines.append(f"| ❌ **{card.name}** (ID {card.id}) | {iss} |")
            lines.append("")
            lines.append("**⚠️  Equipamentos incompativeis encontrados!**")
            lines.append("Considere substituir por alternativas compativeis com os personagens do deck.")
        else:
            lines.append("✅ Todos os equipamentos sao compativeis com os personagens do deck.")
        lines.append("")

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
