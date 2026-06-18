#!/usr/bin/env python3
"""Gera JSONs de efeitos estruturados para Rites que ainda não têm.

Examina cada Rite no banco sem JSON, analisa seu texto,
e gera um JSON de efeitos apropriado.

Uso:
    .venv/bin/python3 scripts/gerar_rite_jsons.py          # gerar todas
    .venv/bin/python3 scripts/gerar_rite_jsons.py --dry    # preview
    .venv/bin/python3 scripts/gerar_rite_jsons.py --id 101 # só uma carta
"""

import json, os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

CARDS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cards')


def slug_from_card(card) -> str:
    slug = card.slug or f'card_{card.id}'
    if len(slug) > 40:
        return f'card_{card.id}'
    return slug


def _txt(t):
    return (t or '').lower()


def has_phrase(texto_lower, *phrases):
    return any(p in texto_lower for p in phrases)


def gerar_json(card, dry_run=False):
    """Gera JSON estruturado para um Rite."""
    slug = slug_from_card(card)
    nome = card.name
    texto = texto_original(card)
    t = _txt(texto)

    # ── Skip playtest / empty text ──
    if not texto or 'playtesting' in t or 'teste rite' in t:
        return None
    if nome.lower().startswith('rite ') and 'playtesting' in texto.lower():
        return None

    json_id = card.slug or f'card_{card.id}'
    desc = nome
    efeitos = []

    # ── 1. BUFFS DE ATRIBUTO ──
    if 'rite of the stone' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 1, "params": {"duracao": "permanente"}})
        efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                        "quantidade": 1, "params": {"duracao": "permanente"}})
        desc = "+1 Rage, +1 Gnosis (permanente)"

    elif "ocean's peace" in nome.lower() or "ocean s peace" in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente", "condicao": "vs_nao_aquaticos"}})
        efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente", "condicao": "vs_nao_aquaticos"}})
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 2, "params": {"duracao": "permanente", "condicao": "vs_nao_aquaticos"}})
        desc = "+2 Rage/Gnosis/Health vs nao-Aquaticos"

    elif 'eternal dragon form' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                        "quantidade": 6, "params": {"duracao": "permanente", "rage_fixo": True}})
        efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                        "quantidade": 9, "params": {"duracao": "permanente", "gnosis_fixo": True}})
        efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                        "quantidade": 6, "params": {"duracao": "permanente", "health_fixo": True}})
        desc = "Rage=6, Gnosis=9, Health=6 (Crinos)"

    elif 'rite of fear' in nome.lower():
        efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                        "quantidade": -2, "params": {"duracao": "ate_fim_turno"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"restricao": "sem_firearms", "duracao": "ate_fim_turno"}})
        desc = "-2 Rage inimigos, sem Firearms"

    # ── 2. CANCELAMENTO ──
    elif 'the vigil forsaken' in nome.lower():
        efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo",
                        "quantidade": 0, "params": {"tipo_alvo": "rite", "remove_do_jogo": True}})
        desc = "Cancela qualquer Rite em jogo"

    elif 'rite of forgetting' in nome.lower():
        efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo",
                        "quantidade": 0, "params": {"tipo_alvo": "rite/gift_anexado", "remove_do_jogo": True}})
        desc = "Cancela Rite ou Gift anexado ao usuario"

    # ── 3. DESCARTE / BURN ──
    elif 'burn the library' in nome.lower():
        efeitos.append({"tipo": "descartar_metade_mao", "condicao_alvo": "jogador_inimigo",
                        "quantidade": 0, "params": {"descarta_do_topo_sept": 3}})
        desc = "Descarta top 3 cartas do sept deck alvo"

    elif 'devour the dead' in nome.lower():
        efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"cura_todo_dano": True, "condicao": "packmate_morto"}})
        desc = "Cura todo dano de um packmate (se Fomori matou)"

    # ── 4. DRAW / COMPRA ──
    elif 'call the four winds' in nome.lower():
        efeitos.append({"tipo": "destruir", "condicao_alvo": "carta_em_jogo",
                        "quantidade": 0, "params": {"tipo_alvo": "event_nao_totem", "por_bastet_gurahl_theurge": True}})
        desc = "Descarta Events nao-Totem (por Bastet/Gurahl/Theurge)"

    # ── 5. SEARCH / BUSCA ──
    elif 'baptism of fire' in nome.lower():
        efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                        "quantidade": 0, "params": {"busca_no_deck": True, "tipo_busca": "garou_character"}})
        desc = "Buscar Garou Character do deck/mao"

    elif "allies' gateway" in nome.lower() or "allies gateway" in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "usa_outro_caern", "duracao": "permanente"}})
        desc = "Usar beneficios de outro Caern (com consentimento)"

    # ── 6. DISCARD PILE / GRAVEYARD ──
    elif 'blood omen' in nome.lower():
        efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                        "quantidade": 0, "params": {"busca_no_sept_deck": True, "look_top_7": True}})
        desc = "Olhar top 7 do sept deck e pegar 1 (apos matar Victim)"

    # ── 7. EQUIP / BINDING ──
    elif 'rite of binding' in nome.lower():
        efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"tipo": "spirit_ally", "apos_derrotar": True}})
        desc = "Bind spirit ally recem-derrotado"

    elif 'rite of investiture' in nome.lower():
        efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"tipo": "ally", "apos_moot": True}})
        desc = "Selecionar 1 Ally apos Moot bem-sucedido"

    elif 'yang-attuned' in nome.lower() or 'yang attuned' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["combat_hand_size"],
                                                     "valor": 1, "duracao": "permanente"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "recruta_human_ally", "duracao": "permanente"}})
        desc = "Recruta Human Ally, +1 combat hand"

    elif 'yin-attuned' in nome.lower() or 'yin attuned' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["sept_hand_size"],
                                                     "valor": 1, "duracao": "permanente"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "recruta_spirit_ally", "duracao": "permanente"}})
        desc = "Recruta Spirit Ally, +1 sept hand"

    # ── 8. RENOWN / MOOT ──
    elif 'stone of scorn' in nome.lower():
        efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"tipo_acao": "votar", "duracao": "ate_desafio_aceito"}})
        desc = "Alvo perde direito a voto ate aceitar desafio"

    elif 'rite of wisdom' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["renown_moot"],
                                                     "valor": 3, "duracao": "este_moot"}})
        desc = "+3 Renown para votacao de Moot"

    elif 'satire song' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"atributos": ["renown"],
                                                     "valor": -99, "duracao": "permanente",
                                                     "condicao": "renome_maior"}})
        desc = "Vitima perde todo Renown (se Galliard tem mais)"

    # ── 9. COMBAT ──
    elif 'rite of summoning' in nome.lower():
        efeitos.append({"tipo": "cancelar_acao", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"forca_alpha_atacar_usuario": True}})
        desc = "Forca alpha a declarar ataque contra usuario"

    elif 'rite of wounding' in nome.lower():
        efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"nao_pode_regenerar": True,
                                                     "duracao": "ate_entrar_em_combate"}})
        desc = "Alvo nao regenera ate entrar em combate"

    elif 'rite of glory' in nome.lower():
        efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"zona": "hunting_grounds", "antes_alpha": True}})
        desc = "Entra no Hunting Grounds antes de alphas"

    # ── 10. OUTROS ──
    elif 'unholy sacrifice' in nome.lower():
        efeitos.append({"tipo": "remover_do_jogo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"remove_criatura_do_pack": True}})
        desc = "Remove character do pack (inicio do jogo) do jogo"

    elif 'lone wolf' in nome.lower():
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"restricao": "sem_acoes_pack", "duracao": "permanente"}})
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"restricao": "sem_acoes_pack", "duracao": "permanente"}})
        desc = "Usuario nao faz pack actions; oponentes tambem nao"

    elif 'summon the rain' in nome.lower():
        efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "jogador_inimigo",
                        "quantidade": 0, "params": {"tipo_acao": "pack_actions", "duracao": "ate_fim_turno"}})
        desc = "Outros packs nao usam pack actions"

    elif 'goblin chrysalis' in nome.lower():
        efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"tipo": "fomori_ally", "origem": "victory_pile"}})
        desc = "Transforma criatura do VP em Fomori Ally"

    elif 'akuma' in nome.lower():
        efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"atributos": ["keyword"],
                                                     "valor": 0, "novas_keywords": "Cult.Infernalist"}})
        efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"cura_dano_agravado": True}})
        desc = "Ganha Cult.Infernalist, cura dano agravado"

    # ── 11. FALLBACK GENERICO ──
    else:
        if has_phrase(t, 'heal', 'cura', 'regenera'):
            efeitos.append({"tipo": "curar", "condicao_alvo": "criatura_aliada",
                            "quantidade": 3})
            desc = "Curar (inferido)"
        elif has_phrase(t, 'cancel', 'counter', 'anular'):
            efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo",
                            "quantidade": 0})
            desc = "Anular (inferido)"
        elif has_phrase(t, '+1 rage', '+1 gnosis', '+1 health'):
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["rage", "gnosis", "health"],
                                                         "valor": 1, "duracao": "permanente"}})
            desc = "+1 atributo (inferido)"
        elif has_phrase(t, 'discard'):
            efeitos.append({"tipo": "descarte", "condicao_alvo": "jogador_inimigo",
                            "quantidade": 1})
            desc = "Descartar (inferido)"
        elif has_phrase(t, 'search', 'look at', 'busca'):
            efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"busca_no_deck": True}})
            desc = "Busca (inferido)"
        elif has_phrase(t, 'vote', 'moot', 'junta'):
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["votos"],
                                                         "valor": 1, "duracao": "este_moot"}})
            desc = "Votacao (inferido)"
        else:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True,
                                                         "texto_original": (texto or '')[:120]}})
            desc = f"{nome} (REVISAO MANUAL NECESSARIA)"

    if not efeitos:
        return None

    modelo = {
        "id": json_id,
        "nome": nome,
        "tipo": "Rite",
        "modos": [{
            "descricao": desc,
            "efeitos": efeitos
        }],
        "_metadata": {
            "fonte": "gerador_rite_jsons",
            "card_id": card.id,
            "texto_original": texto,
            "keywords": card.keyword or "",
            "gnosis": card.gnosis or 0,
            "rage": card.rage or 0,
            "health": card.health or 0,
            "precisa_revisao": True,
            "slug": slug
        }
    }

    return modelo


def texto_original(card) -> str:
    return (card.text or '').strip()


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

        cards = Card.query.filter(Card.tipo.ilike('%rite%')).all()
        pendentes = [c for c in cards if (c.slug or f'card_{c.id}') not in CARTAS_EXEMPLO
                     and f'card_{c.id}' not in CARTAS_EXEMPLO]

        if apenas_id:
            pendentes = [c for c in pendentes if c.id == apenas_id]

        print(f'Gerando JSONs para {len(pendentes)} rites...')
        gerados = 0
        erros = 0
        pulados = 0

        for card in pendentes:
            slug = slug_from_card(card)
            try:
                modelo = gerar_json(card, dry_run)
                if modelo is None:
                    print(f'  ⏭️  {card.name:<45s} (ID:{card.id}) — pulado (playtest/sem texto)')
                    pulados += 1
                    continue

                path = os.path.join(CARDS_DIR, f'{slug}.json')
                if dry_run:
                    print(f'  📄 {slug}.json — {card.name:<45s} (ID:{card.id})')
                else:
                    with open(path, 'w') as f:
                        json.dump(modelo, f, indent=2, ensure_ascii=False)
                    print(f'  ✅ {slug}.json — {card.name:<45s} (ID:{card.id})')
                gerados += 1

            except Exception as e:
                print(f'  ❌ {card.name:<45s} (ID:{card.id}) — ERRO: {e}')
                import traceback; traceback.print_exc()
                erros += 1

        print(f'\nResumo: {gerados} gerados, {pulados} pulados, {erros} erros de {len(pendentes)}')


if __name__ == '__main__':
    main()
