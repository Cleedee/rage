"""Testes do motor de jogo: state e combat queue."""

import pytest

from rage_web.game_engine.state import (
    GameState, PlayerState, CardInstance, CombatState, Zone,
)
from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, reveal_all, feint_action,
    can_feint, resolve_combat, end_combat, get_declaration_summary,
    get_combatants,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def player1() -> PlayerState:
    p = PlayerState(id='p1', name='Jogador 1')
    # Deck de combate com algumas cartas
    for i in range(5):
        p.deck_combat.append(CardInstance(
            card_id=100 + i, name=f'Combat Card {i}',
            card_type='Combat Action', zone=Zone.DECK_COMBAT,
            owner_id='p1', controller_id='p1',
        ))
    # Deck de sept
    for i in range(5):
        p.deck_sept.append(CardInstance(
            card_id=200 + i, name=f'Sept Card {i}',
            card_type='Event', zone=Zone.DECK_SEPT,
            owner_id='p1', controller_id='p1',
        ))
    return p


@pytest.fixture
def player2() -> PlayerState:
    p = PlayerState(id='p2', name='Jogador 2')
    for i in range(5):
        p.deck_combat.append(CardInstance(
            card_id=300 + i, name=f'Combat Card {i}',
            card_type='Combat Action', zone=Zone.DECK_COMBAT,
            owner_id='p2', controller_id='p2',
        ))
    for i in range(5):
        p.deck_sept.append(CardInstance(
            card_id=400 + i, name=f'Sept Card {i}',
            card_type='Event', zone=Zone.DECK_SEPT,
            owner_id='p2', controller_id='p2',
        ))
    return p


@pytest.fixture
def game(player1: PlayerState, player2: PlayerState) -> GameState:
    g = GameState(players=[player1, player2])
    return g


@pytest.fixture
def creature1(player1: PlayerState) -> CardInstance:
    return CardInstance(
        card_id=1, name='Lobo Solitario', card_type='Character',
        zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
        rage=4, gnosis=3, health=6, health_current=6,
    )


@pytest.fixture
def creature2(player2: PlayerState) -> CardInstance:
    return CardInstance(
        card_id=2, name='Wyrm Hound', card_type='Enemy',
        zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
        rage=3, gnosis=2, health=4, health_current=4,
    )


# ---------------------------------------------------------------------------
# Testes: GameState
# ---------------------------------------------------------------------------

class TestGameState:
    def test_create_game(self, player1, player2):
        g = GameState(players=[player1, player2])
        assert len(g.players) == 2
        assert g.phase == 'gather'
        assert g.turn_number == 1
        assert g.current_player.id == 'p1'

    def test_next_player(self, game):
        assert game.current_player.id == 'p1'
        game.next_player()
        assert game.current_player.id == 'p2'
        game.next_player()
        assert game.current_player.id == 'p1'

    def test_next_phase(self, game):
        assert game.phase == 'gather'
        game.next_phase()
        assert game.phase == 'action'
        game.next_phase()
        assert game.phase == 'combat'
        game.next_phase()
        assert game.phase == 'discard'
        game.next_phase()
        # Volta para gather, incrementa turno
        assert game.phase == 'gather'
        assert game.turn_number == 2

    def test_add_log(self, game):
        game.add_log('Teste')
        assert len(game.log) == 1
        assert '[T1 GATHER] Teste' in game.log[0]


# ---------------------------------------------------------------------------
# Testes: PlayerState
# ---------------------------------------------------------------------------

class TestPlayerState:
    def test_draw_combat(self, player1):
        assert len(player1.hand) == 0
        drawn = player1.draw_combat(2)
        assert len(drawn) == 2
        assert len(player1.hand) == 2
        assert len(player1.deck_combat) == 3

    def test_draw_sept(self, player1):
        drawn = player1.draw_sept(1)
        assert len(drawn) == 1
        assert len(player1.hand) == 1
        assert drawn[0].zone == Zone.HAND

    def test_pass_turn(self, player1):
        assert not player1.has_passed
        player1.pass_turn()
        assert player1.has_passed
        player1.reset_pass()
        assert not player1.has_passed

    def test_cards_in_play(self, player1, creature1):
        assert player1.total_cards_in_play == 0
        player1.pack_home.append(creature1)
        assert player1.total_cards_in_play == 1


# ---------------------------------------------------------------------------
# Testes: CombatState
# ---------------------------------------------------------------------------

class TestCombatState:
    def test_initial_state(self):
        cs = CombatState()
        assert not cs.is_active
        assert cs.step == ''
        assert cs.last_to_declare is None

    def test_declare_action(self):
        cs = CombatState(is_active=True, step='declare',
                          attackers=['c1'], defenders=['c2'])
        assert cs.declare('c1', 'strike')
        assert cs.declarations == {'c1': 'strike'}
        assert cs.last_to_declare == 'c1'

    def test_declare_twice_fails(self):
        cs = CombatState(is_active=True, step='declare',
                          attackers=['c1'], defenders=['c2'])
        assert cs.declare('c1', 'strike')
        assert not cs.declare('c1', 'block')  # Ja declarou

    def test_last_to_declare(self):
        cs = CombatState(is_active=True, step='declare',
                          attackers=['c1', 'c2'], defenders=['c3'])
        cs.declare('c1', 'strike')
        assert cs.last_to_declare == 'c1'
        cs.declare('c2', 'block')
        assert cs.last_to_declare == 'c2'
        cs.declare('c3', 'dodge')
        assert cs.last_to_declare == 'c3'  # Ultimo = vantagem

    def test_all_declared(self):
        cs = CombatState(is_active=True, step='declare',
                          attackers=['c1', 'c2'], defenders=['c3'])
        cs.declare('c1', 'strike')
        assert not cs.all_declared(['c1', 'c2', 'c3'])
        cs.declare('c2', 'block')
        cs.declare('c3', 'dodge')
        assert cs.all_declared(['c1', 'c2', 'c3'])


# ---------------------------------------------------------------------------
# Testes: Combat Queue (integracao)
# ---------------------------------------------------------------------------

class TestCombatQueue:
    def test_start_combat(self, game, creature1, creature2):
        c1_id, c2_id = 'c1', 'c2'
        game.players[0].pack_home.append(creature1)
        game.players[1].pack_home.append(creature2)

        assert start_combat(game, [c1_id], [c2_id])
        assert game.combat.is_active
        assert game.combat.step == 'declare'
        assert c1_id in game.combat.attackers
        assert c2_id in game.combat.defenders

    def test_start_combat_already_active(self, game):
        start_combat(game, ['c1'], ['c2'])
        assert not start_combat(game, ['c3'], ['c4'])

    def test_declare_full_cycle(self, game):
        """Ciclo completo: declarar, revelar, resolver, encerrar."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])

        # Declaracoes
        assert declare_action(game, c1, 'strike')
        assert declare_action(game, c2, 'block')

        # Revelar
        assert reveal_all(game)
        assert game.combat.step == 'reveal'

        # Ver resumo
        summary = get_declaration_summary(game)
        assert summary['declarations'][c1] == 'strike'
        assert summary['declarations'][c2] == 'block'
        assert summary['last_to_declare'] == c2

        # Resolver
        assert resolve_combat(game)
        assert game.combat.step == 'end'

        # Encerrar
        assert end_combat(game)
        assert not game.combat.is_active

    def test_declare_order_matters(self, game):
        """Quem declara por ultimo tem vantagem (pode Feint)."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])

        declare_action(game, c1, 'strike')   # c1 declara primeiro
        declare_action(game, c2, 'dodge')    # c2 declara por ultimo
        reveal_all(game)

        # c2 declarou por ultimo -> pode Feint
        assert can_feint(game, c2)
        # c1 declarou primeiro -> NAO pode Feint (a menos que tenha habilidade)
        assert not can_feint(game, c1)

    def test_feint_changes_action(self, game):
        """Feint troca a acao declarada."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])
        declare_action(game, c1, 'strike')
        declare_action(game, c2, 'dodge')
        reveal_all(game)

        # Ultimo a declarar (c2) usa Feint
        assert feint_action(game, c2, 'strike')
        assert game.combat.declarations[c2] == 'strike'

    def test_feint_not_for_early_declarer(self, game):
        """Quem declarou primeiro nao pode Feint (regra basica)."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])
        declare_action(game, c1, 'strike')
        declare_action(game, c2, 'dodge')
        reveal_all(game)

        assert not feint_action(game, c1, 'block')

    def test_cannot_declare_invalid_action(self, game):
        start_combat(game, ['c1'], ['c2'])
        assert not declare_action(game, 'c1', 'invalid_action')

    def test_cannot_declare_before_combat(self, game):
        assert not declare_action(game, 'c1', 'strike')

    def test_cannot_declare_wrong_step(self, game):
        start_combat(game, ['c1'], ['c2'])
        declare_action(game, 'c1', 'strike')
        declare_action(game, 'c2', 'block')
        reveal_all(game)
        # Nao pode declarar no reveal step
        assert not declare_action(game, 'c3', 'strike')

    def test_cannot_feint_before_reveal(self, game):
        """Feint so funciona no Reveal Step."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])
        declare_action(game, c1, 'strike')
        declare_action(game, c2, 'dodge')
        # Ainda em 'declare', nao pode Feint
        assert not can_feint(game, c2)

    def test_declaration_summary_hidden_before_reveal(self, game):
        """Antes da revelacao, as acoes sao ocultas."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])
        declare_action(game, c1, 'strike')

        summary = get_declaration_summary(game)
        assert 'declared_count' in summary
        assert 'declarations' not in summary or not summary['declarations']

    def test_multiple_attackers_and_defenders(self, game):
        """Combate com multiplas criaturas de cada lado."""
        c1, c2, c3 = 'c1', 'c2', 'c3'
        start_combat(game, [c1, c2], [c3])

        assert declare_action(game, c1, 'strike')
        assert declare_action(game, c2, 'strike')
        assert declare_action(game, c3, 'block')

        reveal_all(game)
        resolve_combat(game)
        end_combat(game)

        assert not game.combat.is_active

    def test_resolve_auto_reveals(self, game):
        """Se tentar resolver sem revelar, faz reveal automatico."""
        c1, c2 = 'c1', 'c2'
        start_combat(game, [c1], [c2])
        declare_action(game, c1, 'strike')
        declare_action(game, c2, 'block')

        # Pula direto para resolve (deve revelar internamente)
        assert resolve_combat(game)
        assert game.combat.step == 'end'

    def test_get_combatants(self, game):
        start_combat(game, ['c1', 'c2'], ['c3'])
        combatants = get_combatants(game)
        assert 'c1' in combatants
        assert 'c2' in combatants
        assert 'c3' in combatants
        assert len(combatants) == 3
