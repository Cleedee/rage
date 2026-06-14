"""Sistema de internacionalização (i18n) para o Bot Telegram Rage CCG.

Suporta múltiplos idiomas via arquivos JSON em locales/.
Fallback padrão: pt_BR (português brasileiro).

Uso:
    from rage_web.telegram_bot.i18n import t, available_languages

    # No handler:
    lang = context.user_data.get('lang', 'pt_BR')
    msg = t('welcome', lang=lang, name=user_name)
    msg = t('game.not_your_turn', lang=lang)

Para registrar idioma do usuário:
    context.user_data['lang'] = 'en_US'

Para web: importar e usar a mesma função t().
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


_LOCALES_DIR = Path(__file__).parent / 'locales'
_cache: dict[str, dict[str, str]] = {}

# ── Idiomas disponíveis ────────────────────────────────────────────

LANGUAGES = {
    'pt_BR': 'Português (BR)',
    'en_US': 'English (US)',
}

DEFAULT_LANG = 'pt_BR'


def available_languages() -> list[str]:
    """Retorna lista de códigos de idioma disponíveis."""
    return list(LANGUAGES.keys())


def language_name(code: str) -> str:
    """Retorna o nome amigável do idioma."""
    return LANGUAGES.get(code, code)


def _load(lang: str) -> dict[str, str]:
    """Carrega (e cacheia) o arquivo de tradução de um idioma."""
    if lang not in _cache:
        filepath = _LOCALES_DIR / f'{lang}.json'
        if filepath.exists():
            with open(filepath, encoding='utf-8') as f:
                _cache[lang] = json.load(f)
        else:
            _cache[lang] = {}
    return _cache[lang]


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Traduz uma chave para o idioma especificado.

    Args:
        key: Chave de tradução (ex: 'welcome', 'game.play_card').
        lang: Código do idioma (ex: 'pt_BR', 'en_US').
        **kwargs: Parâmetros para formatação com str.format().

    Returns:
        String traduzida, ou a própria chave se não encontrada.
    """
    # Tenta no idioma solicitado
    data = _load(lang)
    if key in data:
        template = data[key]
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    # Fallback para pt_BR
    if lang != DEFAULT_LANG:
        data_br = _load(DEFAULT_LANG)
        if key in data_br:
            template = data_br[key]
            try:
                return template.format(**kwargs)
            except KeyError:
                return template

    # Último fallback: retorna a própria chave
    return key


def tt(key: str, context_user_data: dict, **kwargs) -> str:
    """Atalho que pega o idioma do context.user_data.

    Args:
        key: Chave de tradução.
        context_user_data: context.user_data do handler.
        **kwargs: Parâmetros de formatação.

    Uso:
        msg = tt('welcome', context.user_data, name=name)
    """
    lang = context_user_data.get('lang', DEFAULT_LANG)
    return t(key, lang=lang, **kwargs)


# ── Comando /lang ──────────────────────────────────────────────────

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /lang — escolher idioma."""
    keyboard = []
    for code, name in LANGUAGES.items():
        selected = '✅ ' if context.user_data.get('lang') == code else ''
        keyboard.append([
            InlineKeyboardButton(
                f'{selected}{name}',
                callback_data=f'lang:{code}',
            )
        ])

    await update.message.reply_text(
        t('lang.choose', context.user_data.get('lang', DEFAULT_LANG)),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
