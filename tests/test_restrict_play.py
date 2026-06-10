import pytest
from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, _processar_bluff, _find_card,
    COMBAT_ACTION_PROPS, COMBAT_ACTIONS, get_combatants,
    advance_combat_step,
)
from rage_web.game_engine.state import Zone


class TestRestrictForcedRandomPlay:
    """Testes das regras 6.6.6 — Restricted / Forced / Random Play."""

    def _setup_game(self, seed=42):
        from rage_web.game_engine.cli import build_game_from_decks
        game = build_game_from_decks(160, 629, seed=seed)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
            p.draw_combat(p.hand_size_combat)
        return game

    def _advance_to_play_card(self, game):
        for step_name in ['declaration', 'pre_combat', 'beginning_of_combat']:
            game.combat.step = step_name
            advance_combat_step(game)

    def test_restricted_play_torna_acao_ilegal(self):
        """6.6.6a: Restricted Play (Rage <= 2) torna savage_beatdown (req=3) ilegal."""
        game = self._setup_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = max(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = max(p2.pack_home, key=lambda c: c.effective_rage)
        # Precisa de Rage >= 3 para savage_beatdown
        assert atk.effective_rage >= 3, 'atk precisa Rage >= 3'

        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        self._advance_to_play_card(game)

        # Aplica Restricted Play (Rage <= 2) no atacante
        game.combat.aplicar_restricao_round(
            str(atk.card_id), restricted=2)

        # savage_beatdown tem rage_requirement=3
        game.combat.step = 'play_card'
        ok = declare_action(game, str(atk.card_id), 'savage_beatdown')
        assert ok, 'savage_beatdown deve ser aceita no play_card'

        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)

        # Bluff Step: deve detectar como ilegal por Restricted Play
        game.combat.step = 'bluff'
        _processar_bluff(game)

        assert str(atk.card_id) in game.combat.illegal_cards, \
            'savage_beatdown com Restricted Rage<=2 deve ser ilegal (6.6.6a)'
        assert str(atk.card_id) not in game.combat.declarations, \
            'Carta ilegal removida das declaracoes'

    def test_restricted_play_permite_acao_valida(self):
        """6.6.6a: Restricted Play (Rage <= 4) permite savage_beatdown (req=3)."""
        game = self._setup_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = max(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = max(p2.pack_home, key=lambda c: c.effective_rage)

        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        self._advance_to_play_card(game)

        # Restricted Rage <= 4 — savage_beatdown (req=3) deve ser valido
        game.combat.aplicar_restricao_round(
            str(atk.card_id), restricted=4)

        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'savage_beatdown')
        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)

        game.combat.step = 'bluff'
        _processar_bluff(game)

        assert str(atk.card_id) not in game.combat.illegal_cards, \
            'savage_beatdown com Restricted Rage<=4 deve ser legal'
        assert str(atk.card_id) in game.combat.declarations, \
            'Carta valida mantida nas declaracoes'

    def test_reseta_restricoes_entre_rodadas(self):
        """Restricoes resetam a cada nova rodada de combate."""
        game = self._setup_game()
        p1 = game.players[0]
        atk = p1.pack_home[0]

        game.combat.aplicar_restricao_round(
            str(atk.card_id), restricted=2, forced=True)
        assert game.combat.get_restricted_level(str(atk.card_id)) == 2
        assert game.combat.has_forced_play(str(atk.card_id))

        # Nova rodada
        game.combat.iniciar_nova_rodada()

        assert game.combat.get_restricted_level(str(atk.card_id)) is None, \
            'Restricoes devem ser resetadas na nova rodada'
        assert not game.combat.has_forced_play(str(atk.card_id)), \
            'Forced Play resetado'
