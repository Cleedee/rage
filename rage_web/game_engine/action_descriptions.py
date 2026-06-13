"""Descricoes humanas para acoes do jogo.

Converte acoes tecnicas (ex: 'use_card_790_modo0') em descricoes
legiveis por humanos (ex: 'Usou Friends in High Places (Gift Gn3)').

Usado por rage-match, rage-cli e tutorial.
"""

from __future__ import annotations
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Dicionario de acoes conhecidas
# ---------------------------------------------------------------------------

# Acoes de combate
COMBAT_ACTIONS_HUMAN = {
    'strike': 'Atacar (Strike)',
    'dodge': 'Esquivar (Dodge)',
    'block': 'Bloquear (Block)',
    'bite': 'Morder (Bite)',
    'claw': 'Arranhar (Claw)',
    'flee': 'Fugir (Flee)',
    'head_butt': 'Head Butt',
    'tail_lash': 'Tail Lash',
    'anatomy_lesson': 'Anatomy Lesson',
    'savage_beatdown': 'Savage Beatdown',
    'submission_hold': 'Submission Hold',
    'block_and_roll': 'Block and Roll',
    'block_and_strike': 'Block and Strike',
    'careful_strike': 'Careful Strike',
    'evade_and_strike': 'Evade and Strike',
    'fast_strike': 'Fast Strike',
    'planned_strike': 'Planned Strike',
    'stunning_strike': 'Stunning Strike',
    'aggressive_bite': 'Aggressive Bite',
    'mitey_bitey': 'Mitey Bitey',
    'spirited_strike': 'Spirited Strike',
    'fetal_position': 'Fetal Position',
    'forceful_wind': 'Forceful Wind',
    'body_slam': 'Body Slam',
    'bum_rush': 'Bum Rush',
    'pack_defense': 'Pack Defense',
    'attacking_the_wyrm': 'Attacking the Wyrm',
}

# Tipos de carta
CARD_TYPE_HUMAN = {
    'Character': 'Personagem',
    'Combat Action': 'Ação de Combate',
    'Combat Event': 'Evento de Combate',
    'Gift': 'Gift',
    'Equipment': 'Equipamento',
    'Event': 'Evento',
    'Action': 'Ação',
    'Ally': 'Aliado',
    'Territory': 'Território',
    'Quest': 'Quest',
    'Rite': 'Rito',
    'Moot': 'Junta',
    'Board Meeting': 'Reunião de Conselho',
    'Caern': 'Caern',
    'Victim': 'Vítima',
    'Enemy': 'Inimigo',
    'Battlefield': 'Campo de Batalha',
    'Past Life': 'Vida Passada',
    'Realm': 'Reino',
}

# Fases
PHASE_HUMAN = {
    'redraw': 'Redraw',
    'regeneration': 'Regeneração',
    'resource': 'Recurso',
    'umbra': 'Umbra',
    'moot': 'Moot',
    'combate': 'Combate',
}


def _resolve_action_name(action: str, card_name: Optional[str] = None,
                          game=None) -> str:
    """Resolve um nome de acao de combate para formato legivel.

    Usado para logs de declaracao/revelacao de combate.

    Args:
        action: Nome da acao (ex: 'strike', 'block', 'ce_282', 'bum_rush').
        card_name: Nome da criatura que declarou.
        game: GameState opcional.

    Returns:
        "Stalks Death declarou Atacar (Strike)" ou similar.
    """
    if not action:
        return card_name or 'Acao vazia'

    # Combat Events: ce_<card_id>
    if action.startswith('ce_'):
        ce_id = action[3:]
        if game:
            ce_card = None
            for p in game.players:
                for zone_list in (p.discard_combat, p.discard_sept, p.hand):
                    for c in zone_list:
                        if c.card_id == int(ce_id):
                            ce_card = c
                            break
            if ce_card:
                ce_name = ce_card.name
            else:
                # Procura no banco
                try:
                    from rage_web.models.card import Card as CardModel
                    card_banco = CardModel.query.get(int(ce_id))
                    ce_name = card_banco.name if card_banco else f'CE#{ce_id}'
                except Exception:
                    ce_name = f'CE#{ce_id}'
        else:
            ce_name = f'CE#{ce_id}'
        if card_name:
            return f'{card_name} jogou {ce_name} (Evento)'
        return f'{ce_name} (Evento)'

    # Acoes padrao de combate
    human = COMBAT_ACTIONS_HUMAN.get(action, action.replace('_', ' ').title())
    if card_name:
        return f'{card_name} declarou {human}'
    return human


def describe_action(acao: str, game=None) -> str:
    """Converte uma acao tecnica em descricao humana.

    Args:
        acao: String da acao (ex: 'use_card_790_modo0')
        game: GameState opcional para buscar nomes de cartas

    Returns:
        Descricao humana (ex: 'Usou Friends in High Places (Gift Gn3)')
    """
    if not acao or acao == 'wait':
        return 'Aguardando'

    # Tentar extrair ID da carta e nome do log do jogo
    card_name = _find_card_name(acao, game)
    card_type = _find_card_type(acao, game)

    # Padroes de acao
    if acao.startswith('use_card_') or acao.startswith('use_'):
        return _describe_use_card(acao, card_name, card_type, game)
    elif acao.startswith('play_'):
        return _describe_play_card(acao, card_name, card_type, game)
    elif acao.startswith('moot_'):
        return _describe_moot(acao, card_name, game)
    elif acao.startswith('umbra_'):
        return _describe_umbra(acao, card_name, game)
    elif acao.startswith('declare_'):
        return _describe_declare(acao, card_name, game)
    elif acao.startswith('attack_') or acao.startswith('eliminate_'):
        return _describe_attack(acao, card_name, game)
    elif acao.startswith('feint_'):
        return _describe_feint(acao, card_name, game)
    elif acao.startswith('alpha_'):
        return _describe_alpha(acao, card_name, game)
    elif acao.startswith('redraw_'):
        return _describe_redraw(acao, game)
    elif acao.startswith('pass_'):
        return _describe_pass(acao)
    elif acao.startswith('target_'):
        parts = acao.split('_')
        if len(parts) == 3:
            return f'Escolher alvo: {parts[1]} -> {parts[2]}'
        return acao
    elif acao == 'reveal':
        return 'Revelar ações'
    elif acao.startswith('bluff_'):
        return _describe_bluff(acao, card_name, game)
    elif acao in ('end_combat', 'combat_end'):
        return 'Encerrar combate'
    elif acao.startswith('combat_to_'):
        return _describe_combat_transition(acao)
    elif acao == 'combat_wait':
        return 'Aguardando combate'
    elif acao == 'draw':
        return 'Comprar carta'

    # Fallback: formatar a acao tecnica
    return _format_fallback(acao)


def _find_card_name(acao: str, game=None) -> Optional[str]:
    """Tenta extrair o nome da carta da acao ou do log do jogo.

    Prioridade:
    1. Extrair card_id da action string e buscar nas zonas do jogo
       (mais preciso, evita nomes de cartas errados de entradas
       de log nao relacionadas).
    2. Fallback: ultima entrada 'jogou'/'usou' do log.
    """
    # 1. Tentar extrair ID da carta da acao e buscar nas zonas
    card_id = _extract_card_id(acao, game)
    if card_id and game:
        for p in game.players:
            for zone in (p.pack_home, p.hand, p.discard_combat, p.discard_sept,
                         p.hunting_grounds, p.umbra, p.victory_pile):
                for c in zone:
                    if c.card_id == card_id:
                        return c.name
    # 1b. Fallback: buscar pelo nome do banco usando o slug
    if not card_id:
        slug = _extract_action_name(acao)
        if slug:
            from rage_web.models.card import Card as CardModel
            try:
                slug_normalized = slug.lower().replace(' ', '-')
                card_banco = CardModel.query.filter_by(slug=slug_normalized).first()
                if card_banco:
                    return card_banco.name
            except Exception:
                pass

    # 2. Fallback: usar o nome da action string
    # Extrai o slug da action (ex: use_careful-strike_modo0 -> Careful Strike)
    action_name = _extract_action_name(acao)
    if action_name:
        return action_name

    return None


def _find_card_type(acao: str, game=None) -> Optional[str]:
    """Tenta extrair o tipo da carta."""
    # 1. Buscar nas zonas do jogo
    card_id = _extract_card_id(acao, game)
    if card_id and game:
        for p in game.players:
            for zone in (p.pack_home, p.hand, p.discard_combat, p.discard_sept,
                         p.hunting_grounds, p.umbra, p.victory_pile):
                for c in zone:
                    if c.card_id == card_id:
                        return c.card_type
    # 2. Fallback: buscar pelo slug no CARTAS_EXEMPLO (em memoria, sem banco)
    slug = _extract_action_name(acao)
    if slug:
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        slug_norm = slug.lower().replace(' ', '-')
        modelo = CARTAS_EXEMPLO.get(slug_norm)
        if modelo:
            return modelo.tipo
    return None


_slug_to_id_cache: dict[str, int] = {}


def _extract_card_id(acao: str, game=None) -> Optional[int]:
    """Extrai o ID da carta de uma string de acao."""
    # Padroes: use_card_790_modo0, play_character_123, umbra_step_134, etc.
    match = re.search(r'(?:card_|step_|back_|play_|declare_|attack_|eliminate_|feint_|alpha_)(\d+)', acao)
    if match:
        return int(match.group(1))
    # Formato alternativo: use_<slug>_modo<N>
    # Extrai o slug e busca no cache ou no banco
    if acao.startswith('use_'):
        rest = acao[4:]
        if '_modo' in rest:
            slug = rest[:rest.index('_modo')]
            if slug in _slug_to_id_cache:
                return _slug_to_id_cache[slug]
            try:
                from rage_web.models.card import Card
                card = Card.query.filter_by(slug=slug).first()
                if card:
                    _slug_to_id_cache[slug] = card.id
                    return card.id
            except Exception:
                pass
    return None


def _extract_action_name(acao: str) -> Optional[str]:
    """Extrai o nome da carta da propria string de acao.

    Ex: use_careful-strike_modo0 -> Careful Strike
        use_razor-claws_modo0 -> Razor Claws
    """
    # Formato: use_<slug>_modo<N> ou play_<slug>
    for prefix in ('use_', 'play_', 'declare_'):
        if acao.startswith(prefix):
            rest = acao[len(prefix):]
            # Remover modo
            if '_modo' in rest:
                rest = rest[:rest.index('_modo')]
            # Remover card_id (declare_12345_acao)
            parts = rest.split('_')
            if parts and parts[0].isdigit():
                parts = parts[1:]
            slug = '_'.join(parts)
            # Converter slug para nome legivel
            return slug.replace('-', ' ').replace('_', ' ').title()
    return None


def _describe_use_card(acao: str, card_name: Optional[str], card_type: Optional[str], game=None) -> str:
    """Descreve acoes de uso de carta (use_card_XXX_modoY ou use_XXX_modoY)."""
    # Extrair modo
    modo_match = re.search(r'modo(\d+)', acao)
    modo = modo_match.group(1) if modo_match else None

    nome = card_name or 'Carta desconhecida'
    tipo = card_type or ''

    # Se o nome veio do log (pode estar errado), usar o slug da acao
    if nome and nome != 'Carta desconhecida':
        slug_name = _extract_action_name(acao)
        if slug_name and nome != slug_name:
            nome = slug_name

    # Buscar o tipo pelo slug (mais confiavel que o card_type do CardInstance)
    slug = _extract_action_name(acao)
    if slug:
        from rage_web.models.card import Card as CardModel
        try:
            slug_norm = slug.lower().replace(' ', '-')
            card_banco = CardModel.query.filter_by(slug=slug_norm).first()
            if card_banco:
                tipo = card_banco.tipo
        except Exception:
            pass

    if tipo:
        tipo_human = CARD_TYPE_HUMAN.get(tipo, tipo)
        if 'careful' in acao.lower():
            import sys as _sys
            print(f'[DBG] nome={nome}, tipo={tipo}, tipo_human={tipo_human}, modo={modo}', file=_sys.stderr)
        if modo and modo != '0':
            return f'Usou {nome} ({tipo_human}, modo {modo})'
        return f'Usou {nome} ({tipo_human})'

    if modo and modo != '0':
        return f'Usou {nome} (modo {modo})'
    return f'Usou {nome}'


def _describe_play_card(acao: str, card_name: Optional[str], card_type: Optional[str], game=None) -> str:
    """Descretes acoes de jogar carta (play_XXX_YYY)."""
    nome = card_name or 'Carta desconhecida'
    tipo = card_type or ''

    # Determinar tipo da acao
    if 'character' in acao.lower():
        return f'Jogou {nome} (Personagem)'
    elif tipo:
        tipo_human = CARD_TYPE_HUMAN.get(tipo, tipo)
        return f'Jogou {nome} ({tipo_human})'

    return f'Jogou {nome}'


def _describe_moot(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de Moot."""
    if 'chamar' in acao:
        nome = card_name or _extract_moot_name(acao)
        return f'Convocou Junta: {nome}'
    elif 'voto' in acao:
        nome = card_name or _extract_moot_name(acao)
        return f'Votou na Junta: {nome}'
    return f'Ação de Moot: {acao}'


def _extract_moot_name(acao: str) -> str:
    """Extrai o nome do Moot da acao."""
    # moot_chamar_Skindancer -> Skindancer
    # moot_voto_Silver Record -> Silver Record
    parts = acao.split('_', 2)
    if len(parts) > 2:
        return parts[2].replace('_', ' ')
    return acao


def _describe_umbra(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de Umbra."""
    if 'step' in acao:
        nome = card_name or f'Personagem #{_extract_card_id(acao, game)}'
        return f'{nome} entrou na Umbra'
    elif 'back' in acao:
        nome = card_name or f'Personagem #{_extract_card_id(acao, game)}'
        return f'{nome} voltou da Umbra'
    return f'Ação de Umbra'


def _describe_declare(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de declaracao de combate."""
    # declare_1469_block -> Personagem 1469 declarou Block
    # declare_1469_head_butt -> Personagem 1469 declarou Head Butt
    card_id = _extract_card_id(acao, game)
    # Extrair acao de combate (tudo apos o card_id)
    # Formato: declare_<card_id>_<acao> onde acao pode ter underscores
    prefix = f'declare_{card_id}_'
    if acao.startswith(prefix):
        combat_action = acao[len(prefix):]
    else:
        combat_action = acao.split('_')[-1] if '_' in acao else acao
    combat_human = COMBAT_ACTIONS_HUMAN.get(combat_action, combat_action)

    if card_name:
        return f'{card_name} declarou {combat_human}'
    elif card_id:
        return f'Personagem #{card_id} declarou {combat_human}'
    return f'Declarou {combat_human}'


def _describe_attack(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de ataque."""
    if 'hg' in acao:
        return 'Atacou Hunting Grounds'
    elif 'alpha' in acao:
        nome = card_name or f'Personagem #{_extract_card_id(acao, game)}'
        return f'{nome} atacou (Alpha)'
    else:
        nome = card_name or f'Personagem #{_extract_card_id(acao, game)}'
        return f'{nome} atacou'


def _describe_feint(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de Feint."""
    card_id = _extract_card_id(acao, game)
    parts = acao.split('_')
    nova_acao = parts[-1] if parts else ''
    nova_human = COMBAT_ACTIONS_HUMAN.get(nova_acao, nova_acao)

    if card_name:
        return f'{card_name} usou Feint! Nova ação: {nova_human}'
    elif card_id:
        return f'Personagem #{card_id} usou Feint! Nova ação: {nova_human}'
    return f'Feint: {nova_human}'


def _describe_alpha(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de alpha."""
    if 'attack' in acao:
        return 'Ataque Alpha'
    if 'challenge_refused' in acao:
        return 'Desafio Recusado'
    if 'challenge' in acao:
        return 'Desafio Alpha'
    return 'Ação Alpha'


def _describe_redraw(acao: str, game=None) -> str:
    """Descreve acoes de redraw."""
    if 'descarte' in acao:
        match = re.search(r'descarte_(\d+)', acao)
        qtd = match.group(1) if match else '?'
        return f'Descartou {qtd} carta(s) e comprou'
    return 'Comprou cartas'


def _describe_pass(acao: str) -> str:
    """Descreve acoes de passar."""
    parts = acao.split('_')
    if len(parts) > 1:
        fase = parts[1]
        fase_human = PHASE_HUMAN.get(fase, fase)
        return f'Passou ({fase_human})'
    return 'Passou'


# Nomes amigaveis para steps de combate
COMBAT_STEP_NAMES = {
    'pre_combat': 'Pré-Combate',
    'beginning_of_combat': 'Início do Combate',
    'play_card': 'Jogar Carta',
    'targeting': 'Atribuir Alvos',
    'reveal': 'Revelar',
    'feint': 'Finta',
    'bluff': 'Blefe',
    'resolution': 'Resolução',
    'withdrawal': 'Retirada',
    'between_rounds': 'Entre Rodadas',
    'end': 'Fim do Combate',
}


def _describe_combat_transition(acao: str) -> str:
    """Descreve transicoes de step de combate.

    Acao: combat_to_pre_combat, combat_to_play_card, etc.
    """
    # Extrai o nome do step apos 'combat_to_'
    step_name = acao[len('combat_to_'):]
    nome = COMBAT_STEP_NAMES.get(step_name, step_name.replace('_', ' '))
    return f'→ {nome}'


def _format_fallback(acao: str) -> str:
    """Formata acoes desconhecidas de forma legivel."""
    # Substituir underscores por espaços
    legivel = acao.replace('_', ' ')
    # Capitalizar primeira letra
    return legivel.capitalize()


def _describe_bluff(acao: str, card_name: Optional[str], game=None) -> str:
    """Describe uma acao de blefe (jogar Combat Action sem atender requisitos)."""
    parts = acao.split('_')
    if len(parts) >= 3 and card_name:
        return f'Blefe com {card_name}'
    return 'Blefe'


# ---------------------------------------------------------------------------
# Descricoes de estado do jogo
# ---------------------------------------------------------------------------

def describe_zone(zone: str) -> str:
    """Converte nome de zona em descricao humana."""
    zones = {
        'pack_home': 'Pack Home',
        'hunting_grounds': 'Hunting Grounds',
        'umbra': 'Umbra',
        'deck_combat': 'Deck de Combate',
        'deck_sept': 'Deck de Sept',
        'hand': 'Mão',
        'discard_combat': 'Descarte de Combate',
        'discard_sept': 'Descarte de Sept',
        'victory_pile': 'Pilha de Vitória',
        'out_of_play': 'Fora de Jogo',
    }
    return zones.get(zone, zone)


def describe_card_type(card_type: str) -> str:
    """Converte tipo de carta em descricao humana."""
    return CARD_TYPE_HUMAN.get(card_type, card_type)


def describe_phase(phase: str) -> str:
    """Converte nome de fase em descricao humana."""
    return PHASE_HUMAN.get(phase, phase)
