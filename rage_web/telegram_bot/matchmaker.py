"""Sistema de matchmaking e lobby para partidas via Telegram.

Gerencia:
  - Desafios entre jogadores (/duel)
  - Aceite/recusa de desafios (/accept, /decline)
  - Criação de partidas a partir de decks do banco
  - Filas de espera para partidas rápidas
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Optional

from rage_web.game_engine.cli import build_game_from_decks_n
from rage_web.game_engine.state import GameState


@dataclass
class Challenge:
    """Um desafio pendente entre dois jogadores."""
    challenger_id: int
    challenger_name: str
    challenged_id: int
    deck_challenger: int
    deck_challenged: int | None  # None = oponente escolhe depois
    created_at: float = field(default_factory=time.time)
    expires_at: float = 120.0  # expira em 2 minutos
    status: str = 'pending'  # pending | accepted | declined | expired


class Matchmaker:
    """Gerencia desafios e criação de partidas.

    Diferente do GameManager que mantém partidas ativas, o Matchmaker
    só lida com o estado pré-jogo (desafios pendentes).
    """

    def __init__(self):
        self._challenges: dict[int, list[Challenge]] = {}
        # _challenges[challenged_telegram_id] = [Challenge, ...]

    # ── Desafios ────────────────────────────────────────────────────

    def create_challenge(self, challenger_id: int, challenger_name: str,
                         challenged_id: int, deck_challenger: int,
                         deck_challenged: int | None = None) -> Challenge:
        """Cria um novo desafio.

        Args:
            deck_challenged: Se None, o desafiado escolhe o deck ao aceitar.
        """
        challenge = Challenge(
            challenger_id=challenger_id,
            challenger_name=challenger_name,
            challenged_id=challenged_id,
            deck_challenger=deck_challenger,
            deck_challenged=deck_challenged,
        )
        if challenged_id not in self._challenges:
            self._challenges[challenged_id] = []
        self._challenges[challenged_id].append(challenge)
        return challenge

    def get_pending_challenges(self, telegram_id: int) -> list[Challenge]:
        """Retorna desafios pendentes para um jogador."""
        challenges = self._challenges.get(telegram_id, [])
        # Filtra expirados
        now = time.time()
        active = [
            c for c in challenges
            if c.status == 'pending'
            and now - c.created_at < c.expires_at
        ]
        if len(active) != len(challenges):
            self._challenges[telegram_id] = active
        return active

    def accept_challenge(self, challenged_id: int,
                         challenger_id: int,
                         deck_challenged: int) -> Optional[Challenge]:
        """Aceita um desafio e retorna o Challenge (ou None)."""
        challenges = self._challenges.get(challenged_id, [])
        for c in challenges:
            if (c.challenger_id == challenger_id
                    and c.status == 'pending'):
                c.status = 'accepted'
                c.deck_challenged = deck_challenged
                self._cleanup_challenge(challenged_id, challenger_id)
                return c
        return None

    def decline_challenge(self, challenged_id: int,
                          challenger_id: int) -> bool:
        """Recusa um desafio."""
        return self._remove_challenge(challenged_id, challenger_id)

    def cancel_challenge(self, challenger_id: int,
                         challenged_id: int) -> bool:
        """Cancela um desafio enviado."""
        return self._remove_challenge(challenged_id, challenger_id)

    def _remove_challenge(self, challenged_id: int,
                          challenger_id: int) -> bool:
        """Remove um desafio específico."""
        challenges = self._challenges.get(challenged_id, [])
        for i, c in enumerate(challenges):
            if c.challenger_id == challenger_id:
                challenges.pop(i)
                if not challenges:
                    del self._challenges[challenged_id]
                return True
        return False

    def _cleanup_challenge(self, challenged_id: int, challenger_id: int):
        """Remove da lista após aceite/recusa."""
        self._remove_challenge(challenged_id, challenger_id)

    # ── Criação de partidas ─────────────────────────────────────────

    def create_game_from_challenge(self, challenge: Challenge,
                                   seed: Optional[int] = None) -> GameState:
        """Cria um GameState a partir de um desafio aceito.

        Usa os decks definidos no desafio para montar a partida.
        """
        if not challenge.deck_challenged:
            raise ValueError(
                'Deck do desafiado não definido. Aceite o desafio'
                ' com `/accept @user <deck_id>`.'
            )
        seed = seed or random.randint(0, 999999)
        game = build_game_from_decks_n(
            challenge.deck_challenger,
            challenge.deck_challenged,
            seed=seed,
        )
        return game

    # ── Limpeza ─────────────────────────────────────────────────────

    def clean_expired(self, max_age: float = 120.0):
        """Remove desafios expirados."""
        now = time.time()
        expired_ids = []
        for cid, challenges in self._challenges.items():
            challenges[:] = [
                c for c in challenges
                if c.status == 'pending'
                and now - c.created_at < c.expires_at
            ]
            if not challenges:
                expired_ids.append(cid)
        for cid in expired_ids:
            del self._challenges[cid]

    def has_pending_from(self, challenger_id: int,
                         challenged_id: int) -> bool:
        """Verifica se já existe um desafio pendente entre dois players."""
        challenges = self._challenges.get(challenged_id, [])
        return any(
            c.challenger_id == challenger_id and c.status == 'pending'
            for c in challenges
        )
