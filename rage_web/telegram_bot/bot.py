"""Ponto de entrada do Bot Telegram Rage CCG.

Inicializa e configura a aplicação python-telegram-bot,
registra todos os handlers e oferece dois modos de operação:

- Polling (padrão): Bot consulta o Telegram periodicamente.
  Funciona sem necessidade de URL pública ou HTTPS.
  Ideal para rodar localmente ou em um VPS.

- Webhook: Bot recebe updates via POST.
  Requer URL pública com HTTPS.
  Ideal para produção em serviços como PythonAnywhere, Fly.io, etc.

Uso:
    rage-bot                          # Modo polling (token do env BOT_TOKEN)
    rage-bot --token 123456:ABC-DEF   # Token explícito
    rage-bot --webhook --url https://...  # Modo webhook
    rage-bot --webhook --url https://... --port 8443
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from pathlib import Path

# Suprime warnings do python-telegram-bot sobre per_message
warnings.filterwarnings('ignore', message=".*per_message.*")
warnings.filterwarnings('ignore', category=UserWarning, module='telegram')


# ── Carregar .env automaticamente ────────────────────────────────

def _load_dotenv(path: str = '.env'):
    """Carrega variaveis de um arquivo .env simples.

    Suporta:
      KEY=value
      export KEY=value
      # comentarios
      linhas em branco
    """
    env_path = Path(path)
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            if '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv()

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from rage_web.telegram_bot.handlers import (
    # Comandos básicos
    start,
    help_command,
    # Decks
    decks,
    # Matchmaking
    decline,
    duel_bot,
    # Jogabilidade
    board,
    hand,
    status,
    actions,
    play,
    use_card,
    attack,
    declare,
    reveal,
    feint,
    resolve,
    endcombat,
    draw,
    pass_turn,
    next_phase,
    concede,
    timer_command,
    deck_command,
    stats_command,
    rank_command,
    card_command,
    # Error handler
    error_handler,
    # Callback handler (inline keyboards)
    handle_callback,
)

from rage_web.telegram_bot.conversations import (
    get_duel_conversation,
    get_accept_conversation,
)
from rage_web.telegram_bot.i18n import cmd_lang


# ── Configuração de logging ─────────────────────────────────────────

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Lista de comandos para o BotFather ─────────────────────────────

COMMANDS = [
    ('start', '🐺 Boas-vindas e instruções'),
    ('help', '📖 Ajuda detalhada'),
    ('decks', '📚 Listar seus decks'),
    ('duel', '⚔️ Desafiar jogador: /duel @joao <deck_id>'),
    ('accept', '✅ Aceitar desafio: /accept @joao <deck_id>'),
    ('lang', '🌐 Mudar idioma / Change language'),
    ('decline', '❌ Recusar desafio'),
    ('board', '🗺️ Ver tabuleiro'),
    ('hand', '🃏 Ver sua mão'),
    ('status', '📊 Status da partida'),
    ('actions', '🎯 Ações disponíveis'),
    ('play', '▶️ Jogar carta: /play <N>'),
    ('use', '🎁 Usar carta de efeito: /use <N>'),
    ('attack', '⚔️ Iniciar combate: /attack <id> [alvo]'),
    ('declare', '🗣️ Declarar ação: /declare <id> <ação>'),
    ('reveal', '👁️ Revelar ações'),
    ('feint', '🎭 Trocar ação: /feint <id> <ação>'),
    ('resolve', '💥 Resolver combate'),
    ('endcombat', '🏁 Encerrar combate'),
    ('draw', '📥 Comprar cartas'),
    ('pass', '⏭️ Passar a vez'),
    ('next', '⏩ Avançar fase'),
    ('concede', '🏳️ Desistir'),
    ('duel_bot', '🤖 Desafiar bot: /duel-bot <deck_id> [bot_deck_id]'),
]


# Referência global para o Application (usada pelo timeout handler)
_app: Application | None = None


async def _restore_active_games(app: Application):
    """Restaura partidas salvas no banco e notifica jogadores.

    Chamado como post_init no ApplicationBuilder.
    """
    from rage_web.telegram_bot.handlers import game_manager as gm
    try:
        games = gm.load_all_active_games()
        if not games:
            return
        logger.info(f'Restaurando {len(games)} partidas ativas...')
        for game_id, session in games:
            # Notifica ambos os jogadores
            for tid in session.players:
                try:
                    await app.bot.send_message(
                        chat_id=tid,
                        text=(
                            f'🔄 *Partida restaurada!*'
                            f'\nO bot foi reiniciado, mas sua partida'
                            f' continua ativa.'
                            f'\nUse `/board` para ver o tabuleiro.'
                        ),
                        parse_mode='Markdown',
                    )
                except Exception:
                    pass
            # Reagenda timer para o jogador atual
            cp_tid = gm.get_current_player_telegram_id(game_id)
            if cp_tid:
                gm.schedule_turn_timer(game_id)
        logger.info(f'{len(games)} partidas restauradas com sucesso.')
    except Exception as e:
        logger.error(f'Erro ao restaurar partidas: {e}')


def build_application(token: str) -> Application:
    """Constrói e configura a aplicação do bot com todos os handlers."""
    global _app

    app = ApplicationBuilder()\
        .token(token)\
        .post_init(_restore_active_games)\
        .build()
    _app = app

    # ── Configura timeout de turno ──
    from rage_web.telegram_bot.handlers import turn_timeout_handler
    from rage_web.telegram_bot.handlers import game_manager
    game_manager.set_turn_timeout_callback(turn_timeout_handler)

    # ── Comandos básicos ──
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('lang', cmd_lang))

    # ── Decks ──
    app.add_handler(CommandHandler('decks', decks))

    # ── Matchmaking (ConversationHandlers têm prioridade) ──
    app.add_handler(get_duel_conversation())
    app.add_handler(get_accept_conversation())
    app.add_handler(CommandHandler('decline', decline))

    # ── Jogabilidade ──
    app.add_handler(CommandHandler('board', board))
    app.add_handler(CommandHandler('hand', hand))
    app.add_handler(CommandHandler('status', status))
    app.add_handler(CommandHandler('actions', actions))
    app.add_handler(CommandHandler('play', play))
    app.add_handler(CommandHandler('use', use_card))
    app.add_handler(CommandHandler('attack', attack))
    app.add_handler(CommandHandler('declare', declare))
    app.add_handler(CommandHandler('reveal', reveal))
    app.add_handler(CommandHandler('feint', feint))
    app.add_handler(CommandHandler('resolve', resolve))
    app.add_handler(CommandHandler('endcombat', endcombat))
    app.add_handler(CommandHandler('draw', draw))
    app.add_handler(CommandHandler('pass', pass_turn))
    app.add_handler(CommandHandler('next', next_phase))
    app.add_handler(CommandHandler('concede', concede))
    app.add_handler(CommandHandler('timer', timer_command))

    # ── Estatísticas ──
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('rank', rank_command))

    # ── Card Detail ──
    app.add_handler(CommandHandler('card', card_command))

    # ── Galeria de Decks ──
    app.add_handler(CommandHandler('deck', deck_command))

    # ── Bot Duel ──
    app.add_handler(CommandHandler('duel_bot', duel_bot))

    # ── Callback handler (inline keyboards) ──
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Error handler ──
    app.add_error_handler(error_handler)

    return app


def run_polling(token: str):
    """Inicia o bot em modo polling (simples, sem precisar de URL pública)."""
    logger.info('Iniciando Rage CCG Bot em modo polling...')
    app = build_application(token)
    logger.info('Bot está rodando! Pressione Ctrl+C para parar.')
    app.run_polling(drop_pending_updates=True)


def run_webhook(token: str, url: str, port: int = 8443,
                webhook_path: str = '/webhook'):
    """Inicia o bot em modo webhook (requer URL pública com HTTPS).

    Args:
        token: Token do bot.
        url: URL pública do webhook (ex: https://meusite.com).
        port: Porta para o servidor web.
        webhook_path: Caminho do webhook (padrão: /webhook).
    """
    logger.info(
        'Iniciando Rage CCG Bot em modo webhook: %s:%s%s',
        url, port, webhook_path,
    )
    app = build_application(token)
    app.run_webhook(
        listen='0.0.0.0',
        port=port,
        url_path=webhook_path,
        webhook_url=f'{url}:{port}{webhook_path}',
    )


def main():
    """Entry point CLI para o bot."""
    parser = argparse.ArgumentParser(
        description='Bot Telegram para Rage CCG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Exemplos:\n'
            '  rage-bot                              # Token da env BOT_TOKEN\n'
            '  rage-bot --token 123456:ABC-DEF       # Token explícito\n'
            '  rage-bot --webhook --url https://meusite.com\n'
        ),
    )
    parser.add_argument(
        '--token',
        default=None,
        help='Token do bot Telegram (default: env BOT_TOKEN)',
    )
    parser.add_argument(
        '--webhook',
        action='store_true',
        help='Usar modo webhook em vez de polling',
    )
    parser.add_argument(
        '--url',
        default=None,
        help='URL pública para webhook (obrigatório se --webhook)',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8443,
        help='Porta do webhook (default: 8443)',
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Log detalhado (DEBUG)',
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve o token (suporta BOT_TOKEN, TELEGRAM_KEY_TOKEN, ou --token)
    token = (args.token
             or os.environ.get('BOT_TOKEN')
             or os.environ.get('TELEGRAM_KEY_TOKEN'))
    if not token:
        parser.error(
            'Token não encontrado. Defina BOT_TOKEN ou TELEGRAM_KEY_TOKEN'
            ' no ambiente, crie um arquivo .env, ou use --token.'
        )

    if args.webhook:
        if not args.url:
            parser.error('--url é obrigatório no modo webhook.')
        run_webhook(token, args.url, args.port)
    else:
        run_polling(token)


if __name__ == '__main__':
    main()
