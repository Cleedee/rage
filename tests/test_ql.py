"""Testes do agente Q-Learning (macro-ações + Q-Linear numpy)."""

import os

import numpy as np
import pytest

from rage_web.game_engine.bot.priority_bot import PriorityBot
from rage_web.game_engine.bot.ql.actions import (ALL_MACROS, N_ACTIONS,
                                                 execute_macro, legal_mask)
from rage_web.game_engine.bot.ql.agent import QLearningBot, shaping_reward
from rage_web.game_engine.bot.ql.features import encode_state, n_features
from rage_web.game_engine.bot.ql.qlearner import LinearQLearner
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.match import run_match


@pytest.fixture
def game():
    return create_sample_game(seed=42)


@pytest.fixture
def learner():
    return LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS,
                          seed=7)


@pytest.fixture
def agent(game, learner):
    return QLearningBot(game, game.players[0].id, learner=learner,
                        greedy=True)


# ── Features ──────────────────────────────────────────────────────────

def test_encode_state_shape(game):
    nf = n_features()
    s = encode_state(game, game.players[0].id)
    assert s.shape == (nf,)
    assert s.dtype == np.float64
    assert np.isfinite(s).all()


def test_encode_state_deterministic(game):
    s1 = encode_state(game, game.players[0].id)
    s2 = encode_state(game, game.players[0].id)
    np.testing.assert_array_equal(s1, s2)


def test_encode_state_ultima_feature_bias(game):
    s = encode_state(game, game.players[0].id)
    assert s[-1] == 1.0


# ── QLearner ──────────────────────────────────────────────────────────

def test_action_values_mask(learner):
    s = np.ones(learner.n_features)
    mask = [False] * learner.n_actions
    mask[3] = True
    q = learner.action_values(s, mask)
    assert q[3] == 0.0
    assert np.all(q[np.arange(learner.n_actions) != 3] <= -1e8)


def test_choose_action_respeita_mask(learner):
    s = np.ones(learner.n_features)
    mask = [False] * learner.n_actions
    mask[5] = True
    for _ in range(20):
        a = learner.choose_action(s, mask=mask, greedy=True)
        assert a == 5


def test_update_movimenta_theta(learner):
    s = np.zeros(learner.n_features)
    s[0] = 1.0
    s_next = np.zeros_like(s)
    s_next[1] = 1.0
    before = learner.theta.copy()
    learner.update(s, 0, 1.0, s_next, mask_next=None)
    assert not np.array_equal(learner.theta, before)
    # Ação não escolhida não muda
    assert np.array_equal(learner.theta[1], before[1])


def test_terminal_update(learner):
    s = np.zeros(learner.n_features)
    s[2] = 1.0
    before = learner.theta.copy()
    learner.terminal_update(s, 4, 1.0)
    assert not np.array_equal(learner.theta[4], before[4])


def test_theta_nao_diverge(learner):
    """Um punhado de updates não pode explodir os pesos."""
    rng = np.random.default_rng(0)
    for _ in range(500):
        s = rng.random(learner.n_features)
        s_next = rng.random(learner.n_features)
        a = int(rng.integers(learner.n_actions))
        r = rng.uniform(-2, 2)
        if rng.random() < 0.2:
            learner.terminal_update(s, a, r)
        else:
            learner.update(s, a, r, s_next, mask_next=None)
    assert np.isfinite(learner.theta).all()
    assert float(np.abs(learner.theta).max()) < 50.0


def test_save_load_roundtrip(tmp_path, learner):
    learner.update(np.ones(learner.n_features), 2, 1.0,
                   np.ones(learner.n_features))
    path = str(tmp_path / 'pesos.npz')
    learner.save(path)
    novo = LinearQLearner(n_features=learner.n_features,
                          n_actions=learner.n_actions, seed=1)
    assert novo.load(path)
    np.testing.assert_array_equal(novo.theta, learner.theta)
    assert novo.epsilon == learner.epsilon
    assert novo.steps == learner.steps


# ── Macro-ações ───────────────────────────────────────────────────────

def test_macro_index_completo():
    assert len(set(ALL_MACROS)) == N_ACTIONS
    assert len(ALL_MACROS) == 22


def test_legal_mask_redraw_turn1(game, agent):
    game.phase = 'redraw'
    game.turn_number = 1
    game.players[0].is_first_turn = True
    mask = legal_mask(agent)
    names = {ALL_MACROS[i] for i in range(N_ACTIONS) if mask[i]}
    assert 'redraw_lunar' in names
    assert 'redraw_pass' in names
    assert 'redraw_discard' not in names  # turno 1 não descarta


def test_legal_mask_turno_alheio(game, agent):
    game.current_player_index = 1
    mask = legal_mask(agent)
    assert not mask.any()


def test_execute_macro_desconhecido_retorna_none(game, agent):
    assert execute_macro(agent, 'nao_existe') is None


def test_execute_macro_redraw_pass(game, agent):
    game.phase = 'redraw'
    result = execute_macro(agent, 'redraw_pass')
    assert result is not None


# ── Agente ────────────────────────────────────────────────────────────

def test_shaping_reward_bounded(game):
    r = shaping_reward(game, game.players[0].id)
    assert np.isfinite(r)


def test_decide_retorna_acao_valida(game, learner):
    bot = QLearningBot(game, game.players[0].id, learner=learner,
                       greedy=False, seed=3)
    a = bot.decide()
    assert isinstance(a, str)
    assert a
    assert len(bot._pending) == 1


def test_decide_fora_da_vez(game, learner):
    bot = QLearningBot(game, game.players[0].id, learner=learner,
                       greedy=True)
    game.current_player_index = 1
    assert bot.decide() == 'wait'
    assert bot._pending == []


def test_finish_episode_limpa_pendente(game, learner):
    bot = QLearningBot(game, game.players[0].id, learner=learner,
                       greedy=True)
    bot.decide()
    assert bot._pending
    bot.finish_episode('p1')
    assert bot._pending == []


def test_finish_episode_recompensa_vencedor():
    game = create_sample_game(seed=1)
    learner = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS,
                             seed=2)
    bot = QLearningBot(game, game.players[0].id, learner=learner,
                       greedy=True)
    bot.decide()
    antes = learner.theta.copy()
    bot.finish_episode('p1')
    assert not np.array_equal(learner.theta, antes)


def test_determinismo_mesma_seed():
    def roda(seed):
        game = create_sample_game(seed=5)
        learner = LinearQLearner(n_features=n_features(),
                                 n_actions=N_ACTIONS, seed=seed)
        bot = QLearningBot(game, game.players[0].id, learner=learner,
                           greedy=False, seed=seed)
        acoes = []
        for _ in range(10):
            game.current_player.id = bot.player_id
            acoes.append(bot.decide())
        return acoes

    assert roda(11) == roda(11)


# ── Integração ────────────────────────────────────────────────────────

def test_match_integracao_ql_vs_easy():
    """Partida completa QL (p1) vs PriorityBot easy (p2) não pode quebrar."""
    learner = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS,
                             seed=9)
    agents = {}

    def factory(game, pid):
        ag = QLearningBot(game, pid, learner=learner, greedy=False, seed=9)
        agents[pid] = ag
        return ag

    result = run_match(seed=99, max_turns=6,
                       difficulty_p1='hard', difficulty_p2='easy',
                       delay=0, verbose=0, bot_factory=factory)
    assert result in ('p1', 'p2', 'draw', 'timeout')
    assert 'p1' in agents
    agents['p1'].finish_episode(result)
    assert np.isfinite(learner.theta).all()
    # Pesos não podem divergir em uma partida curta
    assert float(np.abs(learner.theta).max()) < 50.0


def test_match_controle_prioritybot_vs_prioritybot():
    """Controle: sem bot_factory o run_match segue funcionando."""
    result = run_match(seed=99, max_turns=6,
                       difficulty_p1='hard', difficulty_p2='easy',
                       delay=0, verbose=0)
    assert result in ('p1', 'p2', 'draw', 'timeout')


def test_agente_usado_como_factory_retorna_bot(game, learner):
    bot = QLearningBot(game, game.players[0].id, learner=learner,
                       greedy=True)
    assert isinstance(bot, PriorityBot)


# ── Per-deck: factory recebe deck_id ──────────────────────────────────

def test_match_factory_recebe_deck_id():
    """Factory com 3 args recebe o deck_id de cada jogador (None no sample)."""
    seen = {}

    def factory(game, player_id, deck_id):
        seen[player_id] = deck_id
        return QLearningBot(
            game, player_id,
            learner=LinearQLearner(n_features=n_features(),
                                   n_actions=N_ACTIONS, seed=1),
            greedy=True)

    result = run_match(seed=3, max_turns=2, delay=0, verbose=0,
                       bot_factory=factory)
    assert result in ('p1', 'p2', 'draw', 'timeout')
    assert set(seen) == {'p1', 'p2'}
    assert seen['p1'] is None and seen['p2'] is None


def test_match_factory_none_cai_no_prioritybot():
    """Factory retornando None para p2 → run_match cria PriorityBot."""
    learners = {}

    def factory(game, player_id, deck_id):
        if player_id == 'p1':
            ag = QLearningBot(
                game, player_id,
                learner=LinearQLearner(n_features=n_features(),
                                       n_actions=N_ACTIONS, seed=1),
                greedy=False)
            learners[player_id] = ag
            return ag
        return None

    result = run_match(seed=4, max_turns=3, delay=0, verbose=0,
                       difficulty_p2='easy', bot_factory=factory)
    assert result in ('p1', 'p2', 'draw', 'timeout')
    assert 'p1' in learners
    learners['p1'].finish_episode(result)
    assert np.isfinite(learners['p1'].learner.theta).all()


def test_match_factory_2args_retrocompat():
    """Factory com 2 args (assinatura antiga) continua funcionando."""
    def factory(game, player_id):
        return QLearningBot(
            game, player_id,
            learner=LinearQLearner(n_features=n_features(),
                                   n_actions=N_ACTIONS, seed=1),
            greedy=True)

    result = run_match(seed=5, max_turns=2, delay=0, verbose=0,
                       bot_factory=factory)
    assert result in ('p1', 'p2', 'draw', 'timeout')


def test_match_multideck_factory_recebe_deck_por_jogador():
    """Partida com 3 decks: factory vê o deck de cada jogador."""
    ids = [465, 1044, 1045]
    seen = {}

    def factory(game, player_id, deck_id):
        seen[player_id] = deck_id
        return QLearningBot(
            game, player_id,
            learner=LinearQLearner(n_features=n_features(),
                                   n_actions=N_ACTIONS, seed=1),
            greedy=True)

    result = run_match(seed=6, max_turns=3, deck_ids=ids, delay=0,
                       verbose=0, bot_factory=factory)
    if result == 'error':
        pytest.skip('decks 465/1044/1045 indisponíveis no banco')
    assert seen == {'p1': ids[0], 'p2': ids[1], 'p3': ids[2]}
    assert result in ('p1', 'p2', 'p3', 'draw', 'timeout')


# ── Per-deck: treino e persistência ───────────────────────────────────

def test_parse_pairs_multi_deck():
    from rage_web.game_engine.bot.ql import train as tr
    assert tr._parse_pairs('7-90,1050-90') == [(7, 90), (1050, 90)]
    assert tr._parse_pairs('7,90,1050') == [(7, 90, 1050)]
    assert tr._parse_pairs('1,2,3;4,5,6') == [(1, 2, 3), (4, 5, 6)]
    assert tr._parse_pairs('7-90;1050-90') == [(7, 90), (1050, 90)]
    assert tr._parse_pairs(None) == tr.DEFAULT_PAIRS
    assert tr._parse_pairs('7,90') == [(7, 90)]


def test_treino_salva_modelo_por_deck(tmp_path):
    from rage_web.game_engine.bot.ql import train as tr
    l7 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=1)
    l90 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=2)
    l7.theta[3, 0] = 42.0
    out = str(tmp_path)
    tr._save_learners({'7': l7, '90': l90}, out)
    assert os.path.exists(os.path.join(out, 'deck7.npz'))
    assert os.path.exists(os.path.join(out, 'deck90.npz'))

    novo7 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=3)
    novo90 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=4)
    assert novo7.load(os.path.join(out, 'deck7.npz'))
    assert novo90.load(os.path.join(out, 'deck90.npz'))
    assert float(novo7.theta[3, 0]) == 42.0
    assert float(novo90.theta[3, 0]) == 0.0


def test_make_deck_aware_factory_seleciona_modelo(tmp_path):
    """A factory por deck carrega o npz certo e cacheia por deck."""
    from rage_web.game_engine.bot.ql import train as tr
    l7 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=1)
    l90 = LinearQLearner(n_features=n_features(), n_actions=N_ACTIONS, seed=2)
    l7.theta[3, 0] = 42.0
    tr._save_learners({'7': l7, '90': l90}, str(tmp_path))

    factory = tr.make_deck_aware_factory(models_dir=str(tmp_path), greedy=True)
    game = create_sample_game(seed=1)
    bot7 = factory(game, 'p1', 7)
    bot90 = factory(game, 'p1', 90)
    assert float(bot7.learner.theta[3, 0]) == 42.0
    assert float(bot90.learner.theta[3, 0]) == 0.0
    # cache: segundo bot do deck 7 usa o mesmo learner
    assert factory(game, 'p1', 7).learner is bot7.learner
    # sem deck (sample) → modelo 'sample'
    bot_sample = factory(game, 'p2', None)
    assert float(bot_sample.learner.theta[3, 0]) == 0.0

