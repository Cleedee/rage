"""Teclados inline para o Bot Telegram Rage CCG.

Constrói InlineKeyboardMarkup contextuais para cada situação de jogo:
  - Mão do jogador (jogar/usar carta)
  - Tabuleiro (ações disponíveis)
  - Combate (declarar, revelar, fingir)
  - Seleção de alvos
  - Navegação (board, hand, status)

Cada callback_data segue o formato: `ação:param1:param2`
"""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from rage_web.game_engine.state import GameState
from rage_web.game_engine.combat_queue import COMBAT_ACTIONS
from rage_web.telegram_bot.render import ICONES


# ── Helpers de layout ──────────────────────────────────────────────

def _btn(text: str, callback_data: str,
         width: int = 1) -> list[InlineKeyboardButton]:
    """Cria um botão."""
    return [InlineKeyboardButton(text, callback_data=callback_data)]


def _row(*buttons: tuple[str, str]) -> list[InlineKeyboardButton]:
    """Cria uma linha de botões: (texto, callback_data), ..."""
    return [InlineKeyboardButton(text, callback_data=cb) for text, cb in buttons]


def _build_menu(rows: list[list[InlineKeyboardButton]],
                ) -> InlineKeyboardMarkup:
    """Constrói o markup a partir de linhas de botões."""
    return InlineKeyboardMarkup(rows)


# ── Teclado da mão ─────────────────────────────────────────────────

def hand_keyboard(game: GameState, player_id: str) -> InlineKeyboardMarkup:
    """Botões para cada carta na mão: [Play N] [Use N] + navegação.

    Se a carta tiver modelo_id (efeito), mostra [Use N].
    Caso contrário, mostra [Play N].
    """
    player = next((p for p in game.players if p.id == player_id), None)
    if not player or not player.hand:
        return _build_menu([
            _row(('🗺️ Board', 'bd'), ('🃏 Hand', 'hd'), ('📊 Status', 'st')),
        ])

    rows = []
    for i, card in enumerate(player.hand):
        nome = card.name[:20]
        icon = '🐺' if card.modelo_id else '🃏'
        custo = ''
        if card.rage:
            custo += f'🩸{card.rage}'
        if card.gnosis:
            custo += f'🧠{card.gnosis}'
        label = f'{icon} {nome} {custo}'.strip()
        rows.append(_row((f'{label}', f'shw:cd:{i}')))

    # Linha de ações rápidas para as primeiras cartas
    action_row = []
    for i, card in enumerate(player.hand[:6]):
        if card.modelo_id:
            action_row.append((f'Usar {i}', f'u:{i}'))
        else:
            action_row.append((f'Jogar {i}', f'p:{i}'))

    if action_row:
        # Quebra em linhas de 3 botões
        for j in range(0, len(action_row), 3):
            chunk = action_row[j:j+3]
            rows.append(_row(*chunk))

    # Linha de navegação
    rows.append(_row(
        ('🗺️ Board', 'bd'),
        ('📊 Status', 'st'),
        ('⏭️ Passar', 'ps'),
    ))

    return _build_menu(rows)


# ── Teclado do tabuleiro ───────────────────────────────────────────

def board_keyboard(game: GameState, player_id: str) -> InlineKeyboardMarkup:
    """Ações contextuais baseadas no estado do jogo."""
    rows = []

    cp = next((p for p in game.players if p.id == player_id), None)
    is_my_turn = cp and cp.id == game.current_player.id

    if game.combat.is_active:
        # ── Em combate ──
        if is_my_turn:
            cs = game.combat
            rows.append(_row(('👁️ Revelar', 'rv'), ('💥 Resolver', 'rs'),
                            ('🏁 Encerrar', 'ec')))

            # Botões de declarar ações (se há personagens)
            if hasattr(cp, 'pack_home') and cp.pack_home:
                declare_btns = []
                for c in cp.pack_home[:4]:
                    cid = str(c.card_id)
                    declare_btns.append((f'⚔️ {c.name[:8]}', f'shw:dc:{cid}'))
                if declare_btns:
                    rows.append(_row(*declare_btns))

            rows.append(_row(('⏭️ Passar', 'ps')))
        else:
            rows.append(_row(('⏳ Aguardando oponente...', 'wait')))

    else:
        # ── Fora de combate ──
        if is_my_turn:
            # Mão → atalhos para primeiras cartas
            if cp and cp.hand:
                play_btns = []
                for i, c in enumerate(cp.hand[:5]):
                    if c.modelo_id:
                        play_btns.append((f'🎁 {c.name[:8]}', f'u:{i}'))
                    else:
                        play_btns.append((f'▶️ {c.name[:8]}', f'p:{i}'))
                if play_btns:
                    for j in range(0, len(play_btns), 3):
                        rows.append(_row(*play_btns[j:j+3]))

            # Ações de fase
            action_row = []
            if cp and cp.pack_home:
                for c in cp.pack_home[:3]:
                    cid = str(c.card_id)
                    action_row.append((f'⚔️ {c.name[:8]}', f'atk:{cid}:hg'))
            if action_row:
                rows.append(_row(*action_row))

            rows.append(_row(
                ('📥 Comprar', 'dr:c:1'),
                ('⏭️ Passar', 'ps'),
                ('⏩ Avançar', 'nx'),
            ))
        else:
            rows.append(_row(('⏳ Aguardando oponente...', 'wait')))

    # Navegação fixa
    rows.append(_row(
        ('🃏 Mão', 'hd'),
        ('🗺️ Board', 'bd'),
        ('📊 Status', 'st'),
    ))

    return _build_menu(rows)


# ── Teclado de combate ─────────────────────────────────────────────

def combat_keyboard(game: GameState, player_id: str) -> InlineKeyboardMarkup:
    """Ações específicas de combate."""
    rows = []
    cp = next((p for p in game.players if p.id == player_id), None)
    is_my_turn = cp and cp.id == game.current_player.id

    if not is_my_turn:
        return _build_menu([
            _row(('⏳ Aguardando oponente...', 'wait')),
            _row(('🗺️ Board', 'bd'), ('🃏 Mão', 'hd')),
        ])

    cs = game.combat

    # Botões de declarar para cada combatente do jogador
    if cs.step in ('declaration', 'play_card') or not cs.step:
        if cp:
            combatentes = [c for c in cp.pack_home
                          if str(c.card_id) in cs.attackers + cs.defenders
                          or c.health_current > 0]
            for c in combatentes[:4]:
                cid = str(c.card_id)
                # Menu de ações para esta criatura
                if c.card_id in [int(x) for x in cs.attackers
                                 if x.isdigit()] + [int(x) for x in cs.defenders
                                                     if x.isdigit()]:
                    rows.append(_row(
                        (f'{c.name[:10]} ⚔️ strike', f'dc:{cid}:strike'),
                        (f'🛡️ block', f'dc:{cid}:block'),
                    ))
                    rows.append(_row(
                        (f'💨 dodge', f'dc:{cid}:dodge'),
                        (f'🤼 grapple', f'dc:{cid}:grapple'),
                    ))
                else:
                    rows.append(_row(
                        (f'{c.name[:10]} ⚔️', f'atk:{cid}:hg'),
                    ))

    # Ações globais de combate
    action_btns = []
    if cs.step in ('declaration', 'play_card', ''):
        action_btns.append(('👁️ Revelar', 'rv'))
    if cs.step in ('reveal',):
        if cs.last_to_declare:
            action_btns.append(('🎭 Feint', 'shw:ft'))
        action_btns.append(('💥 Resolver', 'rs'))
    action_btns.append(('🏁 Encerrar', 'ec'))
    if action_btns:
        rows.append(_row(*action_btns))

    rows.append(_row(
        ('🗺️ Board', 'bd'),
        ('🃏 Mão', 'hd'),
        ('⏭️ Passar', 'ps'),
    ))

    return _build_menu(rows)


# ── Teclado de declaração (escolher ação para criatura) ────────────

COMBAT_ACTION_LABELS = {
    'strike': '⚔️ Strike',
    'block': '🛡️ Block',
    'dodge': '💨 Dodge',
    'grapple': '🤼 Grapple',
    'feint': '🎭 Feint',
    'frenzy': '😡 Frenzy',
    'overpower': '💪 Overpower',
    'retreat': '🏃 Retreat',
}


def declare_keyboard(card_id: str) -> InlineKeyboardMarkup:
    """Teclado para escolher ação de combate para uma criatura."""
    rows = []
    acts = list(COMBAT_ACTIONS)
    for i in range(0, len(acts), 2):
        chunk = acts[i:i+2]
        row = []
        for act in chunk:
            label = COMBAT_ACTION_LABELS.get(act, f'⚡ {act}')
            row.append((label, f'dc:{card_id}:{act}'))
        rows.append(_row(*row))

    rows.append(_row(('🔙 Voltar', 'bd')))
    return _build_menu(rows)


# ── Teclado de Feint (trocar ação) ─────────────────────────────────

def feint_keyboard(game: GameState) -> InlineKeyboardMarkup:
    """Teclado para Feint: escolher criatura e nova ação."""
    rows = []
    cs = game.combat
    if cs.last_to_declare:
        cid = cs.last_to_declare
        acts = list(COMBAT_ACTIONS)
        for i in range(0, len(acts), 2):
            chunk = acts[i:i+2]
            row = []
            for act in chunk:
                label = COMBAT_ACTION_LABELS.get(act, f'⚡ {act}')
                row.append((label, f'ft:{cid}:{act}'))
            rows.append(_row(*row))
    rows.append(_row(('🔙 Voltar', 'bd')))
    return _build_menu(rows)


# ── Teclado de navegação ───────────────────────────────────────────

def nav_keyboard() -> InlineKeyboardMarkup:
    """Teclado de navegação simples."""
    return _build_menu([
        _row(('🗺️ Board', 'bd'), ('🃏 Mão', 'hd'), ('📊 Status', 'st')),
        _row(('🎯 Ações', 'ac'), ('⏭️ Passar', 'ps'), ('🏳️ Conceder', 'cd')),
    ])


def wait_keyboard() -> InlineKeyboardMarkup:
    """Mostra que é a vez do oponente."""
    return _build_menu([
        _row(('⏳ Aguardando oponente...', 'wait')),
        _row(('🗺️ Board', 'bd'), ('🃏 Mão', 'hd'), ('📊 Status', 'st')),
    ])


def target_keyboard(game: GameState, player_id: str,
                    action_type: str = 'attack') -> InlineKeyboardMarkup:
    """Teclado para selecionar alvo.

    action_type: 'attack' → mostra alvos atacáveis
                 'use' → mostra alvos de efeito
    """
    rows = []
    player = next((p for p in game.players if p.id == player_id), None)
    if not player:
        return nav_keyboard()

    if action_type == 'attack':
        # Atacar Hunting Grounds
        rows.append(_row(('🎯 Hunting Grounds', 'atk:hg:hg')))

        # Criaturas do oponente
        for p in game.players:
            if p.id == player_id:
                continue
            for c in p.pack_home:
                if c.health_current > 0:
                    rows.append(_row(
                        (f'⚔️ {c.name[:15]} ❤️{c.health_current}',
                         f'atk:{c.card_id}:hg')
                    ))

        # Presas no Hunting Grounds global
        hg_cards = getattr(game, 'hunting_grounds_cards', [])
        for c in hg_cards:
            if c.health_current > 0:
                rows.append(_row(
                    (f'🎯 {c.name[:15]} ❤️{c.health_current}',
                     f'atk:{c.card_id}:hg')
                ))

    rows.append(_row(('🔙 Voltar', 'bd')))
    return _build_menu(rows)
