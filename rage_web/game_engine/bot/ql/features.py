"""Encodificação do estado do jogo em vetor de features.

Cada feature é normalizada para o intervalo ~[0, 1] para que o
Q-Learning linear (Q(s,a) = θ[a] · φ(s)) tenha escala uniforme.
"""

from __future__ import annotations

import numpy as np

from rage_web.game_engine.bot.evaluator import BoardEvaluator
from rage_web.game_engine.state import GameState, Zone

PHASES = ('redraw', 'regeneration', 'resource', 'umbra', 'moot', 'combat')
COMBAT_STEPS = ('select_alpha', 'alpha_action', 'declaration', 'pre_combat',
                'beginning_of_combat', 'play_card', 'targeting', 'reveal',
                'feint', 'bluff', 'resolution', 'withdrawal',
                'between_rounds', 'end')


def _find_player(game: GameState, player_id: str):
    for p in game.players:
        if p.id == player_id:
            return p
    raise ValueError(f'Jogador {player_id} nao encontrado')


def _n_chars(player) -> int:
    return sum(1 for c in player.pack_home
               if 'character' in (c.card_type or '').lower())


def _min_health_ratio(player) -> float:
    chars = [c for c in player.pack_home
             if 'character' in (c.card_type or '').lower()]
    if not chars:
        return 0.0
    return min(1.0, max(0.0, min(c.health_current / max(c.health, 1)
                                 for c in chars)))


def encode_state(game: GameState, player_id: str) -> np.ndarray:
    """Gera o vetor de features para o jogador dado."""
    p = _find_player(game, player_id)
    opp = next((o for o in game.players if o.id != player_id), None)
    oppc = opp.pack_home if opp else []

    feats: list[float] = []

    # Turno e fase
    feats.append(min(game.turn_number / 30.0, 1.0))
    for ph in PHASES:
        feats.append(1.0 if game.phase == ph else 0.0)

    # Mão e decks
    feats.append(len(p.hand) / 10.0)
    feats.append(len(p.combat_hand) / 5.0)
    feats.append(len(p.deck_combat) / 30.0)
    feats.append(len(p.deck_sept) / 40.0)

    # Pack próprio
    feats.append(len(p.pack_home) / 10.0)
    feats.append(_n_chars(p) / 6.0)
    feats.append(sum(c.health_current for c in p.pack_home) / 30.0)
    feats.append(sum(c.rage for c in p.pack_home) / 30.0)
    feats.append(sum(c.gnosis for c in p.pack_home) / 30.0)
    feats.append(_min_health_ratio(p))

    # Pack inimigo
    if opp:
        feats.append(len(opp.pack_home) / 10.0)
        feats.append(_n_chars(opp) / 6.0)
        feats.append(sum(c.health_current for c in oppc) / 30.0)
        feats.append(sum(c.rage for c in oppc) / 30.0)
        feats.append(sum(c.gnosis for c in oppc) / 30.0)
        feats.append(len(opp.hand) / 10.0)
    else:
        feats += [0.0] * 6

    # Vitória
    feats.append(
        (p.victory_points - (opp.victory_points if opp else 0))
        / max(p.renown_level, 1)
    )
    feats.append(min(p.victory_points / max(p.renown_level, 1), 1.0))

    # Pools de Rage/Gnosis
    feats.append(min(p.rage_pool / 20.0, 1.0))
    feats.append(min(p.gnosis_pool / 20.0, 1.0))

    # Hunting Grounds
    feats.append(len(p.hunting_grounds) / 10.0)
    feats.append(len(opp.hunting_grounds) / 10.0 if opp else 0.0)
    feats.append(len(game.hunting_grounds_cards) / 10.0)

    # Umbra
    feats.append(len(p.umbra) / 5.0)
    feats.append(len(opp.umbra) / 5.0 if opp else 0.0)

    # Combate
    combat = game.combat
    feats.append(1.0 if combat.is_active else 0.0)
    feats.append(len(combat.attackers) / 10.0)
    feats.append(len(combat.defenders) / 10.0)
    step = getattr(combat, 'step', '')
    if combat.is_active and step in COMBAT_STEPS:
        feats.append(COMBAT_STEPS.index(step) / (len(COMBAT_STEPS) - 1))
    else:
        feats.append(0.0)
    feats.append(1.0 if combat.alphas.get(player_id) else 0.0)

    # Estado do jogador
    feats.append(1.0 if p.has_passed else 0.0)
    feats.append(1.0 if getattr(p, 'eliminado', False) else 0.0)
    feats.append(min(getattr(p, 'hand_size_sept', 5) / 10.0, 1.0))

    # Avaliação heurística do tabuleiro (BoardEvaluator)
    try:
        ev = BoardEvaluator(game, player_id)
        feats.append(ev.threat_score() / 10.0)
        feats.append(ev.advantage_score() / 10.0)
        feats.append(ev.pressure_score() / 10.0)
        feats.append(ev.victory_score() / 10.0)
        feats.append(ev.composite_score() / 10.0)
    except Exception:
        feats += [0.0] * 5

    # Bias (permite deslocamento constante no Q)
    feats.append(1.0)

    return np.asarray(feats, dtype=np.float64)


def n_features() -> int:
    """Número de features do vetor gerado por encode_state."""
    # Sample game mínimo para medir o tamanho (sem depender de banco)
    from rage_web.game_engine.cli import create_sample_game
    g = create_sample_game(seed=0)
    return int(encode_state(g, g.players[0].id).shape[0])
