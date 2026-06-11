"""Modelos para o sistema de torneios.

Suporta formatos: Suíço, Single Elimination, Double Elimination.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rage_web.ext.database import db


class Tournament(db.Model):
    """Um torneio com players, partidas e classificação."""
    __tablename__ = 'tournament'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    formato: Mapped[str] = mapped_column(String(20), default='swiss')
    status: Mapped[str] = mapped_column(String(20), default='open')
    max_rounds: Mapped[int] = mapped_column(Integer, default=0)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    vp_to_win: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc))
    description: Mapped[str] = mapped_column(Text, default='')

    # Configuração do formato grupos + mata-mata
    num_groups: Mapped[int] = mapped_column(Integer, default=0)
    advance_per_group: Mapped[int] = mapped_column(Integer, default=0)
    group_stage_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    bracket_json: Mapped[str] = mapped_column(Text, default='')

    players: Mapped[List['TournamentPlayer']] = relationship(
        back_populates='tournament', cascade='all, delete-orphan')
    matches: Mapped[List['TournamentMatch']] = relationship(
        back_populates='tournament', cascade='all, delete-orphan')


class TournamentPlayer(db.Model):
    """Um jogador (humano ou bot) inscrito num torneio."""
    __tablename__ = 'tournament_player'

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey('tournament.id'), nullable=False)
    player_name: Mapped[str] = mapped_column(String(100))
    deck_id: Mapped[int] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default='hard')
    is_bot: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    sos: Mapped[float] = mapped_column(Float, default=0.0)  # Sum of Opponents' Scores
    ext_sos: Mapped[float] = mapped_column(Float, default=0.0)  # Extended SOS
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    eliminated_round: Mapped[int] = mapped_column(Integer, default=0)

    # Grupo (para formato grupos + mata-mata)
    group: Mapped[int] = mapped_column(Integer, default=0)

    tournament: Mapped['Tournament'] = relationship(back_populates='players')

    @property
    def wins(self) -> int:
        return sum(1 for m in self._matches_as_p1 if m.winner_id == self.id) + \
               sum(1 for m in self._matches_as_p2 if m.winner_id == self.id)

    @property
    def losses(self) -> int:
        return sum(1 for m in self._matches_as_p1
                   if m.winner_id and m.winner_id != self.id) + \
               sum(1 for m in self._matches_as_p2
                   if m.winner_id and m.winner_id != self.id)

    @property
    def draws(self) -> int:
        return sum(1 for m in self._matches_as_p1 if m.is_draw) + \
               sum(1 for m in self._matches_as_p2 if m.is_draw)

    @property
    def _matches_as_p1(self):
        return [m for m in self.tournament.matches
                if m.player1_id == self.id]

    @property
    def _matches_as_p2(self):
        return [m for m in self.tournament.matches
                if m.player2_id == self.id]


class TournamentMatch(db.Model):
    """Uma partida dentro de um torneio."""
    __tablename__ = 'tournament_match'

    id: Mapped[int] = mapped_column(primary_key=True)
    tournament_id: Mapped[int] = mapped_column(
        ForeignKey('tournament.id'), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    player1_id: Mapped[int] = mapped_column(
        ForeignKey('tournament_player.id'), nullable=True)
    player2_id: Mapped[int] = mapped_column(
        ForeignKey('tournament_player.id'), nullable=True)
    score_p1: Mapped[float] = mapped_column(Float, default=0.0)
    score_p2: Mapped[float] = mapped_column(Float, default=0.0)
    winner_id: Mapped[int] = mapped_column(Integer, nullable=True)
    is_draw: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    seed: Mapped[int] = mapped_column(Integer, default=0)
    game_log: Mapped[str] = mapped_column(Text, default='')

    tournament: Mapped['Tournament'] = relationship(back_populates='matches')
