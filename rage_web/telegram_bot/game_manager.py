"""Gerenciador de sessões de partida.

Mantém o estado das partidas em memória e mapeia jogadores do Telegram
aos seus respectivos jogos. Reutiliza a mesma lógica da API REST
(api.py) mas sem a camada HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from rage_web.game_engine.state import GameState, PlayerState
from rage_web.telegram_bot.persistence import GamePersistence


logger = logging.getLogger(__name__)


# ── Constantes de timeout ──────────────────────────────────────────

# Tempo padrão para timeout de turno (em segundos)
DEFAULT_TURN_TIMEOUT = 7200  # 2 horas (antes era 24h)

# Número de timeouts consecutivos antes de conceder automaticamente
MAX_MISSED_TURNS = 3
PERSISTENCE_ENABLED = True


@dataclass
class PlayerSession:
    """Vínculo entre um usuário do Telegram e uma partida ativa."""
    telegram_id: int
    telegram_username: str
    player_id: str          # ID do jogador dentro do GameState (ex: 'p1')
    game_id: str            # ID da partida
    deck_id: int | None = None


@dataclass
class GameSession:
    """Sessão completa de uma partida multiplayer."""
    game: GameState
    players: dict[int, str]  # telegram_id → player_id
    turn_notifications: bool = True

    # ── Controle de timeout ──
    turn_timeout_seconds: int = DEFAULT_TURN_TIMEOUT
    turn_timeout_task: asyncio.Task | None = None
    missed_turns: int = 0           # timeouts consecutivos do jogador atual
    max_missed_turns: int = MAX_MISSED_TURNS
    last_turn_change: float = 0.0   # timestamp da última troca de turno


class GameManager:
    """Gerencia múltiplas partidas e seus jogadores.

    Armazena em memória:
      - _games: dict[game_id, GameSession]  ← partidas ativas
      - _players: dict[telegram_id, PlayerSession]  ← jogador → partida
      - _pending_challenges: dict  ← desafios pendentes

    Controle de timeout:
      - _turn_timeout_callback: função chamada quando um turno expira
      - Deve ser configurada via set_turn_timeout_callback() por quem
        cria o bot (ex: bot.py)
    """

    def __init__(self):
        self._games: dict[str, GameSession] = {}
        self._players: dict[int, PlayerSession] = {}
        self._pending_challenges: dict[int, list[dict]] = {}
        self._turn_timeout_callback: Callable | None = None
        self._persistence = GamePersistence() if PERSISTENCE_ENABLED else None
        # callback(game_id, telegram_id_do_jogador_que_tomou_timeout)

    def set_turn_timeout_callback(self, callback: Callable):
        """Define a função chamada quando um turno expira.

        A assinatura deve ser:
          async def callback(game_id: str, timed_out_tid: int, context: Any)

        Onde context é o objeto passado em schedule_turn_timer().
        """
        self._turn_timeout_callback = callback
        # pending_challenges = { challenged_telegram_id: [challenge, ...] }
        # challenge = { challenger_id, challenger_name, deck_id, game_id? }

    # ── Gerenciamento de partidas ───────────────────────────────────

    def create_game(self, game: GameState,
                    player_map: dict[int, str]) -> str:
        """Registra uma nova partida.

        Args:
            game: GameState já configurado com jogadores.
            player_map: {telegram_id: player_id} mapeando usuários do
                        Telegram aos jogadores no GameState.

        Returns:
            game_id (string UUID).
        """
        gid = game.id if game.id else str(uuid.uuid4())[:8]
        game.id = gid
        self._games[gid] = GameSession(game=game, players=player_map)

        for tid, pid in player_map.items():
            self._players[tid] = PlayerSession(
                telegram_id=tid,
                telegram_username='',
                player_id=pid,
                game_id=gid,
            )

        # Persistência automática
        self._save_game(gid)

        return gid

    def get_game(self, game_id: str) -> Optional[GameState]:
        """Retorna o GameState de uma partida."""
        session = self._games.get(game_id)
        return session.game if session else None

    def get_session(self, game_id: str) -> Optional[GameSession]:
        return self._games.get(game_id)

    def get_player_game(self, telegram_id: int) -> Optional[GameState]:
        """Retorna a partida ativa de um jogador."""
        ps = self._players.get(telegram_id)
        if not ps:
            return None
        return self.get_game(ps.game_id)

    def get_player_session(self, telegram_id: int) -> Optional[PlayerSession]:
        return self._players.get(telegram_id)

    def remove_game(self, game_id: str):
        """Remove uma partida e libera os jogadores."""
        # Cancela timer ativo
        self.cancel_turn_timer(game_id)
        session = self._games.pop(game_id, None)
        if not session:
            return

        # Remove da persistência
        if self._persistence:
            self._persistence.delete_game(game_id)

        # Remove todos os jogadores vinculados a esta partida
        to_remove = [
            tid for tid, ps in self._players.items()
            if ps.game_id == game_id
        ]
        for tid in to_remove:
            self._players.pop(tid, None)

    def remove_player(self, telegram_id: int):
        """Remove um jogador de qualquer partida ativa."""
        self._players.pop(telegram_id, None)

    def get_player_id_in_game(self, telegram_id: int) -> Optional[str]:
        """Retorna o player_id (ex: 'p1') do Telegram user numa partida."""
        ps = self._players.get(telegram_id)
        return ps.player_id if ps else None

    def get_opponent_telegram_id(self, telegram_id: int) -> Optional[int]:
        """Retorna o Telegram ID do oponente numa partida 1v1."""
        ps = self._players.get(telegram_id)
        if not ps:
            return None
        session = self._games.get(ps.game_id)
        if not session:
            return None
        for tid in session.players:
            if tid != telegram_id:
                return tid
        return None

    def get_current_player_telegram_id(self, game_id: str) -> Optional[int]:
        """Retorna o Telegram ID do jogador que deve agir agora."""
        session = self._games.get(game_id)
        if not session:
            return None
        cp = session.game.current_player
        for tid, pid in session.players.items():
            if pid == cp.id:
                return tid
        return None

    # ── Persistência ────────────────────────────────────────────────

    def _save_game(self, game_id: str):
        """Persiste o estado atual da partida (auto-save)."""
        if not self._persistence:
            return
        session = self._games.get(game_id)
        if session:
            self._persistence.save_game(game_id, session)

    def load_all_active_games(self) -> list:
        """Carrega todas as partidas salvas no banco.

        Deve ser chamado na inicialização do bot.
        Retorna lista de (game_id, GameSession) para que quem chamou
        possa reagendar timers e notificar jogadores.
        """
        if not self._persistence:
            return []
        games = self._persistence.load_all_games()
        restored = []
        for game_id, session in games:
            if game_id in self._games:
                continue  # Já está em memória
            self._games[game_id] = session
            # Reconstrói _players a partir da sessão
            for tid, pid in session.players.items():
                self._players[tid] = PlayerSession(
                    telegram_id=tid,
                    telegram_username='',
                    player_id=pid,
                    game_id=game_id,
                )
            restored.append((game_id, session))
        logger.info(f'Restauradas {len(restored)} partidas do banco')
        return restored

    # ── Timer de turno ─────────────────────────────────────────────

    def set_turn_timeout_callback(self, callback: Callable):
        """Define callback para quando um turno expira.

        Assinatura:
            async def cb(game_id: str, timed_out_tid: int)
        """
        self._turn_timeout_callback = callback

    def schedule_turn_timer(self, game_id: str,
                            timeout_seconds: int | None = None):
        """Agenda o timeout para o turno atual.

        Cancela qualquer timer anterior e cria um novo.
        O timer executa self._on_turn_timeout() após o delay.

        Args:
            game_id: ID da partida.
            timeout_seconds: Tempo em segundos (default: do GameSession).
        """
        session = self._games.get(game_id)
        if not session:
            return

        # Cancela timer anterior
        self.cancel_turn_timer(game_id)

        timeout = timeout_seconds or session.turn_timeout_seconds
        session.last_turn_change = time.time()

        async def _timer_task():
            try:
                await asyncio.sleep(timeout)
                # Timer expirou: executa callback
                if self._turn_timeout_callback:
                    cp_tid = self.get_current_player_telegram_id(game_id)
                    if cp_tid:
                        await self._turn_timeout_callback(
                            game_id, cp_tid,
                        )
            except asyncio.CancelledError:
                pass  # Timer cancelado (jogador agiu)
            except Exception as e:
                logger.error(f'Erro no timer de turno: {e}')

        session.turn_timeout_task = asyncio.create_task(_timer_task())

    def cancel_turn_timer(self, game_id: str):
        """Cancela o timer de turno ativo, se houver."""
        session = self._games.get(game_id)
        if session and session.turn_timeout_task:
            session.turn_timeout_task.cancel()
            session.turn_timeout_task = None

    def set_turn_timeout(self, game_id: str, hours: int) -> bool:
        """Define timeout do turno em horas."""
        session = self._games.get(game_id)
        if not session:
            return False
        seconds = max(60, min(hours * 3600, 172800))  # 1min ~ 48h
        session.turn_timeout_seconds = seconds
        # Reagenda com novo timeout se houver timer ativo
        self.cancel_turn_timer(game_id)
        self.schedule_turn_timer(game_id)
        return True

    def reset_missed_turns(self, game_id: str):
        """Zera o contador de timeouts consecutivos."""
        session = self._games.get(game_id)
        if session:
            session.missed_turns = 0

    def increment_missed_turns(self, game_id: str):
        """Incrementa contador de timeouts consecutivos."""
        session = self._games.get(game_id)
        if session:
            session.missed_turns += 1
        return session.missed_turns if session else 0

    def get_missed_turns(self, game_id: str) -> int:
        """Retorna quantos timeouts consecutivos o jogador atual já tomou."""
        session = self._games.get(game_id)
        return session.missed_turns if session else 0

    def get_timeout_config(self, game_id: str) -> tuple[int, int]:
        """Retorna (timeout_seconds, max_missed_turns)."""
        session = self._games.get(game_id)
        if session:
            return (session.turn_timeout_seconds, session.max_missed_turns)
        return (DEFAULT_TURN_TIMEOUT, MAX_MISSED_TURNS)

    # ── Desafios (matchmaking) ──────────────────────────────────────

    def add_challenge(self, challenger_id: int, challenger_name: str,
                      challenged_id: int, deck_id: int):
        """Registra um desafio pendente."""
        if challenged_id not in self._pending_challenges:
            self._pending_challenges[challenged_id] = []
        self._pending_challenges[challenged_id].append({
            'challenger_id': challenger_id,
            'challenger_name': challenger_name,
            'deck_id': deck_id,
            'created_at': __import__('time').time(),
        })

    def get_challenges(self, telegram_id: int) -> list[dict]:
        """Retorna desafios pendentes para um jogador."""
        return self._pending_challenges.get(telegram_id, [])

    def remove_challenge(self, challenged_id: int, challenger_id: int) -> bool:
        """Remove um desafio específico."""
        challenges = self._pending_challenges.get(challenged_id, [])
        for i, c in enumerate(challenges):
            if c['challenger_id'] == challenger_id:
                challenges.pop(i)
                if not challenges:
                    del self._pending_challenges[challenged_id]
                return True
        return False

    def clean_expired_challenges(self, max_age: float = 120.0):
        """Remove desafios expirados (default: 2 minutos)."""
        now = __import__('time').time()
        expired_ids = []
        for cid, challenges in self._pending_challenges.items():
            challenges[:] = [c for c in challenges
                             if now - c.get('created_at', 0) < max_age]
            if not challenges:
                expired_ids.append(cid)
        for cid in expired_ids:
            del self._pending_challenges[cid]

    # ── Utilitários ─────────────────────────────────────────────────

    def list_active_games(self) -> list[str]:
        """Lista IDs de partidas ativas."""
        return list(self._games.keys())

    def count_players(self) -> int:
        return len(self._players)

    def is_player_in_game(self, telegram_id: int) -> bool:
        return telegram_id in self._players
