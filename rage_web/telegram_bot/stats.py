"""Estatísticas de partidas e ranking de jogadores.

Armazena histórico de partidas em SQLite e provê consultas
de winrate, ranking ELO simples e estatísticas por deck.

Tabelas:
  - match_history: cada partida finalizada
  - player_ratings: rating ELO por jogador

Uso:
    from rage_web.telegram_bot.stats import StatsManager

    stats = StatsManager()
    stats.record_match(winner_id, loser_id, winner_deck, loser_deck,
                       turns, method='concede')
    s = stats.get_player_stats(telegram_id)
    rank = stats.get_rankings(top=10)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / 'stats.db'

# ELO constants
ELO_K = 32
ELO_DEFAULT = 1200


class StatsManager:
    """Gerencia estatísticas de jogadores e partidas."""

    def __init__(self, db_path: str | Path = _DB_PATH):
        self._db_path = Path(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                winner_id INTEGER NOT NULL,
                loser_id INTEGER NOT NULL,
                winner_deck_id INTEGER,
                loser_deck_id INTEGER,
                winner_deck_name TEXT,
                loser_deck_name TEXT,
                turns INTEGER DEFAULT 0,
                method TEXT DEFAULT 'concede',
                played_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mh_winner
            ON match_history(winner_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mh_loser
            ON match_history(loser_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_ratings (
                telegram_id INTEGER PRIMARY KEY,
                rating INTEGER DEFAULT 1200,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_game_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pr_rating
            ON player_ratings(rating DESC)
        """)
        conn.commit()
        conn.close()
        logger.info(f'Stats inicializado: {self._db_path}')

    # ── Registrar partida ───────────────────────────────────────────

    def record_match(
        self,
        winner_id: int,
        loser_id: int,
        winner_deck_id: int | None = None,
        loser_deck_id: int | None = None,
        winner_deck_name: str = '',
        loser_deck_name: str = '',
        turns: int = 0,
        method: str = 'concede',
    ):
        """Registra o resultado de uma partida e atualiza ratings.

        Args:
            winner_id: Telegram ID do vencedor.
            loser_id: Telegram ID do perdedor.
            winner_deck_id: ID do deck usado pelo vencedor.
            loser_deck_id: ID do deck usado pelo perdedor.
            winner_deck_name: Nome do deck do vencedor.
            loser_deck_name: Nome do deck do perdedor.
            turns: Número de turnos da partida.
            method: Como terminou (concede, timeout, victory, etc).
        """
        now = time.time()
        conn = self._get_conn()

        # Insere histórico
        conn.execute("""
            INSERT INTO match_history
            (winner_id, loser_id, winner_deck_id, loser_deck_id,
             winner_deck_name, loser_deck_name, turns, method, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (winner_id, loser_id, winner_deck_id, loser_deck_id,
              winner_deck_name, loser_deck_name, turns, method, now))

        # Atualiza ratings ELO
        self._update_elo(conn, winner_id, loser_id)

        conn.commit()
        conn.close()

    def _update_elo(self, conn: sqlite3.Connection,
                    winner_id: int, loser_id: int):
        """Atualiza ratings ELO dos dois jogadores."""
        # Garante que ambos existem na tabela
        for tid in (winner_id, loser_id):
            conn.execute("""
                INSERT OR IGNORE INTO player_ratings (telegram_id)
                VALUES (?)
            """, (tid,))

        # Lê ratings atuais
        cursor = conn.execute(
            "SELECT telegram_id, rating FROM player_ratings "
            "WHERE telegram_id IN (?, ?)",
            (winner_id, loser_id),
        )
        ratings = {row['telegram_id']: row['rating']
                   for row in cursor.fetchall()}

        r_winner = ratings.get(winner_id, ELO_DEFAULT)
        r_loser = ratings.get(loser_id, ELO_DEFAULT)

        # Probabilidade esperada
        e_winner = 1 / (1 + 10 ** ((r_loser - r_winner) / 400))
        e_loser = 1 - e_winner

        # Novo rating
        new_winner = round(r_winner + ELO_K * (1 - e_winner))
        new_loser = round(r_loser + ELO_K * (0 - e_loser))

        # Atualiza
        now = time.time()
        conn.execute("""
            UPDATE player_ratings SET
                rating = ?, games_played = games_played + 1,
                wins = wins + 1, last_game_at = ?
            WHERE telegram_id = ?
        """, (new_winner, now, winner_id))
        conn.execute("""
            UPDATE player_ratings SET
                rating = ?, games_played = games_played + 1,
                losses = losses + 1, last_game_at = ?
            WHERE telegram_id = ?
        """, (new_loser, now, loser_id))

    # ── Consultas ───────────────────────────────────────────────────

    def get_player_stats(self, telegram_id: int) -> Optional[dict]:
        """Retorna estatísticas de um jogador."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT * FROM player_ratings
            WHERE telegram_id = ?
        """, (telegram_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        stats = dict(row)

        # Últimas 5 partidas
        cursor = conn.execute("""
            SELECT * FROM match_history
            WHERE winner_id = ? OR loser_id = ?
            ORDER BY played_at DESC LIMIT 5
        """, (telegram_id, telegram_id))
        stats['recent_matches'] = [dict(r) for r in cursor.fetchall()]

        # Deck mais usado
        cursor = conn.execute("""
            SELECT winner_deck_name as deck, COUNT(*) as cnt
            FROM match_history
            WHERE winner_id = ? AND winner_deck_name != ''
            GROUP BY winner_deck_name
            ORDER BY cnt DESC LIMIT 1
        """, (telegram_id,))
        fav = cursor.fetchone()
        stats['favorite_deck'] = fav['deck'] if fav else None

        cursor = conn.execute("""
            SELECT loser_deck_name as deck, COUNT(*) as cnt
            FROM match_history
            WHERE loser_id = ? AND loser_deck_name != ''
            GROUP BY loser_deck_name
            ORDER BY cnt DESC LIMIT 1
        """, (telegram_id,))
        fav_l = cursor.fetchone()

        conn.close()
        return stats

    def get_rankings(self, top: int = 10) -> list[dict]:
        """Retorna ranking global (ordenado por rating)."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT * FROM player_ratings
            ORDER BY rating DESC
            LIMIT ?
        """, (top,))
        rankings = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rankings

    def get_deck_stats(self, deck_id: int) -> dict:
        """Retorna winrate de um deck específico."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN winner_deck_id = ? THEN 1 ELSE 0 END) as wins
            FROM match_history
            WHERE winner_deck_id = ? OR loser_deck_id = ?
        """, (deck_id, deck_id, deck_id))
        row = cursor.fetchone()
        conn.close()
        if row and row['total']:
            return {
                'total': row['total'],
                'wins': row['wins'],
                'losses': row['total'] - row['wins'],
                'winrate': round(row['wins'] / row['total'] * 100, 1),
            }
        return {'total': 0, 'wins': 0, 'losses': 0, 'winrate': 0.0}

    def get_total_games(self) -> int:
        """Retorna total de partidas registradas."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM match_history")
        count = cursor.fetchone()[0]
        conn.close()
        return count
