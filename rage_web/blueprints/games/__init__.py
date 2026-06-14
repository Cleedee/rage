"""Blueprint da página 'Meus Jogos' — lista partidas ativas do jogador."""

from __future__ import annotations

from flask import (
    Blueprint, redirect, render_template, request, session, url_for,
)

bp = Blueprint('games', __name__, template_folder='templates',
               url_prefix='/games')


def _login_required():
    """Verifica se usuário está logado."""
    if not session.get('logged_in'):
        return False
    return True


def _get_bot_games_for_player(telegram_id: int) -> list:
    """Retorna partidas ativas de um jogador no bot Telegram."""
    try:
        from rage_web.telegram_bot.handlers import game_manager
        ps = game_manager.get_player_session(telegram_id)
        if ps:
            game = game_manager.get_game(ps.game_id)
            if game:
                return [game]
    except Exception:
        pass
    return []


@bp.route('/')
def my_games():
    """Lista partidas ativas do jogador."""
    if not _login_required():
        return redirect(url_for('auth.login', next=url_for('games.my_games')))

    telegram_id = session.get('telegram_id')
    games = _get_bot_games_for_player(telegram_id)

    from rage_web.game_engine.state import GameState
    web_games = []
    # Também busca no blueprint game local
    from rage_web.blueprints.game import _games as local_games
    for gid, g in local_games.items():
        if g.players:
            for p in g.players:
                if str(telegram_id) in p.id or \
                   (hasattr(p, 'telegram_id') and p.telegram_id == telegram_id):
                    web_games.append((gid, g))
                    break

    return render_template(
        'games/list.html',
        bot_games=games,
        web_games=web_games,
        telegram_id=telegram_id,
    )
