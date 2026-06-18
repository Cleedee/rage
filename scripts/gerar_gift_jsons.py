#!/usr/bin/env python3
"""Gera JSONs de efeitos estruturados para Gifts que ainda não têm.

Examina cada Gift no banco sem JSON, analisa seu texto,
e gera um JSON de efeitos apropriado.

Uso:
    .venv/bin/python3 scripts/gerar_gift_jsons.py          # gerar todas
    .venv/bin/python3 scripts/gerar_gift_jsons.py --dry    # preview
    .venv/bin/python3 scripts/gerar_gift_jsons.py --id 101 # só uma carta
"""

import json, os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

CARDS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cards')


def slug_from_card(card) -> str:
    slug = card.slug or f'card_{card.id}'
    if len(slug) > 40 or slug.startswith('if-played') or slug.startswith('combat-restricted'):
        return f'card_{card.id}'
    return slug


def texto_original(card) -> str:
    return (card.text or '').strip()


# ── Detection helpers ──

def _txt(t):
    return (t or '').lower()


def has_phrase(texto_lower, *phrases):
    return any(p in texto_lower for p in phrases)


def _gn(card):
    return card.gnosis or 0


def gift_name(card):
    return card.name


def gerar_json(card, dry_run=False):
    """Gera JSON estruturado para um Gift."""
    slug = slug_from_card(card)
    nome = gift_name(card)
    texto = texto_original(card)
    t = _txt(texto)
    gn = _gn(card)

    # ── Skip playtest / empty text ──
    if not texto or 'playtesting' in t or 'teste gift' in t:
        return None
    if nome.lower().startswith('gift ') and 'playtesting' in texto.lower():
        return None

    # ── Categoriza o gift ──
    # O id interno do JSON deve ser o slug original do card,
    # mas slugs muito longos (>40) viram card_{id}.
    raw_slug = card.slug or f'card_{card.id}'
    json_id = raw_slug if len(raw_slug) <= 40 else f'card_{card.id}'

    # Prepara descricao padrao
    desc = nome
    efeitos = []

    # ── 1. PERMANENT GIFTS (simples buffs de atributo) ──
    if has_phrase(t, 'gains', '+2 rage') or has_phrase(t, 'gain', '+2 rage'):
        # Might of Thor: +2 Rage in Crinos
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente"}})
        desc = "+2 Rage"

    elif has_phrase(t, 'gains', '+1 rage') or has_phrase(t, 'gain', '+1 rage'):
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 1, "params": {"duracao": "permanente"}})
        desc = "+1 Rage"

    elif has_phrase(t, '+2 health') and 'develops huge chitinous plates' in t:
        # Armor of the Ancients: +3 Health, dodge is bluff
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 3, "params": {"duracao": "permanente"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "dodge_eh_bluff", "duracao": "permanente"}})
        desc = "+3 Health (dodge vira bluff)"

    elif has_phrase(t, '+2 health') and 'aggravated' in t:
        # Skin of the Adder: +2 Health, agg->normal
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente"}})
        efeitos.append({"tipo": "modificar_reducao_dano", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"tipo": "agg_para_normal", "duracao": "permanente"}})
        desc = "+2 Health (agg vira normal)"

    elif has_phrase(t, '+1 health'):
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 1, "params": {"duracao": "permanente"}})
        desc = "+1 Health"

    elif has_phrase(t, '+2 gnosis') or has_phrase(t, '+2 gnosis'):
        efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente"}})
        desc = "+2 Gnosis"

    elif has_phrase(t, 'gains 2 additional rage') or has_phrase(t, 'horn') and 'impaler' in t:
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente"}})
        desc = "+2 Rage (permanente)"

    # ── 2. Gifts de DANO ──
    elif 'wasp talons' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 4})
        desc = "Causar 4 de dano (firearm)"

    elif 'tongue of the serpent' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2,
                        "params": {"agravado": True}})
        desc = "Causar 2 dano agravado (Fast Striking)"

    elif 'blood lash' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 4,
                        "params": {"agravado": True, "nao_bloqueavel": True}})
        desc = "Causar 4 dano agravado (nao bloqueavel)"

    elif 'backbite' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 1})
        efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99})
        desc = "Causar 1 dano + esquiva todos ataques no prox round"

    elif 'gaia\'s vengeance' in nome.lower():
        dmg = 8
        if 'does 5 damage' in t:
            dmg = 5
        elif 'does 8 damage' in t:
            dmg = 8
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg})
        desc = f"Causar {dmg} de dano (Withdrawal step)"

    elif 'gaia\'s will corrupted' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 5})
        desc = "Causar 5 de dano (Withdrawal step)"

    elif 'coup de grace' in nome.lower() or 'coup de grâce' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 4,
                        "params": {"condicao": "nao_primeiro_round"}})
        desc = "+4 dano a partir do R2"

    elif 'crawling poison' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 1,
                        "params": {"bonus_proximo_ataque": True}})
        desc = "Proximo ataque +1 dano, vitima nao regenera"

    elif 'kiss of helios' in nome.lower():
        # Duas opções: +2 dano OU ignorar flamethrower
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["dano_proximo_ataque"],
                                                     "valor": 2, "duracao": "proximo_ataque"}})
        desc = "Proximo ataque +2 dano OU ignora Flamethrower"

    elif 'circle of death' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 3})
        desc = "Causar 3 de dano"

    elif 'ghost flame' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 7})
        desc = "Causar 7 de dano"

    elif 'gnosis bomb' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                        "params": {"dano_igual_gnosis": True}})
        desc = "Dano igual ao Gnosis do usuario"

    elif 'lightning bolt' in nome.lower():
        efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 6})
        desc = "Causar 6 de dano"

    # ── 3. Gifts de CURA ──
    elif 'kiss of life' in nome.lower() and 'heal' in t:
        efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada_ferida",
                        "quantidade": 6, "params": {"max_dano_carta": 6}})
        desc = "Curar ate 6 de dano (1 carta)"

    elif 'mother\'s touch' in nome.lower() or "mother's touch" in nome.lower():
        efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada_ferida",
                        "quantidade": 4, "params": {"max_dano_carta": 4, "cura_agravado": True}})
        desc = "Curar ate 4 de dano (cura agravado)"

    # ── 4. Gifts de COMPRAR / DRAW ──
    elif 'draw 1 additional combat card' in t or 'draw 1 combat card' in t:
        efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 1})
        desc = "Comprar 1 combat card"

    elif 'draw 2 combat cards' in t:
        efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 2})
        desc = "Comprar 2 combat cards"

    elif 'draw' in t and 'combat card' in t:
        m = re.search(r'draw\s+(\d+)', t)
        qtd = int(m.group(1)) if m else 1
        efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": qtd})
        desc = f"Comprar {qtd} combat card(s)"

    elif 'draw 1 combat card' in t or 'draw one combat card' in t:
        efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 1})
        desc = "Comprar 1 combat card"

    # ── 5. Gifts de REDUCAO DE RAGE (debuff) ──
    elif has_phrase(t, '-2 rage') or has_phrase(t, '-2 rage') and 'curse of aeolus' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -2, "params": {"duracao": "primeiro_round"}})
        desc = "-2 Rage para oponentes (R1)"

    elif 'curse of hatred' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -2, "params": {"duracao": "proxima_acao"}})
        desc = "-2 Rage na proxima Combat Action"

    elif 'whelp body' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -3, "params": {"duracao": "permanente"}})
        desc = "-3 Rage (minimo 1)"

    elif 'shriek' in nome.lower() and 'act at' in t:
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -99, "params": {"rage_fixo": 1, "duracao": "proximo_round"}})
        desc = "Oponentes com Gn < seu agem com Rage 1 no prox round"

    # ── 6. Gifts de CANCELAMENTO ──
    elif 'greater banishment' in nome.lower():
        efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo", "quantidade": 0,
                        "params": {"tipo_alvo": "gift", "remove_do_jogo": True}})
        desc = "Cancela qualquer Gift (remove do jogo)"

    elif 'lesser banishment' in nome.lower():
        efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo", "quantidade": 0,
                        "params": {"tipo_alvo": "gift", "gnosis_max": 5, "remove_do_jogo": True}})
        desc = "Cancela Gift Gnosis <=5 (remove do jogo)"

    elif 'remove gaia\'s blessing' in nome.lower():
        efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo", "quantidade": 0,
                        "params": {"tipo_alvo": "gift", "gnosis_max": 7, "remove_do_jogo": True}})
        desc = "Cancela Gift Gnosis <=7 (remove do jogo)"

    elif 'serenity' in nome.lower() and 'cancel' in t:
        efeitos.append({"tipo": "anular", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                        "params": {"cancela_frenesi": True}})
        desc = "Cancela frenesi"

    elif "heart of fury" in nome.lower():
        efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"nao_pode_frenesi": True, "duracao": "permanente"}})
        desc = "Alvo nao pode frenesi (cancela se frenetico)"

    # ── 7. Gifts que TERMINAM COMBATE ──
    elif 'bellow' in nome.lower() and 'end combat' in t:
        efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99,
                        "params": {"termina_combate": True}})
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -2, "params": {"duracao": "ate_proxima_regeneracao"}})
        desc = "Termina combate, oponentes -2 Rage"

    elif 'staredown' in nome.lower() or 'stare down' in nome.lower():
        efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99,
                        "params": {"termina_combate": True}})
        desc = "Termina combate (intimidacao)"

    elif 'merciful blow' in nome.lower():
        efeitos.append({"tipo": "remover_do_combate", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0})
        desc = "Remove alvo do combate (sem dano)"

    elif 'shroud' in nome.lower() and 'end' in t and 'combat' in t:
        efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99,
                        "params": {"termina_combate": True}})
        desc = "Termina combate envolvendo o alvo"

    elif 'trackless waste' in nome.lower():
        efeitos.append({"tipo": "cancelar_acao", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"cancela_ataque": True}})
        desc = "Cancela ataque declarado"

    # ── 8. Gifts de DEFESA / ESQUIVA ──
    elif 'feline grace' in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "esquiva_rage_igual",
                                                     "duracao": "este_combate"}})
        desc = "Esquiva CA com mesmo Rage"

    elif 'shield of gaia' in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "imune_dano_nao_fetish",
                                                     "duracao": "permanente"}})
        desc = "Imune a Combat Actions de armas nao-Fetish"

    elif 'insightful eyes' in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"restricao": "nao_pode_esquivar",
                                                     "duracao": "permanente"}})
        desc = "Combat Actions do usuario nao podem ser esquivadas"

    elif 'armor of the ancients' in nome.lower():
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 3, "params": {"duracao": "permanente"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "dodge_eh_bluff",
                                                     "duracao": "permanente"}})
        desc = "+3 Health (dodge vira bluff)"

    elif 'shagreen shield' in nome.lower():
        efeitos.append({"tipo": "modificar_reducao_dano", "condicao_alvo": "criatura_aliada",
                        "quantidade": 1, "params": {"duracao": "permanente"}})
        desc = "Bloqueia 1 dano de todos ataques"

    # ── 9. Gifts de RENOME / MOOT ──
    elif 'glib tongue' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["renown_moot"],
                                                     "valor": 5, "duracao": "este_moot"}})
        desc = "+5 Renown para votacao de Moot"

    elif 'voice of reason' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["votos_junta"],
                                                     "valor": 2, "duracao": "permanente"}})
        desc = "+2 votos em Juntas"

    elif 'aura of confidence' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["renown"],
                                                     "valor": 1, "duracao": "permanente"}})
        desc = "+1 Renown"

    elif 'seizing the edge' in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"restricao": "moot_requer_renome_maior",
                                                     "duracao": "este_moot"}})
        desc = "Moot falha so com voto de Renome >= usuario"

    # ── 10. Gifts de FRENESI ──
    elif 'savage fury' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "todas_criaturas",
                        "quantidade": 0, "params": {"entra_frenesi": True}})
        desc = "Usuario e oponente entram em frenesi"

    elif 'song of rage' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"entra_frenesi": True,
                                                     "condicao": "gnosis_alvo_menor"}})
        desc = "Alvo com Gn < seu entra em frenesi"

    # ── 11. Gifts de BUSCA no deck ──
    elif 'deep journey' in nome.lower():
        efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                        "quantidade": 0, "params": {"busca_no_sept_deck": True,
                                                     "tipo_busca": "caern/totem/spirit/fetish"}})
        desc = "Buscar Caern/Totem/Spirit Ally/Fetish do sept deck"

    elif 'tribal wisdom' in nome.lower():
        efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                        "quantidade": 0, "params": {"busca_no_sept_deck": True,
                                                     "tipo_busca": "battlefield"}})
        desc = "Buscar Battlefield do sept deck"

    # ── 12. Gifts de EQUIPAMENTO ──
    elif 'jam technology' in nome.lower():
        efeitos.append({"tipo": "destruir", "condicao_alvo": "equipamento_inimigo",
                        "quantidade": 1, "params": {"filtro": "nao_fetish"}})
        desc = "Descarta 1 equipamento nao-Fetish"

    elif 'bane infestation' in nome.lower():
        efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"rouba_equipamento": True,
                                                     "filtro": "fetish"}})
        desc = "Rouba 1 Fetish Equipment (deve atender Gnosis)"

    elif 'mystic acquisition' in nome.lower():
        efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"ignora_restricoes": True,
                                                     "origem": "discard_pile"}})
        desc = "Equipa qualquer Equipment do descarte (ignora restricoes)"

    # ── 13. Gifts que modificam GAUNTLET ──
    elif 'corrupting presence' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "caern",
                        "quantidade": 0, "params": {"atributos": ["gauntlet"],
                                                     "valor": 3, "duracao": "permanente"}})
        desc = "Aumenta Gauntlet de 1 Caern em +3"

    # ── 14. FALLBACK generico ──
    else:
        # Tenta inferir algo basico do texto
        if has_phrase(t, 'damage') and has_phrase(t, '+'):
            m = re.search(r'\+(\d+)\s*damage', t)
            d = int(m.group(1)) if m else 1
            efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": d})
            desc = f"Causar {d} de dano (inferido)"
        elif has_phrase(t, 'heal') or has_phrase(t, 'cura'):
            efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada", "quantidade": 3})
            desc = "Curar 3 (inferido)"
        elif has_phrase(t, '+1 rage'):
            efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"duracao": "permanente"}})
            desc = "+1 Rage (inferido)"
        elif has_phrase(t, 'cancel') or has_phrase(t, 'counter'):
            efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo", "quantidade": 0})
            desc = "Anular (inferido)"
        elif has_phrase(t, 'dodge') or has_phrase(t, 'avoid'):
            efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 1})
            desc = "Esquivar (inferido)"
        else:
            # Placeholder para revisao manual
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True,
                                                         "texto_original": texto[:120]}})
            desc = f"{nome} (REVISAO MANUAL NECESSARIA)"

    if not efeitos:
        return None

    modelo = {
        "id": json_id,
        "nome": nome,
        "tipo": "Gift",
        "modos": [{
            "descricao": desc,
            "efeitos": efeitos
        }],
        "_metadata": {
            "fonte": "gerador_gift_jsons",
            "card_id": card.id,
            "texto_original": texto,
            "keywords": card.keyword or "",
            "gnosis": gn,
            "rage": card.rage or 0,
            "health": card.health or 0,
            "precisa_revisao": True,
            "slug": slug
        }
    }

    return modelo


def main():
    dry_run = '--dry' in sys.argv
    apenas_id = None
    for arg in sys.argv:
        if arg.startswith('--id='):
            apenas_id = int(arg.split('=')[1])

    with app.app_context():
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        from rage_web.ext.database import db
        from rage_web.models.card import Card

        cards = Card.query.filter(Card.tipo.ilike('%gift%')).all()
        pendentes = [c for c in cards if (c.slug or f'card_{c.id}') not in CARTAS_EXEMPLO
                     and f'card_{c.id}' not in CARTAS_EXEMPLO]

        if apenas_id:
            pendentes = [c for c in pendentes if c.id == apenas_id]

        print(f'Gerando JSONs para {len(pendentes)} gifts...')
        gerados = 0
        erros = 0
        pulados = 0

        for card in pendentes:
            slug = slug_from_card(card)
            try:
                modelo = gerar_json(card, dry_run)
                if modelo is None:
                    print(f'  ⏭️  {card.name:<35s} (ID:{card.id}) — pulado (playtest/sem texto)')
                    pulados += 1
                    continue

                path = os.path.join(CARDS_DIR, f'{slug}.json')
                if dry_run:
                    print(f'  📄 {slug}.json — {card.name:<35s} (ID:{card.id}, Gn:{card.gnosis or 0})')
                else:
                    with open(path, 'w') as f:
                        json.dump(modelo, f, indent=2, ensure_ascii=False)
                    print(f'  ✅ {slug}.json — {card.name:<35s} (ID:{card.id}, Gn:{card.gnosis or 0})')
                gerados += 1

            except Exception as e:
                print(f'  ❌ {card.name:<35s} (ID:{card.id}) — ERRO: {e}')
                import traceback; traceback.print_exc()
                erros += 1

        print(f'\nResumo: {gerados} gerados, {pulados} pulados, {erros} erros de {len(pendentes)}')


if __name__ == '__main__':
    main()
