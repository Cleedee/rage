"""Persistência de partidas em SQLite.

Salva e carrega partidas ativas usando pickle, garantindo que
partidas não sejam perdidas quando o bot reiniciar.

Arquitetura:
  - Cada partida (GameState) é serializada via pickle e armazenada
    como blob na tabela active_games.
  - GameSession (metadados como timeout, missed_turns, timestamps)
    também é preservada.
  - O campo turn_timeout_task (asyncio.Task) não é serializável —
    é salvo como None e recriado no load.
  - Na inicialização do bot, todas as partidas ativas são
    restauradas e timers são reagendados.

Uso:
    from rage_web.telegram_bot.persistence import GamePersistence
    
    p = GamePersistence()
    p.save_game(game_id, game_session)
    session = p.load_game(game_id)
    sessions = p.load_all_games()
    p.delete_game(game_id)
"""

from __future__ import annotations

import logging
import pickle
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent / 'persistence.db'


class GamePersistence:
    """Gerencia persistência de partidas em SQLite."""

    def __init__(self, db_path: str | Path = _DB_PATH):
        self._db_path = Path(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Retorna nova conexão (thread-safe)."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Cria tabelas se não existirem."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_games (
                game_id TEXT PRIMARY KEY,
                game_session BLOB NOT NULL,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_games_player1
            ON active_games(player1_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_games_player2
            ON active_games(player2_id)
        """)
        conn.commit()
        conn.close()
        logger.info(f'Persistência inicializada: {self._db_path}')

    def save_game(self, game_id: str, game_session) -> bool:
        """Salva uma partida no banco.

        Args:
            game_id: ID único da partida.
            game_session: Objeto GameSession (de game_manager).

        Returns:
            True se salvou com sucesso.
        """
        try:
            # Preserva task para restaurar depois
            task = getattr(game_session, 'turn_timeout_task', None)
            game_session.turn_timeout_task = None

            blob = pickle.dumps(game_session)

            # Restaura task
            game_session.turn_timeout_task = task

            now = time.time()
            players = getattr(game_session, 'players', {})
            p1 = next(iter(players.keys())) if players else 0
            p2 = list(players.keys())[1] if len(players) > 1 else None

            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO active_games
                (game_id, game_session, player1_id, player2_id,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, COALESCE(
                    (SELECT created_at FROM active_games WHERE game_id = ?),
                    ?
                ), ?)
            """, (game_id, blob, p1, p2, game_id, now, now))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f'Erro ao salvar partida {game_id}: {e}')
            return False

    def load_game(self, game_id: str) -> Optional[object]:
        """Carrega uma partida específica.

        Args:
            game_id: ID da partida.

        Returns:
            GameSession desserializado ou None.
        """
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT game_session FROM active_games WHERE game_id = ?",
                (game_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                session = pickle.loads(row[0])
                session.turn_timeout_task = None  # Task não sobrevive a pickle
                return session
            return None
        except Exception as e:
            logger.error(f'Erro ao carregar partida {game_id}: {e}')
            return None

    def load_all_games(self) -> list:
        """Carrega todas as partidas ativas.

        Returns:
            Lista de tuplas (game_id, GameSession).
        """
        games = []
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT game_id, game_session FROM active_games"
            )
            for row in cursor.fetchall():
                game_id, blob = row
                try:
                    session = pickle.loads(blob)
                    session.turn_timeout_task = None
                    games.append((game_id, session))
                except Exception as e:
                    logger.warning(
                        f'Partida {game_id} corrompida, ignorando: {e}'
                    )
            conn.close()
        except Exception as e:
            logger.error(f'Erro ao carregar partidas: {e}')
        return games

    def delete_game(self, game_id: str) -> bool:
        """Remove uma partida do banco."""
        try:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM active_games WHERE game_id = ?",
                (game_id,),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f'Erro ao remover partida {game_id}: {e}')
            return False

    def count_active_games(self) -> int:
        """Retorna número de partidas ativas."""
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT COUNT(*) FROM active_games")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
