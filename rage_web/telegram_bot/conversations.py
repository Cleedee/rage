"""ConversationHandlers para fluxos guiados do Bot Telegram.

Substitui os comandos diretos por diálogos passo-a-passo:
  - /duel  → perguntar @username → perguntar deck → enviar desafio
  - /accept → mostrar desafios → perguntar deck → criar partida

Mantém compatibilidade com o formato direto:
  /duel @joao 7    (processa imediatamente, sem conversation)
  /accept @joao 90 (processa imediatamente, sem conversation)
"""

from __future__ import annotations

import re
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from rage_web.telegram_bot.keyboards import nav_keyboard, board_keyboard
from rage_web.telegram_bot.render import (
    render_board, render_deck_list, ICONES,
)
from rage_web.telegram_bot.i18n import t, LANGUAGES
from rage_web.telegram_bot.user_registry import (
    register_user, resolve_username, resolve_username_via_api,
)

from rage_web.game_engine.cli import build_game_from_decks_n

# ── Instâncias globais (compartilhadas com handlers.py) ────────────

from rage_web.telegram_bot.handlers import game_manager, matchmaker

# ── Helpers ─────────────────────────────────────────────────────────

def _extract_mentions(text: str) -> list[str]:
    return re.findall(r'@(\w+)', text)

def _parse_int(text: str, default=None) -> int | None:
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else default

def _get_user_decks(telegram_id: int) -> list[tuple[int, str, int]]:
    """Retorna lista de decks do usuário."""
    try:
        from rage_web import create_app
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db

        flask_app = create_app()
        with flask_app.app_context():
            decks_list = []
            for d in Deck.query.order_by(Deck.name).all():
                qtd = len(d.cards) if hasattr(d, 'cards') and d.cards else 0
                decks_list.append((d.id, d.name, qtd))
            return decks_list
    except Exception:
        return []

def _make_deck_keyboard(decks: list[tuple[int, str, int]],
                        prefix: str = 'duel_deck') -> InlineKeyboardMarkup:
    """Cria teclado inline com a lista de decks."""
    rows = []
    for did, name, qtd in decks[:10]:
        label = f'{name[:20]} ({qtd} cartas)'
        rows.append([
            InlineKeyboardButton(label, callback_data=f'{prefix}:{did}')
        ])
    rows.append([
        InlineKeyboardButton('🔙 Cancelar', callback_data=f'{prefix}:cancel')
    ])
    return InlineKeyboardMarkup(rows)

# ═══════════════════════════════════════════════════════════════════
# FLUXO: /duel
# ═══════════════════════════════════════════════════════════════════

(
    DUEL_USERNAME,  # 0: aguardando @username do oponente
    DUEL_DECK,      # 1: aguardando deck ID (texto ou callback)
) = range(2)

async def duel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point do /duel.

    Se já veio com parâmetros (/duel @joao 7), processa direto.
    Caso contrário, inicia o diálogo.
    """
    uid = update.effective_user.id
    lang = context.user_data.get('lang', 'pt_BR')
    text = update.message.text

    # Registra o usuário no banco de resolução de @username
    user = update.effective_user
    register_user(user.id, user.username, user.full_name)

    # Verifica se não está em jogo
    if game_manager.is_player_in_game(uid):
        await update.message.reply_text(
            t('error.already_in_game', lang=lang),
        )
        return ConversationHandler.END

    # Tenta processar como comando direto: /duel @joao 7
    parts = text.strip().split()
    mentions = _extract_mentions(text)
    deck_id = None
    for p in parts:
        pid = _parse_int(p)
        if pid:
            deck_id = pid
            break

    if mentions and deck_id:
        # Modo direto: processa igual ao handler antigo
        challenged_username = mentions[0].lower()
        user_username = (update.effective_user.username or '').lower()

        if challenged_username == user_username:
            await update.message.reply_text(t('error.duel_self', lang=lang))
            return ConversationHandler.END

        # Resolve @username para Telegram user_id
        challenged_id = resolve_username(challenged_username)
        if not challenged_id:
            # Fallback: tenta via API do Telegram
            challenged_id = await resolve_username_via_api(
                challenged_username, context
            )

        if challenged_id:
            # Cria desafio no Matchmaker (com user_id real)
            matchmaker.create_challenge(
                challenger_id=uid,
                challenger_name=update.effective_user.full_name,
                challenged_id=challenged_id,
                deck_challenger=deck_id,
            )
            # Tenta notificar o desafiado
            try:
                await context.bot.send_message(
                    chat_id=challenged_id,
                    text=(
                        f'⚔️ *Desafio!* {update.effective_user.full_name}'
                        f' quer duelar com você!'
                        f'\n\nDeck dele: `{deck_id}`'
                        f'\n\nUse `/accept` para aceitar!'
                    ),
                    parse_mode='Markdown',
                )
            except Exception:
                pass  # Desafiado nunca interagiu com o bot

            await update.message.reply_text(
                f'✅ Desafio enviado para @{challenged_username}!'
                f' Aguardando resposta... (expira em 2 min)',
            )
        else:
            await update.message.reply_text(
                f'⚠️ Não foi possível encontrar @{challenged_username}.'
                f' Ele precisa iniciar uma conversa comigo primeiro'
                f' (enviar /start para @furia_ccg_bot).'
            )
        return ConversationHandler.END

    # Modo guiado: pergunta o @username
    await update.message.reply_text(
        t('duel.ask_username', lang=lang),
        parse_mode='Markdown',
    )
    return DUEL_USERNAME

async def duel_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passo 1: recebe o @username do oponente."""
    lang = context.user_data.get('lang', 'pt_BR')
    text = update.message.text.strip()
    mentions = _extract_mentions(text)

    if not mentions:
        await update.message.reply_text(
            f'⚠️ {t("duel.ask_username", lang=lang)}',
        )
        return DUEL_USERNAME

    challenged = mentions[0].lower()
    user_username = (update.effective_user.username or '').lower()

    if challenged == user_username:
        await update.message.reply_text(t('error.duel_self', lang=lang))
        return DUEL_USERNAME

    context.user_data['duel_challenged'] = challenged

    # Pergunta o deck
    decks = _get_user_decks(update.effective_user.id)
    if not decks:
        await update.message.reply_text(t('error.no_decks', lang=lang))
        return ConversationHandler.END

    await update.message.reply_text(
        f'{t("duel.ask_deck_title", lang=lang)}\n\n'
        f'{t("duel.ask_deck", lang=lang)}\n'
        f'*Ou clique no deck abaixo:*',
        parse_mode='Markdown',
        reply_markup=_make_deck_keyboard(decks, 'duel_deck'),
    )
    return DUEL_DECK

async def duel_deck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passo 2: recebe o deck (via texto ou callback)."""
    lang = context.user_data.get('lang', 'pt_BR')
    uid = update.effective_user.id
    name = update.effective_user.full_name
    challenged = context.user_data.get('duel_challenged')

    deck_id = None

    # Verifica se é callback (clique no botão)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.endswith(':cancel'):
            await query.edit_message_text('🔙 Cancelado.')
            context.user_data.pop('duel_challenged', None)
            return ConversationHandler.END
        try:
            deck_id = int(data.split(':')[-1])
        except (ValueError, IndexError):
            pass
    else:
        # Texto: "/deck 7" ou "7"
        deck_id = _parse_int(update.message.text)

    if not deck_id:
        await update.message.reply_text(
            f'⚠️ ID inválido. {t("duel.ask_deck", lang=lang)}',
            reply_markup=_make_deck_keyboard(
                _get_user_decks(uid), 'duel_deck'
            ),
        )
        return DUEL_DECK

    # Verifica se o deck existe
    try:
        from rage_web import create_app
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db

        flask_app = create_app()
        with flask_app.app_context():
            deck = db.session.get(Deck, deck_id)
            if not deck:
                await update.message.reply_text(
                    t('error.deck_not_found', lang=lang, id=deck_id),
                )
                return DUEL_DECK
    except Exception as e:
        await update.message.reply_text(f'❌ Erro: {e}')
        return DUEL_DECK

    # Resolve @username para Telegram user_id
    challenged_id = resolve_username(challenged)
    if not challenged_id:
        challenged_id = await resolve_username_via_api(
            challenged, context
        )

    if challenged_id:
        # Usa o Matchmaker centralizado
        matchmaker.create_challenge(
            challenger_id=uid,
            challenger_name=name,
            challenged_id=challenged_id,
            deck_challenger=deck_id,
        )

        # Notifica o desafiado
        try:
            await context.bot.send_message(
                chat_id=challenged_id,
                text=(
                    f'⚔️ *Desafio!* {name} quer duelar com você!'
                    f'\n\nDeck dele: `{deck_id}`'
                    f'\n\nUse `/accept` para aceitar!'
                ),
                parse_mode='Markdown',
            )
        except Exception:
            pass

        msg = f'✅ Desafio enviado para @{challenged}! Aguardando resposta...'
    else:
        msg = (
            f'⚠️ Não foi possível encontrar @{challenged}.'
            f' Ele precisa iniciar uma conversa comigo primeiro'
            f' (enviar /start para @furia_ccg_bot).'
        )

    if update.callback_query:
        await update.callback_query.edit_message_text(msg)
    else:
        await update.message.reply_text(msg)

    context.user_data.pop('duel_challenged', None)
    return ConversationHandler.END

async def duel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o fluxo de desafio."""
    lang = context.user_data.get('lang', 'pt_BR')
    context.user_data.pop('duel_challenged', None)
    await update.message.reply_text('🔙 Cancelado.', reply_markup=nav_keyboard())
    return ConversationHandler.END

def get_duel_conversation() -> ConversationHandler:
    """Retorna o ConversationHandler configurado para /duel."""
    return ConversationHandler(
        entry_points=[CommandHandler('duel', duel_start)],
        states={
            DUEL_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, duel_username),
            ],
            DUEL_DECK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, duel_deck),
                CallbackQueryHandler(duel_deck, pattern=r'^duel_deck:'),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', duel_cancel),
            MessageHandler(filters.COMMAND, duel_cancel),
        ],
        name='duel_conversation',
        persistent=False,
        per_message=False,
    )

# ═══════════════════════════════════════════════════════════════════
# FLUXO: /accept
# ═══════════════════════════════════════════════════════════════════

(
    ACCEPT_SELECT,  # 0: selecionar qual desafio aceitar
    ACCEPT_DECK,    # 1: escolher deck
) = range(2)

async def accept_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point do /accept.

    Se já veio com parâmetros (/accept @joao 90), processa direto.
    Caso contrário, inicia o diálogo.
    """
    uid = update.effective_user.id
    lang = context.user_data.get('lang', 'pt_BR')
    text = update.message.text

    # Registra o usuário
    user = update.effective_user
    register_user(user.id, user.username, user.full_name)

    if game_manager.is_player_in_game(uid):
        await update.message.reply_text(t('error.already_in_game', lang=lang))
        return ConversationHandler.END

    # Tenta processar como comando direto: /accept @joao 90
    parts = text.strip().split()
    mentions = _extract_mentions(text)
    deck_id = None
    for p in parts:
        pid = _parse_int(p)
        if pid:
            deck_id = pid
            break

    if mentions and deck_id:
        # Modo direto: busca desafio pendente
        username_to_match = mentions[0].lower()
        my_username = (update.effective_user.username or '').lower()

        # Busca nas pending_challenges de outros usuários
        # (no MVP, busca no context.user_data de outros — simplificado)
        # Idealmente teria um banco; por hora, tenta criar partida
        # com os dados que estão no matchmaker
        challenges = matchmaker.get_pending_challenges(uid)
        if not challenges:
            await update.message.reply_text(
                t('accept.no_pending', lang=lang),
            )
            return ConversationHandler.END

        challenge = challenges[0]
        accepted = matchmaker.accept_challenge(
            uid, challenge.challenger_id, deck_id
        )
        if not accepted:
            await update.message.reply_text(
                t('accept.no_pending', lang=lang),
            )
            return ConversationHandler.END

        # Cria partida
        return await _create_game_from_challenge(
            update, context, challenge, uid, deck_id
        )

    # Modo guiado: mostra desafios pendentes
    challenges = matchmaker.get_pending_challenges(uid)

    if not challenges:
        await update.message.reply_text(
            t('accept.no_pending', lang=lang),
        )
        return ConversationHandler.END

    if len(challenges) == 1:
        # Só um desafio: pergunta o deck direto
        c = challenges[0]
        context.user_data['accept_challenge'] = c
        decks = _get_user_decks(uid)
        if not decks:
            await update.message.reply_text(t('error.no_decks', lang=lang))
            return ConversationHandler.END

        await update.message.reply_text(
            f'{t("accept.ask_deck", lang=lang)}\n\n'
            f'Desafiante: *{c.challenger_name}*\n\n'
            f'{t("accept.ask_deck_id", lang=lang)}',
            parse_mode='Markdown',
            reply_markup=_make_deck_keyboard(decks, 'accept_deck'),
        )
        return ACCEPT_DECK

    # Múltiplos desafios: pergunta qual
    lines = []
    for i, c in enumerate(challenges):
        lines.append(
            f'`[{i+1}]` {c.challenger_name} — deck {c.deck_challenger}'
        )
    context.user_data['accept_challenges'] = challenges

    await update.message.reply_text(
        f'{t("accept.ask_which", lang=lang, list="\\n".join(lines))}\n\n'
        f'{t("accept.ask_number", lang=lang)}',
        parse_mode='Markdown',
    )
    return ACCEPT_SELECT

async def accept_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passo 1: seleciona qual desafio aceitar (quando há múltiplos)."""
    lang = context.user_data.get('lang', 'pt_BR')
    challenges = context.user_data.get('accept_challenges', [])

    idx = _parse_int(update.message.text)
    if idx is None or idx < 1 or idx > len(challenges):
        await update.message.reply_text(
            f'⚠️ Número inválido. Digite um número entre 1 e {len(challenges)}:',
        )
        return ACCEPT_SELECT

    challenge = challenges[idx - 1]
    context.user_data['accept_challenge'] = challenge
    context.user_data.pop('accept_challenges', None)

    # Pergunta o deck
    uid = update.effective_user.id
    decks = _get_user_decks(uid)
    if not decks:
        await update.message.reply_text(t('error.no_decks', lang=lang))
        return ConversationHandler.END

    await update.message.reply_text(
        f'{t("accept.ask_deck", lang=lang)}\n\n'
        f'Desafiante: *{challenge.challenger_name}*\n\n'
        f'{t("accept.ask_deck_id", lang=lang)}',
        parse_mode='Markdown',
        reply_markup=_make_deck_keyboard(decks, 'accept_deck'),
    )
    return ACCEPT_DECK

async def accept_deck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passo 2: recebe o deck (texto ou callback) e cria partida."""
    lang = context.user_data.get('lang', 'pt_BR')
    uid = update.effective_user.id
    challenge = context.user_data.get('accept_challenge')

    if not challenge:
        await update.message.reply_text('❌ Desafio expirado.')
        return ConversationHandler.END

    deck_id = None

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data.endswith(':cancel'):
            await query.edit_message_text('🔙 Cancelado.')
            context.user_data.pop('accept_challenge', None)
            return ConversationHandler.END
        try:
            deck_id = int(data.split(':')[-1])
        except (ValueError, IndexError):
            pass
    else:
        deck_id = _parse_int(update.message.text)

    if not deck_id:
        await update.message.reply_text(
            f'⚠️ ID inválido. {t("accept.ask_deck_id", lang=lang)}',
            reply_markup=_make_deck_keyboard(
                _get_user_decks(uid), 'accept_deck'
            ),
        )
        return ACCEPT_DECK

    # Verifica deck
    try:
        from rage_web import create_app
        from rage_web.models.deck import Deck
        from rage_web.ext.database import db

        flask_app = create_app()
        with flask_app.app_context():
            deck = db.session.get(Deck, deck_id)
            if not deck:
                await update.message.reply_text(
                    f'❌ Deck {deck_id} não encontrado.',
                )
                return ACCEPT_DECK
    except Exception as e:
        await update.message.reply_text(f'❌ Erro: {e}')
        return ACCEPT_DECK

    # Aceita o desafio
    accepted = matchmaker.accept_challenge(
        challenge.challenged_id, challenge.challenger_id, deck_id
    )
    if not accepted:
        await update.message.reply_text(
            '❌ Desafio expirou ou foi cancelado.',
        )
        return ConversationHandler.END

    return await _create_game_from_challenge(
        update, context, challenge, uid, deck_id
    )

async def _create_game_from_challenge(update, context, challenge,
                                       uid: int, deck_id: int):
    """Cria a partida a partir de um desafio aceito."""
    lang = context.user_data.get('lang', 'pt_BR')

    try:
        game = matchmaker.create_game_from_challenge(challenge)
    except Exception as e:
        await update.message.reply_text(f'❌ Erro ao criar partida: {e}')
        return ConversationHandler.END

    # Registra no GameManager
    player_map = {
        challenge.challenger_id: game.players[0].id,
        uid: game.players[1].id,
    }
    gid = game_manager.create_game(game, player_map)

    # Agenda timer de turno (quem começa tem X horas para agir)
    game_manager.schedule_turn_timer(gid)

    # Atualiza nomes
    game.players[0].name = challenge.challenger_name
    game.players[1].name = update.effective_user.full_name

    msg = t('duel.accepted', lang=lang, challenger=challenge.challenger_name)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, parse_mode='Markdown',
        )
    else:
        await update.message.reply_text(msg, parse_mode='Markdown')

    # Envia board para ambos os jogadores
    for tid in (challenge.challenger_id, uid):
        pid = game_manager.get_player_id_in_game(tid)
        if pid:
            try:
                board_msg = render_board(game, pid)
                kb = board_keyboard(game, pid)
                await context.bot.send_message(
                    chat_id=tid,
                    text=board_msg,
                    parse_mode='Markdown',
                    reply_markup=kb,
                )
            except Exception:
                pass

    context.user_data.pop('accept_challenge', None)
    return ConversationHandler.END

async def accept_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o fluxo de aceitação."""
    context.user_data.pop('accept_challenge', None)
    context.user_data.pop('accept_challenges', None)
    await update.message.reply_text('🔙 Cancelado.', reply_markup=nav_keyboard())
    return ConversationHandler.END

def get_accept_conversation() -> ConversationHandler:
    """Retorna o ConversationHandler configurado para /accept."""
    return ConversationHandler(
        entry_points=[CommandHandler('accept', accept_start)],
        states={
            ACCEPT_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, accept_select),
            ],
            ACCEPT_DECK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, accept_deck),
                CallbackQueryHandler(accept_deck, pattern=r'^accept_deck:'),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', accept_cancel),
            MessageHandler(filters.COMMAND, accept_cancel),
        ],
        name='accept_conversation',
        persistent=False,
        per_message=False,
    )
