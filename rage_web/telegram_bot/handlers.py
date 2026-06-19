"""Handlers de comandos e callbacks do bot Telegram.

Organizado em grupos lógicos:
  - Comandos básicos: /start, /help
  - Decks: /decks
  - Matchmaking: /duel, /accept, /decline, /cancel
  - Jogabilidade: /play, /use, /attack, /declare, /reveal, /feint,
    /resolve, /endcombat, /draw, /pass, /next
  - Informação: /board, /hand, /status, /card
  - Utilitários: /concede, /quit

Cada handler recebe (update, context) e interage com o GameManager
e o Matchmaker.
"""

from __future__ import annotations

import re
import random
import asyncio
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from rage_web.telegram_bot.game_manager import GameManager
from rage_web.telegram_bot.matchmaker import Matchmaker
from rage_web.telegram_bot.i18n import t, LANGUAGES
from rage_web.telegram_bot.user_registry import auto_register, register_user
from rage_web.telegram_bot.stats import StatsManager
from rage_web.telegram_bot.keyboards import (
    hand_keyboard, board_keyboard, combat_keyboard,
    declare_keyboard, feint_keyboard, nav_keyboard,
    wait_keyboard, target_keyboard,
)
from rage_web.telegram_bot.render import (
    render_board, render_hand, render_game_status,
    render_legal_actions, render_victory, render_card_detail,
    render_deck_list, render_combat_summary, render_card_portrait,
    ICONES,
)


# ── Instâncias globais dos gerenciadores ────────────────────────────

game_manager = GameManager()
matchmaker = Matchmaker()
stats_manager = StatsManager()


# ── Decks com estratégia disponíveis para o bot ──────────────────────

# Telegram ID fake para o bot (nao conflita com usuarios reais)
BOT_TELEGRAM_ID = -1

# Decks que o bot pode usar (tem config de estrategia)
BOT_DECKS: dict[int, str] = {
    465: 'Apocalypse — First Team #21 (Wyrm Pentex, aggro)',
    1044: 'Ajaba — Hienas da Savana (combo, Frenesi+Crush)',
    1055: 'O Julgamento — Philodox (controle, cura+defesa)',
}

# Nomes para os bots
BOT_NAMES: dict[int, str] = {
    465: 'Bot Wyrm',
    1044: 'Bot Ajaba',
    1055: 'Bot Philodox',
}


# ── Helpers ─────────────────────────────────────────────────────────

def _get_player_id(update: Update) -> int:
    """Retorna o Telegram user ID."""
    return update.effective_user.id


def _get_player_name(update: Update) -> str:
    """Retorna o nome de exibição do jogador."""
    user = update.effective_user
    return user.full_name or user.username or f'User{user.id}'


def _get_username(update: Update) -> str:
    """Retorna o @username ou 'User' do jogador."""
    user = update.effective_user
    return f'@{user.username}' if user.username else user.full_name


def _mention(update: Update) -> str:
    """Mensão no formato Markdown."""
    user = update.effective_user
    if user.username:
        return f'@{user.username}'
    return f'[{user.full_name}](tg://user?id={user.id})'


def _extract_mentions(text: str) -> list[str]:
    """Extrai @mentions de um texto."""
    return re.findall(r'@(\w+)', text)


async def _send_card_image(context, chat_id: int, card) -> bool:
    """Tenta enviar a imagem de uma carta.

    Verifica se existe arquivo de imagem (fan_image) para a carta
    e envia como foto. Retorna True se conseguiu, False se não.
    """
    from rage_web import create_app
    from rage_web.models.card import Card as CardModel

    # Verifica se a carta tem fan_image
    if not hasattr(card, 'fan_image') or not card.fan_image:
        return False

    # Constrói o path da imagem
    try:
        app = create_app()
        with app.app_context():
            img_path = str(app.instance_path / 'images' / card.fan_image)
            import os
            if os.path.isfile(img_path):
                with open(img_path, 'rb') as f:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=f'🖼️ *{card.name}*',
                        parse_mode='Markdown',
                    )
                    return True
    except Exception:
        pass
    return False


def _parse_int(text: str, default=None) -> Optional[int]:
    """Tenta extrair um inteiro de um texto."""
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else default


def _ensure_not_in_game(update: Update, context) -> bool:
    """Verifica se o jogador NÃO está em uma partida ativa.

    Se estiver, envia mensagem e retorna False.
    """
    uid = _get_player_id(update)
    if game_manager.is_player_in_game(uid):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'{ICONES["warning"]} Você já está em uma partida ativa!'
                 f' Use `/concede` para desistir ou `/status` para ver.',
        )
        return False
    return True


def _ensure_in_game(update: Update, context) -> bool:
    """Verifica se o jogador está em uma partida ativa.

    Se não estiver, envia mensagem e retorna False.
    """
    uid = _get_player_id(update)
    if not game_manager.is_player_in_game(uid):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'{ICONES["warning"]} Você não está em nenhuma partida.'
                 f' Use `/duel @jogador <deck_id>` para desafiar alguém!',
        )
        return False
    return True


def _ensure_is_turn(update: Update, context) -> bool:
    """Verifica se é a vez do jogador."""
    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    if not game:
        return False
    pid = game_manager.get_player_id_in_game(uid)
    if not pid or game.current_player.id != pid:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'{ICONES["hourglass"]} Não é sua vez. Aguarde o oponente.',
        )
        return False
    return True


def _check_victory(update: Update, context, game, game_id: str) -> bool:
    """Verifica condições de vitória. Se alguém venceu, encerra e retorna True."""
    for p in game.players:
        if p.victory_points >= p.renown_level:
            vencedor_id = p.id
            # Descobre Telegram ID do vencedor
            vencedor_tid = None
            session = game_manager.get_session(game_id)
            if session:
                for tid, pid in session.players.items():
                    if pid == vencedor_id:
                        vencedor_tid = tid
                        break
            msg = render_victory(game, vencedor_id)
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=msg,
                parse_mode='Markdown',
            )
            # Notifica o oponente
            op_tid = game_manager.get_opponent_telegram_id(
                _get_player_id(update)
            )
            if op_tid:
                context.bot.send_message(
                    chat_id=op_tid,
                    text=msg,
                    parse_mode='Markdown',
                )
            game_manager.remove_game(game_id)
            return True
    return False


# ── Helpers de teclado inline ───────────────────────────────────────

async def _send_board_with_keyboard(update_or_tid, context, game,
                                     player_id, chat_id=None):
    """Envia o board com teclado contextual."""
    msg = render_board(game, player_id)
    if game.combat.is_active:
        kb = combat_keyboard(game, player_id)
    else:
        kb = board_keyboard(game, player_id)

    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id, text=msg,
            parse_mode='Markdown', reply_markup=kb,
        )
    else:
        await update_or_tid.message.reply_text(
            msg, parse_mode='Markdown', reply_markup=kb,
        )


async def _edit_with_keyboard(query, text: str, keyboard):
    """Edita a mensagem atual com novo texto e teclado."""
    try:
        await query.edit_message_text(
            text, parse_mode='Markdown', reply_markup=keyboard,
        )
    except Exception:
        await query.answer(
            '⚠️ Não foi possível atualizar. Use /board.', show_alert=False,
        )


async def _notify_opponent(context, op_tid, game, player_id, message: str):
    """Notifica o oponente com board atualizado se for a vez dele."""
    if not op_tid:
        return
    try:
        op_pid = game_manager.get_player_id_in_game(op_tid)
        if op_pid and game.current_player.id == op_pid:
            # Envia notificação separada (pequena)
            await context.bot.send_message(
                chat_id=op_tid,
                text=f'{ICONES["info"]} {message}',
            )
            # Board editado para não floodar
            await _update_board_message(
                None, context, game, op_pid, chat_id=op_tid,
            )
        else:
            await context.bot.send_message(
                chat_id=op_tid, text=message,
            )
    except Exception as e:
        logger.debug(f'Erro notificando oponente: {e}')


# ── Helper de edição de mensagens ──────────────────────────────────
# Evita flood editando a mensagem do board em vez de enviar nova.

async def _update_board_message(
    update_or_event, context, game, pid,
    chat_id: int | None = None,
    force_new: bool = False,
):
    """Tenta editar a última mensagem do board. Se falhar, envia nova.

    Armazena o message_id em context.user_data['board_msg_id']
    para reuso na próxima chamada.

    Args:
        update_or_event: Update (para reply) ou CallbackQuery (para edit).
        context: Context do handler.
        game: GameState.
        pid: Player ID do jogador.
        chat_id: Chat alvo (opcional, default: do update).
        force_new: Se True, sempre envia mensagem nova.
    """
    msg = render_board(game, pid)
    kb = (combat_keyboard(game, pid) if game.combat.is_active
          else board_keyboard(game, pid))

    stored_msg_id = context.user_data.get('board_msg_id')
    stored_chat_id = context.user_data.get('board_chat_id')
    target_chat = chat_id or stored_chat_id

    # Tenta editar mensagem existente
    if not force_new and stored_msg_id and target_chat:
        try:
            await context.bot.edit_message_text(
                msg,
                chat_id=target_chat,
                message_id=stored_msg_id,
                parse_mode='Markdown',
                reply_markup=kb,
            )
            return  # Editou com sucesso
        except Exception:
            pass  # Mensagem muito antiga ou apagada → envia nova

    # Fallback: envia mensagem nova
    effective_chat = chat_id
    if not effective_chat:
        if hasattr(update_or_event, 'effective_chat'):
            effective_chat = update_or_event.effective_chat.id
        elif hasattr(update_or_event, 'message'):
            effective_chat = update_or_event.message.chat_id
        else:
            effective_chat = stored_chat_id

    if not effective_chat:
        return

    sent = await context.bot.send_message(
        chat_id=effective_chat,
        text=msg,
        parse_mode='Markdown',
        reply_markup=kb,
    )
    context.user_data['board_msg_id'] = sent.message_id
    context.user_data['board_chat_id'] = sent.chat_id


# ── Handlers ────────────────────────────────────────────────────────

@auto_register
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — boas-vindas e instruções."""
    name = _get_player_name(update)
    msg = (
        f'🐺 *Bem-vindo ao Rage CCG, {name}!*\n\n'
        f'Use este bot para desafiar amigos e jogar Rage CCG '
        f'diretamente pelo Telegram.\n\n'
        f'*Comandos básicos:*\n'
        f'   `/decks` — Seus decks cadastrados\n'
        f'   `/duel @jogador <deck_id>` — Desafiar alguém\n'
        f'   `/accept @jogador <deck_id>` — Aceitar desafio\n'
        f'   `/decline @jogador` — Recusar desafio\n\n'
        f'*Durante a partida:*\n'
        f'   `/board` — Ver tabuleiro\n'
        f'   `/hand` — Ver sua mão\n'
        f'   `/play N` — Jogar carta N da mão\n'
        f'   `/attack <id> [alvo]` — Iniciar combate\n'
        f'   `/pass` — Passar a vez\n'
        f'   `/concede` — Desistir\n\n'
        f'*Dica:* Use `/help` para ajuda detalhada.'
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help — ajuda detalhada."""
    msg = (
        f'{ICONES["info"]} *Rage CCG Bot — Ajuda Completa*\n\n'
        f'*Comandos de partida:*\n'
        f'`/board` — Mostra o tabuleiro completo\n'
        f'`/hand` — Mostra sua mão com índices\n'
        f'`/status` — Status resumido da partida\n'
        f'`/play <N>` — Joga a carta de índice N da mão\n'
        f'`/use <N>` — Usa carta de efeito (Gift, Rite, etc.)\n'
        f'`/attack <id>` — Ataca Hunting Grounds\n'
        f'`/attack <atacante> <defensor>` — Inicia combate\n'
        f'`/declare <card_id> <ação>` — Declara ação (strike/block/dodge)\n'
        f'`/reveal` — Revela ações declaradas\n'
        f'`/feint <card_id> <ação>` — Troca ação (Último a Declarar)\n'
        f'`/resolve` — Resolve combate\n'
        f'`/endcombat` — Encerra combate\n'
        f'`/draw [deck] [qtd]` — Compra cartas\n'
        f'`/pass` — Passa a vez\n'
        f'`/next` — Avança fase\n'
        f'`/actions` — Mostra ações disponíveis\n'
        f'`/concede` — Desiste da partida\n\n'
        f'*Comandos de deck:*\n'
        f'`/decks [página]` — Lista seus decks\n'
        f'`/deck <id>` — Detalhes de um deck\n\n'
        f'*Matchmaking:*\n'
        f'`/duel @jogador <deck_id>` — Desafia jogador\n'
        f'`/accept @jogador <deck_id>` — Aceita desafio\n'
        f'`/decline @jogador` — Recusa desafio\n'
        f'`/cancel @jogador` — Cancela desafio enviado'
    )
    await update.message.reply_text(msg, parse_mode='Markdown')


# ── Decks ───────────────────────────────────────────────────────────

async def decks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /decks — lista decks do jogador."""
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        app = create_app()
        with app.app_context():
            decks_list = []
            for d in Deck.query.order_by(Deck.name).all():
                qtd = len(d.cards) if hasattr(d, 'cards') and d.cards else 0
                decks_list.append((d.id, d.name, qtd))

        if not decks_list:
            await update.message.reply_text(
                f'{ICONES["warning"]} Você não tem decks cadastrados.'
                f' Crie um em: http://127.0.0.1:5000/decks/new'
            )
            return

        # Paginação
        args = context.args
        page = 0
        if args:
            page = max(0, _parse_int(args[0], 0) - 1)

        msg = render_deck_list(decks_list, page=page)
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao carregar decks: {e}'
        )


# ── Galeria de Decks ───────────────────────────────────────────────

async def deck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /deck <subcomando> [args]

    Subcomandos:
      /deck search <termo>  — busca decks públicos
      /deck view <id>       — mostra cartas de um deck
      /deck share [id]      — alterna público/privado
      /deck top             — decks mais usados
      /deck <termo>         — atalho para search
    """
    args = context.args
    sub = args[0].lower() if args else ''

    if sub == 'search':
        await _deck_search(update, context)
    elif sub == 'view':
        await _deck_view(update, context)
    elif sub == 'share':
        await _deck_share(update, context)
    elif sub == 'top':
        await _deck_top(update, context)
    elif args:
        # Atalho: /deck <termo> = /deck search <termo>
        context.args = args
        await _deck_search(update, context)
    else:
        await update.message.reply_text(
            f'{ICONES["info"]} *Comandos de Deck:*'
            f'\n  `/deck search <termo>` — Buscar decks públicos'
            f'\n  `/deck view <id>` — Ver cartas de um deck'
            f'\n  `/deck share [id]` — Tornar deck público/privado'
            f'\n  `/deck top` — Decks mais usados',
            parse_mode='Markdown',
        )


async def _deck_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca decks públicos."""
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        args = context.args
        term = ' '.join(args) if args else ''

        app = create_app()
        with app.app_context():
            if term:
                decks_list = Deck.query.filter(
                    Deck.is_public == True,
                    Deck.name.ilike(f'%{term}%'),
                ).order_by(Deck.usage_count.desc()).limit(20).all()
            else:
                decks_list = Deck.query.filter(
                    Deck.is_public == True,
                ).order_by(Deck.usage_count.desc()).limit(20).all()

        if not decks_list:
            await update.message.reply_text(
                f'{ICONES["warning"]} Nenhum deck público encontrado.'
                f'\n\nUse `/deck share <id>` para tornar um deck seu público!'
                f'\nOu busque por nome: `/deck search <termo>`.',
                parse_mode='Markdown',
            )
            return

        lines = [f'📚 *Decks Públicos*{" — " + term if term else ""}'] + ['_' * 30]
        for d in decks_list:
            qtd = len(d.cards) if hasattr(d, 'cards') and d.cards else 0
            owner = d.telegram_owner_id or 0
            lines.append(
                f'`{d.id:>4}` {d.name[:25]}'
                f'  ({qtd} cartas)'
                f'  ⭐ {d.usage_count}'
            )
        lines.append('')
        lines.append(f'Use `/deck view <id>` para ver detalhes.')

        await update.message.reply_text(
            '\n'.join(lines), parse_mode='Markdown',
        )

    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro: {e}'
        )


async def deck_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /deck view <id> — mostra cartas de um deck."""
    args = context.args
    if not args:
        await update.message.reply_text(
            f'{ICONES["warning"]} Use: `/deck view <id>`',
            parse_mode='Markdown',
        )
        return

    deck_id = _parse_int(args[0])
    if not deck_id:
        await update.message.reply_text(
            f'{ICONES["cross"]} ID inválido.'
        )
        return

    try:
        from rage_web.models.deck import Deck
        from rage_web.models.card import Card
        from rage_web.ext.database import db
        from rage_web import create_app

        app = create_app()
        with app.app_context():
            deck = Deck.query.get(deck_id)
            if not deck or not deck.is_public:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Deck não encontrado ou não é público.'
                )
                return

            lines = [
                f'📋 *{deck.name}*',
                f'├ Descrição: {deck.description or "Sem descrição"}',
                f'├ Cartas: {len(deck.cards) if hasattr(deck, "cards") and deck.cards else 0}',
                f'├ ⭐ Uso: {deck.usage_count}',
                f'└ Renome Cap: {deck.renown_cap}',
                '',
                '*Cartas:*',
            ]

            # Agrupa cartas por tipo
            tipo_order = {'Character': 0, 'Equipment': 1, 'Gift': 2,
                          'Combat Action': 3, 'Event': 4, 'Ally': 5,
                          'Enemy': 6, 'Victim': 7, 'Territory': 8,
                          'Caern': 9, 'Rite': 10, 'Moot': 11, 'Action': 12,
                          'Quest': 13, 'Outro': 99}
            cards_sorted = sorted(
                deck.cards,
                key=lambda c: (tipo_order.get(getattr(c, 'tipo', ''), 99), c.name),
            )

            for card in cards_sorted:
                tipo = getattr(card, 'tipo', '')
                rage = getattr(card, 'rage', 0) or ''
                gnosis = getattr(card, 'gnosis', 0) or ''
                extra = f' [{rage}/{gnosis}]' if rage or gnosis else ''
                lines.append(f'  • {card.name}{extra}')
                if len(lines) > 50:
                    lines.append('... (mais cartas omitidas)')
                    break

            await update.message.reply_text(
                '\n'.join(lines), parse_mode='Markdown',
            )

            # Incrementa contagem de uso
            deck.usage_count = (deck.usage_count or 0) + 1
            db.session.commit()

    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro: {e}'
        )


async def deck_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /deck share [id] — alterna público/privado."""
    uid = _get_player_id(update)
    args = context.args
    deck_id = _parse_int(args[0]) if args else None

    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        app = create_app()
        with app.app_context():
            if deck_id:
                deck = Deck.query.get(deck_id)
            else:
                # Pega o deck mais recente do usuário
                deck = Deck.query.filter_by(
                    telegram_owner_id=uid
                ).order_by(Deck.id.desc()).first()

            if not deck:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Deck não encontrado.'
                    f' Use `/deck share <id>`.',
                    parse_mode='Markdown',
                )
                return

            # Verifica ownership
            if deck.telegram_owner_id and deck.telegram_owner_id != uid:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Você não é dono deste deck.'
                )
                return

            # Se não tem dono, assume
            if not deck.telegram_owner_id:
                deck.telegram_owner_id = uid

            # Alterna público/privado
            deck.is_public = not deck.is_public
            db.session.commit()

            status = '✅ Público' if deck.is_public else '🔒 Privado'
            await update.message.reply_text(
                f'{status}: *{deck.name}*'
                f'\nAgora qualquer um pode ver e usar este deck!'
                if deck.is_public
                else f'{status}: *{deck.name}*'
                f'\nApenas você pode ver este deck.'
                ,
                parse_mode='Markdown',
            )

    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro: {e}'
        )


async def deck_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /deck top — decks mais usados."""
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        app = create_app()
        with app.app_context():
            top = Deck.query.filter(
                Deck.is_public == True,
            ).order_by(
                Deck.usage_count.desc()
            ).limit(10).all()

        if not top:
            await update.message.reply_text(
                f'{ICONES["warning"]} Nenhum deck público ainda.'
            )
            return

        lines = ['🏆 *Decks Mais Usados*', '───']
        medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        for i, d in enumerate(top):
            qtd = len(d.cards) if hasattr(d, 'cards') and d.cards else 0
            medal = medals[i] if i < len(medals) else f'{i+1}.'
            lines.append(
                f'{medal} `{d.id:>4}` {d.name[:25]}'
                f'  ({qtd} cartas) — ⭐ {d.usage_count}'
            )
        lines.append('')
        lines.append('Use `/deck view <id>` para ver detalhes.')

        await update.message.reply_text(
            '\n'.join(lines), parse_mode='Markdown',
        )

    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro: {e}'
        )


# ── Matchmaking ─────────────────────────────────────────────────────

async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /duel @jogador <deck_id> — desafia alguém."""
    if not _ensure_not_in_game(update, context):
        return

    uid = _get_player_id(update)
    name = _get_player_name(update)
    text = update.message.text

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/duel @jogador <deck_id>`\n'
            f'Exemplo: `/duel @joao 7`',
            parse_mode='Markdown',
        )
        return

    # Extrai @mention e deck_id
    mentions = _extract_mentions(text)
    if not mentions:
        await update.message.reply_text(
            f'{ICONES["warning"]} Mencione o jogador com @.'
            f' Exemplo: `/duel @joao 7`',
            parse_mode='Markdown',
        )
        return

    deck_id = _parse_int(args[-1])
    if not deck_id:
        await update.message.reply_text(
            f'{ICONES["warning"]} Informe o ID do deck.'
            f' Exemplo: `/duel @joao 7`',
            parse_mode='Markdown',
        )
        return

    # Verifica se o deck existe
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        flask_app = create_app()
        with flask_app.app_context():
            deck = db.session.get(Deck, deck_id)
            if not deck:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Deck {deck_id} não encontrado.'
                )
                return
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao verificar deck: {e}'
        )
        return

    # A @mention pode ser de um usuário que não está no banco do bot.
    # Para o MVP, o desafiador precisa saber o @username do oponente.
    username_mention = mentions[0]

    # Registra o desafio (não sabemos o Telegram ID do mencionado —
    # a resolução será pelo username quando ele chamar /accept)
    # Por hora, armazenamos por username mesmo.
    challenged_username = username_mention.lower()

    # Verifica se não está desafiando a si mesmo
    user_username = (update.effective_user.username or '').lower()
    if challenged_username == user_username:
        await update.message.reply_text(
            f'{ICONES["warning"]} Você não pode desafiar a si mesmo!'
        )
        return

    # Armazena o desafio no matchmaker (usando username como chave)
    # Também armazena no context.user_data para referência
    if 'pending_challenges' not in context.user_data:
        context.user_data['pending_challenges'] = []

    challenge_data = {
        'challenger_id': uid,
        'challenger_name': name,
        'challenged_username': challenged_username,
        'deck_challenger': deck_id,
        'created_at': __import__('time').time(),
    }
    context.user_data['pending_challenges'].append(challenge_data)

    await update.message.reply_text(
        f'{ICONES["check"]} Desafio enviado para @{challenged_username}!\n\n'
        f'Seu deck: `{deck.name}` (ID {deck_id})\n\n'
        f'Aguardando resposta... '
        f'O desafio expira em 2 minutos.\n\n'
        f'@{challenged_username}: use `/accept @{user_username or "desafiante"}'
        f' <deck_id>` para aceitar!',
        parse_mode='Markdown',
    )


async def accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /accept @jogador <deck_id> — aceita desafio."""
    if not _ensure_not_in_game(update, context):
        return

    uid = _get_player_id(update)
    name = _get_player_name(update)
    text = update.message.text
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/accept @jogador <deck_id>`\n'
            f'Exemplo: `/accept @joao 90`',
            parse_mode='Markdown',
        )
        return

    mentions = _extract_mentions(text)
    if not mentions:
        await update.message.reply_text(
            f'{ICONES["warning"]} Mencione o desafiante com @.'
            f' Exemplo: `/accept @joao 90`',
            parse_mode='Markdown',
        )
        return

    deck_id = _parse_int(args[-1])
    if not deck_id:
        await update.message.reply_text(
            f'{ICONES["warning"]} Informe o ID do seu deck.'
            f' Exemplo: `/accept @joao 90`',
            parse_mode='Markdown',
        )
        return

    # Verifica se o deck existe
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        flask_app = create_app()
        with flask_app.app_context():
            deck = db.session.get(Deck, deck_id)
            if not deck:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Deck {deck_id} não encontrado.'
                )
                return
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao verificar deck: {e}'
        )
        return

    # Busca desafio pendente
    my_username = (update.effective_user.username or '').lower()
    challenger_username = mentions[0].lower()

    found_challenge = None
    if 'pending_challenges' in context.user_data:
        for c in context.user_data['pending_challenges']:
            if (c.get('challenged_username') == my_username or
                c.get('challenger_username', '').lower() == challenger_username):
                # Na verdade, o desafio está armazenado no context do desafiador
                # Precisamos de um mecanismo cross-user
                pass

    # Para o MVP, vamos usar uma abordagem mais simples:
    # o desafio é registrado no Matchmaker global (acessível via IDs)
    # Como não temos resolução de username→id sem um banco de usuários,
    # vamos simplificar: o desafiante menciona o @ e o desafiado responde
    # com /accept @desafiante <deck_id>

    # Busca na lista de desafios pendentes do matchmaker
    challenges = matchmaker.get_pending_challenges(uid)
    if not challenges:
        # Tenta buscar por username inverso: o desafio pode estar registrado
        # com o username do desafiado como chave
        await update.message.reply_text(
            f'{ICONES["warning"]} Nenhum desafio pendente encontrado para você.\n\n'
            f'Peça para alguém usar `/duel @{my_username} <deck_id>`.',
            parse_mode='Markdown',
        )
        return

    # Pega o primeiro desafio pendente (1v1 simplificado)
    challenge = challenges[0]
    matchmaker.accept_challenge(uid, challenge.challenger_id, deck_id)

    # Cria a partida
    try:
        game = matchmaker.create_game_from_challenge(challenge)
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao criar partida: {e}'
        )
        matchmaker.decline_challenge(uid, challenge.challenger_id)
        return

    # Registra no GameManager
    player_map = {
        challenge.challenger_id: game.players[0].id,
        uid: game.players[1].id,
    }
    gid = game_manager.create_game(game, player_map)

    # Atualiza nomes dos jogadores
    game.players[0].name = challenge.challenger_name
    game.players[1].name = name

    web_url = f'http://127.0.0.1:5000/game/{gid}'
    msg = (
        f'{ICONES["check"]} *Desafio aceito! Partida criada!*\n\n'
        f'🎮 *ID da partida:* `{gid}`\n'
        f'🐺 {challenge.challenger_name} vs {name}\n\n'
        f'{ICONES["info"]} Use `/board` para ver o tabuleiro.\n'
        f'{ICONES["info"]} Use `/hand` para ver sua mão.\n'
        f'{ICONES["info"]} Use `/actions` para ver o que fazer.'
        f'\n[🌐 Acompanhar no navegador]({web_url})'
    )
    await update.message.reply_text(
        msg, parse_mode='Markdown',
        disable_web_page_preview=True,
    )

    # Notifica o desafiante
    # URL do web app para acompanhar a partida
    web_url = f'http://127.0.0.1:5000/game/{gid}'
    try:
        await context.bot.send_message(
            chat_id=challenge.challenger_id,
            text=(
                f'{ICONES["check"]} *{name} aceitou seu desafio!*\n\n'
                f'🎮 Partida `{gid}` iniciada!\n'
                f'Use `/board` para começar.'
                f'\n\n[🌐 Acompanhar no navegador]({web_url})'
            ),
            parse_mode='Markdown',
            disable_web_page_preview=True,
        )
    except Exception:
        pass

    # Mostra o board inicial
    game = game_manager.get_game(gid)
    if game:
        for tid in (challenge.challenger_id, uid):
            pid = game_manager.get_player_id_in_game(tid)
            try:
                board_msg = render_board(game, pid)
                await context.bot.send_message(
                    chat_id=tid,
                    text=board_msg,
                    parse_mode='Markdown',
                )
            except Exception:
                pass


@auto_register
async def decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /decline @jogador — recusa desafio."""
    uid = _get_player_id(update)
    text = update.message.text
    mentions = _extract_mentions(text)
    challenger_username = mentions[0].lower() if mentions else ''

    challenges = matchmaker.get_pending_challenges(uid)
    if not challenges:
        await update.message.reply_text(
            f'{ICONES["warning"]} Nenhum desafio pendente.'
        )
        return

    challenge = challenges[0]
    matchmaker.decline_challenge(uid, challenge.challenger_id)

    await update.message.reply_text(
        f'{ICONES["cross"]} Desafio recusado.'
    )

    # Notifica o desafiante
    try:
        await context.bot.send_message(
            chat_id=challenge.challenger_id,
            text=f'{ICONES["cross"]} {_get_player_name(update)} recusou seu desafio.',
        )
    except Exception:
        pass


# ── Jogabilidade ────────────────────────────────────────────────────

async def board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /board — mostra tabuleiro completo com teclado inline."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    if not game or not pid:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro: partida não encontrada.'
        )
        return

    await _update_board_message(update, context, game, pid)


async def hand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /hand — mostra a mão com botões para jogar/usar cada carta."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    if not game or not pid:
        return

    msg = render_hand(game, pid)
    kb = hand_keyboard(game, pid)
    await update.message.reply_text(
        msg, parse_mode='Markdown', reply_markup=kb,
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status — status resumido da partida."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    if not game or not pid:
        return

    msg = render_game_status(game, pid)
    await update.message.reply_text(msg, parse_mode='Markdown')


async def actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /actions — ações disponíveis com teclado inline."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    if not game or not pid:
        return

    msg = render_legal_actions(game, pid)
    if game.combat.is_active:
        kb = combat_keyboard(game, pid)
    else:
        kb = board_keyboard(game, pid)
    await update.message.reply_text(
        msg, parse_mode='Markdown', reply_markup=kb,
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /play <N> — joga carta da mão."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    args = context.args
    if not args:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/play <N>` — N é o índice da carta na mão.',
            parse_mode='Markdown',
        )
        return

    idx = _parse_int(args[0], -1)
    if idx < 0:
        await update.message.reply_text(
            f'{ICONES["cross"]} Índice inválido.'
        )
        return

    # Busca o player
    player = next((p for p in game.players if p.id == pid), None)
    if not player:
        return

    if idx >= len(player.hand):
        await update.message.reply_text(
            f'{ICONES["cross"]} Índice {idx} inválido.'
            f' Mão tem {len(player.hand)} cartas.'
        )
        return

    card = player.hand[idx]

    # Verifica se é Ally (precisa de personagem compatível)
    from rage_web.game_engine.rules import zona_da_carta, pode_recrutar_ally

    if 'Ally' in (card.card_type or ''):
        if not pode_recrutar_ally(player, card):
            await update.message.reply_text(
                f'{ICONES["cross"]} Não pode recrutar {card.name}:'
                f' nenhum personagem atende "{card.requires}"'
            )
            return

    # Joga a carta
    zone_name = zona_da_carta(card.card_type or '')
    player.hand.pop(idx)

    from rage_web.game_engine.state import Zone
    if zone_name == 'hunting_grounds':
        card.zone = Zone.HUNTING_GROUNDS
        player.hunting_grounds.append(card)
    else:
        card.zone = Zone.PACK_HOME
        # Se for personagem, inicializa vida
        if 'character' in (card.card_type or '').lower():
            card.health_current = card.health
        player.pack_home.append(card)

    game.add_log(f'{player.name} jogou {card.name}')

    # Jogador agiu: reseta timer do turno
    _ps = game_manager.get_player_session(uid)
    if _ps:
        game_manager.cancel_turn_timer(_ps.game_id)
        game_manager.reset_missed_turns(_ps.game_id)
        game_manager.schedule_turn_timer(_ps.game_id)

    # Envia confirmação + retrato da carta + board atualizado
    portrait = render_card_portrait(card)
    await update.message.reply_text(
        f'{ICONES["play"]} *{player.name}* jogou *{card.name}*!'
        f'\n\n{portrait}',
        parse_mode='Markdown',
    )
    # Tenta enviar imagem da carta (se disponível)
    await _send_card_image(context, update.effective_chat.id, card)
    await _update_board_message(update, context, game, pid)

    # Notifica oponente com board se for a vez dele
    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await _notify_opponent(
            context, op_tid, game, pid,
            f'{ICONES["play"]} *{player.name}* jogou *{card.name}*!',
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def use_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /use <N> — usa carta de efeito da mão (Gift, Rite, etc)."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    args = context.args
    if not args:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/use <N>` — N é o índice na mão.',
            parse_mode='Markdown',
        )
        return

    idx = _parse_int(args[0], -1)
    if idx < 0:
        await update.message.reply_text(f'{ICONES["cross"]} Índice inválido.')
        return

    player = next((p for p in game.players if p.id == pid), None)
    if not player or idx >= len(player.hand):
        await update.message.reply_text(f'{ICONES["cross"]} Índice inválido.')
        return

    card = player.hand[idx]
    if not card.modelo_id:
        await update.message.reply_text(
            f'{ICONES["cross"]} {card.name} não tem modelo de efeitos.'
        )
        return

    # Resolve o efeito
    from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
    from rage_web.game_engine.rules import parse_custo_rage

    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
    if not modelo:
        await update.message.reply_text(
            f'{ICONES["cross"]} Modelo {card.modelo_id} não encontrado.'
        )
        return

    # Verifica custo Rage
    custo_rage = parse_custo_rage(card.damage)
    if custo_rage is not None and custo_rage > 0:
        pagador = player.pagar_custo_rage(custo_rage)
        if not pagador:
            await update.message.reply_text(
                f'{ICONES["cross"]} Custo de Rage {custo_rage} não pode ser pago.'
            )
            return
        game.add_log(f'{player.name} pagou Rage {custo_rage} para {card.name}')

    # Remove da mão
    player.hand.pop(idx)

    # Aplica efeitos (modo 0 por padrão — no futuro, suportar escolha)
    logs = aplicar_carta(game, modelo, pid, modo_idx=0)

    log_msg = '\n'.join(logs[-3:]) if logs else ''
    await update.message.reply_text(
        f'{ICONES["gift"]} *{player.name}* usou *{card.name}*!\n{log_msg}',
        parse_mode='Markdown',
    )

    # Notifica oponente
    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=(
                f'{ICONES["gift"]} *{player.name}* usou *{card.name}*!'
                f'\n{log_msg}'
            ),
            parse_mode='Markdown',
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /attack <atacante_id> [defensor_id] — inicia combate."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    args = context.args
    if not args:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/attack <atacante_id> [defensor_id]`\n'
            f'Exemplo: `/attack 500` (ataca Hunting Grounds)\n'
            f'Exemplo: `/attack 500 601` (ataca criatura específica)',
            parse_mode='Markdown',
        )
        return

    attacker_id = args[0]
    defender_id = args[1] if len(args) > 1 else 'hg'

    from rage_web.game_engine.combat_queue import start_combat

    if not start_combat(game, [attacker_id], [defender_id]):
        await update.message.reply_text(
            f'{ICONES["cross"]} Não foi possível iniciar combate. '
            f'(Já existe um combate ativo?)'
        )
        return

    game.add_log(f'{game.current_player.name} iniciou combate: '
                 f'{attacker_id} vs {defender_id}')

    combat_msg = render_combat_summary(game)
    await update.message.reply_text(
        f'{ICONES["combat"]} *Combate iniciado!*\n\n{combat_msg}',
        parse_mode='Markdown',
    )

    # Notifica oponente
    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=(
                f'{ICONES["combat"]} *Combate iniciado!*\n'
                f'{game.current_player.name} atacou!\n\n'
                f'{combat_msg}\n\n'
                f'Use `/declare <card_id> <ação>` para declarar.'
            ),
            parse_mode='Markdown',
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def declare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /declare <card_id> <ação> — declara ação de combate."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/declare <card_id> <acao>`\n'
            f'Ações: strike, block, dodge, grapple, feint, etc.',
            parse_mode='Markdown',
        )
        return

    card_id = args[0]
    action = args[1].lower()

    from rage_web.game_engine.combat_queue import (
        declare_action, COMBAT_ACTIONS
    )

    if action not in COMBAT_ACTIONS:
        await update.message.reply_text(
            f'{ICONES["cross"]} Ação inválida: {action}\n'
            f'Válidas: {", ".join(sorted(COMBAT_ACTIONS))}'
        )
        return

    if not declare_action(game, card_id, action):
        await update.message.reply_text(
            f'{ICONES["cross"]} Não foi possível declarar.'
        )
        return

    await update.message.reply_text(
        f'{ICONES["check"]} {card_id}: {action} declarada.'
    )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /reveal — revela ações de combate."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)

    from rage_web.game_engine.combat_queue import reveal_all, get_declaration_summary

    if not reveal_all(game):
        await update.message.reply_text(
            f'{ICONES["cross"]} Não foi possível revelar.'
        )
        return

    summary = get_declaration_summary(game)
    msg = f'{ICONES["combat"]} *Ações reveladas!*\n'
    if 'declarations' in summary:
        for cid, action in summary['declarations'].items():
            msg += f'   {cid}: {action}\n'

    await update.message.reply_text(msg, parse_mode='Markdown')

    # Notifica oponente
    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=f'{ICONES["combat"]} Ações reveladas!\n{msg}',
            parse_mode='Markdown',
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def feint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /feint <card_id> <ação> — troca ação (último a declarar)."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/feint <card_id> <nova_acao>`',
            parse_mode='Markdown',
        )
        return

    card_id = args[0]
    new_action = args[1].lower()

    from rage_web.game_engine.combat_queue import feint_action

    if not feint_action(game, card_id, new_action):
        await update.message.reply_text(
            f'{ICONES["cross"]} Não foi possível usar Feint.'
        )
        return

    await update.message.reply_text(
        f'{ICONES["check"]} Feint: {card_id} agora executa {new_action}.'
    )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resolve — resolve combate."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)
    gid = game_manager.get_player_session(uid).game_id

    from rage_web.game_engine.combat_queue import resolve_combat

    if not resolve_combat(game):
        await update.message.reply_text(
            f'{ICONES["cross"]} Não foi possível resolver o combate.'
        )
        return

    # Mostra resultado
    await update.message.reply_text(
        f'{ICONES["combat"]} *Combate resolvido!*\n'
        f'Use `/board` para ver o estado atual.',
        parse_mode='Markdown',
    )

    # Notifica oponente
    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=f'{ICONES["combat"]} Combate resolvido! Use `/board`.',
            parse_mode='Markdown',
        )

    # Verifica vitória
    _check_victory(update, context, game, gid)

    # Roda turnos do bot se necessario
    await _run_bot_turns_if_needed(update, context, gid)


async def endcombat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /endcombat — encerra combate forçadamente."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)

    from rage_web.game_engine.combat_queue import end_combat

    end_combat(game)

    await update.message.reply_text(
        f'{ICONES["check"]} Combate encerrado.'
    )

    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=f'{ICONES["check"]} Combate encerrado.',
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /draw [deck] [qtd] — compra cartas."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    args = context.args
    deck = args[0] if args and args[0] in ('combat', 'sept') else 'combat'
    count = _parse_int(args[-1], 1) if args else 1

    player = next((p for p in game.players if p.id == pid), None)
    if not player:
        return

    if deck == 'combat':
        drawn = player.draw_combat(count)
    else:
        drawn = player.draw_sept(count)

    drawn_names = ', '.join(c.name for c in drawn) if drawn else 'nada'
    await update.message.reply_text(
        f'{ICONES["hand"]} Comprou {len(drawn)} carta(s) do deck {deck}:'
        f' {drawn_names}',
    )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def pass_turn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /pass — passa a vez."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)
    gid = game_manager.get_player_session(uid).game_id

    player = next((p for p in game.players if p.id == pid), None)
    if not player:
        return

    player.pass_turn()

    all_passed = all(p.has_passed for p in game.players)
    if all_passed:
        old_phase = game.phase
        game.next_phase()
        for p in game.players:
            p.reset_pass()
        game.add_log(f'Todos passaram. {old_phase} → {game.phase}')

        await update.message.reply_text(
            f'{ICONES["pass"]} Todos passaram. Avançando para {game.phase}.',
        )
        await _update_board_message(update, context, game, pid)

        # Notifica oponente com board
        op_tid = game_manager.get_opponent_telegram_id(uid)
        if op_tid:
            op_pid = game_manager.get_player_id_in_game(op_tid)
            if op_pid:
                await _update_board_message(
                    update, context, game, op_pid, chat_id=op_tid,
                )
                await context.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["pass"]} Todos passaram. Avançando para {game.phase}.',
                )
    else:
        game.next_player()
        game.add_log(f'{player.name} passou.')

        await update.message.reply_text(
            f'{ICONES["pass"]} Você passou. Aguarde o oponente.',
        )

        # Agenda timer para o turno do oponente
        game_manager.schedule_turn_timer(gid)

        # Notifica oponente com board + teclado (agora é a vez dele!)
        op_tid = game_manager.get_opponent_telegram_id(uid)
        if op_tid:
            op_pid = game_manager.get_player_id_in_game(op_tid)
            if op_pid:
                await context.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["pass"]} *{player.name}* passou! É sua vez!',
                    parse_mode='Markdown',
                )
                await _send_board_with_keyboard(
                    update, context, game, op_pid, chat_id=op_tid,
                )

    # Verifica vitória
    _check_victory(update, context, game, gid)

    # Roda turnos do bot se necessario
    await _run_bot_turns_if_needed(update, context, gid)


async def next_phase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /next — avança fase forçadamente."""
    if not _ensure_in_game(update, context) or not _ensure_is_turn(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)

    old_phase = game.phase
    game.next_phase()
    game.add_log(f'Avancou: {old_phase} → {game.phase}')

    # Agenda timer para nova fase
    _ps = game_manager.get_player_session(uid)
    if _ps:
        game_manager.cancel_turn_timer(_ps.game_id)
        game_manager.reset_missed_turns(_ps.game_id)
        game_manager.schedule_turn_timer(_ps.game_id)

    await update.message.reply_text(
        f'{ICONES["pass"]} Fase avançada: {old_phase} → {game.phase}',
    )

    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=(
                f'{ICONES["pass"]} Fase avançada:'
                f' {old_phase} → {game.phase}'
            ),
        )

    # Roda turnos do bot se necessario
    ps = game_manager.get_player_session(uid)
    if ps:
        await _run_bot_turns_if_needed(update, context, ps.game_id)


async def concede(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /concede — desiste da partida."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)
    ps = game_manager.get_player_session(uid)
    if not ps:
        return

    gid = ps.game_id
    player_name = next(
        (p.name for p in game.players if p.id == pid),
        'Jogador'
    )

    await update.message.reply_text(
        f'{ICONES["death"]} *{player_name} desistiu!*'
        f'\nFim de jogo.',
        parse_mode='Markdown',
    )

    op_tid = game_manager.get_opponent_telegram_id(uid)
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=(
                f'{ICONES["trophy"]} *Vitória!*'
                f' {player_name} desistiu da partida!'
            ),
            parse_mode='Markdown',
        )

    # Registra estatísticas
    if op_tid:
        player_session = game_manager.get_player_session(op_tid)
        op_pid = game_manager.get_player_id_in_game(op_tid)
        op_name = next(
            (p.name for p in game.players if p.id == op_pid),
            'Oponente'
        ) if op_pid else 'Oponente'
        winner_deck = getattr(player_session, 'deck_id', None) if player_session else None
        loser_deck = getattr(ps, 'deck_id', None)

        try:
            stats_manager.record_match(
                winner_id=op_tid,
                loser_id=uid,
                winner_deck_id=winner_deck,
                loser_deck_id=loser_deck,
                method='concede',
            )
        except Exception as e:
            logger.error(f'Erro ao registrar stats: {e}')

    game_manager.remove_game(gid)


async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /timer <horas> — define timeout do turno."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    ps = game_manager.get_player_session(uid)
    if not ps:
        return

    args = context.args
    if not args:
        # Mostra timeout atual
        session = game_manager._games.get(ps.game_id)
        if session:
            h = session.turn_timeout_seconds / 3600
            await update.message.reply_text(
                f'⏱️ Timeout atual: **{h:.1f}h**'
                f'\nUse `/timer <horas>` para alterar.'
                f'\nMin: 1h | Max: 48h',
                parse_mode='Markdown',
            )
        return

    hours = _parse_int(args[0])
    if hours is None or hours < 1:
        await update.message.reply_text(
            f'{ICONES["cross"]} Use: `/timer <horas>` (mínimo 1h, máximo 48h)',
            parse_mode='Markdown',
        )
        return

    hours = max(1, min(hours, 48))
    ok = game_manager.set_turn_timeout(ps.game_id, hours)
    if ok:
        await update.message.reply_text(
            f'✅ Timeout alterado para **{hours}h**.'
            f'\nSe ninguém agir nesse período, o turno será passado automaticamente.',
            parse_mode='Markdown',
        )
        # Notifica oponente
        op_tid = game_manager.get_opponent_telegram_id(uid)
        if op_tid:
            await context.bot.send_message(
                chat_id=op_tid,
                text=(
                    f'⏱️ Timeout alterado para **{hours}h**'
                    f' por {update.effective_user.full_name}.'
                ),
                parse_mode='Markdown',
            )
    else:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao alterar timeout.',
        )


# ── Card Detail ────────────────────────────────────────────────────

async def card_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /card <N> — mostra detalhes de uma carta da mão."""
    if not _ensure_in_game(update, context):
        return

    uid = _get_player_id(update)
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)
    args = context.args

    if not args:
        await update.message.reply_text(
            f'{ICONES["warning"]} Use: `/card <N>` — N é o índice na mão.',
            parse_mode='Markdown',
        )
        return

    idx = _parse_int(args[0], -1)
    if idx < 0:
        await update.message.reply_text(
            f'{ICONES["cross"]} Índice inválido.'
        )
        return

    player = next((p for p in game.players if p.id == pid), None)
    if not player or idx >= len(player.hand):
        await update.message.reply_text(
            f'{ICONES["cross"]} Carta não encontrada na mão.'
        )
        return

    card = player.hand[idx]
    portrait = render_card_portrait(card)
    detail = render_card_detail(card)
    msg = f'{portrait}\n\n{detail}'

    await update.message.reply_text(
        msg, parse_mode='Markdown',
    )
    await _send_card_image(context, update.effective_chat.id, card)


# ── Estatísticas e Ranking ──────────────────────────────────────────

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats — estatísticas do jogador."""
    uid = _get_player_id(update)

    try:
        data = stats_manager.get_player_stats(uid)
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao carregar estatísticas: {e}'
        )
        return

    if not data:
        name = _get_player_name(update)
        await update.message.reply_text(
            f'{ICONES["info"]} *{name}*, você ainda não tem partidas'
            f' registradas. Jogue algumas partidas para ver'
            f' suas estatísticas!'
            f'\n\nUse `/duel @jogador <deck>` para começar.',
            parse_mode='Markdown',
        )
        return

    name = _get_player_name(update)
    rating = data.get('rating', 1200)
    wins = data.get('wins', 0)
    losses = data.get('losses', 0)
    played = wins + losses
    winrate = round(wins / played * 100, 1) if played else 0
    fav = data.get('favorite_deck', '—')

    # Medalha por rating
    medal = '🥉' if rating < 1300 else '🥈' if rating < 1500 else '🥇'

    lines = [
        f'{ICONES["status"]} *Estatísticas de {name}*',
        f'{"─" * 30}',
        f'{medal} *Rating ELO:* {rating}',
        f'├ *Partidas:* {played} (🏆 {wins}W / 💀 {losses}L)',
        f'├ *Winrate:* {winrate}%',
        f'└ *Deck favorito:* {fav}',
        '',
        f'Use `/rank` para ver o ranking global.',
    ]

    await update.message.reply_text(
        '\n'.join(lines), parse_mode='Markdown',
    )


async def rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /rank — ranking global de jogadores."""
    try:
        rankings = stats_manager.get_rankings(top=15)
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao carregar ranking: {e}'
        )
        return

    if not rankings:
        await update.message.reply_text(
            f'{ICONES["info"]} Nenhuma partida registrada ainda.'
            f'\n\nSeja o primeiro a jogar!'
            f' Use `/duel @jogador <deck>`.',
            parse_mode='Markdown',
        )
        return

    total = stats_manager.get_total_games()
    lines = [
        f'{ICONES["trophy"]} *Ranking Global*  (📊 {total} partidas)',
        f'{"─" * 30}',
    ]

    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣',
              '9️⃣', '🔟', '11️⃣', '12️⃣', '13️⃣', '14️⃣', '15️⃣']

    for i, r in enumerate(rankings):
        medal = medals[i] if i < len(medals) else f'{i+1}.'
        tid = r.get('telegram_id', 0)
        # Tenta obter username do registry
        from rage_web.telegram_bot.user_registry import get_username
        uname = get_username(tid) or f'ID:{tid}'
        rating = r.get('rating', 1200)
        w = r.get('wins', 0)
        l = r.get('losses', 0)
        p = w + l
        wr = round(w / p * 100, 1) if p else 0
        lines.append(f'{medal} @{uname} — ⭐{rating} ({w}W/{l}L, {wr}%)')

    await update.message.reply_text(
        '\n'.join(lines), parse_mode='Markdown',
    )


# ── Callback handler (botões inline) ───────────────────────────────

# Mapeia ações para funções inline
_CALLBACK_ACTIONS = {}


def _register_cb(action: str):
    """Decorator para registrar handler de callback."""
    def decorator(func):
        _CALLBACK_ACTIONS[action] = func
        return func
    return decorator


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteia callbacks dos botões inline para os handlers específicos.

    Formato do callback_data:
        ação:param1:param2

    Exemplos:
        p:0       → play card 0
        u:1       → use card 1
        atk:500:hg → attack with 500 vs hunting grounds
        dc:500:strike → declare 500 as strike
        rv        → reveal
        rs        → resolve
        ps        → pass
        bd        → show board
        hd        → show hand
        cd        → concede
        shw:cd:i  → show card detail at index i
        shw:dc:cid → show declare menu for creature
        shw:ft    → show feint menu
    """
    query = update.callback_query
    await query.answer()

    if not query.data or query.data == 'wait':
        return

    uid = update.effective_user.id

    parts = query.data.split(':')
    action = parts[0]

    # 🔴 Bugfix: Se o callback_data começa com prefixo de
    # ConversationHandler (duel_deck, accept_deck), ignora —
    # quem trata é o próprio ConversationHandler.
    if action in ('duel_deck', 'accept_deck'):
        return
    params = parts[1:]

    # Handlers de sistema (não precisam de partida)
    if action == 'lang' and params:
        lang_code = params[0]
        context.user_data['lang'] = lang_code
        from rage_web.telegram_bot.i18n import t
        lang_name = LANGUAGES.get(lang_code, lang_code)
        await query.edit_message_text(
            t('lang.changed', lang=lang_code, language=lang_name),
        )
        return

    # Busca jogo e jogador
    game = game_manager.get_player_game(uid)
    pid = game_manager.get_player_id_in_game(uid)
    ps = game_manager.get_player_session(uid)

    if not game or not pid or not ps:
        await _edit_with_keyboard(
            query,
            f'{ICONES["cross"]} Nenhuma partida ativa. Use `/duel` para começar.',
            nav_keyboard(),
        )
        return

    # Roteia para o handler específico
    handler = _CALLBACK_ACTIONS.get(action)
    if handler:
        await handler(query, context, game, pid, ps, params)
    else:
        await query.answer(f'Ação desconhecida: {action}', show_alert=True)


# ── Handlers de callback ────────────────────────────────────────────

@_register_cb('p')
async def _cb_play(query, context, game, pid, ps, params):
    """Callback: jogar carta da mão."""
    if not params:
        return
    try:
        idx = int(params[0])
    except ValueError:
        return
    player = next((p for p in game.players if p.id == pid), None)
    if not player or idx >= len(player.hand):
        await query.answer('Indice invalido!', show_alert=True)
        return

    card = player.hand[idx]

    from rage_web.game_engine.rules import zona_da_carta, pode_recrutar_ally
    if 'Ally' in (card.card_type or ''):
        if not pode_recrutar_ally(player, card):
            await query.answer(
                f'Nao pode recrutar {card.name}: requisito "{card.requires}"',
                show_alert=True,
            )
            return

    zone_name = zona_da_carta(card.card_type or '')
    player.hand.pop(idx)

    from rage_web.game_engine.state import Zone
    if zone_name == 'hunting_grounds':
        card.zone = Zone.HUNTING_GROUNDS
        player.hunting_grounds.append(card)
    else:
        card.zone = Zone.PACK_HOME
        if 'character' in (card.card_type or '').lower():
            card.health_current = card.health
        player.pack_home.append(card)

    game.add_log(f'{player.name} jogou {card.name}')

    # Jogador agiu: reseta timer do turno
    game_manager.cancel_turn_timer(ps.game_id)
    game_manager.reset_missed_turns(ps.game_id)
    game_manager.schedule_turn_timer(ps.game_id)

    op_tid = game_manager.get_opponent_telegram_id(
        update.effective_user.id
    )

    if op_tid:
        await _notify_opponent(
            context, op_tid, game, pid,
            f'{ICONES["play"]} {player.name} jogou {card.name}!',
        )

    await _edit_with_keyboard(
        query,
        render_board(game, pid),
        combat_keyboard(game, pid) if game.combat.is_active
        else board_keyboard(game, pid),
    )


@_register_cb('u')
async def _cb_use(query, context, game, pid, ps, params):
    """Callback: usar carta de efeito."""
    if not params:
        return
    try:
        idx = int(params[0])
    except ValueError:
        return
    player = next((p for p in game.players if p.id == pid), None)
    if not player or idx >= len(player.hand):
        await query.answer('Indice invalido!', show_alert=True)
        return

    card = player.hand[idx]
    if not card.modelo_id:
        await query.answer(f'{card.name} nao tem efeito estrutrado', show_alert=True)
        return

    from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
    from rage_web.game_engine.rules import parse_custo_rage

    modelo = CARTAS_EXEMPLO.get(card.modelo_id)
    if not modelo:
        await query.answer(f'Modelo {card.modelo_id} nao encontrado', show_alert=True)
        return

    custo_rage = parse_custo_rage(card.damage)
    if custo_rage is not None and custo_rage > 0:
        pagador = player.pagar_custo_rage(custo_rage)
        if not pagador:
            await query.answer(f'Custo de Rage {custo_rage} nao pode ser pago', show_alert=True)
            return
        game.add_log(f'{player.name} pagou Rage {custo_rage} para {card.name}')

    # Jogador agiu: reseta timer
    game_manager.cancel_turn_timer(ps.game_id)
    game_manager.reset_missed_turns(ps.game_id)
    game_manager.schedule_turn_timer(ps.game_id)

    player.hand.pop(idx)
    logs = aplicar_carta(game, modelo, pid, modo_idx=0)
    log_msg = '\n'.join(logs[-3:]) if logs else ''

    op_tid = game_manager.get_opponent_telegram_id(
        update.effective_user.id
    )

    await query.edit_message_text(
        f'{ICONES["gift"]} *{player.name}* usou *{card.name}*!' 
        f'{log_msg}',
        parse_mode='Markdown',
    )

    if op_tid:
        await _notify_opponent(
            context, op_tid, game, pid,
            f'{ICONES["gift"]} {player.name} usou {card.name}!',
        )


@_register_cb('atk')
async def _cb_attack(query, context, game, pid, ps, params):
    """Callback: iniciar combate."""
    if len(params) < 2:
        await query.answer('Parametros insuficientes', show_alert=True)
        return
    attacker_id = params[0]
    defender_id = params[1]

    from rage_web.game_engine.combat_queue import start_combat

    if not start_combat(game, [attacker_id], [defender_id]):
        await query.answer('Nao foi possivel iniciar combate', show_alert=True)
        return

    game.add_log(f'{game.current_player.name} iniciou combate')

    # Jogador agiu: reseta timer
    game_manager.cancel_turn_timer(ps.game_id)
    game_manager.reset_missed_turns(ps.game_id)
    game_manager.schedule_turn_timer(ps.game_id)

    await _edit_with_keyboard(
        query,
        render_board(game, pid),
        combat_keyboard(game, pid),
    )

    op_tid = game_manager.get_opponent_telegram_id(
        update.effective_user.id
    )
    if op_tid:
        op_pid = game_manager.get_player_id_in_game(op_tid)
        if op_pid:
            await context.bot.send_message(
                chat_id=op_tid,
                text=f'{ICONES["combat"]} *Combate iniciado!* Use /board para declarar acoes.',
                parse_mode='Markdown',
                reply_markup=combat_keyboard(game, op_pid),
            )


@_register_cb('dc')
async def _cb_declare(query, context, game, pid, ps, params):
    """Callback: declarar ação de combate."""
    if len(params) < 2:
        return
    card_id = params[0]
    action = params[1].lower()

    from rage_web.game_engine.combat_queue import declare_action, COMBAT_ACTIONS

    if action not in COMBAT_ACTIONS:
        await query.answer(f'Acão invalida: {action}', show_alert=True)
        return

    if not declare_action(game, card_id, action):
        await query.answer('Nao foi possivel declarar', show_alert=True)
        return

    await query.answer(f'{card_id}: {action} declarada!')

    # Jogador agiu: reseta timer
    game_manager.cancel_turn_timer(ps.game_id)
    game_manager.reset_missed_turns(ps.game_id)
    game_manager.schedule_turn_timer(ps.game_id)

    await _edit_with_keyboard(
        query,
        render_combat_summary(game) or render_board(game, pid),
        combat_keyboard(game, pid),
    )


@_register_cb('rv')
async def _cb_reveal(query, context, game, pid, ps, params):
    """Callback: revelar ações."""
    from rage_web.game_engine.combat_queue import reveal_all, get_declaration_summary

    if not reveal_all(game):
        await query.answer('Nao foi possivel revelar', show_alert=True)
        return

    summary = get_declaration_summary(game)
    msg_parts = [f'{ICONES["combat"]} *Acoes reveladas!*']
    if 'declarations' in summary:
        for cid, act in summary['declarations'].items():
            msg_parts.append(f'   {cid}: {act}')

    await _edit_with_keyboard(
        query,
        '\n'.join(msg_parts),
        combat_keyboard(game, pid),
    )


@_register_cb('rs')
async def _cb_resolve(query, context, game, pid, ps, params):
    """Callback: resolver combate."""
    from rage_web.game_engine.combat_queue import resolve_combat

    if not resolve_combat(game):
        await query.answer('Nao foi possivel resolver', show_alert=True)
        return

    gid = ps.game_id
    vencido = _check_victory(query, context, game, gid)

    if vencido:
        return

    # Reseta timer (jogador agiu)
    game_manager.cancel_turn_timer(gid)
    game_manager.reset_missed_turns(gid)
    game_manager.schedule_turn_timer(gid)

    await _edit_with_keyboard(
        query,
        render_board(game, pid),
        board_keyboard(game, pid),
    )

    op_tid = game_manager.get_opponent_telegram_id(
        update.effective_user.id
    )
    if op_tid:
        op_pid = game_manager.get_player_id_in_game(op_tid)
        if op_pid:
            await context.bot.send_message(
                chat_id=op_tid,
                text=f'{ICONES["combat"]} Combate resolvido!',
                reply_markup=board_keyboard(game, op_pid),
            )


@_register_cb('ec')
async def _cb_endcombat(query, context, game, pid, ps, params):
    """Callback: encerrar combate."""
    from rage_web.game_engine.combat_queue import end_combat
    end_combat(game)

    await _edit_with_keyboard(
        query,
        render_board(game, pid),
        board_keyboard(game, pid),
    )


@_register_cb('ft')
async def _cb_feint(query, context, game, pid, ps, params):
    """Callback: feint (trocar ação)."""
    if len(params) < 2:
        return
    card_id = params[0]
    new_action = params[1].lower()

    from rage_web.game_engine.combat_queue import feint_action
    if not feint_action(game, card_id, new_action):
        await query.answer('Nao foi possivel usar Feint', show_alert=True)
        return

    await query.answer(f'Feint: {card_id} agora executa {new_action}')
    await _edit_with_keyboard(
        query,
        render_combat_summary(game) or render_board(game, pid),
        combat_keyboard(game, pid),
    )


@_register_cb('ps')
async def _cb_pass(query, context, game, pid, ps, params):
    """Callback: passar a vez."""
    player = next((p for p in game.players if p.id == pid), None)
    if not player:
        return

    player.pass_turn()
    all_passed = all(p.has_passed for p in game.players)
    uid = update.effective_user.id
    gid = ps.game_id

    if all_passed:
        old_phase = game.phase
        game.next_phase()
        for p in game.players:
            p.reset_pass()
        game.add_log(f'Todos passaram. {old_phase} to {game.phase}')

        await _edit_with_keyboard(
            query,
            f'{ICONES["pass"]} Todos passaram. Avancando para {game.phase}.',
            board_keyboard(game, pid),
        )

        # Agenda timer para nova fase
        game_manager.cancel_turn_timer(gid)
        game_manager.reset_missed_turns(gid)
        game_manager.schedule_turn_timer(gid)

        op_tid = game_manager.get_opponent_telegram_id(uid)
        if op_tid:
            op_pid = game_manager.get_player_id_in_game(op_tid)
            if op_pid:
                await context.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["pass"]} Todos passaram. Avancando para {game.phase}.',
                    reply_markup=board_keyboard(game, op_pid),
                )
    else:
        game.next_player()
        game.add_log(f'{player.name} passou.')

        await _edit_with_keyboard(
            query,
            f'{ICONES["pass"]} Voce passou. Aguarde o oponente.',
            wait_keyboard(),
        )

        # Agenda timer para o turno do oponente
        game_manager.cancel_turn_timer(gid)
        game_manager.reset_missed_turns(gid)
        game_manager.schedule_turn_timer(gid)

        op_tid = game_manager.get_opponent_telegram_id(uid)
        if op_tid:
            op_pid = game_manager.get_player_id_in_game(op_tid)
            if op_pid:
                await context.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["pass"]} *{player.name}* passou! E sua vez!',
                    parse_mode='Markdown',
                    reply_markup=board_keyboard(game, op_pid),
                )

    _check_victory(query, context, game, ps.game_id)


@_register_cb('nx')
async def _cb_next(query, context, game, pid, ps, params):
    """Callback: avançar fase."""
    old_phase = game.phase
    game.next_phase()
    game.add_log(f'Avancou: {old_phase} to {game.phase}')

    # Agenda timer para nova fase
    game_manager.cancel_turn_timer(ps.game_id)
    game_manager.reset_missed_turns(ps.game_id)
    game_manager.schedule_turn_timer(ps.game_id)

    await _edit_with_keyboard(
        query,
        f'{ICONES["next"]} Fase avancada: {old_phase} to {game.phase}',
        board_keyboard(game, pid),
    )


@_register_cb('cd')
async def _cb_concede(query, context, game, pid, ps, params):
    """Callback: conceder partida."""
    player_name = next(
        (p.name for p in game.players if p.id == pid),
        'Jogador',
    )
    gid = ps.game_id

    await _edit_with_keyboard(
        query,
        f'{ICONES["death"]} *{player_name} desistiu!* Fim de jogo.',
        None,
    )

    op_tid = game_manager.get_opponent_telegram_id(
        update.effective_user.id
    )
    if op_tid:
        await context.bot.send_message(
            chat_id=op_tid,
            text=f'{ICONES["trophy"]} *Vitoria!* {player_name} desistiu!',
            parse_mode='Markdown',
        )

    game_manager.remove_game(gid)


@_register_cb('bd')
async def _cb_board(query, context, game, pid, ps, params):
    """Callback: mostrar tabuleiro."""
    await _edit_with_keyboard(
        query,
        render_board(game, pid),
        combat_keyboard(game, pid) if game.combat.is_active
        else board_keyboard(game, pid),
    )


@_register_cb('hd')
async def _cb_hand(query, context, game, pid, ps, params):
    """Callback: mostrar mão."""
    await _edit_with_keyboard(
        query,
        render_hand(game, pid),
        hand_keyboard(game, pid),
    )


@_register_cb('st')
async def _cb_status(query, context, game, pid, ps, params):
    """Callback: mostrar status."""
    await _edit_with_keyboard(
        query,
        render_game_status(game, pid),
        nav_keyboard(),
    )


@_register_cb('ac')
async def _cb_actions(query, context, game, pid, ps, params):
    """Callback: mostrar ações disponíveis."""
    kb = combat_keyboard(game, pid) if game.combat.is_active else board_keyboard(game, pid)
    await _edit_with_keyboard(query, render_legal_actions(game, pid), kb)


@_register_cb('shw')
async def _cb_show(query, context, game, pid, ps, params):
    """Callback: mostrar sub-menus (card detail, declare, feint)."""
    if not params:
        return
    sub = params[0]

    if sub == 'cd' and len(params) > 1:
        # Mostrar detalhe de carta da mão
        try:
            idx = int(params[1])
        except ValueError:
            return
        player = next((p for p in game.players if p.id == pid), None)
        if player and idx < len(player.hand):
            card = player.hand[idx]
            await _edit_with_keyboard(
                query,
                render_card_detail(card),
                hand_keyboard(game, pid),
            )

    elif sub == 'dc' and len(params) > 1:
        # Menu de declaração para uma criatura
        cid = params[1]
        await _edit_with_keyboard(
            query,
            f'{ICONES["combat"]} Escolha a acao para criatura *{cid}*:',
            declare_keyboard(cid),
        )

    elif sub == 'ft':
        # Menu de feint
        await _edit_with_keyboard(
            query,
            f'{ICONES["combat"]} Escolha a nova acao (Feint):',
            feint_keyboard(game),
        )


# ── Timeout de turno ──────────────────────────────────────────────

def get_player_name_from_id(game, pid: str) -> str:
    """Retorna o nome do jogador pelo player_id."""
    for p in game.players:
        if p.id == pid:
            return p.name
    return 'Jogador'


async def turn_timeout_handler(game_id: str, timed_out_tid: int):
    """Callback chamado quando o timer de turno expira.

    Auto-passa a vez. Se o jogador excedeu o limite de timeouts
    consecutivos, auto-concede a partida.
    """
    from rage_web.telegram_bot.game_manager import game_manager as gm

    game = gm.get_game(game_id)
    if not game:
        return  # Jogo já foi removido

    session = gm.get_session(game_id)
    if not session:
        return

    pid = gm.get_player_id_in_game(timed_out_tid)
    if not pid:
        return

    # Verifica se realmente é a vez desse jogador
    if game.current_player.id != pid:
        return  # Jogador já agiu, timer defasado

    player_name = get_player_name_from_id(game, pid)

    # Incrementa contador de timeouts
    missed = gm.increment_missed_turns(game_id)
    _, max_missed = gm.get_timeout_config(game_id)

    if missed >= max_missed:
        # ── Auto-concede ──
        op_tid = gm.get_opponent_telegram_id(timed_out_tid)

        # Registra estatísticas
        if op_tid:
            try:
                stats_manager.record_match(
                    winner_id=op_tid,
                    loser_id=timed_out_tid,
                    method='timeout',
                )
            except Exception as e:
                logger.error(f'Erro ao registrar stats por timeout: {e}')

        gm.remove_game(game_id)

        try:
            from rage_web.telegram_bot.bot import _app
            if _app and op_tid:
                await _app.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["trophy"]} *Vitoria!* {player_name}'
                         f' nao agiu a tempo e foi desclassificado!'
                         f'\n\n(turno expirado {missed}x consecutivas)',
                    parse_mode='Markdown',
                )
            if _app:
                await _app.bot.send_message(
                    chat_id=timed_out_tid,
                    text=f'{ICONES["death"]} *Derrota!*'
                         f' Voce nao agiu a tempo e foi desclassificado.'
                         f'\n\nLimite de {max_missed} turnos excedido.',
                    parse_mode='Markdown',
                )
        except Exception as e:
            __import__('logging').error(f'Erro notificando timeout: {e}')

    else:
        # ── Auto-passa a vez ──
        player = next((p for p in game.players if p.id == pid), None)
        if not player:
            return

        player.pass_turn()
        all_passed = all(p.has_passed for p in game.players)

        if all_passed:
            game.next_phase()
            for p in game.players:
                p.reset_pass()
            game.add_log(f'Todos passaram (timeout).')
        else:
            game.next_player()
            game.add_log(f'{player_name} passou por timeout.')

        # Agenda timer para o próximo turno
        gm.schedule_turn_timer(game_id)

        # Notifica jogadores
        op_tid = gm.get_opponent_telegram_id(timed_out_tid)
        restantes = max_missed - missed

        from rage_web.telegram_bot.i18n import t

        try:
            from rage_web.telegram_bot.bot import _app
            if not _app:
                return

            lang_player = 'pt_BR'  # fallback
            # Notifica o jogador que perdeu o timeout
            await _app.bot.send_message(
                chat_id=timed_out_tid,
                text=f'{ICONES["hourglass"]} *Timeout!*'
                     f' Voce demorou demais e seu turno foi passado.'
                     f'\n\n{restantes} falta(s) para ser desclassificado.',
                parse_mode='Markdown',
            )

            # Notifica o oponente
            if op_tid:
                from rage_web.telegram_bot.keyboards import board_keyboard
                op_pid = gm.get_player_id_in_game(op_tid)
                await _app.bot.send_message(
                    chat_id=op_tid,
                    text=f'{ICONES["pass"]} *{player_name}*'
                         f' nao agiu a tempo! E sua vez!'
                         f'\n({restantes} timeout(s) restante(s) antes de W.O.)',
                    parse_mode='Markdown',
                )
                if op_pid:
                    from rage_web.telegram_bot.render import render_board
                    board_msg = render_board(game, op_pid)
                    kb = board_keyboard(game, op_pid)
                    await _app.bot.send_message(
                        chat_id=op_tid,
                        text=board_msg,
                        parse_mode='Markdown',
                        reply_markup=kb,
                    )
        except Exception as e:
            __import__('logging').error(f'Erro notificando timeout: {e}')


# ── Modo contra-bot ────────────────────────────────────────────────
# Comando /duel-bot <deck_id> [bot_deck_id] — desafia um bot.
# O bot usa PriorityBot com decisoes automaticas.

async def duel_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /duel-bot <deck_id> [bot_deck_id] — desafia um bot."""
    if not _ensure_not_in_game(update, context):
        return

    uid = _get_player_id(update)
    name = _get_player_name(update)
    args = context.args

    if len(args) < 1:
        await update.message.reply_text(
            f'{ICONES["warning"]} Uso: `/duel-bot <deck_id> [bot_deck_id]`\n'
            f'Exemplo: `/duel-bot 7 1055` (deck 7 vs Bot Philodox)\n'
            f'Exemplo: `/duel-bot 7` (bot escolhe aleatorio)',
            parse_mode='Markdown',
        )
        return

    player_deck_id = _parse_int(args[0])
    if not player_deck_id:
        await update.message.reply_text(
            f'{ICONES["warning"]} Informe o ID do seu deck.'
            f' Exemplo: `/duel-bot 7`',
            parse_mode='Markdown',
        )
        return

    # Deck do bot: especificado ou aleatorio entre os configurados
    if len(args) >= 2:
        bot_deck_id = _parse_int(args[1])
        if not bot_deck_id or bot_deck_id not in BOT_DECKS:
            disponiveis = ', '.join(str(k) for k in BOT_DECKS)
            await update.message.reply_text(
                f'{ICONES["warning"]} Deck do bot invalido.'
                f' Disponiveis: {disponiveis}\n'
                f'Exemplo: `/duel-bot {player_deck_id} 1055`',
            )
            return
    else:
        bot_deck_id = random.choice(list(BOT_DECKS.keys()))

    # Verifica se o deck do jogador existe
    try:
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db
        from rage_web import create_app

        flask_app = create_app()
        with flask_app.app_context():
            deck = db.session.get(Deck, player_deck_id)
            if not deck:
                await update.message.reply_text(
                    f'{ICONES["cross"]} Deck {player_deck_id} nao encontrado.'
                )
                return
            player_deck_name = deck.name or f'Deck {player_deck_id}'
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao verificar deck: {e}'
        )
        return

    # Cria a partida
    import random as rng_mod
    seed = rng_mod.randint(0, 999999)

    try:
        from rage_web.game_engine.cli import build_game_from_decks_n
        game = build_game_from_decks_n(player_deck_id, bot_deck_id, seed=seed)
    except Exception as e:
        await update.message.reply_text(
            f'{ICONES["cross"]} Erro ao criar partida: {e}'
        )
        return

    # Renomeia o bot player para algo mais amigavel
    bot_name = BOT_NAMES.get(bot_deck_id, f'Bot (Deck {bot_deck_id})')
    for p in game.players:
        if 'Jogador 2' in p.name or 'Deck 2' in p.name or p.id == 'p2':
            p.name = bot_name
            p.deck_id = bot_deck_id

    bot_desc = BOT_DECKS.get(bot_deck_id, f'Deck {bot_deck_id}')

    # Registra no GameManager
    player_map = {uid: 'p1', BOT_TELEGRAM_ID: 'p2'}
    gid = game_manager.create_game(game, player_map)

    # Mensagem de inicio
    msg = (
        f'⚔️ *Partida contra Bot!*\n\n'
        f'Seu deck: `{player_deck_name}` ({player_deck_id})\n'
        f'Bot: `{bot_name}` ({bot_desc})\n'
        f'Seed: {seed}\n\n'
        f'{ICONES["info"]} O bot joga automaticamente. '
        f'Use `/board` para ver o tabuleiro e os comandos de jogo.\n'
        f'{ICONES["warning"]} Para sair, use `/concede`.'
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

    # Se o bot joga primeiro, executa as turnos do bot imediatamente
    await _run_bot_turns(context, game, gid, uid)


async def _run_bot_turns(context, game, gid, human_tid):
    """Executa turnos do bot ate que seja a vez do humano ou a partida termine.

    Chamado apos cada acao do jogador humano. O bot joga automaticamente
    usando PriorityBot.
    """
    from rage_web.game_engine.bot.priority_bot import PriorityBot

    max_loops = 100  # Seguranca: evita loop infinito
    loop_count = 0

    while loop_count < max_loops:
        # Verifica se a partida ainda existe
        session = game_manager.get_session(gid)
        if not session:
            return

        cp = game.current_player

        # Se e a vez do humano, para
        if cp.id == 'p1':
            # Envia board pro humano
            pid = game_manager.get_player_id_in_game(human_tid)
            if pid:
                await _update_board_message(
                    None, context, game, pid, chat_id=human_tid,
                )
            return

        # Se nao e a vez do bot (outro jogador), espera
        if cp.id != 'p2':
            return

        # Cancela timer (bot joga agora, nao precisa de timeout)
        game_manager.cancel_turn_timer(gid)

        # Cria bot e decide acao
        try:
            bot = PriorityBot(game, cp.id, difficulty='hard')
            action = bot.decide()
        except Exception as e:
            __import__('logging').error(f'Erro no bot decide(): {e}')
            break

        if not action or action == 'wait':
            break

        # Log da acao do bot
        __import__('logging').info(
            f'[BOT] {cp.name}: {action}'
        )

        # Pequena pausa para nao floodar
        await asyncio.sleep(0.05)

        # Verifica vitoria/eliminacao
        from rage_web.game_engine.combat_queue import (
            _tem_character, _eliminar_jogador,
        )
        for p in game.players:
            if not _tem_character(p) and not getattr(p, 'eliminado', False):
                _eliminar_jogador(game, p)
                __import__('logging').info(
                    f'{p.name} foi eliminado! (sem Characters)'
                )

        # Verifica se alguem venceu
        vencedor = None
        for p in game.players:
            if p.victory_points >= p.renown_level:
                vencedor = p
                game.add_log(
                    f'🏆 {p.name} VENCEU! ({p.victory_points}/{p.renown_level} VP)'
                )
                break

        if vencedor:
            # Encerra a partida
            msg = render_victory(game, vencedor.id)
            try:
                await context.bot.send_message(
                    chat_id=human_tid,
                    text=msg,
                    parse_mode='Markdown',
                )
            except Exception:
                pass
            game_manager.remove_game(gid)
            return

        jogadores_ativos = [p for p in game.players
                           if not getattr(p, 'eliminado', False)]
        if len(jogadores_ativos) <= 1:
            if jogadores_ativos:
                v = jogadores_ativos[0]
                msg = render_victory(game, v.id)
            else:
                msg = '💀 Todos os jogadores foram eliminados! Empate.'
            try:
                await context.bot.send_message(
                    chat_id=human_tid,
                    text=msg,
                    parse_mode='Markdown',
                )
            except Exception:
                pass
            game_manager.remove_game(gid)
            return

        loop_count += 1

    # Se saiu do loop sem ser a vez do humano, envia board
    pid = game_manager.get_player_id_in_game(human_tid)
    if pid and game_manager.get_session(gid):
        await _update_board_message(
            None, context, game, pid, chat_id=human_tid,
        )


async def _is_bot_game(game) -> bool:
    """Verifica se a partida atual e contra um bot."""
    return hasattr(game, 'players') and any(
        hasattr(p, 'deck_id') and p.deck_id in BOT_DECKS
        for p in game.players if p.id == 'p2'
    )


async def _run_bot_turns_if_needed(update, context, gid):
    """Helper: verifica se e partida contra bot e roda turnos do bot."""
    if not gid:
        return
    session = game_manager.get_session(gid)
    if not session:
        return
    game = session.game
    if not game:
        return

    # Verifica se e partida contra bot
    is_bot = False
    for tid in session.players:
        if tid == BOT_TELEGRAM_ID:
            is_bot = True
            break
    if not is_bot:
        return

    # Verifica de quem e a vez
    cp = game.current_player
    if cp.id == 'p2':
        # E a vez do bot — descobre o Telegram ID do humano
        human_tid = None
        for tid, pid in session.players.items():
            if pid == 'p1':
                human_tid = tid
                break
        if human_tid:
            await _run_bot_turns(context, game, gid, human_tid)


# ── Error handler ──────────────────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler global de erros."""
    from telegram.error import TelegramError

    error = context.error
    if isinstance(error, TelegramError):
        return

    __import__('logging').error(
        'Exception while handling an update: %s', error,
        exc_info=True,
    )
