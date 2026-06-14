"""Registro de usuários do Telegram para resolução @username → user_id.

Armazena em um banco SQLite local (user_registry.db) o mapeamento
entre @username e Telegram user_id, permitindo que o matchmaking
funcione sem depender de lookup externo.

Uso:
    from rage_web.telegram_bot.user_registry import (
        register_user, resolve_username, init_db
    )

    # Ao receber qualquer comando:
    register_user(user_id, username, full_name)

    # Ao processar /duel @joao:
    user_id = resolve_username('joao')  # Retorna o int user_id ou None
    if user_id is None:
        user_id = await resolve_via_api(context, '@joao')
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes


_DB_PATH = Path(__file__).parent / 'user_registry.db'


# ── Inicialização ──────────────────────────────────────────────────

def init_db():
    """Cria a tabela de usuários se não existir."""
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            first_seen REAL,
            last_seen REAL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
    )
    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    """Retorna conexão com o banco."""
    return sqlite3.connect(str(_DB_PATH))


# ── CRUD ───────────────────────────────────────────────────────────

def register_user(user_id: int, username: str | None,
                  full_name: str | None):
    """Registra ou atualiza um usuário no banco.

    O username é armazenado em lowercase para permitir
    busca case-insensitive.
    """
    now = time.time()
    username_lower = username.lower() if username else None
    conn = get_connection()
    conn.execute("""
        INSERT INTO users (user_id, username, full_name, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name,
            last_seen = excluded.last_seen
    """, (user_id, username_lower, full_name, now, now))
    conn.commit()
    conn.close()

    # 🔴 Fix: também atualiza entradas antigas que tenham
    # username com maiúsculas, normalizando para lowercase
    if username_lower and username != username_lower:
        conn2 = get_connection()
        conn2.execute(
            "UPDATE users SET username = ? WHERE username = ?",
            (username_lower, username),
        )
        conn2.commit()
        conn2.close()


def resolve_username(username: str) -> Optional[int]:
    """Resolve @username para Telegram user_id.

    Busca case-insensitive: armazenamos em lowercase,
    e o LIKE sem CASE também funciona como fallback.

    Args:
        username: Nome de usuário sem @.

    Returns:
        user_id (int) ou None se não encontrado.
    """
    username = username.lower().strip().lstrip('@')
    conn = get_connection()
    cursor = conn.execute(
        "SELECT user_id FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()

    # 🔴 Fallback: se não achou com =, tenta LIKE (case-insensitive)
    # Útil para dados armazenados antes da normalização.
    if not row:
        cursor = conn.execute(
            "SELECT user_id FROM users WHERE username LIKE ?",
            (username,),
        )
        row = cursor.fetchone()

    conn.close()
    return row[0] if row else None


def get_username(user_id: int) -> Optional[str]:
    """Retorna o @username de um user_id (lowercase)."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT username FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def count_users() -> int:
    """Retorna total de usuários registrados."""
    conn = get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


# ── Resolução via API do Telegram (fallback) ───────────────────────

async def resolve_username_via_api(
    username: str,
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[int]:
    """Tenta resolver @username via API do Telegram (getChat).

    Esse método funciona mesmo para usuários que nunca interagiram
    com o bot, contanto que o username exista.

    Args:
        username: Nome de usuário (com ou sem @).
        context: Context do handler.

    Returns:
        user_id (int) ou None se não encontrado.
    """
    username = username.strip().lstrip('@')
    try:
        chat = await context.bot.get_chat(f'@{username}')
        if chat:
            # Registra para consultas futuras
            # register_user já normaliza para lowercase
            register_user(chat.id, username, chat.full_name or username)
            return chat.id
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(
            f'resolve_username_via_api falhou para @{username}: {e}'
        )
    return None


# ── Decorator / middleware para registrar usuários automaticamente ──

def auto_register(func):
    """Decorator que registra o usuário antes de executar o handler.

    Uso:
        @auto_register
        async def my_handler(update, context):
            ...
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user:
            register_user(
                user.id,
                user.username,
                user.full_name,
            )
        return await func(update, context)
    return wrapper


# ── Inicialização na importação ────────────────────────────────────

init_db()
