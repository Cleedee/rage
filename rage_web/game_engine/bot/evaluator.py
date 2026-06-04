"""Sistema de avaliacao de estado para o bot.

Atribui notas 0-10 para cada fator: ameaca, vantagem, pressao, vitoria.
"""

from __future__ import annotations

from rage_web.game_engine.state import GameState, PlayerState, CardInstance


class BoardEvaluator:
    """Avalia o tabuleiro e retorna notas para cada fator."""

    # Pesos para calculo da nota composta
    WEIGHTS = {
        'threat': 0.35,
        'advantage': 0.25,
        'pressure': 0.25,
        'victory': 0.15,
    }

    def __init__(self, game: GameState, player_id: str):
        self.game = game
        self.player = self._find_player(player_id)
        self.opponent = self._find_opponent(player_id)

    def _find_player(self, player_id: str) -> PlayerState:
        for p in self.game.players:
            if p.id == player_id:
                return p
        raise ValueError(f'Jogador {player_id} nao encontrado')

    def _find_opponent(self, player_id: str) -> PlayerState:
        for p in self.game.players:
            if p.id != player_id:
                return p
        raise ValueError('Nenhum oponente encontrado')

    # ------------------------------------------------------------------
    # Fatores individuais (0-10)
    # ------------------------------------------------------------------

    def threat_score(self) -> float:
        """Ameaca do oponente (0 = nenhuma, 10 = letal).

        Baseado no Rage total, quantidade de criaturas e
        equipamentos do oponente.
        """
        opp = self.opponent
        if not opp.pack_home:
            return 0.0

        total_rage = sum(c.rage for c in opp.pack_home)
        num_creatures = len(opp.pack_home)
        total_health = sum(c.health_current for c in opp.pack_home)

        # Quanto maior o rage, maior a ameaca
        rage_score = min(total_rage / 3.0, 5.0)

        # Quantidade de criaturas
        count_score = min(num_creatures * 2.0, 3.0)

        # Saude total (mais saude = mais ameaca)
        health_score = min(total_health / 6.0, 2.0)

        return min(rage_score + count_score + health_score, 10.0)

    def advantage_score(self) -> float:
        """Vantagem de mesa (-10 a +10, normalizado para 0-10).

        Positivo = meu lado esta melhor.
        Negativo = oponente esta melhor.
        """
        me = self.player
        opp = self.opponent

        my_creatures = len(me.pack_home)
        opp_creatures = len(opp.pack_home)
        my_health = sum(c.health_current for c in me.pack_home)
        opp_health = sum(c.health_current for c in opp.pack_home)
        my_hand = len(me.hand)
        opp_hand = len(opp.hand)

        # Diferenca de criaturas
        creature_diff = (my_creatures - opp_creatures) * 1.5
        # Diferenca de vida
        health_diff = (my_health - opp_health) * 0.3
        # Diferenca de mao
        hand_diff = (my_hand - opp_hand) * 0.5

        total = creature_diff + health_diff + hand_diff
        # Normaliza para 0-10 (5 = neutro)
        normalized = max(0, min(10, total + 5))
        return normalized

    def pressure_score(self) -> float:
        """Pressao de vida dos meus personagens (0-10).

        0 = todos saudaveis, 10 = todos prestes a morrer.
        """
        me = self.player
        if not me.pack_home:
            return 10.0  # Sem criaturas = pressao maxima

        total_pressure = 0.0
        for c in me.pack_home:
            if c.health > 0:
                # Proporcao de vida perdida
                ratio = 1.0 - (c.health_current / c.health)
                total_pressure += ratio * 10.0

        return min(total_pressure / len(me.pack_home), 10.0)

    def victory_score(self) -> float:
        """Proximidade da vitoria (0-10).

        0 = longe, 10 = falta 1 VP.
        """
        me = self.player
        if me.renown_level <= 0:
            return 0.0

        progress = me.victory_points / me.renown_level
        return min(progress * 10.0, 10.0)

    # ------------------------------------------------------------------
    # Nota composta
    # ------------------------------------------------------------------

    def composite_score(self) -> float:
        """Nota composta 0-10 considerando todos os fatores.

        Usada pelo bot para decidir se deve atacar ou se defender.
        """
        threat = self.threat_score()
        advantage = self.advantage_score()
        pressure = self.pressure_score()
        victory = self.victory_score()

        # Inverte pressure: menos pressao = melhor
        safety = 10.0 - pressure

        score = (
            self.WEIGHTS['threat'] * threat
            + self.WEIGHTS['advantage'] * advantage
            + self.WEIGHTS['pressure'] * safety
            + self.WEIGHTS['victory'] * victory
        )
        return score

    def summary(self) -> dict:
        """Retorna resumo da avaliacao."""
        return {
            'threat': round(self.threat_score(), 1),
            'advantage': round(self.advantage_score(), 1),
            'pressure': round(self.pressure_score(), 1),
            'victory': round(self.victory_score(), 1),
            'composite': round(self.composite_score(), 2),
        }
