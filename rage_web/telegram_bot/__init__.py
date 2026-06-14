"""Bot do Telegram para jogar Rage CCG.

Pacote que integra o motor de jogo existente com a plataforma Telegram,
permitindo partidas multiplayer assíncronas, matchmaking e gerenciamento
de decks.

Uso:
    rage-bot                          # Inicia o bot em modo polling
    rage-bot --token TOKEN            # Com token personalizado
    rage-bot --webhook --url URL      # Modo webhook

Estrutura:
    bot.py          — Ponto de entrada, configuração da aplicação Telegram
    handlers.py     — Handlers de comandos e callbacks
    game_manager.py — Gerenciamento de sessões de partida
    matchmaker.py   — Matchmaking (desafios, aceite)
    render.py       — Formatação do estado do jogo para exibição
"""

from __future__ import annotations

from rage_web.telegram_bot.bot import build_application, run_polling, run_webhook
from rage_web.telegram_bot.game_manager import GameManager, GameSession, PlayerSession
from rage_web.telegram_bot.matchmaker import Matchmaker, Challenge
from rage_web.telegram_bot.render import (
    render_board,
    render_hand,
    render_game_status,
    render_legal_actions,
    render_combat_summary,
    render_victory,
    render_card_detail,
    render_deck_list,
    render_player_decks_html,
)

__all__ = [
    'build_application',
    'run_polling',
    'run_webhook',
    'GameManager',
    'GameSession',
    'PlayerSession',
    'Matchmaker',
    'Challenge',
    'render_board',
    'render_hand',
    'render_game_status',
    'render_legal_actions',
    'render_combat_summary',
    'render_victory',
    'render_card_detail',
    'render_deck_list',
    'render_player_decks_html',
]
