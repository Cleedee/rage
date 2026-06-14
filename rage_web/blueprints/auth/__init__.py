"""Blueprint de autenticação via Telegram Login Widget.

Permite que jogadores façam login no site usando sua conta Telegram.
Após autenticado, o usuário pode ver suas partidas ativas no navegador.

Uso:
    1. Adicionar o widget Telegram à página de login
    2. Callback /auth/telegram verifica a assinatura HMAC-SHA256
    3. Dados do usuário armazenados na sessão Flask
"""

from __future__ import annotations

import hashlib
import hmac
import os

from flask import (
    Blueprint, redirect, render_template, request, session, url_for,
    current_app,
)

bp = Blueprint('auth', __name__, template_folder='templates',
               url_prefix='/auth')


def _get_bot_token() -> str:
    """Retorna o token do bot Telegram."""
    return os.environ.get('TELEGRAM_KEY_TOKEN', '')


def _verify_telegram_login(data: dict) -> bool:
    """Verifica a autenticidade dos dados do Telegram Login Widget.

    O widget envia: id, first_name, last_name, username, photo_url,
    auth_date, hash.

    A verificação segue: https://core.telegram.org/widgets/login
    """
    bot_token = _get_bot_token()
    if not bot_token:
        current_app.logger.error('TELEGRAM_KEY_TOKEN não configurado')
        return False

    received_hash = data.pop('hash', '')
    if not received_hash:
        return False

    # Ordena campos, cria string de verificação
    check_list = [f'{k}={v}' for k, v in sorted(data.items())]
    check_string = '\n'.join(check_list)

    # HMAC-SHA256 com o token do bot
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(
        secret_key, check_string.encode(), hashlib.sha256,
    ).hexdigest()

    return computed_hash == received_hash


@bp.route('/login')
def login():
    """Página de login com Telegram Login Widget."""
    bot_username = os.environ.get('BOT_USERNAME', 'furia_ccg_bot')
    return render_template(
        'auth/login.html',
        bot_username=bot_username,
    )


@bp.route('/telegram', methods=['GET'])
def telegram_callback():
    """Callback do Telegram Login Widget.

    Recebe os dados via GET (query string) após o usuário autorizar.
    """
    data = dict(request.args)

    if not _verify_telegram_login(data):
        return render_template(
            'auth/login.html',
            error='Falha na verificação. Tente novamente.',
        )

    # Dados verificados — salva na sessão
    user_id = int(data.get('id', 0))
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    username = data.get('username', '')
    photo_url = data.get('photo_url', '')

    session['telegram_id'] = user_id
    session['telegram_username'] = username
    session['telegram_full_name'] = f'{first_name} {last_name}'.strip()
    session['telegram_photo_url'] = photo_url
    session['logged_in'] = True

    current_app.logger.info(
        f'Login via Telegram: {username} ({user_id})'
    )

    # Redireciona para meus jogos ou para onde estava
    next_page = request.args.get('next') or url_for('games.my_games')
    return redirect(next_page)


@bp.route('/logout')
def logout():
    """Desconecta o usuário."""
    session.clear()
    return redirect(url_for('auth.login'))


def inject_telegram_user():
    """Injeta dados do usuário Telegram nos templates.

    Usado como context_processor.
    """
    return {
        'telegram_user': {
            'id': session.get('telegram_id'),
            'username': session.get('telegram_username'),
            'full_name': session.get('telegram_full_name'),
            'photo_url': session.get('telegram_photo_url'),
            'logged_in': session.get('logged_in', False),
        } if session.get('logged_in') else None,
    }
