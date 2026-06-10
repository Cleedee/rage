"""Parsers refinados com padrões expandidos para cada tipo de carta.

Cada função recebe um objeto Card do banco e retorna um dicionário
no formato do modelo JSON de efeitos, ou None se não conseguir parsear.

Princípios:
1. Combat: dano primário = campo `damage` (custo = dano causado)
2. Personagens: só extraem efeitos MUITO claros (draw combat card)
3. Texto de oponente ("anyone who defeats him") NÃO vira benefício do jogador
4. Negação ("cannot", "may not") NÃO gera efeito falso
5. Lore/flavor é ignorado
6. Padrões expandidos: destruir, descartar, impedir ações, redirecionar,
   redução de dano, mover/buscar, ataque imediato, combar ação, etc.
"""

from __future__ import annotations
import re
from typing import Any, Optional
from slugify import slugify


# ═══════════════════════════════════════════════════════════════════════════
# Helpers de ID
# ═══════════════════════════════════════════════════════════════════════════

def _card_id(card) -> str:
    """Gera ID estavel para o JSON: slug do nome.
    
    Prioridade:
    1. Se card tem slug no banco, usa
    2. Se card tem renown, adiciona _r{N}
    3. Fallback: card_{id}
    """
    if hasattr(card, 'slug') and card.slug:
        return card.slug
    # Fallback: gera slug na hora
    slug_base = slugify(card.name) if card.name else _card_id(card)
    if card.renown and card.renown > 0:
        return f'{slug_base}_r{card.renown}'
    return slug_base

# ═══════════════════════════════════════════════════════════════════════════
# Helpers de parsing
# ═══════════════════════════════════════════════════════════════════════════

def _texto(text: str | None) -> str:
    return (text or '').strip()


def _match(text: str, pattern: str) -> Optional[re.Match]:
    return re.search(pattern, text, re.IGNORECASE)


def _tem(text: str | None, palavra: str) -> bool:
    if not text:
        return False
    return palavra.lower() in text.lower()


def _tem_qualquer(text: str | None, palavras: list[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(p.lower() in t for p in palavras)


def _is_immune(text: str) -> bool:
    """Verifica se o texto fala de imunidade / indestrutibilidade."""
    return _tem_qualquer(text, [
        'cannot be destroyed', 'can never be destroyed', 'truly immortal',
        'cannot be removed', 'cannot leave play',
        'não pode ser destruído', 'não pode ser removido',
        'spirits will not attack',
    ])


def _is_opponent_benefit(text: str) -> bool:
    """Detecta texto que descreve benefício para o oponente."""
    return _tem_qualquer(text, [
        'anyone who defeats him', 'anyone who defeats',
        'quem o derrotar', 'quem derrotar',
        'opponent gains', 'adversário ganha',
        'your opponent may', 'your opponent draws',
        'for killing him',
    ])


def _is_flavor(text: str) -> bool:
    """Detecta texto puramente narrativo/lore."""
    return _tem_qualquer(text, [
        'playtesting info', 'playtesting information',
        'this indirect shot', 'this light swipe',
        'this well-placed blow', 'no matter where you get kicked',
        'has never lost a combat', 'bears many scars across',
        'calling takes many forms', 'truly immortal',
        'suited to the revelation',
    ])


def _is_negative(text: str) -> bool:
    """Verifica se o texto contém negação que invalida efeitos."""
    return _tem_qualquer(text, [
        'cannot', "can't", 'may not', "mayn't",
        'not affected by', 'not be used',
        'não pode', 'não é afetado', 'não sofre', 'não pode ser',
        'can only be played', 'só pode ser jogado',
    ])


def _extrair_qtd(text: str) -> int:
    """Extrai quantidade numérica genérica do texto."""
    m = _match(text, r'(\d+)\s*(?:de\s*)?(?:dano|damage|carta|carta[s]?|card[s]?|ponto[s]?|point[s]?|vp|vez[es]|turno[s]?)')
    if m:
        return int(m.group(1))
    return 1


# ═══════════════════════════════════════════════════════════════════════════
# Extração de efeitos específicos
# ═══════════════════════════════════════════════════════════════════════════

def _extrair_dano(text: str) -> Optional[dict]:
    """Extrai efeito de causar dano do texto."""
    if _is_flavor(text) or _is_opponent_benefit(text):
        return None

    m = _match(text, r'(?:causa|deal|inflict|faz|sofre|toma|leva|add[s]?)\s*(\d+)\s*(?:de\s*)?(?:dano|damage)')
    if m:
        return {'tipo': 'dano', 'condicao_alvo': 'criatura_inimiga', 'quantidade': int(m.group(1))}

    m = _match(text, r'(\d+)\s*(?:de\s*)?(?:dano|damage)\s*(?:aggravated|extra)?')
    if m:
        return {'tipo': 'dano', 'condicao_alvo': 'criatura_inimiga', 'quantidade': int(m.group(1))}

    return None


def _extrair_comprar(text: str) -> Optional[dict]:
    """Extrai efeito de comprar cartas."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # Padrão: "draw a combat card", "draw 2 cards", etc.
    m = _match(text, r'(?:draw|compr[ae]|busque?|procure?)\s+(?:a|an|the|os|as|um|uma|\d+)?\s*(?:combat\s*)?(?:card|carta|cards?|cartas?)')
    if m:
        qtd = 1
        m2 = _match(text, r'(?:draw|compr[ae]|busque?)\s+(\d+)')
        if m2:
            qtd = int(m2.group(1))

        zona = 'deck_combate' if _tem(text, 'combat') else 'deck_sept'
        return {'tipo': 'comprar', 'condicao_alvo': 'jogador', 'quantidade': qtd,
                'params': {'zona': zona}}

    # "Pode comprar 1 carta de combate"
    m = _match(text, r'pode\s+compr[ae][rn]?\s+(\d+)?\s*(?:combat\s*)?(?:card|carta)')
    if m:
        qtd = int(m.group(1)) if m.group(1) else 1
        zona = 'deck_combate' if _tem(text, 'combat') else 'deck_sept'
        return {'tipo': 'comprar', 'condicao_alvo': 'jogador', 'quantidade': qtd,
                'params': {'zona': zona}}

    return None


def _extrair_destruir(text: str) -> Optional[dict]:
    """Extrai efeito de destruir.

    CUIDADO:
    - "cannot be destroyed" = imunidade (não vira destruir)
    - "anyone who defeats/kills him" = oponente (não vira efeito do jogador)
    - "if you kill" = condicional, normalmente vira ganhar_vp
    """
    if _is_immune(text) or _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # Destruição condicional que rende VP
    m = _match(text, r'(?:if you kill|if.*kills?|if.*destroy|se.*matar|se.*destruir)')
    if m:
        # Não é destruição ativa — é um bônus condicional
        return None  # Vai ser pego pelo ganhar_vp condicional

    # Destruição ativa
    if _tem_qualquer(text, ['destroy', 'destruir', 'slay your opponent']):
        return {'tipo': 'destruir', 'condicao_alvo': 'criatura_inimiga',
                'params': {'condicao': 'dano_mortal'}}

    return None


def _extrair_descarte(text: str) -> Optional[dict]:
    """Extrai efeito de descartar.

    "Discard" pode ser:
    - Custo/aftermath ("Discard this Gift after use"): não gera efeito
    - Ação ativa ("discard a card from opponent's hand"): vira descarte
    """
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # Discard como custo (após uso) — ignorar
    if _match(text, r'(?:discard|descarte).*(?:after use|depois de usar|this card after)'):
        return None

    # Discard de mão do oponente
    if _match(text, r'(?:discard|descarte|descartar).*(?:opponent|adversário|inimigo|hand|mão)'):
        return {'tipo': 'descarte', 'condicao_alvo': 'jogador_inimigo', 'quantidade': 1}

    # Discard de deck/carta específico
    if _tem_qualquer(text, ['discard.*deck', 'discard.*library', 'descarte.*deck',
                              'discard.*draw', 'descarte.*carta']):
        return {'tipo': 'descarte', 'condicao_alvo': 'jogador_inimigo', 'quantidade': 1}

    return None


def _extrair_tapar(text: str) -> Optional[dict]:
    if _is_negative(text) or _is_opponent_benefit(text):
        return None
    if _tem_qualquer(text, ['tap', 'tapar', 'paralyze', 'paralis', 'immobil', 'imobiliz']):
        return {'tipo': 'tapar', 'condicao_alvo': 'criatura_inimiga'}
    return None


def _extrair_fugir(text: str) -> Optional[dict]:
    if _is_negative(text) or _is_opponent_benefit(text):
        return None
    if _tem_qualquer(text, ['flee combat', 'fugir do combate', 'encerrar combate',
                             'end combat', 'withdraw from combat', 'retirar do combate',
                             'escape from combat']):
        return {'tipo': 'fugir', 'condicao_alvo': 'criatura_aliada'}
    return None


def _extrair_curar(text: str) -> Optional[dict]:
    if _is_negative(text) or _is_opponent_benefit(text) or _is_flavor(text):
        return None
    m = _match(text, r'(?:heal|regenerat?|cura|cicatriza)\s*(?:de\s*)?(\d+)?')
    if m:
        qtd = int(m.group(1)) if m.group(1) else 1
        return {'tipo': 'curar', 'condicao_alvo': 'criatura_aliada', 'quantidade': qtd}
    # "heals all damage"
    if _match(text, r'(?:heal|regenerat?|cura|cicatriza).*(?:all|todo).*(?:damage|dano)'):
        return {'tipo': 'curar', 'condicao_alvo': 'criatura_aliada', 'quantidade': 99}
    return None


def _extrair_modificar_atributo(text: str) -> Optional[dict]:
    """Extrai modificação de atributo (Rage/Gnosis/Health)."""
    if _is_negative(text) or _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # "+1 Rage", "-1 Gnosis", "acts at +1 Rage"
    m = _match(text, r'(?:[+-]?\d+|a\s*\+?\d*)\s*(?:de\s*)?(?:rage|gnosis|health|vida)')
    if m:
        val_str = m.group(0)
        try:
            val = int(val_str.replace('a +', '+').replace('a ', '+').replace('+', '+'))
        except ValueError:
            val = 1
            # Extrair número
            m2 = re.search(r'([+-]?\d+)', val_str)
            if m2:
                val = int(m2.group(1))

        atributos = []
        if _tem_qualquer(text, ['rage', 'furia', 'fúria', 'raiva']):
            atributos.append('rage')
        if _tem(text, 'gnosis') or _tem(text, 'gnose'):
            atributos.append('gnosis')
        if _tem(text, 'health') or _tem(text, 'vida') or _tem(text, 'saúde'):
            atributos.append('health')

        if atributos:
            return {'tipo': 'modificar_atributo', 'condicao_alvo': 'criatura_aliada',
                    'params': {'atributos': atributos, 'valor': val,
                               'duracao': 'ate_fim_combate'}}

    # "gain(s) N Rage" / "gains +N Gnosis"
    m = _match(text, r'(?:gain|gains?|get|recebe|ganha)\s*(?:de\s*)?([+-]?\d+)\s*(?:de\s*)?(?:rage|gnosis)')
    if m:
        val = int(m.group(1))
        attr = 'rage' if _tem(text, 'rage') else 'gnosis'
        return {'tipo': 'modificar_atributo', 'condicao_alvo': 'criatura_aliada',
                'params': {'atributos': [attr], 'valor': val,
                           'duracao': 'ate_fim_combate'}}

    return None


def _extrair_anular(text: str) -> Optional[dict]:
    if _is_negative(text) or _is_opponent_benefit(text) or _is_flavor(text):
        return None
    if _tem_qualquer(text, ['cancel', 'anular', 'negate', 'prevent', 'does not take effect']):
        return {'tipo': 'anular', 'condicao_alvo': 'criatura_inimiga'}
    return None


def _extrair_ganhar_vp(text: str) -> Optional[dict]:
    """Extrai ganhar VP.

    CUIDADO com "anyone who defeats him... earning them +1 VP" — é benefício
    do oponente, não do controlador!
    """
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # "for an additional X victory points"
    m = _match(text, r'(?:for|ganha|recebe|earning)\s*(?:an\s*)?(?:additional\s*)?(\d+)\s*(?:victory point|vp|ponto.*vit)')
    if m:
        return {'tipo': 'ganhar_vp', 'condicao_alvo': 'jogador', 'quantidade': int(m.group(1))}

    # "place this card in your victory pile for +N VP"
    m = _match(text, r'(?:victory pile|pilha.*vit[óo]ria|place.*vp).*(\d+)\s*(?:vp|victory)')
    if m:
        return {'tipo': 'ganhar_vp', 'condicao_alvo': 'jogador', 'quantidade': int(m.group(1))}

    # "+N victory points"
    m = _match(text, r'(\+?\d+)\s*(?:victory point|vp|ponto[s]?\s*de\s*vit[óo]ria)')
    if m:
        val = int(m.group(1).replace('+', ''))
        return {'tipo': 'ganhar_vp', 'condicao_alvo': 'jogador', 'quantidade': val}

    return None


def _extrair_perder_vp(text: str) -> Optional[dict]:
    """Extrai perder VP (efeito negativo para o oponente)."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None
    if _tem_qualquer(text, ['lose.*vp', 'perde.*vp', 'perde.*ponto.*vit']):
        return {'tipo': 'perder_vp', 'condicao_alvo': 'jogador_inimigo', 'quantidade': 1}
    return None


def _extrair_impedir_acoes(text: str) -> Optional[dict]:
    """Extrai efeito de impedir ações do oponente.

    "cannot play Combat Actions", "may not play cards", etc.
    Isso é um DEBUFF no oponente.
    """
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # "victim may not play" / "cannot play" — afeta o oponente
    m = _match(text, r'(?:victim|opponent|adversário|inimigo|personagem).*(?:may not play|cannot play|não pode jogar)')
    if m:
        return {'tipo': 'impedir_acoes', 'condicao_alvo': 'criatura_inimiga',
                'params': {'duracao': 'proximo_turno'}}

    # Ações mais específicas: "may not play Combat Actions"
    if _match(text, r'(?:may not|cannot|não pode).*(?:play|jogar|usar).*(?:combat|action|ação|gift|card|carta)'):
        return {'tipo': 'impedir_acoes', 'condicao_alvo': 'criatura_inimiga',
                'params': {'duracao': 'proximo_turno'}}

    # "your character cannot play" — isso é AUTO-RESTRIÇÃO, não debuff
    # (como Reckless Swing: "your character cannot play a combat action")
    if _match(text, r'(?:your|seu|sua).*(?:cannot|may not|não pode).*(?:play|jogar)'):
        return None  # É auto-restrição, não debuff no oponente

    return None


def _extrair_impedir_retirada(text: str) -> Optional[dict]:
    """Extrai impedir retirada (cannot withdraw/escape)."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    if _match(text, r'(?:opponent|victim|inimigo|adversário|attacker|atacante).*(?:cannot|may not|não pode).*(?:withdraw|escape|retirar|fugir)'):
        return {'tipo': 'impedir_retirada', 'condicao_alvo': 'criatura_inimiga'}
    return None


def _extrair_ataque_imediato(text: str) -> Optional[dict]:
    """Extrai efeito de ataque imediato / Fast Striking."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    if _tem(text, 'fast striking') or _tem(text, 'fast_striking') or _tem(text, 'ataque rápido'):
        # Fast Striking é uma keyword que dá prioridade, não um ataque extra
        return {'tipo': 'ataque_imediato', 'condicao_alvo': 'criatura_aliada',
                'params': {'speed': 'fast'}}

    if _tem_qualquer(text, ['immediately attack', 'ataca.*imediatamente']):
        return {'tipo': 'ataque_imediato', 'condicao_alvo': 'criatura_aliada'}

    return None


def _extrair_combar_acao(text: str) -> Optional[dict]:
    """Extrai efeito de combar/jogar ações adicionais."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    if _match(text, r'(?:may also play|pode.*jogar.*tamb[eé]m|play any.*simultaneously)'):
        return {'tipo': 'combar_acao', 'condicao_alvo': 'criatura_aliada'}

    if _match(text, r'(?:additional|extra|adicional)\s*(?:combat\s*)?(?:card|carta|action|ação)'):
        return {'tipo': 'combar_acao', 'condicao_alvo': 'criatura_aliada'}

    # "draws 1 additional combat card" (Mamu, Joseph)
    if _match(text, r'(?:draw|compr[ae]|pux[ae]).*(?:additional|extra|adicional).*(?:combat|card|carta)'):
        return {'tipo': 'combar_acao', 'condicao_alvo': 'criatura_aliada'}

    # "take an additional alpha action"
    if _match(text, r'(?:additional|extra|adicional).*(?:alpha action|ação alfa)'):
        return {'tipo': 'combar_acao', 'condicao_alvo': 'criatura_aliada'}

    return None


def _extrair_mover_para(text: str) -> Optional[dict]:
    """Extrai efeito de mover carta (search deck, place in hand, etc.)."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # Search deck → hand
    if _match(text, r'(?:search|procure?|busque?|look through).*(?:deck|library).*(?:hand|mão)'):
        return {'tipo': 'mover_para', 'condicao_alvo': 'jogador',
                'params': {'origem': 'deck', 'destino': 'hand'}}

    # Place/put back into deck
    if _match(text, r'(?:place|put|coloca|devolv|return|devolv).*(?:back|volta|into).*(?:deck|library)'):
        return {'tipo': 'mover_para', 'condicao_alvo': 'jogador',
                'params': {'origem': 'play', 'destino': 'deck'}}

    # Search generic
    if _match(text, r'(?:search|procure?|busque?).*deck'):
        return {'tipo': 'mover_para', 'condicao_alvo': 'jogador',
                'params': {'descricao': 'buscar_no_deck'}}

    # Transfer equipment (Old One-Eye)
    if _match(text, r'(?:transfer|transfira|mova).*(?:equip|equipamento)'):
        return {'tipo': 'mover_para', 'condicao_alvo': 'jogador',
                'params': {'descricao': 'transferir_equipamento'}}

    return None


def _extrair_redirecionar(text: str) -> Optional[dict]:
    """Extrai efeito de redirecionar ataque.

    CUIDADO: "may not be redirected" é uma imunidade, não redirecionamento!
    """
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # "cannot be redirected" / "may not be redirected" → imunidade (não gera efeito)
    if _match(text, r'(?:cannot|may not|não pode).*(?:redirect|redireciona)'):
        return None

    if _tem_qualquer(text, ['redirect', 'redireciona', 'desviar', 'step in.*replace']):
        return {'tipo': 'redirecionar', 'condicao_alvo': 'criatura_aliada'}

    return None


def _extrair_modificar_reducao_dano(text: str) -> Optional[dict]:
    """Extrai efeito de redução de dano (block / dodge)."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None

    # "Reduces the damage... by up to N"
    m = _match(text, r'(?:block|reduces?|reduce|reduz)\s+(?:the\s+)?(?:damage|dano)?.*?(?:up to|at[eé]|de|by)\s*(\d+)\s*(?:points?|de\s*)?(?:damage|dano)?')
    if m:
        return {'tipo': 'modificar_reducao_dano', 'condicao_alvo': 'criatura_aliada',
                'quantidade': int(m.group(1))}

    # "Avoids/Avoid one attack" — dodge completo
    m = _match(text, r'(?:avoid[s]?|dodge|esquiv[ae])\s+(?:one|1\s+)?\s*(?:attack|atq|ataque)')
    if m:
        return {'tipo': 'modificar_reducao_dano', 'condicao_alvo': 'criatura_aliada',
                'quantidade': 4}  # Dodge completo

    return None


def _extrair_remover_do_combate(text: str) -> Optional[dict]:
    """Extrai efeito de remover criatura do combate."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None
    if _tem_qualquer(text, ['remove.*combat', 'remover.*combate', 'remove.*fight']):
        return {'tipo': 'remover_do_combate', 'condicao_alvo': 'criatura_inimiga'}
    return None


def _extrair_olhar_mao(text: str) -> Optional[dict]:
    """Extrai efeito de olhar mão do oponente."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None
    if _match(text, r'(?:look|look at|olhar|reveal).*(?:opponent|adversário).*(?:hand|mão)'):
        return {'tipo': 'olhar_topo_deck', 'condicao_alvo': 'jogador_inimigo'}
    return None


def _extrair_perder_acao(text: str) -> Optional[dict]:
    """Extrai perder ação (bluff forçado, etc)."""
    if _is_opponent_benefit(text) or _is_flavor(text):
        return None
    if _match(text, r'(?:must bluff|forçado.*bluff|bluff.*or.*discard)'):
        return {'tipo': 'forcar_bluff', 'condicao_alvo': 'criatura_inimiga'}
    return None


_EFFECT_EXTRACTORS = [
    ('comprar', _extrair_comprar),
    ('fugir', _extrair_fugir),
    ('tapar', _extrair_tapar),
    ('anular', _extrair_anular),
    ('impedir_acoes', _extrair_impedir_acoes),
    ('impedir_retirada', _extrair_impedir_retirada),
    ('ataque_imediato', _extrair_ataque_imediato),
    ('combar_acao', _extrair_combar_acao),
    ('ganhar_vp', _extrair_ganhar_vp),
    ('perder_vp', _extrair_perder_vp),
    ('curar', _extrair_curar),
    ('modificar_atributo', _extrair_modificar_atributo),
    ('destruir', _extrair_destruir),
    ('descarte', _extrair_descarte),
    ('modificar_reducao_dano', _extrair_modificar_reducao_dano),
    ('mover_para', _extrair_mover_para),
    ('redirecionar', _extrair_redirecionar),
    ('remover_do_combate', _extrair_remover_do_combate),
    ('olhar_mao', _extrair_olhar_mao),
    ('forcar_bluff', _extrair_perder_acao),
]


def _extrair_efeitos(text: str, max_efeitos: int = 2) -> list[dict]:
    """Extrai efeitos do texto na ordem de prioridade.

    Percorre os extratores em ordem de prioridade e retorna
    até `max_efeitos` efeitos encontrados (evita acumular tudo).
    """
    if _is_flavor(text) or _is_opponent_benefit(text) or not text:
        return []

    efeitos = []
    for nome, extrator in _EFFECT_EXTRACTORS:
        e = extrator(text)
        if e:
            # Evitar duplicatas do mesmo tipo
            if nome not in [x.get('_nome', '') for x in efeitos]:
                e['_nome'] = nome
                efeitos.append(e)
                if len(efeitos) >= max_efeitos:
                    break

    # Limpar campos internos
    for e in efeitos:
        e.pop('_nome', None)

    return efeitos


# ═══════════════════════════════════════════════════════════════════════════
# Parsers por tipo de carta
# ═══════════════════════════════════════════════════════════════════════════

def parse_combat_action(card) -> Optional[dict]:
    """Parser para Combat Action / Combat Event.

    Dano primário = campo `damage` (custo = dano causado).
    Efeitos secundários do texto.
    """
    text = _texto(card.text)
    damage_str = (card.damage or '').strip()
    efeitos = []

    # 1. Dano do campo `damage`
    if damage_str:
        try:
            qtd = int(damage_str)
            if qtd > 0:
                efeitos.append({
                    'tipo': 'dano',
                    'condicao_alvo': 'criatura_inimiga',
                    'quantidade': qtd,
                })
        except ValueError:
            pass

    # 2. Efeitos secundários do texto (combar, impedir, etc.)
    if text:
        extras = _extrair_efeitos(text, max_efeitos=1)
        for e in extras:
            if e['tipo'] not in [x['tipo'] for x in efeitos]:
                efeitos.append(e)

    # 3. Fallback: carta defensiva
    if not efeitos:
        if _tem_qualquer(text, ['block', 'dodge', 'avoid', 'esquiva', 'defende',
                                'reduces', 'reduce', 'reduz']):
            # Tenta extrair quantidade de dano que pode bloquear
            qtd = 2
            m = _match(text, r'(\d+)\s*(?:point|dano|damage|de\s+dano)')
            if m:
                qtd = int(m.group(1))
            elif _tem_qualquer(text, ['avoid', 'dodge', 'esquiva']):
                qtd = 4  # Esquiva completa
            efeitos.append({
                'tipo': 'modificar_reducao_dano',
                'condicao_alvo': 'criatura_aliada',
                'quantidade': qtd,
            })
        else:
            efeitos.append({
                'tipo': 'restringir',
                'condicao_alvo': 'criatura_aliada',
                'params': {'descricao': 'efeito_passivo'},
            })

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': card.tipo,
        'modos': [{'descricao': 'Ação de Combate', 'efeitos': efeitos}],
    }


def parse_combat_event(card) -> Optional[dict]:
    """Parser para Combat Event."""
    return parse_combat_action(card)


def parse_gift(card) -> Optional[dict]:
    """Parser para Gift."""
    text = _texto(card.text)
    gnosis = card.gnosis or 0

    if _is_flavor(text) or _is_opponent_benefit(text):
        return None

    efeitos = _extrair_efeitos(text, max_efeitos=2)

    if not efeitos:
        # Gifts sem efeito claro: buff genérico
        if _tem(text, 'claw') or _tem(text, 'garra') or _tem(text, 'fang') or _tem(text, 'presa'):
            efeitos.append({
                'tipo': 'modificar_atributo',
                'condicao_alvo': 'criatura_aliada',
                'params': {'atributos': ['dano_agravado'], 'valor': True, 'duracao': 1},
            })
        else:
            efeitos.append({
                'tipo': 'modificar_atributo',
                'condicao_alvo': 'criatura_aliada',
                'params': {'atributos': ['rage'], 'valor': 1, 'duracao': 'ate_fim_combate'},
            })

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Gift',
        'modos': [{'descricao': f'Usar Gift (Gn{gnosis})', 'efeitos': efeitos}],
    }


def parse_equipment(card) -> Optional[dict]:
    """Parser para Equipment."""
    text = _texto(card.text)
    gnosis = card.gnosis or 0

    is_weapon = _tem_qualquer(text, ['weapon', 'arma', 'klaive', 'sword', 'espada',
                                      'claw', 'garra', 'gun', 'firearm', 'rifle'])

    efeitos = _extrair_efeitos(text, max_efeitos=2)

    if is_weapon:
        try:
            dmg = int(card.damage or '1')
        except ValueError:
            dmg = 1
        # Só adicionar dano se já não tem
        if not any(e['tipo'] == 'dano' for e in efeitos):
            efeitos.append({
                'tipo': 'dano',
                'condicao_alvo': 'criatura_inimiga',
                'quantidade': dmg,
            })

    if not efeitos:
        efeitos.append({'tipo': 'equipar', 'condicao_alvo': 'criatura_aliada'})

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Equipment',
        'modos': [{'descricao': f'Equipar (Gn{gnosis})', 'efeitos': efeitos}],
    }


def parse_event(card) -> Optional[dict]:
    """Parser para Event."""
    text = _texto(card.text)

    is_totem = _tem_qualquer(text, ['pack totem', 'totem do pack'])

    if is_totem:
        efeitos = [{
            'tipo': 'modificar_atributo',
            'condicao_alvo': 'criatura_aliada',
            'params': {'atributos': ['rage', 'health'], 'duracao': 'permanente'},
        }]
    else:
        efeitos = _extrair_efeitos(text, max_efeitos=1)
        if not efeitos:
            efeitos = [{'tipo': 'comprar', 'condicao_alvo': 'jogador',
                        'quantidade': 1, 'params': {'zona': 'deck_sept'}}]

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Event',
        'modos': [{'descricao': 'Evento', 'efeitos': efeitos}],
    }


def parse_action(card) -> Optional[dict]:
    """Parser para Action."""
    text = _texto(card.text)

    efeitos = _extrair_efeitos(text, max_efeitos=1)

    if not efeitos:
        if _tem_qualquer(text, ['step sideways', 'umbra', 'passo lateral']):
            efeitos = [{'tipo': 'mover_para', 'condicao_alvo': 'criatura_aliada',
                        'params': {'destino': 'umbra'}}]
        elif _tem_qualquer(text, ['shapeshift', 'shape shift', 'transform', 'mudar forma']):
            efeitos = [{'tipo': 'restringir', 'condicao_alvo': 'criatura_aliada',
                        'params': {'forma': 'crinos'}}]
        else:
            efeitos = [{'tipo': 'comprar', 'condicao_alvo': 'jogador',
                        'quantidade': 1, 'params': {'zona': 'deck_sept'}}]

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Action',
        'modos': [{'descricao': 'Ação', 'efeitos': efeitos}],
    }


def parse_ally(card) -> Optional[dict]:
    """Parser para Ally."""
    text = _texto(card.text)
    health = card.health or 1

    efeitos = _extrair_efeitos(text, max_efeitos=1)

    if not efeitos:
        efeitos = [{'tipo': 'restringir', 'condicao_alvo': 'jogador',
                    'params': {'descricao': f'aliado_h{health}'}}]

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Ally',
        'modos': [{'descricao': f'Aliado (H{health})', 'efeitos': efeitos}],
    }


def parse_territory(card) -> Optional[dict]:
    """Parser para Territory."""
    text = _texto(card.text)

    if _tem_qualquer(text, ['protect from gifts', 'not affected by gifts',
                             'proteger de gifts', 'immune to gifts']):
        efeitos = [{'tipo': 'anular', 'condicao_alvo': 'criatura_aliada'}]
    elif _tem_qualquer(text, ['neutralize.*territor', 'neutraliza.*territor',
                                'remove.*territor', 'cancela.*territor']):
        efeitos = [{'tipo': 'anular', 'condicao_alvo': 'jogador',
                    'params': {'tipo': 'territory'}}]
    else:
        efeitos = _extrair_efeitos(text, max_efeitos=1)
        if not efeitos:
            efeitos = [{'tipo': 'restringir', 'condicao_alvo': 'jogador',
                        'params': {'descricao': 'territorio'}}]

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': 'Territory',
        'modos': [{'descricao': 'Território', 'efeitos': efeitos}],
    }


def parse_character(card) -> Optional[dict]:
    """Parser para Character.

    Personagens têm habilidades complexas no texto. Só extraímos
    efeitos MUITO claros (ex: "draw a combat card when...").

    NÃO extrair: ganhar_vp, dano, destruir, etc. do texto de personagem.
    """
    text = _texto(card.text)
    rage = card.rage or 0
    gnosis = card.gnosis or 0
    health = card.health or 0
    renown = card.renown or 0

    efeitos = []

    # Extrair APENAS draw de carta de combate (é o mais comum e confiável)
    if _match(text, r'(?:draw|compr[ae]).*combat.*(?:card|carta)'):
        efeitos.append({
            'tipo': 'comprar',
            'condicao_alvo': 'jogador',
            'quantidade': 1,
            'params': {'zona': 'deck_combate'},
        })

    if not efeitos:
        efeitos.append({
            'tipo': 'restringir',
            'condicao_alvo': 'jogador',
            'params': {
                'descricao': f'personagem_rg{rage}_gn{gnosis}_h{health}',
            }
        })

    return {
        'id': _card_id(card),
        'nome': card.name,
        'tipo': card.tipo,
        'modos': [{'descricao': f'Personagem: Rg{rage} Gn{gnosis} H{health} (Ren{renown})',
                    'efeitos': efeitos}],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Parsers secundários
# ═══════════════════════════════════════════════════════════════════════════

def parse_rite(card) -> Optional[dict]:
    text = _texto(card.text)
    efeitos = _extrair_efeitos(text, max_efeitos=1)
    if not efeitos:
        efeitos = [{'tipo': 'comprar', 'condicao_alvo': 'jogador',
                    'quantidade': 1, 'params': {'zona': 'deck_sept'}}]
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Rite',
        'modos': [{'descricao': 'Rito', 'efeitos': efeitos}],
    }


def parse_moot(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Moot',
        'modos': [{'descricao': 'Junta', 'efeitos': [
            {'tipo': 'restringir', 'condicao_alvo': 'jogador',
             'params': {'descricao': 'moot'}}
        ]}],
    }


def parse_board_meeting(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Board Meeting',
        'modos': [{'descricao': 'Reunião', 'efeitos': [
            {'tipo': 'restringir', 'condicao_alvo': 'jogador',
             'params': {'descricao': 'board_meeting'}}
        ]}],
    }


def parse_caern(card) -> Optional[dict]:
    gnosis_bonus = 1
    text = _texto(card.text)
    m = _match(text, r'([+-]?\d+)\s*(?:de\s*)?gnosis')
    if m:
        try:
            gnosis_bonus = int(m.group(1))
        except ValueError:
            pass
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Caern',
        'modos': [{'descricao': 'Caern', 'efeitos': [
            {'tipo': 'modificar_gnosis', 'condicao_alvo': 'jogador',
             'quantidade': gnosis_bonus}
        ]}],
    }


def parse_enemy(card) -> Optional[dict]:
    text = _texto(card.text)
    health = card.health or 1
    efeitos = _extrair_efeitos(text, max_efeitos=1)
    if not efeitos:
        dmg = 1
        m = _extrair_dano(text)
        if m:
            dmg = m['quantidade']
        efeitos = [{'tipo': 'dano', 'condicao_alvo': 'criatura_inimiga', 'quantidade': dmg}]
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Enemy',
        'modos': [{'descricao': f'Inimigo (H{health})', 'efeitos': efeitos}],
    }


def parse_victim(card) -> Optional[dict]:
    health = card.health or 1
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Victim',
        'modos': [{'descricao': f'Vítima (H{health})', 'efeitos': [
            {'tipo': 'restringir', 'condicao_alvo': 'jogador',
             'params': {'vida_da_vitima': health}}
        ]}],
    }


def parse_quest(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Quest',
        'modos': [{'descricao': 'Quest', 'efeitos': [
            {'tipo': 'quest_check', 'condicao_alvo': 'jogador'}
        ]}],
    }


def parse_battlefield(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Battlefield',
        'modos': [{'descricao': 'Campo de Batalha', 'efeitos': [
            {'tipo': 'restringir', 'condicao_alvo': 'jogador',
             'params': {'descricao': 'battlefield'}}
        ]}],
    }


def parse_past_life(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Past Life',
        'modos': [{'descricao': 'Vida Passada', 'efeitos': [
            {'tipo': 'modificar_atributo', 'condicao_alvo': 'criatura_aliada',
             'params': {'atributos': ['rage', 'gnosis'], 'valor': 1, 'duracao': 'permanente'}}
        ]}],
    }


def parse_realm(card) -> Optional[dict]:
    return {
        'id': _card_id(card), 'nome': card.name, 'tipo': 'Realm',
        'modos': [{'descricao': 'Reino', 'efeitos': [
            {'tipo': 'restringir', 'condicao_alvo': 'jogador',
             'params': {'descricao': 'realm'}}
        ]}],
    }
