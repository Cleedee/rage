"""Testes do bot: evaluator e arvore de decisao."""

import pytest

from rage_web.game_engine.bot.evaluator import BoardEvaluator
from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.state import CardInstance, Zone


@pytest.fixture
def game():
    return create_sample_game(seed=42)


@pytest.fixture
def evaluator(game):
    return BoardEvaluator(game, player_id='p1')


class TestBoardEvaluator:
    def test_create(self, evaluator):
        assert evaluator.player.id == 'p1'
        opps = evaluator._get_opponents()
        assert len(opps) == 1
        assert opps[0].id == 'p2'

    def test_threat_score(self, evaluator):
        score = evaluator.threat_score()
        assert 0 <= score <= 10

    def test_threat_zero_when_no_creatures(self, game):
        game.players[1].pack_home.clear()
        ev = BoardEvaluator(game, 'p1')
        assert ev.threat_score() == 0.0

    def test_advantage_score(self, evaluator):
        score = evaluator.advantage_score()
        assert 0 <= score <= 10

    def test_pressure_score(self, evaluator):
        score = evaluator.pressure_score()
        assert 0 <= score <= 10

    def test_pressure_max_when_no_creatures(self, game):
        game.players[0].pack_home.clear()
        ev = BoardEvaluator(game, 'p1')
        assert ev.pressure_score() == 10.0

    def test_victory_score(self, evaluator):
        score = evaluator.victory_score()
        assert 0 <= score <= 10

    def test_victory_progress(self, game):
        game.players[0].victory_points = 10
        game.players[0].renown_level = 20
        ev = BoardEvaluator(game, 'p1')
        assert ev.victory_score() == 5.0

    def test_composite_score(self, evaluator):
        score = evaluator.composite_score()
        assert 0 <= score <= 10

    def test_summary(self, evaluator):
        s = evaluator.summary()
        assert 'threat' in s
        assert 'advantage' in s
        assert 'pressure' in s
        assert 'victory' in s
        assert 'composite' in s


class TestPriorityBot:
    def test_create(self, game):
        bot = PriorityBot(game, 'p1', difficulty='medium')
        assert bot.player_id == 'p1'
        assert bot.difficulty == 'medium'

    def test_decide_returns_string(self, game):
        bot = PriorityBot(game, 'p1')
        action = bot.decide()
        assert isinstance(action, str)
        assert len(action) > 0

    def test_decide_easy_returns_string(self, game):
        bot = PriorityBot(game, 'p1', difficulty='easy')
        action = bot.decide()
        assert isinstance(action, str)

    def test_decide_wait_when_not_turn(self, game):
        """Bot espera se nao for a vez dele."""
        game.current_player_index = 1  # Vez do P2
        bot = PriorityBot(game, 'p1')
        action = bot.decide()
        assert action == 'wait'

    def test_decide_draw(self, game):
        """Bot pode comprar carta."""
        # Esvazia mao para incentivar compra
        game.players[0].hand.clear()
        bot = PriorityBot(game, 'p1')
        action = bot.decide()
        # Nao pode garantir que vai comprar, mas nao deve dar erro
        assert isinstance(action, str)

    def test_decide_play(self, game):
        """Bot pode jogar carta."""
        # Garante que tem carta na mao
        if not game.players[0].hand:
            game.players[0].draw_combat(1)
        bot = PriorityBot(game, 'p1')
        action = bot.decide()
        assert isinstance(action, str)

    def test_evaluator_updates(self, game):
        """Avaliador reflete mudancas no estado."""
        ev1 = BoardEvaluator(game, 'p1')
        s1 = ev1.summary()

        # Adiciona criatura forte para o oponente
        strong = CardInstance(
            card_id=999, name='Super Inimigo', card_type='Enemy',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=8, gnosis=5, health=10, health_current=10,
        )
        game.players[1].pack_home.append(strong)

        ev2 = BoardEvaluator(game, 'p1')
        s2 = ev2.summary()

        assert s2['threat'] >= s1['threat']

    def test_decide_combat(self, game):
        """Bot age em combate."""
        bot = PriorityBot(game, 'p1')
        # Adiciona alvo no HG para o combate ser valido
        from rage_web.game_engine.state import Zone, CardInstance
        vitima = CardInstance(
            card_id=9999, name='Victim Test', card_type='Victim',
            zone=Zone.HUNTING_GROUNDS, owner_id='global',
            controller_id='global', health=3, health_current=3,
        )
        game.hunting_grounds_cards.append(vitima)
        # Inicia combate manualmente contra a vitima
        from rage_web.game_engine.combat_queue import start_combat
        atk = game.players[0].pack_home[0]
        start_combat(game, [str(atk.card_id)], [str(vitima.card_id)])

        # Bot esta em combate, deve declarar (novo fluxo: auto-advance
        # por declaration/pre_combat/beginning_of_combat, depois play_card)
        action = bot.decide()
        # O bot pode precisar de algumas chamadas para avancar
        # pelos steps de auto-advance (declaration, pre_combat,
        # beginning_of_combat) antes de jogar a carta
        for _ in range(10):
            if (action.startswith('play_') or action.startswith('declare_')
                    or action == 'combat_wait'):
                break
            action = bot.decide()
        assert (action.startswith('play_') or action.startswith('declare_')
                or action == 'combat_wait'), f'Got: {action}'

    def test_difficulty_levels(self, game):
        """Todos os niveis de dificuldade funcionam."""
        for diff in ['easy', 'medium', 'hard']:
            bot = PriorityBot(game, 'p1', difficulty=diff)
            action = bot.decide()
            assert isinstance(action, str)
