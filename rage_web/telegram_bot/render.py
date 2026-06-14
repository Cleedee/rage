"""Renderização do estado do jogo para mensagens do Telegram.

Formata GameState, cartas, tabuleiro e ações em texto mono-espaçado
com emojis para tornar a experiência visual no chat mais agradável.
"""

from __future__ import annotations

from typing import Optional

from rage_web.game_engine.state import GameState, CardInstance, Zone
from rage_web.game_engine.combat_queue import get_declaration_summary


# ── Ícones ──────────────────────────────────────────────────────────

ICONES = {
    'rage': '🩸',
    'gnosis': '🧠',
    'health': '💚',
    'health_current': '❤️',
    'renown': '👑',
    'victory': '🏆',
    'hand': '🃏',
    'deck': '📚',
    'discard': '🗑️',
    'pack': '🏠',
    'hg': '🎯',
    'umbra': '🌙',
    'combat': '⚔️',
    'shield': '🛡️',
    'death': '💀',
    'check': '✅',
    'cross': '❌',
    'pass': '⏭️',
    'play': '▶️',
    'tap': '🔴',
    'untap': '🟢',
    'face_down': '⬇️',
    'face_up': '⬆️',
    'equip': '🔧',
    'gift': '🎁',
    'ally': '🤝',
    'enemy': '👹',
    'victim': '👤',
    'caern': '🏛️',
    'territory': '🗺️',
    'quest': '📜',
    'event': '📅',
    'moot': '🗳️',
    'rite': '🕯️',
    'frenzy': '😡',
    'crinos': '🐺',
    'spirit': '👻',
    'star': '⭐',
    'info': 'ℹ️',
    'warning': '⚠️',
    'hourglass': '⏳',
    'trophy': '🏅',
    'sep': '━',
    'board': '🗺️',
    'status': '📊',
    'draw': '📥',
    'next': '⏩',
}

FASE_ICONES = {
    'redraw': '🔄',
    'regeneration': '💚',
    'resource': '🛠️',
    'umbra': '🌙',
    'moot': '🗳️',
    'combat': '⚔️',
}

TIPO_ICONES = {
    'character': '🐺',
    'gift': '🎁',
    'equipment': '🔧',
    'ally': '🤝',
    'enemy': '👹',
    'victim': '👤',
    'combat action': '⚡',
    'event': '📅',
    'territory': '🗺️',
    'caern': '🏛️',
    'quest': '📜',
    'rite': '🕯️',
    'moot': '🗳️',
    'action': '📋',
    'battlefield': '🏟️',
}


# ── Helpers ─────────────────────────────────────────────────────────

def _tipo_icone(card_type: str) -> str:
    """Retorna o ícone apropriado para o tipo da carta."""
    if not card_type:
        return '🃏'
    ct = card_type.lower().strip()
    for key, icon in TIPO_ICONES.items():
        if key in ct:
            return icon
    return '🃏'


def _status_bar(valor: int, max_valor: int, filled: str = '█',
                empty: str = '░', size: int = 8) -> str:
    """Barra de progresso estilo HP."""
    if max_valor <= 0:
        return empty * size
    ratio = max(0, min(1, valor / max_valor))
    filled_count = round(ratio * size)
    return filled * filled_count + empty * (size - filled_count)


def _card_short(card: CardInstance) -> str:
    """Representação compacta de uma carta: nome (atributos)."""
    partes = [card.name[:18]]
    if card.health > 0:
        hp = f'{ICONES["health_current"]}{card.health_current}/{card.health}'
        partes.append(hp)
    if card.rage > 0:
        partes.append(f'{ICONES["rage"]}{card.rage}')
    if card.gnosis > 0:
        partes.append(f'{ICONES["gnosis"]}{card.gnosis}')
    if card.is_face_down:
        partes.append('⬇️')
    return ' '.join(partes)


def _card_detail(card: CardInstance) -> str:
    """Detalhes completos de uma carta."""
    icon = _tipo_icone(card.card_type or '')
    lines = [
        f'{icon} *{card.name}*',
        f'   Tipo: {card.card_type or "—"} | Renome: {card.renown or 0}',
    ]
    attr_parts = []
    if card.health > 0:
        bar = _status_bar(card.health_current, card.health)
        attr_parts.append(
            f'{ICONES["health"]}{card.health} {bar}'
            f' {card.health_current}/{card.health}'
        )
    if card.rage > 0:
        attr_parts.append(f'{ICONES["rage"]}{card.rage}')
    if card.gnosis > 0:
        attr_parts.append(f'{ICONES["gnosis"]}{card.gnosis}')
    if attr_parts:
        lines.append(f'   {" | ".join(attr_parts)}')
    if card.is_face_down:
        lines.append(f'   {ICONES["face_down"]} Face-down')
    if card.damage:
        lines.append(f'   Dano: {card.damage}')
    if card.keywords:
        lines.append(f'   {card.keywords}')
    if card.text:
        lines.append(f'   _{card.text[:80]}_')
    # Cartas anexadas (damage, equipment)
    if card.total_dano:
        lines.append(f'   {ICONES["death"]} Dano: {card.total_dano}')
    if card.attached_equipment:
        eqs = ', '.join(e.name[:12] for e in card.attached_equipment)
        lines.append(f'   {ICONES["equip"]} {eqs}')
    return '\n'.join(lines)


# ── Renderização principal ──────────────────────────────────────────

def render_game_status(game: GameState,
                       player_id: Optional[str] = None) -> str:
    """Visão geral do jogo: fase, turno, VP, oponente."""
    fase_icone = FASE_ICONES.get(game.phase, '❓')
    lines = [
        f'{ICONES["info"]} *Rage CCG — Turno {game.turn_number}*'
        f' {fase_icone} {game.phase.upper()}',
    ]
    for p in game.players:
        eh_vez = p.id == game.current_player.id
        marcador = '🎯' if eh_vez else '  '
        icon_p = ICONES["star"] if eh_vez else ''
        nome = p.name
        if player_id and p.id == player_id:
            nome = f'{nome} (você)'
        lines.append(
            f'{marcador} {icon_p} *{nome}*'
            f'  🃏{len(p.hand)}'
            f'  {ICONES["victory"]}{p.victory_points}'
            f'  📚C{len(p.deck_combat)} S{len(p.deck_sept)}'
        )
    # Fase de combate
    if game.combat.is_active:
        lines.append('')
        lines.append(render_combat_summary(game))
    return '\n'.join(lines)


def render_board(game: GameState, player_id: str) -> str:
    """Tabuleiro completo, focado no jogador."""
    lines = [render_game_status(game, player_id)]
    lines.append('')
    lines.append(f'{ICONES["sep"]}{"─" * 35}')

    # Encontra o jogador
    player = None
    opponent = None
    for p in game.players:
        if p.id == player_id:
            player = p
        else:
            opponent = p

    if not player:
        return 'Jogador não encontrado.'

    # ── Pack Home (personagens em jogo) ──
    lines.append(f'\n{ICONES["pack"]} *Pack* (seus personagens):')
    if player.pack_home:
        for i, c in enumerate(player.pack_home):
            tap = '🔴' if c.is_tapped else '🟢'
            hp_info = ''
            if c.health > 0:
                bar = _status_bar(c.health_current, c.health, size=4)
                hp_info = f' {bar} {c.health_current}/{c.health}'
            lines.append(f'   {tap} `[{i}]` {c.name[:16]}')
            if hp_info:
                lines.append(f'       {ICONES["health"]}{hp_info}')
    else:
        lines.append(f'   (vazio)')

    # ── Hunting Grounds ──
    hg_count = len(player.hunting_grounds)
    if hg_count > 0:
        lines.append(f'\n{ICONES["hg"]} *Hunting Grounds* ({hg_count}):')
        for i, c in enumerate(player.hunting_grounds):
            lines.append(f'   `[{i}]` {c.name[:20]}'
                         f' {ICONES["rage"]}{c.rage}')

    # ── Umbra ──
    if player.umbra:
        lines.append(f'\n{ICONES["umbra"]} *Umbra* ({len(player.umbra)}):')
        for c in player.umbra:
            lines.append(f'   {c.name[:20]}')

    # ── Oponente ──
    if opponent:
        op_hp = sum(c.health_current for c in opponent.pack_home)
        op_atk = sum(c.rage for c in opponent.pack_home if not c.is_tapped)
        op_hg = len(opponent.hunting_grounds)
        lines.append(f'\n*Oponente: {opponent.name}*'
                     f'  ({len(opponent.pack_home)} 🏠)'
                     f'  (❤️{op_hp})  (⚔️{op_atk})')
        if opponent.pack_home:
            for c in opponent.pack_home[:3]:  # Só mostra 3
                tap = '🔴' if c.is_tapped else '🟢'
                lines.append(f'   {tap} {c.name[:18]}'
                             f' {ICONES["health"]}{c.health_current}/{c.health}')
            if len(opponent.pack_home) > 3:
                lines.append(f'   ... +{len(opponent.pack_home)-3} mais')
        lines.append(f'   {ICONES["hg"]}{op_hg} {ICONES["umbra"]}{len(opponent.umbra)}'
                     f' {ICONES["hand"]}{len(opponent.hand)} na mão')

    # ── Victory Pile ──
    vp_total = sum(1 for p in game.players for _ in p.victory_pile)
    if vp_total > 0:
        lines.append(f'\n{ICONES["victory"]} *Victory Pile*:')
        for p in game.players:
            if p.victory_pile:
                nomes = ', '.join(
                    c.name[:15] for c in p.victory_pile[-5:]
                )
                lines.append(f'   {p.name}: {len(p.victory_pile)} ({nomes})')

    # ── Discard ──
    discards = []
    if player.discard_combat:
        discards.append(f'{ICONES["combat"]}{len(player.discard_combat)}')
    if player.discard_sept:
        discards.append(f'{ICONES["caern"]}{len(player.discard_sept)}')
    if discards:
        lines.append(f'\n{ICONES["discard"]} Descarte: {" | ".join(discards)}')

    return '\n'.join(lines)


def render_hand(game: GameState, player_id: str) -> str:
    """Mão do jogador com índice para jogar.

    Mostra cada carta com um mini-retrato visual.
    """
    player = next((p for p in game.players if p.id == player_id), None)
    if not player:
        return 'Jogador não encontrado.'

    if not player.hand:
        return f'{ICONES["hand"]} Sua mão está vazia.'

    lines = [
        f'{ICONES["hand"]} *Sua mão* ({len(player.hand)} cartas, '
        f'máx {len(player.hand)})',
    ]

    for i, card in enumerate(player.hand):
        icon = _tipo_icone(card.card_type or '')
        tipo = (card.card_type or '—').upper()[:6]

        # Linha de atributos compacta
        attrs = []
        if card.health > 0:
            attrs.append(f'{ICONES["health"]}{card.health}')
        if card.rage > 0:
            attrs.append(f'{ICONES["rage"]}{card.rage}')
        if card.gnosis > 0:
            attrs.append(f'{ICONES["gnosis"]}{card.gnosis}')
        if card.renown:
            attrs.append(f'{ICONES["renown"]}{card.renown}')
        attr_str = f' [{" ".join(attrs)}]' if attrs else ''

        modelo = ''
        if card.modelo_id:
            modelo = f' ✨'

        # Nome + tipo
        nome = card.name[:20]
        lines.append(f'{icon} `[{i:2d}]` *{nome}* ({tipo}){attr_str}{modelo}')

        # Mini HP bar
        if card.health > 0 and card.health_current:
            bar = _status_bar(card.health_current, card.health, size=5)
            lines.append(f'       ❤️ `{card.health_current:2d}/{card.health:<2d}` {bar}')

        # Texto curto
        if card.text:
            texto = card.text[:50].replace('\n', ' ')
            lines.append(f'       _{texto}_')

        # Separador entre cartas
        if i < len(player.hand) - 1:
            lines.append(f'       {ICONES["sep"]}{"─" * 30}')

    return '\n'.join(lines)


def render_combat_summary(game: GameState) -> str:
    """Sumário do combate atual."""
    if not game.combat.is_active:
        return ''

    cs = game.combat
    lines = [
        f'{ICONES["combat"]} *COMBATE* [{cs.step}]',
        f'   Atacantes: {", ".join(cs.attackers) or "—"}',
        f'   Defensores: {", ".join(cs.defenders) or "—"}',
    ]
    if cs.last_to_declare:
        lines.append(f'   Último a Declarar: {cs.last_to_declare}')

    summary = get_declaration_summary(game)
    if 'declarations' in summary:
        lines.append(f'\n   Declarações:')
        for cid, action in summary['declarations'].items():
            lines.append(f'      {cid}: {action}')
    if 'declared_count' in summary:
        lines.append(f'   Declarados: {summary["declared_count"]}')

    return '\n'.join(lines)


def render_legal_actions(game: GameState, player_id: str) -> str:
    """Ações disponíveis para o jogador."""
    cp = game.current_player
    if cp.id != player_id:
        return f'{ICONES["hourglass"]} Não é sua vez. Aguarde o oponente.'

    actions = [f'{ICONES["info"]} *Ações disponíveis:*\n']

    if game.combat.is_active:
        actions.append(f'   {ICONES["play"]} `/declare <card_id> <acao>`')
        actions.append(f'   {ICONES["play"]} `/reveal`')
        if game.combat.step == 'reveal':
            actions.append(f'   {ICONES["play"]} `/feint <card_id> <acao>`')
        if game.combat.step in ('reveal', 'resolve'):
            actions.append(f'   {ICONES["play"]} `/resolve`')
            actions.append(f'   {ICONES["cross"]} `/endcombat`')
    else:
        actions.append(f'   {ICONES["play"]} `/play <N>` — Jogar carta N da mão')
        actions.append(f'   {ICONES["hand"]} `/use <N>` — Usar carta de efeito')
        actions.append(f'   {ICONES["combat"]} `/attack <id> [alvo]`')
        actions.append(f'   {ICONES["draw"]} `/draw [deck] [qtd]`')
        actions.append(f'   {ICONES["pass"]} `/pass` — Passar a vez')
        actions.append(f'   {ICONES["next"]} `/next` — Avançar fase')

    actions.append(f'')
    actions.append(f'   {ICONES["board"]} `/board` — Ver tabuleiro')
    actions.append(f'   {ICONES["hand"]} `/hand` — Ver mão')
    actions.append(f'   {ICONES["status"]} `/status` — Status resumido')
    actions.append(f'   {ICONES["death"]} `/concede` — Desistir')

    return '\n'.join(actions)


def render_card_portrait(card: CardInstance) -> str:
    """Retrato visual de carta estilo card game.

    Cria uma representação visual rica com emojis e formatação
    que simula uma carta de jogo no chat.
    """
    icon = _tipo_icone(card.card_type or '')
    bar = ''
    if card.health > 0:
        bar = _status_bar(card.health_current, card.health)

    # 🔲 Moldura superior
    lines = [f'{"▔" * 28}']

    # Nome + tipo
    tipo = (card.card_type or '—').upper()
    lines.append(f'▎{icon} *{card.name:24s}* ▎')
    lines.append(f'▎ `{tipo:24s}` ▎')

    # Atributos (se houver)
    attrs = []
    if card.health > 0:
        attrs.append(f'{ICONES["health"]}{card.health}')
    if card.rage > 0:
        attrs.append(f'{ICONES["rage"]}{card.rage}')
    if card.gnosis > 0:
        attrs.append(f'{ICONES["gnosis"]}{card.gnosis}')
    if card.renown:
        attrs.append(f'{ICONES["renown"]}{card.renown}')
    if attrs:
        a = ' | '.join(attrs)
        lines.append(f'▎ {a:26s} ▎')

    # HP bar
    if bar:
        lines.append(f'▎ ❤️ `{card.health_current:2d}/{card.health:<2d}` {bar} ▎')

    # ⬇️ Face-down
    if card.is_face_down:
        lines.append(f'▎ {ICONES["face_down"]} Face-down              ▎')

    # Dano anexado
    dmg_str = ''
    if card.total_dano:
        dmg_str = f'{ICONES["death"]} Dano: {card.total_dano}'
    eq_str = ''
    if card.attached_equipment:
        eqs = ', '.join(e.name[:10] for e in card.attached_equipment)
        eq_str = f'{ICONES["equip"]} {eqs}'
    if dmg_str or eq_str:
        linha = f'{dmg_str}  {eq_str}'[:28]
        lines.append(f'▎ {linha:26s} ▎')

    # Texto / descrição
    if card.text:
        texto = card.text[:60].replace('\n', ' ')
        # Quebra em linhas de 26 chars
        while texto:
            chunk = texto[:28]
            texto = texto[28:]
            lines.append(f'▎ _{chunk:26s}_ ▎')

    # 🔲 Moldura inferior
    keyword = card.keywords[:22] if card.keywords else ''
    if keyword:
        lines.append(f'▎ `{keyword:26s}` ▎')
    lines.append(f'{"▃" * 28}')

    return '\n'.join(lines)


def render_card_detail(card: CardInstance) -> str:
    """Detalhes completos de uma carta."""
    return _card_detail(card)


def render_deck_list(decks: list[tuple[int, str, int]], page: int = 0,
                     per_page: int = 10) -> str:
    """Lista de decks do jogador."""
    total = len(decks)
    start = page * per_page
    end = start + per_page
    page_decks = decks[start:end]

    lines = [
        f'{ICONES["info"]} *Seus Decks* '
        f'({total} total, página {page+1}/{max(1, (total-1)//per_page+1)}):\n'
    ]
    for did, nome, qtd in page_decks:
        lines.append(f'   `{did:4d}` {nome} ({qtd} cartas)')
    if total > per_page:
        lines.append(f'\nUse `/decks {page+2}` para próxima página.')
    return '\n'.join(lines)


def render_victory(game: GameState, winner_id: str) -> str:
    """Mensagem de fim de jogo."""
    lines = [
        f'{"🏆" * 10}',
        f'*FIM DE JOGO!*',
    ]
    for p in game.players:
        if p.id == winner_id:
            lines.append(f'   🥇 *{p.name} VENCEU!*'
                         f' ({p.victory_points} VP)')
        else:
            lines.append(f'   💀 {p.name} — {p.victory_points} VP')
    lines.append(f'{"🏆" * 10}')
    lines.append(f'Turnos: {game.turn_number}')
    return '\n'.join(lines)


def render_player_decks_html(decks: list[tuple[int, str, int]]) -> str:
    """Versão para mensagens de seleção de deck com numeração."""
    lines = ['*Seus decks disponíveis:*', '']
    for did, nome, qtd in decks:
        lines.append(f'   `{did}` — {nome} ({qtd} cartas)')
    lines.append('')
    lines.append('Use `/duel @jogador <deck_id>` para desafiar!')
    return '\n'.join(lines)
