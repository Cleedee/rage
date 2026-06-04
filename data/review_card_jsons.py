#!/usr/bin/env python3
"""Gera JSONs de efeitos revisados baseados no texto das cartas.

Versao 2: analise muito mais completa com padroes para cada tipo de carta.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rage_web import create_app
from rage_web.ext.database import db
from rage_web.models.card import Card as CardModel

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'cards')

# =========================================================================
# PADROES DE TEXTO PARA CADA TIPO DE EFEITO
# =========================================================================

def _all_patterns(text: str, keywords: str, tipo: str, damage: str,
                  rage: int, gnosis: int) -> list[dict]:
    """Retorna todos os modos detectados no texto."""
    tl = text.lower()
    kw = keywords.lower()
    modos = []

    # ---- COMBAT ACTIONS ----
    if tipo == 'Combat Action':
        # Dano basico
        try:
            dano_val = int(damage)
        except (ValueError, TypeError):
            dano_val = 0

        if dano_val > 0:
            conds = []
            if 'fast striking' in kw:
                conds.append('ataque_rapido')
            if 'instinctive' in kw:
                conds.append('instintivo')
            if 'not frenzied' in tl:
                conds.append('nao_frenetico')

            modos.append({
                'descricao': f'Causar {dano_val} de dano'
                             + (f' ({", ".join(conds)})' if conds else ''),
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': dano_val,
                }],
                'condicao_uso': '; '.join(conds) if conds else '',
            })

        # Dodge (modal: 1 attack OR 2 attacks)
        if kw == 'dodge' or 'dodge' in tl:
            dodge_count = 2 if 'dodge 2' in tl or 'dodge two' in tl else 1
            # Fancy Footwork: pode escolher entre esquivar 1 ou 2
            if 'either' in tl and 'or' in tl:
                modos.append({
                    'descricao': 'Esquivar de 1 ataque',
                    'efeitos': [{
                        'tipo': 'fugir',
                        'condicao_alvo': 'criatura_aliada',
                        'quantidade': 1,
                    }],
                })
                modos.append({
                    'descricao': 'Esquivar de 2 ataques',
                    'efeitos': [{
                        'tipo': 'fugir',
                        'condicao_alvo': 'criatura_aliada',
                        'quantidade': 2,
                    }],
                })
            else:
                modos.append({
                    'descricao': f'Esquivar de {dodge_count} ataque(s)',
                    'efeitos': [{
                        'tipo': 'fugir',
                        'condicao_alvo': 'criatura_aliada',
                        'quantidade': dodge_count,
                    }],
                })

        # Modificadores de rage (Bitch Slap: wounded by this, gains 1 Rage)
        if 'gains 1 rage' in tl or 'gain 1 rage' in tl or '+1 rage' in tl:
            modos.append({
                'descricao': 'Alvo ganha +1 de Rage',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 1,
                }],
            })

        # Reduce rage cost next round
        if '-1 Rage' in text or 'at -1 Rage' in tl:
            modos.append({
                'descricao': 'Reduzir custo de Rage em 1',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': -1,
                }],
            })

        # Cancela acao do oponente se rage 1
        if 'rage 1, it does not take effect' in tl:
            modos.append({
                'descricao': 'Anular acao de Rage 1 do oponente',
                'efeitos': [{
                    'tipo': 'anular',
                    'condicao_alvo': 'criatura_inimiga',
                }],
            })

        # Immediately flee (Run Like Hell)
        if 'flees, exiting combat' in tl or 'immediately flees' in tl:
            modos.append({
                'descricao': 'Fugir do combate',
                'efeitos': [{
                    'tipo': 'fugir',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 1,
                }],
            })

        # Danos secundarios por oponente (Full Auto bonus with Firearm)
        if 'firearm' in tl and 'additional' in tl:
            modos.append({
                'descricao': 'Bonus se tiver Firearm',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

        # Instinctive (pode jogar mesmo se nao puder jogar acao de combate)
        if 'instinctive' in kw:
            if not any('instintivo' in (m.get('condicao_uso') or '') for m in modos):
                pass  # Ja tratamos como condicao acima

        # No text or only keywords
        if not text.strip():
            modos.append({
                'descricao': f'Causar {dano_val} de dano',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': dano_val or 1,
                }],
            })

    # ---- COMBAT EVENTS ----
    elif tipo == 'Combat Event':
        # Hunting Party: bonus when attacking
        if 'declaring an attack' in tl:
            modos.append({
                'descricao': 'Bonus ao declarar ataque',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

        # Attacking the Wyrm: choose pack members
        if 'choose any or all' in tl and 'pack' in tl:
            modos.append({
                'descricao': 'Todos do pack atacam junto',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 3,
                }],
            })

        # Taking the Death Blow: redirect wound
        if 'mortal wound' in tl and 'take the wound' in tl:
            modos.append({
                'descricao': 'Redirecionar ferimento mortal',
                'efeitos': [{
                    'tipo': 'curar',
                    'condicao_alvo': 'criatura_aliada_ferida',
                    'quantidade': 999,
                }],
            })

        # Cornered Rat: limited frenzy
        if 'frenzy' in kw or 'frenzy' in tl:
            modos.append({
                'descricao': 'Entrar em frenesi limitado',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 3,
                }],
            })

        # Rally to Battle: draw cards
        if 'draw' in tl and 'combat card' in tl:
            m = re.search(r'draw\s+(\d+)\s+combat card', tl)
            qtd = int(m.group(1)) if m else 3
            modos.append({
                'descricao': f'Comprar {qtd} carta(s) de combate',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_combate',
                    'quantidade': qtd,
                }],
            })

        # Gang Beating: draw bonus when outnumbered
        if 'draw' in tl and 'additional combat card' in tl:
            modos.append({
                'descricao': 'Comprar carta extra quando em desvantagem',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_combate',
                    'quantidade': 1,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Ativar evento de combate',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

    # ---- ACTION / EVENT ----
    elif tipo in ('Action', 'Event'):
        # Friends in High Places: end combat
        if 'end any one combat' in tl:
            modos.append({
                'descricao': 'Encerrar combate',
                'efeitos': [{
                    'tipo': 'fugir',
                    'condicao_alvo': 'todas_criaturas',
                }],
            })

        # Sneak Attack: engage any character
        if 'circumvent' in tl or 'sneak' in tl:
            modos.append({
                'descricao': 'Atacar qualquer personagem',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

        # Checking the Classifieds: search for Territory
        if 'territory' in tl and 'hand' in tl:
            modos.append({
                'descricao': 'Buscar Territorio do deck',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Recycle: draw sept + arrange deck
        if 'draw a sept card' in tl or ('draw' in tl and 'sept' in tl):
            modos.append({
                'descricao': 'Comprar carta de sept',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })
            if 'put up to' in tl:
                modos.append({
                    'descricao': 'Organizar deck (colocar cartas no topo)',
                    'efeitos': [{
                        'tipo': 'comprar',
                        'condicao_alvo': 'discartes',
                        'quantidade': 2,
                    }],
                })

        # The Tide: Second Sign - search for Human
        if 'search their sept deck' in tl and 'human' in tl:
            modos.append({
                'descricao': 'Buscar Humano no deck de sept',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Clashing Boom Boom / Wendigo: Pack Totem
        if 'pack totem' in kw:
            modos.append({
                'descricao': 'Totem do pack',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 2,
                }],
            })

        # Wendigo: increase combat hand
        if 'increase your combat hand' in tl:
            modos.append({
                'descricao': 'Aumentar mao de combate',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_combate',
                    'quantidade': 1,
                }],
            })

        # Visit from White Father: rally
        if 'rally' in tl and 'troops' in tl:
            modos.append({
                'descricao': 'Reunir tropas',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_combate',
                    'quantidade': 2,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Ativar evento',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

    # ---- GIFT ----
    elif tipo == 'Gift':
        # Blur of the Milky Eye: can't redirect attack
        if 'redirected' in tl or 'step in' in tl:
            modos.append({
                'descricao': 'Ataque nao pode ser redirecionado',
                'efeitos': [{
                    'tipo': 'redirecionar',
                    'condicao_alvo': 'criatura_aliada',
                }],
            })

        # Catfeet: dodge all
        if 'dodge' in tl or 'nimble' in tl:
            modos.append({
                'descricao': 'Esquivar de todos os ataques',
                'efeitos': [{
                    'tipo': 'fugir',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 3,
                }],
            })

        # Knife Wind: 1 damage
        m = re.search(r'causing\s+(\d+)\s+damage', tl)
        if m:
            qtd = int(m.group(1))
            modos.append({
                'descricao': f'Causar {qtd} de dano',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': qtd,
                }],
            })

        # Sense Prey: reveal top 5
        if 'reveal the top' in tl and 'victims' in tl:
            modos.append({
                'descricao': 'Revelar topo do deck e buscar Vitimas',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 5,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Usar Gift (gnosis {gnosis})',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': gnosis,
                }],
            })

    # ---- EQUIPMENT ----
    elif tipo == 'Equipment':
        # Flak Jacket: armor
        if 'armor' in kw or 'armor' in tl:
            modos.append({
                'descricao': 'Bloquear ataque (armadura)',
                'efeitos': [{
                    'tipo': 'curar',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 4,
                }],
            })

        # Weapons / Firearms
        if 'weapon' in kw or 'firearm' in kw:
            modos.append({
                'descricao': 'Usar arma (permite acoes de combate)',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

        # Sniper Rifle: ranged attack outside combat
        if 'sniper' in tl or 'cannot be used in combat' in tl:
            modos.append({
                'descricao': 'Ataque a distancia (fora de combate)',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 3,
                }],
            })

        # War Lodge: discard spirit for buff
        if 'discard' in tl and 'spirit' in tl:
            modos.append({
                'descricao': 'Descartar espirito para bonus de combate',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 3,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Usar equipamento (gnosis {gnosis})',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': gnosis or 1,
                }],
            })

    # ---- ALLY ----
    elif tipo == 'Ally':
        # Arms Dealer: search for firearm
        if 'search your sept deck' in tl and 'firearm' in tl:
            modos.append({
                'descricao': 'Buscar Firearm no deck de sept',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Dreamspeaker Mage: cancel gift / step sideways
        if 'cancel' in tl and 'gift' in tl:
            modos.append({
                'descricao': 'Anular Gift',
                'efeitos': [{
                    'tipo': 'anular',
                    'condicao_alvo': 'discartes',
                }],
            })
        if 'step sideways' in tl:
            modos.append({
                'descricao': 'Passar ao lado (umbra)',
                'efeitos': [{
                    'tipo': 'fugir',
                    'condicao_alvo': 'criatura_aliada',
                }],
            })

        # Junkyard Dog: scrounge equipment
        if 'scrounge' in tl and 'equipment' in tl:
            modos.append({
                'descricao': 'Procurar Equipamento',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Kinfolk Small Town Cop: jail
        if 'jail' in tl or 'put in jail' in tl:
            modos.append({
                'descricao': 'Prender personagem',
                'efeitos': [{
                    'tipo': 'tapar',
                    'condicao_alvo': 'criatura_inimiga',
                }],
            })

        # Flame Spirit: burn out for damage
        if 'burn itself out' in tl:
            m = re.search(r'damage\s+(\d+)\s+attack', tl)
            qtd = int(m.group(1)) if m else 3
            modos.append({
                'descricao': f'Queimar-se em ataque de {qtd} de dano',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': qtd,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Usar Ally (rage {rage})',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': rage or 1,
                }],
            })

    # ---- ENEMY ----
    elif tipo == 'Enemy':
        # Big Game Hunter: armed
        if 'firearm' in kw or 'armed' in tl:
            modos.append({
                'descricao': 'Atacar com arma de fogo',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': rage or 2,
                }],
            })

        # Endron Security Team: unique, guards other Pentex
        if 'no other pentex enemy may be attacked' in tl:
            modos.append({
                'descricao': 'Proteger outros Pentex',
                'efeitos': [{
                    'tipo': 'curar',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 2,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Atacar (rage {rage})',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': rage or 2,
                }],
            })

    # ---- VICTIM ----
    elif tipo == 'Victim':
        # Street Bum: counteracts Mass Pollution
        if 'counteract' in tl:
            modos.append({
                'descricao': 'Neutralizar poluicao',
                'efeitos': [{
                    'tipo': 'curar',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 1,
                }],
            })

        # Suburban High School Kid: pack defend
        if 'pack defend' in tl:
            modos.append({
                'descricao': 'Defender em grupo',
                'efeitos': [{
                    'tipo': 'curar',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 2,
                }],
            })

        # Child Soldier: armed
        if 'firearm' in kw or '9mm' in tl:
            modos.append({
                'descricao': 'Atacar com 9mm',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': rage or 1,
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Usar Victim (health {rage})',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 1,
                }],
            })

    # ---- CHARACTER / TERRITORY / QUEST ----
    elif tipo.startswith('Character') or tipo == 'Territory' or tipo == 'Quest':
        # Dharma Bum: -2 Gnosis to opponents
        if '-2 Gnosis' in text or '-2 gnosis' in tl:
            modos.append({
                'descricao': 'Oponentes sofrem -2 Gnosis',
                'efeitos': [{
                    'tipo': 'modificar_gnosis',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': -2,
                }],
            })

        # Roger Daly: destroy guns/techno-equipment
        if 'destroy' in tl and 'equipment' in tl:
            modos.append({
                'descricao': 'Destruir equipamento do oponente',
                'efeitos': [{
                    'tipo': 'destruir',
                    'condicao_alvo': 'criatura_inimiga',
                }],
            })

        # Gnosis bonus per equipment (Haunts)
        if '+1 gnosis' in tl and 'equipment' in tl:
            modos.append({
                'descricao': 'Bonus de Gnosis por equipamento',
                'efeitos': [{
                    'tipo': 'modificar_gnosis',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 1,
                }],
            })

        # Haunts-the-Skyline: equipment = fetish
        if 'all equipment he possesses is considered fetish' in tl:
            modos.append({
                'descricao': 'Equipamentos sao Fetishes',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 1,
                }],
            })

        # Syntax: -2 Rage to Pentex enemies
        if 'pentex' in tl and '-2' in tl and 'rage' in tl:
            modos.append({
                'descricao': 'Reduzir Rage de Pentex inimigos',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': -2,
                }],
            })

        # Firyal: gains weapon if played low-rage attack
        if 'weapon' in tl and 'rage' in tl:
            modos.append({
                'descricao': 'Ganhar arma se ataque de Rage <=2',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 2,
                }],
            })

        # Quari Filth: steal from discard
        if 'target a combat card in' in tl:
            modos.append({
                'descricao': 'Roubar carta de combate do descarte',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'discartes',
                    'quantidade': 1,
                }],
            })

        # Blood-on-the-Wind: +1 Rage / gain Rage
        if '+1 Rage' in text or ('gain +1' in tl and 'rage' in tl):
            modos.append({
                'descricao': 'Bonus de Rage para aliados',
                'efeitos': [{
                    'tipo': 'modificar_rage',
                    'condicao_alvo': 'criatura_aliada',
                    'quantidade': 1,
                }],
            })

        # Old Storm-Chaser: +1 sept hand size
        if 'sept hand size' in tl:
            modos.append({
                'descricao': 'Aumentar mao de sept em +1',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Whispers-in-Pines: multiple totems, draw sept
        if 'draw a sept card' in tl or 'draw a combat card' in tl:
            modos.append({
                'descricao': 'Comprar carta',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Dead Zone: prevent magic
        if 'not affected' in tl and ('gift' in tl or 'gifts' in tl):
            modos.append({
                'descricao': 'Proteger de Gifts',
                'efeitos': [{
                    'tipo': 'anular',
                    'condicao_alvo': 'criatura_aliada',
                }],
            })

        # Monster Joe's: search for equipment
        if 'black-market' in tl or 'goods' in tl:
            modos.append({
                'descricao': 'Buscar equipamento no deck',
                'efeitos': [{
                    'tipo': 'comprar',
                    'condicao_alvo': 'deck_sept',
                    'quantidade': 1,
                }],
            })

        # Bully's Quest: kill victim
        if 'kill' in tl and 'victim' in tl:
            modos.append({
                'descricao': 'Matar vitima de Renome 3 ou menos',
                'efeitos': [{
                    'tipo': 'destruir',
                    'condicao_alvo': 'criatura_inimiga',
                }],
            })

        if not modos:
            modos.append({
                'descricao': f'Usar {tipo}',
                'efeitos': [{
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': 1,
                }],
            })

    # ---- DEFAULT ----
    if not modos:
        modos.append({
            'descricao': f'Usar carta de {tipo}',
            'efeitos': [{
                'tipo': 'dano',
                'condicao_alvo': 'criatura_inimiga',
                'quantidade': 1,
            }],
        })

    return modos


def gerar_json_revisado(card: CardModel) -> dict:
    """Gera JSON de efeitos revisado baseado no texto real."""
    try:
        rage_val = int(card.rage) if card.rage else 0
    except ValueError:
        rage_val = 0
    try:
        gnosis_val = int(card.gnosis) if card.gnosis else 0
    except ValueError:
        gnosis_val = 0
    try:
        health_val = int(card.health) if card.health else 0
    except ValueError:
        health_val = 0

    modos = _all_patterns(
        card.text or '', card.keyword or '',
        card.tipo, card.damage or '',
        rage_val, gnosis_val,
    )

    return {
        'id': f'card_{card.id}',
        'nome': card.name,
        'tipo': card.tipo,
        'custo_acoes': 1,
        'modos': modos,
        '_metadata': {
            'fonte': 'analise_v2',
            'card_id': card.id,
            'texto_original': card.text,
            'keywords': card.keyword,
            'damage': card.damage,
            'rage': card.rage,
            'gnosis': card.gnosis,
            'health': card.health,
            'precisa_revisao': True,
        },
    }


def slug(nome: str) -> str:
    return (nome.lower()
            .replace(' ', '_')
            .replace("'", '')
            .replace('-', '_')
            .replace(':', '')
            .replace('(', '')
            .replace(')', '')
            .replace('/', '_')
            .replace(',', '')
            .replace('.', '')
            .replace('!', '')
            .replace('?', '')
            .replace('"', '')
            .replace('’', '')
            [:45])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    deck_ids = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else [7, 90]

    app = create_app()
    total = 0

    with app.app_context():
        for did in deck_ids:
            from rage_web.models.deck import Deck, deck_cards
            import sqlalchemy as sa

            d = db.session.get(Deck, did)
            if not d:
                print(f'Erro: Deck {did} nao encontrado')
                continue

            print(f'\n=== Revisando JSONs do Deck {did}: {d.name} ===')

            stmt = sa.select(deck_cards).where(deck_cards.c.deck_id == did)
            rows = db.session.execute(stmt).fetchall()

            for row in rows:
                card = db.session.get(CardModel, row.card_id)
                if not card:
                    continue

                dados = gerar_json_revisado(card)
                fname = f'deck{did}_{card.id}_{slug(card.name)}.json'
                path = os.path.join(OUTPUT_DIR, fname)

                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(dados, f, indent=2, ensure_ascii=False)

                n_modos = len(dados['modos'])
                print(f'  {fname}: {n_modos} modo(s)')
                total += 1

    print(f'\nTotal: {total} JSONs revisados em {OUTPUT_DIR}/')


if __name__ == '__main__':
    main()
