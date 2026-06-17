"""
Consultas auxiliares para construção de decks.

Fornece funções que um modelo de IA pode usar DURANTE a construção
do deck para verificar se cartas são compatíveis com os personagens
do pack, evitando erros de pré-requisito.
"""

from __future__ import annotations
from typing import Any

from rage_web.ext.database import db
from rage_web.models.card import Card


def _parse_keywords(raw: str) -> set[str]:
    """Separa keywords hifenizadas num conjunto limpo."""
    if not raw:
        return set()
    return {k.strip().lower() for k in raw.replace('|', '-').split('-') if k.strip()}


# ──────────────────────────────────────────────
# Consultas de compatibilidade
# ──────────────────────────────────────────────


def combat_cards_para_rage(rage_max: int) -> list[dict[str, Any]]:
    """Retorna combat actions que personagens com até `rage_max` podem usar.

    O campo `rage` de uma Combat Action é o requisito mínimo de Rage
    para jogá-la (regra 6.4). Se o personagem tem Rage < rage_da_carta,
    a carta não pode ser jogada nem blefada legalmente (6.9.2).

    Args:
        rage_max: Rage máxima entre os personagens do pack.

    Returns:
        Lista de dicts com as cartas compatíveis.
    """
    cards = db.session.execute(
        db.select(Card).where(
            Card.tipo.ilike('%combat%'),
            Card.rage <= rage_max
        ).order_by(Card.rage, Card.name)
    ).scalars().all()

    result = []
    for c in cards:
        result.append({
            'id': c.id,
            'name': c.name,
            'rage_requerido': c.rage,
            'dano': c.damage,
            'texto': (c.text or '')[:120],
        })
    return result


def combat_cards_para_personagem(personagem_id: int) -> list[dict[str, Any]]:
    """Retorna combat actions que um personagem específico pode usar.

    Args:
        personagem_id: ID do personagem no banco.

    Returns:
        Lista de combat actions com Rage ≤ Rage do personagem.
    """
    char = db.session.get(Card, personagem_id)
    if not char or 'character' not in (char.tipo or '').lower():
        raise ValueError(f'ID {personagem_id} não é um personagem')

    return combat_cards_para_rage(char.rage)


def aliados_recrutaveis(keywords_pack: set[str]) -> list[dict[str, Any]]:
    """Retorna aliados recrutáveis por um pack com as keywords dadas.

    Regra (4.4.1): recrutar Ally requer personagem que atenda ao
    campo `requires` do Ally. O requisito pode ser:
    - 'Any': qualquer personagem
    - 'Keyword': personagem precisa ter a keyword
    - 'Keyword1 - Keyword2': atendendo qualquer uma (OR)
    - '(Gnosis: N) + Keyword': personagem com Gnosis ≥ N + keyword

    Args:
        keywords_pack: Conjunto de keywords de todos os personagens
                       do pack (ex: {'garou', 'homid', 'ahroun'}).

    Returns:
        Lista de aliados recrutáveis.
    """
    cards = db.session.execute(
        db.select(Card).where(Card.tipo.ilike('%ally%'))
    ).scalars().all()

    result = []
    for c in cards:
        requires = (c.requires or '').strip()
        if not requires:
            result.append(_ally_to_dict(c, 'qualquer personagem'))
            continue

        opcoes = [p.strip() for p in requires.split(' - ')]
        atendido = False
        motivo = ''
        for opcao in opcoes:
            opcao_lower = opcao.lower()
            if opcao_lower == 'any':
                atendido = True
                motivo = 'Any'
                break
            kw = _parse_keywords(opcao)
            if kw & keywords_pack:
                atendido = True
                motivo = f'matches {kw & keywords_pack}'
                break

        entry = _ally_to_dict(c, requires)
        entry['recrutavel'] = atendido
        entry['motivo'] = motivo if atendido else f'requer {requires}'
        result.append(entry)

    result.sort(key=lambda x: (not x['recrutavel'], x['name']))
    return result


def _ally_to_dict(c: Card, req_str: str) -> dict[str, Any]:
    return {
        'id': c.id,
        'name': c.name,
        'rage': c.rage,
        'gnosis': c.gnosis,
        'health': c.health,
        'requer': req_str,
        'keywords': c.keyword or '',
        'texto': (c.text or '')[:120],
    }


def equipamentos_equipaveis(gnosis_max: int,
                            keywords_pack: set[str] | None = None) -> list[dict[str, Any]]:
    """Retorna equipamentos que personagens com até `gnosis_max` podem equipar.

    O campo `gnosis` de um Equipment é a Gnosis mínima para equipá-lo.
    Alguns equipamentos também exigem keywords específicas no campo `requires`.

    Args:
        gnosis_max: Gnosis máxima entre os personagens do pack.
        keywords_pack: Keywords dos personagens (para verificar requires).

    Returns:
        Lista de equipamentos compatíveis.
    """
    cards = db.session.execute(
        db.select(Card).where(Card.tipo.ilike('%equipment%'))
    ).scalars().all()

    result = []
    for c in cards:
        if c.gnosis > gnosis_max:
            continue

        requires = (c.requires or '').strip()
        if requires and keywords_pack:
            opcoes = [p.strip() for p in requires.split(' - ')]
            ok = False
            for opcao in opcoes:
                if opcao.lower() == 'any':
                    ok = True
                    break
                kw_set = _parse_keywords(opcao)
                if kw_set & keywords_pack:
                    ok = True
                    break
            if not ok:
                continue

        result.append({
            'id': c.id,
            'name': c.name,
            'gnosis_requerida': c.gnosis,
            'requer': c.requires or '',
            'keywords': c.keyword or '',
            'texto': (c.text or '')[:120],
        })

    return result


def gifts_para_personagens(personagens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retorna gifts que podem ser usados por pelo menos um personagem do pack.

    Args:
        personagens: Lista de dicts com 'id', 'rage', 'gnosis', 'keywords'.

    Returns:
        Lista de gifts compatíveis.
    """
    cards = db.session.execute(
        db.select(Card).where(Card.tipo.ilike('%gift%'))
    ).scalars().all()

    result = []
    for c in cards:
        gnosis_req = c.gnosis
        requires = (c.requires or '').strip()
        req_keywords = _parse_keywords(requires) if requires else set()

        for p in personagens:
            if p['gnosis'] < gnosis_req:
                continue
            if req_keywords:
                p_kw = _parse_keywords(p.get('keywords', ''))
                if not req_keywords & p_kw:
                    continue

            result.append({
                'id': c.id,
                'name': c.name,
                'gnosis_requerida': gnosis_req,
                'requer': requires,
                'usavel_por': p['name'],
            })
            break  # Achou um personagem que pode usar

    return result


def resumo_pack(personagens: list[dict[str, Any]]) -> dict[str, Any]:
    """Gera um resumo das capacidades do pack para orientar a escolha de cartas.

    Args:
        personagens: Lista de dicts com 'name', 'rage', 'gnosis', 'keywords'.

    Returns:
        Dict com limites e keywords do pack.
    """
    if not personagens:
        return {'rage_max': 0, 'gnosis_max': 0, 'keywords': set()}

    rage_max = max(p['rage'] for p in personagens)
    gnosis_max = max(p['gnosis'] for p in personagens)
    todas_keywords: set[str] = set()
    for p in personagens:
        todas_keywords |= _parse_keywords(p.get('keywords', ''))

    return {
        'rage_max': rage_max,
        'gnosis_max': gnosis_max,
        'keywords': sorted(todas_keywords),
        'personagens': [{'name': p['name'],
                         'rage': p['rage'],
                         'gnosis': p['gnosis']}
                        for p in personagens],
        # Regras práticas:
        'combat_actions_ate': rage_max,
        'equipment_gnosis_ate': gnosis_max,
        'gift_gnosis_ate': gnosis_max,
    }
