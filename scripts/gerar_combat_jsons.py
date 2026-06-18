#!/usr/bin/env python3
"""Gera JSONs de efeitos estruturados para Combat Actions que ainda não têm.

Examina cada Combat Action no banco sem JSON, analisa seu texto,
e gera um JSON de efeitos apropriado.

Uso:
    .venv/bin/python3 scripts/gerar_combat_jsons.py          # gerar todas
    .venv/bin/python3 scripts/gerar_combat_jsons.py --dry    # preview
    .venv/bin/python3 scripts/gerar_combat_jsons.py --id 325 # só uma carta
"""

import json, os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

CARDS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cards')


def slug_from_card(card) -> str:
    slug = card.slug or f'card_{card.id}'
    # Slugs muito longos (>40 chars) ou com formato feio
    # viram card_{id} para manter legibilidade
    if len(slug) > 40 or slug.startswith('if-played') or slug.startswith('combat-restricted'):
        return f'card_{card.id}'
    return slug


def texto_original(card) -> str:
    return (card.text or '').strip()


def damage_int(card) -> int:
    dmg = (card.damage or '').strip()
    try:
        return int(dmg)
    except ValueError:
        return 0


def gerar_json(card, dry_run=False):
    """Gera JSON estruturado para uma Combat Action."""
    slug = slug_from_card(card)
    nome = card.name
    texto = texto_original(card)
    texto_lower = texto.lower()
    dmg = damage_int(card)
    rage = card.rage

    # ── Skip playtest cards ──
    if 'playtesting' in texto_lower:
        return None

    modos = []

    # ── 1. CARDS DE ESQUIVA / DEFESA ──
    if 'dodge' in texto_lower and 'attack' in texto_lower and 'avoid' in texto_lower:
        # Dodge-like cards
        if 'all attacks' in texto_lower or 'all attack' in texto_lower:
            modos.append({
                "descricao": "Esquivar de todos os ataques",
                "efeitos": [{"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99}]
            })
        else:
            modos.append({
                "descricao": "Esquivar de 1 ataque",
                "efeitos": [{"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 1}]
            })

    # ── 2. BLOCK / DEFESA (cards com 'block' no texto, sem dano) ──
    elif 'back to back' in texto_lower:
        modos.append({
            "descricao": "Instinctive: Bloquear ate 5 dano entre ataques",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "criatura_aliada", "quantidade": 0,
                         "params": {"restricao": "block_5_damage", "duracao": "este_round"}}]
        })
    elif 'hand smite' in texto_lower:
        modos.append({
            "descricao": "Comprar 1 combat card + bloqueia dano de weapons",
            "efeitos": [
                {"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 1},
                {"tipo": "restringir", "condicao_alvo": "criatura_aliada", "quantidade": 0,
                 "params": {"restricao": "block_dano_weapons", "duracao": "este_round"}}
            ]
        })

    # ── 3. SIMPLE DAMAGE ──
    elif 'this indirect shot barely connects' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })
    elif 'this light swipe barely connects' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })
    elif 'flesh wound' in texto_lower and 'is all it takes' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'well-placed blow' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'tough, scraping blow' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'rend' in texto_lower and 'tear' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    # ── 4. CARDS COM DEBUFF ──
    elif 'eyes gouged' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano e vitima ataca aleatoriamente",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"restricao": "ataque_aleatorio", "duracao": "proximo_round"}}
            ]
        })

    elif 'organ puncture' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano e alvo nao inicia combate",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"tipo_acao": "iniciar_combate", "duracao": "ate_curar"}}
            ]
        })

    elif 'painful slash' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano e limita cartas de combate",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"restricao": "max_1_combat_card", "duracao": "ate_curar"}}
            ]
        })

    elif 'ribs crushed' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano e alvo nao pode blefar",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"restricao": "nao_pode_blefar", "duracao": "ate_curar"}}
            ]
        })

    elif 'whiplash' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano; ambos nao jogam gifts",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "impedir_acoes", "condicao_alvo": "todas_criaturas", "quantidade": 0,
                 "params": {"tipo_acao": "gift", "duracao": "resto_combate"}}
            ]
        })

    # ── 5. KAILINDO ──
    elif 'kailindo' in texto_lower and 'flying tiger' in texto_lower:
        modos.append({
            "descricao": "Kailindo: Causar 5 de dano (sem defesa no mesmo round)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 5}]
        })

    elif 'mantis form' in texto_lower:
        modos.append({
            "descricao": f"Kailindo: Causar {dmg} de dano (entra Crinos se nao estiver)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'nerve cluster' in texto_lower:
        modos.append({
            "descricao": f"Kailindo: Causar {dmg} de dano + vitima tem Rage=0",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga", "quantidade": -99,
                 "params": {"duracao": "resto_combate"}}
            ]
        })

    elif 'passive aggression' in texto_lower:
        modos.append({
            "descricao": "Kailindo: Se oponente Rg<=5, afetado",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                         "params": {"restricao": "passive_aggression", "duracao": "este_round"}}]
        })

    # ── 6. SPECIAL EFFECTS ──
    elif 'get medieval' in texto_lower:
        modos.append({
            "descricao": "Vinganca quando packmate morto",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 6,
                         "params": {"condicao": "packmate_morto_por_alvo"}}]
        })

    elif 'charge' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano, entra Crinos, ataques nao bloqueaveis",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_aliada", "quantidade": 0,
                 "params": {"restricao": "ataques_nao_bloqueaveis", "duracao": "este_round"}}
            ]
        })

    elif 'spite' in texto_lower:
        modos.append({
            "descricao": "Copia dano de Combat Action de Rival",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 1,
                         "params": {"especial": "copia_dano_de_rival"}}]
        })

    elif 'bitter blow' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (inequivavel se contra rival)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg,
                         "params": {"inequivavel_se_rival": True}}]
        })

    elif 'tag teaming' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (+2 se outro Tag Teaming no combate)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg,
                         "params": {"bonus_por_copia": 2}}]
        })

    elif 'harry' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (multiplas copias no deck)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'riposte' in texto_lower:
        modos.append({
            "descricao": "Requires Klaive: Parry + dano 1",
            "efeitos": [
                {"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 1,
                 "params": {"condicao": "equipado_klaive"}},
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 1}
            ]
        })

    elif 'sacrifice' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano, sem acao no prox round",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "impedir_acoes", "condicao_alvo": "criatura_aliada", "quantidade": 0,
                 "params": {"tipo_acao": "combat_action", "duracao": "proximo_round"}}
            ]
        })

    elif 'sucker punch' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (requer: sem weapon)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg,
                         "params": {"requer_sem_weapon": True}}]
        })

    elif 'back to back' in texto_lower:
        modos.append({
            "descricao": "Instinctive: Bloquear ate 5 dano entre ataques",
            "efeitos": [{"tipo": "bloquear", "condicao_alvo": "criatura_aliada", "quantidade": 5}]
        })

    elif 'hand smite' in texto_lower:
        modos.append({
            "descricao": "Draw combat card + blok dano de weapons",
            "efeitos": [
                {"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 1},
                {"tipo": "bloquear", "condicao_alvo": "criatura_aliada", "quantidade": 99,
                 "params": {"filtro": "dano_de_weapons"}}
            ]
        })

    elif 'powerful foot' in texto_lower:
        modos.append({
            "descricao": f"Instinctive: Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'bonded in blood' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano + redirect para packmate leal",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'dragon emerges from mountain' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano + cega oponente",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"restricao": "cego", "duracao": "proximo_round"}}
            ]
        })

    elif 'great blow' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (nao no R1, sem acao no prox se sem klaive)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg,
                         "params": {"condicao": "nao_primeiro_round"}}]
        })

    elif 'slam, bam' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (+2 se Rg>=7, requer nao blefado)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'take away the land' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'trust me' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (so se mutual loyalty)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'shoulder to shoulder' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (face up, nao bluffavel)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'point man' in texto_lower:
        modos.append({
            "descricao": "Permite feint para criatura leal",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "criatura_aliada", "quantidade": 0,
                         "params": {"restricao": "pode_feint", "duracao": "este_round"}}]
        })

    elif 'jab' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano + oponentes perdem Fast Striking",
            "efeitos": [
                {"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg},
                {"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                 "params": {"restricao": "sem_fast_striking", "duracao": "este_round"}}
            ]
        })

    elif 'superior reach' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (inequivavel com Firearm/Iksakku)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'toss' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (+dano se descartar Ally/Equipment Fianna)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'counting coup' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (+1 Rage se Wendigo, Fast Striking)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'falling tempest' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'bonk2' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano; se 0 dano, remove topo do combat deck",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'face pounding' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (pode cancelar remocao de jogo como Combat Event)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'shut up and die' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (pode remover do jogo)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'death rattle' in texto_lower:
        modos.append({
            "descricao": "Mata oponente frenetico ja ferido",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 1,
                         "params": {"condicao": "frenetico_e_ja_ferido_mortal"}}]
        })

    elif 'blood lust' in texto_lower:
        modos.append({
            "descricao": f"Instinctive: Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'sever' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'thrash' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'vicious assault' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano (+3 se Rg>=8)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'mangle' in texto_lower:
        modos.append({
            "descricao": "Crinos only: Causar 6 de dano, nao bluffavel, Slow, sem acoes",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 6}]
        })

    elif 'addannu luku daku' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    elif 'one as one army' in texto_lower:
        modos.append({
            "descricao": f"Causar {dmg} de dano",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
        })

    # ── 7. EVENTOS / COMBAT EVENTS ──
    elif 'no fooling' in texto_lower:
        modos.append({
            "descricao": "Previne blefe no round",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "todas_criaturas", "quantidade": 0,
                         "params": {"restricao": "nao_pode_blefar", "duracao": "este_round"}}]
        })

    elif 'cub' in texto_lower and 'cry' in texto_lower:
        modos.append({
            "descricao": "Termina combate (cub cry)",
            "efeitos": [{"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 99,
                         "params": {"termina_combate": True}}]
        })

    elif 'activate torpedoes' in texto_lower:
        modos.append({
            "descricao": "Ativar torpedos",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 4}]
        })

    elif 'circle of death' in texto_lower:
        modos.append({
            "descricao": "Circulo da morte",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 3}]
        })

    elif 'drag beneath' in texto_lower:
        modos.append({
            "descricao": "Arrastar para baixo",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2}]
        })

    elif 'furocity' in texto_lower:
        modos.append({
            "descricao": "Furocity",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2}]
        })

    elif 'equal ground' in texto_lower:
        modos.append({
            "descricao": "Igualdade de terreno",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "todas_criaturas", "quantidade": 0,
                         "params": {"restricao": "equal_ground", "duracao": "este_round"}}]
        })

    elif 'flow like water' in texto_lower:
        modos.append({
            "descricao": "Flua como agua",
            "efeitos": [{"tipo": "fugir", "condicao_alvo": "criatura_aliada", "quantidade": 1}]
        })

    elif 'ghost flame' in texto_lower:
        modos.append({
            "descricao": "Chama fantasma",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 7}]
        })

    elif 'gnosis bomb' in texto_lower:
        modos.append({
            "descricao": "Bomba de Gnosis (dano X = Gnosis do usuario)",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                         "params": {"dano_igual_gnosis": True}}]
        })

    elif 'lightning bolt' in texto_lower:
        modos.append({
            "descricao": "Raio",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 6}]
        })

    elif 'black wind' in texto_lower:
        modos.append({
            "descricao": "Vento negro",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "todas_criaturas", "quantidade": 0,
                         "params": {"restricao": "black_wind", "duracao": "este_round"}}]
        })

    elif 'high war' in texto_lower:
        modos.append({
            "descricao": "Guerra alta",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 4}]
        })

    elif 'low war' in texto_lower and 'a' in slug:
        modos.append({
            "descricao": "Guerra baixa A",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2}]
        })

    elif 'low war' in texto_lower and 'b' in slug:
        modos.append({
            "descricao": "Guerra baixa B",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2}]
        })

    elif 'sentai action' in texto_lower:
        modos.append({
            "descricao": "Acao Sentai",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 3}]
        })

    elif 'yoke the beast' in texto_lower:
        modos.append({
            "descricao": "Dominar a besta",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                         "params": {"restricao": "yoke_the_beast", "duracao": "este_round"}}]
        })

    elif 'combat reload' in texto_lower:
        modos.append({
            "descricao": "Combat Restricted: Comprar 3 combat cards",
            "efeitos": [{"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 3}]
        })

    elif 'generational jaw' in texto_lower:
        modos.append({
            "descricao": "Alvo nao recruta aliados ate curar (se 7th Gen)",
            "efeitos": [{"tipo": "restringir", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                         "params": {"restricao": "nao_recruta_aliados", "duracao": "ate_curar"}}]
        })

    elif 'frenzy beatdown' in texto_lower:
        modos.append({
            "descricao": "Se frenetico: descarta random combat card",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 2}]
        })

    elif 'teste combat event' in texto_lower:
        modos.append({
            "descricao": "Test card",
            "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 0}]
        })

    # ── 8. GENERIC FALLBACK (baseado em damage) ──
    else:
        if dmg > 0:
            modos.append({
                "descricao": f"Causar {dmg} de dano",
                "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": dmg}]
            })
        else:
            modos.append({
                "descricao": f"{nome}",
                "efeitos": [{"tipo": "dano", "condicao_alvo": "criatura_inimiga", "quantidade": 0,
                             "params": {"texto_original": texto[:80]}}]
            })

    if not modos:
        return None

    # O id interno do JSON deve ser o slug original do card
    # (ou f'card_{id}'), pois o motor busca por esse valor.
    # O nome do arquivo pode ser diferente (slug limpo).
    json_id = card.slug or f'card_{card.id}'
    modelo = {
        "id": json_id,
        "nome": nome,
        "tipo": "Combat Action",
        "modos": modos,
        "_metadata": {
            "fonte": "gerador_combat_actions",
            "card_id": card.id,
            "texto_original": texto,
            "keywords": card.keyword or "",
            "damage": str(dmg) if dmg else "",
            "rage": rage,
            "gnosis": card.gnosis,
            "health": card.health,
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

        cards = Card.query.filter(Card.tipo.ilike('%combat%')).all()
        pendentes = [c for c in cards if (c.slug or f'card_{c.id}') not in CARTAS_EXEMPLO
                     and 'playtest' not in (c.text or '').lower()]

        if apenas_id:
            pendentes = [c for c in pendentes if c.id == apenas_id]

        print(f'Gerando JSONs para {len(pendentes)} combat actions...')
        gerados = 0
        erros = 0
        pulados = 0

        for card in pendentes:
            slug = slug_from_card(card)
            try:
                modelo = gerar_json(card, dry_run)
                if modelo is None:
                    print(f'  ⏭️  {card.name:<35s} (ID:{card.id}) — pulado')
                    pulados += 1
                    continue

                path = os.path.join(CARDS_DIR, f'{slug}.json')
                if dry_run:
                    print(f'  📄 {slug}.json — {len(json.dumps(modelo, indent=2))} bytes')
                else:
                    with open(path, 'w') as f:
                        json.dump(modelo, f, indent=2, ensure_ascii=False)
                    print(f'  ✅ {slug}.json — {card.name} (ID:{card.id})')
                gerados += 1

            except Exception as e:
                print(f'  ❌ {card.name:<35s} (ID:{card.id}) — ERRO: {e}')
                erros += 1

        print(f'\nResumo: {gerados} gerados, {pulados} pulados, {erros} erros de {len(pendentes)}')


if __name__ == '__main__':
    main()
