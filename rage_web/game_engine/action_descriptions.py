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
    if acao.startswith('use_card_'):
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
    elif acao in ('end_combat', 'combat_end'):
        return 'Encerrar combate'
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
    # 1. Tentar extrair ID da carta da acao (mais preciso)
    card_id = _extract_card_id(acao)
    if card_id and game:
        for p in game.players:
            for zone in (p.pack_home, p.hand, p.discard_combat, p.discard_sept,
                         p.hunting_grounds, p.umbra):
                for c in zone:
                    if c.card_id == card_id:
                        return c.name

    # 2. Fallback: extrair do log do jogo
    if game and game.log:
        for log_entry in reversed(game.log):
            if 'jogou ' in log_entry:
                partes = log_entry.split('jogou ')
                if len(partes) > 1:
                    return partes[1].strip()
            elif 'usou ' in log_entry:
                partes = log_entry.split('usou ')
                if len(partes) > 1:
                    nome = partes[1].strip()
                    # Remover parenteses extras
                    if ' (' in nome:
                        nome = nome[:nome.index(' (')]
                    return nome

    return None


def _find_card_type(acao: str, game=None) -> Optional[str]:
    """Tenta extrair o tipo da carta."""
    card_id = _extract_card_id(acao)
    if card_id and game:
        for p in game.players:
            for zone in (p.pack_home, p.hand, p.discard_combat, p.discard_sept,
                         p.hunting_grounds, p.umbra):
                for c in zone:
                    if c.card_id == card_id:
                        return c.card_type
    return None


def _extract_card_id(acao: str) -> Optional[int]:
    """Extrai o ID da carta de uma string de acao."""
    # Padroes: use_card_790_modo0, play_character_123, umbra_step_134, etc.
    match = re.search(r'(?:card_|step_|back_|play_|declare_|attack_|eliminate_|feint_|alpha_)(\d+)', acao)
    if match:
        return int(match.group(1))
    return None


def _describe_use_card(acao: str, card_name: Optional[str], card_type: Optional[str], game=None) -> str:
    """Descreve acoes de uso de carta (use_card_XXX_modoY)."""
    # Extrair modo
    modo_match = re.search(r'modo(\d+)', acao)
    modo = modo_match.group(1) if modo_match else None

    nome = card_name or 'Carta desconhecida'
    tipo = card_type or ''

    if tipo:
        tipo_human = CARD_TYPE_HUMAN.get(tipo, tipo)
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
        nome = card_name or f'Personagem #{_extract_card_id(acao)}'
        return f'{nome} entrou na Umbra'
    elif 'back' in acao:
        nome = card_name or f'Personagem #{_extract_card_id(acao)}'
        return f'{nome} voltou da Umbra'
    return f'Ação de Umbra'


def _describe_declare(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de declaracao de combate."""
    # declare_1469_block -> Personagem 1469 declarou Block
    card_id = _extract_card_id(acao)
    # Extrair acao de combate
    parts = acao.split('_')
    combat_action = parts[-1] if parts else ''
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
        nome = card_name or f'Personagem #{_extract_card_id(acao)}'
        return f'{nome} atacou (Alpha)'
    else:
        nome = card_name or f'Personagem #{_extract_card_id(acao)}'
        return f'{nome} atacou'


def _describe_feint(acao: str, card_name: Optional[str], game=None) -> str:
    """Descreve acoes de Feint."""
    card_id = _extract_card_id(acao)
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


def _format_fallback(acao: str) -> str:
    """Formata acoes desconhecidas de forma legivel."""
    # Substituir underscores por espaços
    legivel = acao.replace('_', ' ')
    # Capitalizar primeira letra
    return legivel.capitalize()


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
