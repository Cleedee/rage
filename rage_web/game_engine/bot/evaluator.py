"""Sistema de avaliacao de estado para o bot.

Atribui notas 0-10 para cada fator: ameaca, vantagem, pressao, vitoria.
"""

from __future__ import annotations

from rage_web.game_engine.state import GameState, PlayerState, CardInstance, Zone
from typing import Optional


class TargetPrioritizer:
    """Avalia e prioriza alvos para o bot.

    Usa multiplos fatores para pontuar criaturas inimigas
    e escolher o melhor atacante para cada alvo.
    """

    # Pesos para calculo de ameaca
    PESOS_THREAT = {
        'rage': 0.30,
        'saude': 0.20,
        'pode_agir': 0.15,
        'renown': 0.10,
        'vp_proximidade': 0.25,
    }

    def __init__(self, game: GameState, player_id: str):
        self.game = game
        self.player_id = player_id

    def _find_owner(self, card: CardInstance) -> Optional[PlayerState]:
        for p in self.game.players:
            if p.id == card.owner_id:
                return p
        return None

    def rate_threat(self, card: CardInstance) -> float:
        """Nota 0-10: o quanto esta criatura e uma ameaca.

        Em jogos com N jogadores, criaturas de oponentes
        com mais VP recebem peso extra (alianca implicita
        contra o lider).
        """
        dono = self._find_owner(card)
        if not dono:
            return 0.0

        score = 0.0
        rage_norm = min(card.rage / 10.0, 1.0) * 10.0 * self.PESOS_THREAT['rage']
        score += rage_norm

        saude = (card.health_current / max(card.health, 1))
        score += saude * 10.0 * self.PESOS_THREAT['saude']


        renown_norm = min(card.renown / 6.0, 1.0) * 10.0 * self.PESOS_THREAT['renown']
        score += renown_norm

        vp_progress = dono.victory_points / max(dono.renown_level, 1)
        score += vp_progress * 10.0 * self.PESOS_THREAT['vp_proximidade']

        # Bonus N-player: se o dono esta perto de vencer,
        # a criatura e ainda mais ameacadora
        if vp_progress > 0.5:
            bonus = (vp_progress - 0.5) * 5.0  # 0 a 2.5 extra
            score += bonus

        return min(score, 10.0)

    def best_threat(self, criaturas: list[CardInstance]) -> Optional[CardInstance]:
        """Retorna a criatura mais ameacadora da lista."""
        if not criaturas:
            return None
        return max(criaturas, key=self.rate_threat)

    def best_attacker_for(self, alvo: CardInstance,
                          disponiveis: list[CardInstance]) -> Optional[CardInstance]:
        """Escolhe o melhor atacante para eliminar um alvo.

        Prefere a criatura com Rage mais proxima do alvo
        (evita overkill), mas capaz de vencer o confronto.
        """
        rage_necessario = alvo.rage
        candidatos = [c for c in disponiveis
                      if c.rage >= rage_necessario * 0.7]
        if not candidatos:
            return None
        return min(candidatos, key=lambda c: abs(c.rage - rage_necessario))

    def pode_eliminar(self, atacante: CardInstance,
                      alvo: CardInstance) -> bool:
        """Verifica se atacante tem chance real contra o alvo."""
        if atacante.rage <= 0:
            return False
        # Atacante precisa ter pelo menos 70% do Rage do alvo
        return atacante.rage >= alvo.rage * 0.7


class BoardEvaluator:
    """Avalia o tabuleiro e retorna notas para cada fator.

    Suporta N jogadores: 'ameaca' e 'vantagem' sao calculados
    contra todos os oponentes, com peso extra no lider em VP.
    """

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

    def _find_player(self, player_id: str) -> PlayerState:
        for p in self.game.players:
            if p.id == player_id:
                return p
        raise ValueError(f'Jogador {player_id} nao encontrado')

    def _get_opponents(self) -> list[PlayerState]:
        """Retorna todos os oponentes."""
        return [p for p in self.game.players if p.id != self.player.id]

    def _vp_weight(self, opp: PlayerState) -> float:
        """Peso extra de ameaca baseado na proximidade da vitoria.

        Retorna 1.0 (neutro) a ~1.75 (quase vencendo).
        Todos os bots tendem a focar no lider (alianca implicita).
        """
        if opp.renown_level <= 0:
            return 1.0
        progress = opp.victory_points / opp.renown_level
        if progress <= 0.5:
            return 1.0
        extra = (progress - 0.5) * 1.5  # 0 a 0.75
        return 1.0 + extra

    # ------------------------------------------------------------------
    # Fatores individuais (0-10)
    # ------------------------------------------------------------------

    def threat_score(self) -> float:
        """Ameaca agregada de TODOS os oponentes (0-10).

        Cada oponente contribui proporcionalmente ao seu poder
        de mesa E proximidade da vitoria.
        """
        opps = self._get_opponents()
        if not opps:
            return 0.0

        total = 0.0
        for opp in opps:
            if not opp.pack_home:
                continue
            total_rage = sum(c.rage for c in opp.pack_home)
            num_creatures = len(opp.pack_home)
            total_health = sum(c.health_current for c in opp.pack_home)

            rage_score = min(total_rage / 3.0, 5.0)
            count_score = min(num_creatures * 2.0, 3.0)
            health_score = min(total_health / 6.0, 2.0)

            raw = rage_score + count_score + health_score
            raw *= self._vp_weight(opp)
            total += raw

        return min(total / len(opps), 10.0)

    def advantage_score(self) -> float:
        """Vantagem de mesa contra a MEDIA dos oponentes (0-10).

        5 = neutro, >5 = estou melhor, <5 = estou pior.
        """
        me = self.player
        opps = self._get_opponents()
        if not opps:
            return 5.0

        my_creatures = len(me.pack_home)
        my_health = sum(c.health_current for c in me.pack_home)
        my_hand = len(me.hand)

        avg_creatures = sum(len(o.pack_home) for o in opps) / len(opps)
        avg_health = sum(
            sum(c.health_current for c in o.pack_home) for o in opps
        ) / len(opps)
        avg_hand = sum(len(o.hand) for o in opps) / len(opps)

        creature_diff = (my_creatures - avg_creatures) * 1.5
        health_diff = (my_health - avg_health) * 0.3
        hand_diff = (my_hand - avg_hand) * 0.5

        total = creature_diff + health_diff + hand_diff
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
