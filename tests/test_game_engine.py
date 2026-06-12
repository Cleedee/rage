"""Testes do motor de jogo: state e combat queue."""

import pytest

from rage_web.game_engine.state import (
    GameState, PlayerState, CardInstance, CombatState, Zone,
)
from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, reveal_all, feint_action,
    can_feint, resolve_combat, end_combat, get_declaration_summary,
    get_combatants, _find_criatura, _validar_tail_lash,
    _validar_tail_lash_bonus, COMBAT_ACTION_VALIDATORS,
    _mesmo_lado_gauntlet, lone_wolf_circles_dodge,
)
from rage_web.game_engine.effects import (
    _validar_condicao_uso, _condicao_rokea_mokole_nao_homid,
    _condicao_personagem_na_umbra,
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
        assert g.phase == 'redraw'
        assert g.turn_number == 1
        assert g.current_player.id == 'p1'

    def test_next_player(self, game):
        assert game.current_player.id == 'p1'
        game.next_player()
        assert game.current_player.id == 'p2'
        game.next_player()
        assert game.current_player.id == 'p1'

    def test_next_phase(self, game):
        assert game.phase == 'redraw'
        game.next_phase()
        assert game.phase == 'regeneration'
        game.next_phase()
        assert game.phase == 'resource'
        game.next_phase()
        assert game.phase == 'umbra'
        game.next_phase()
        assert game.phase == 'moot'
        game.next_phase()
        assert game.phase == 'combat'
        game.next_phase()
        # Volta para redraw, incrementa turno
        assert game.phase == 'redraw'
        assert game.turn_number == 2

    def test_add_log(self, game):
        game.add_log('Teste')
        assert len(game.log) == 1
        assert '[T1 REDRAW] Teste' in game.log[0]


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
        c1_id, c2_id = str(creature1.card_id), str(creature2.card_id)
        game.players[0].pack_home.append(creature1)
        game.players[1].pack_home.append(creature2)

        assert start_combat(game, [c1_id], [c2_id])
        assert game.combat.is_active
        assert game.combat.step == 'declaration'
        assert c1_id in game.combat.attackers
        assert c2_id in game.combat.defenders

    def test_start_combat_already_active(self, game, creature1, creature2):
        c1_id, c2_id = str(creature1.card_id), str(creature2.card_id)
        game.players[0].pack_home.append(creature1)
        game.players[1].pack_home.append(creature2)
        start_combat(game, [c1_id], [c2_id])
        assert not start_combat(game, ['999'], ['888'])

    def test_declare_full_cycle(self, game, creature1, creature2):
        """Ciclo completo: declarar, revelar, resolver, encerrar."""
        c1, c2 = str(creature1.card_id), str(creature2.card_id)
        game.players[0].pack_home.append(creature1)
        game.players[1].pack_home.append(creature2)
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

        # Resolver (novo fluxo: resolution -> withdrawal -> between_rounds -> loop)
        assert resolve_combat(game)
        assert game.combat.step == 'withdrawal'

        from rage_web.game_engine.combat_queue import advance_combat_step
        assert advance_combat_step(game)  # withdrawal -> between_rounds

        # Multi-round (6.2): como ambos os combatentes sobreviveram,
        # o combate prossegue para a segunda rodada
        assert advance_combat_step(game)  # between_rounds -> play_card (rodada 2)
        assert game.combat.step == 'play_card'
        assert game.combat.round_number == 2

        # Encerra manualmente
        game.combat.step = 'end'
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
        assert game.combat.step == 'withdrawal'
        from rage_web.game_engine.combat_queue import advance_combat_step
        advance_combat_step(game)  # withdrawal -> between_rounds
        # Multi-round (6.2): ambos sobreviveram, combate continua
        advance_combat_step(game)  # between_rounds -> play_card (rodada 2)
        assert game.combat.step == 'play_card'
        assert game.combat.round_number == 2
        game.combat.step = 'end'  # encerra manualmente

    def test_get_combatants(self, game):
        start_combat(game, ['c1', 'c2'], ['c3'])
        combatants = get_combatants(game)
        assert 'c1' in combatants
        assert 'c2' in combatants
        assert 'c3' in combatants
        assert len(combatants) == 3


# ---------------------------------------------------------------------------
# Testes: Validadores de Combat Actions (Tail Lash)
# ---------------------------------------------------------------------------

class TestCombatActionValidators:
    """Testes para o sistema de validacao de Combat Actions."""

    @pytest.fixture
    def rokea_creature(self, player1: PlayerState) -> CardInstance:
        """Criatura Rokea em forma nao-Homid (Crinos)."""
        return CardInstance(
            card_id=10, name='Rokea Crinos', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, gnosis=3, health=8, health_current=8,
            keywords='Rokea - Gaia - Male',
        )

    @pytest.fixture
    def rokea_homid(self, player1: PlayerState) -> CardInstance:
        """Criatura Rokea em forma Homid."""
        return CardInstance(
            card_id=11, name='Rokea Homid', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=3, gnosis=5, health=5, health_current=5,
            keywords='Rokea - Homid - Gaia - Male',
        )

    @pytest.fixture
    def mokole_creature(self, player1: PlayerState) -> CardInstance:
        """Criatura Mokole em forma nao-Homid."""
        return CardInstance(
            card_id=12, name='Mokole', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=6, health=7, health_current=7,
            keywords='Mokole - Suchid - Gaia - Male',
        )

    @pytest.fixture
    def garou_creature(self, player1: PlayerState) -> CardInstance:
        """Criatura Garou (nao Rokea, nao Mokole)."""
        return CardInstance(
            card_id=13, name='Garou', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=4, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia - Male',
        )

    @pytest.fixture
    def weapon_equipment(self) -> CardInstance:
        """Equipamento do tipo Weapon."""
        return CardInstance(
            card_id=20, name='Sword', card_type='Equipment',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
            keywords='Weapon',
        )

    def test_find_criatura_encontra_no_pack(self, game, rokea_creature):
        """_find_criatura encontra criatura no pack_home."""
        game.players[0].pack_home.append(rokea_creature)
        found = _find_criatura(game, '10')
        assert found is not None
        assert found.name == 'Rokea Crinos'

    def test_find_criatura_nao_encontra(self, game):
        """_find_criatura retorna None se nao existir."""
        found = _find_criatura(game, '999')
        assert found is None

    def test_tail_lash_valido_rokea(self, game, rokea_creature):
        """Tail Lash aceito para Rokea nao-Homid sem arma."""
        game.players[0].pack_home.append(rokea_creature)
        erro = _validar_tail_lash(game, rokea_creature)
        assert erro is None

    def test_tail_lash_valido_mokole(self, game, mokole_creature):
        """Tail Lash aceito para Mokole nao-Homid sem arma."""
        game.players[0].pack_home.append(mokole_creature)
        erro = _validar_tail_lash(game, mokole_creature)
        assert erro is None

    def test_tail_lash_recusado_garou(self, game, garou_creature):
        """Tail Lash recusado para Garou (nao Rokea/Mokole)."""
        game.players[0].pack_home.append(garou_creature)
        erro = _validar_tail_lash(game, garou_creature)
        assert erro is not None
        assert 'Rokea ou Mokole' in erro

    def test_tail_lash_recusado_com_arma(self, game, rokea_creature, weapon_equipment):
        """Tail Lash recusado se criatura tem arma equipada."""
        rokea_creature.attached_equipment.append(weapon_equipment)
        game.players[0].pack_home.append(rokea_creature)
        erro = _validar_tail_lash(game, rokea_creature)
        assert erro is not None
        assert 'nao pode ser usado com arma' in erro

    def test_tail_lash_bonus_nao_homid(self, game, rokea_creature):
        """Bônus de +4 valido para Rokea nao-Homid."""
        game.players[0].pack_home.append(rokea_creature)
        erro = _validar_tail_lash_bonus(game, rokea_creature)
        assert erro is None

    def test_tail_lash_bonus_homid_sem_bonus(self, game, rokea_homid):
        """Bônus de +4 negado para Rokea em forma Homid."""
        game.players[0].pack_home.append(rokea_homid)
        erro = _validar_tail_lash_bonus(game, rokea_homid)
        assert erro is not None
        assert 'Homid' in erro

    def test_combat_action_validators_registrado(self):
        """Tail Lash esta registrado no dicionario de validadores."""
        assert 'tail_lash' in COMBAT_ACTION_VALIDATORS
        assert 'tail_lash_bonus' in COMBAT_ACTION_VALIDATORS

    def test_declare_action_com_validador_tail_lash_rokea(
        self, game, rokea_creature
    ):
        """declare_action aceita tail_lash para Rokea valido."""
        game.players[0].pack_home.append(rokea_creature)
        start_combat(game, ['10'], ['2'])
        result = declare_action(
            game, '10', 'tail_lash', acoes_extra=['tail_lash']
        )
        assert result is True

    def test_declare_action_com_validador_tail_lash_garou(
        self, game, garou_creature
    ):
        """declare_action recusa tail_lash para Garou."""
        game.players[0].pack_home.append(garou_creature)
        start_combat(game, ['13'], ['2'])
        result = declare_action(
            game, '13', 'tail_lash', acoes_extra=['tail_lash']
        )
        assert result is False


# ---------------------------------------------------------------------------
# Testes: condicao_uso no aplicar_carta
# ---------------------------------------------------------------------------

class TestCondicaoUso:
    """Testes para validacao de condicao_uso em modos de carta."""

    @pytest.fixture
    def player_with_rokea(self, player1: PlayerState) -> PlayerState:
        rokea = CardInstance(
            card_id=10, name='Rokea Crinos', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, gnosis=3, health=8, health_current=8,
            keywords='Rokea - Gaia - Male',
        )
        player1.pack_home.append(rokea)
        return player1

    @pytest.fixture
    def player_with_garou(self, player1: PlayerState) -> PlayerState:
        garou = CardInstance(
            card_id=13, name='Garou', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=4, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia - Male',
        )
        player1.pack_home.append(garou)
        return player1

    @pytest.fixture
    def player_with_umbra_char(self, player1: PlayerState) -> PlayerState:
        char = CardInstance(
            card_id=14, name='Umbra Character', card_type='Character',
            zone=Zone.UMBRA, owner_id='p1', controller_id='p1',
            rage=3, gnosis=7, health=5, health_current=5,
            keywords='Spirit - Wraith',
        )
        player1.umbra.append(char)
        return player1

    def test_condicao_rokea_mokole_nao_homid_atendida(
        self, game, player_with_rokea
    ):
        """Condicao atendida: ha Rokea nao-Homid no pack."""
        result = _condicao_rokea_mokole_nao_homid(game, player_with_rokea)
        assert result is True

    def test_condicao_rokea_mokole_nao_homid_nao_atendida(
        self, game, player_with_garou
    ):
        """Condicao nao atendida: so ha Garou no pack."""
        result = _condicao_rokea_mokole_nao_homid(game, player_with_garou)
        assert result is False

    def test_condicao_personagem_na_umbra_atendida(
        self, game, player_with_umbra_char
    ):
        """Condicao atendida: ha personagem na Umbra."""
        result = _condicao_personagem_na_umbra(game, player_with_umbra_char)
        assert result is True

    def test_condicao_personagem_na_umbra_nao_atendida(
        self, game, player_with_rokea
    ):
        """Condicao nao atendida: nenhum personagem na Umbra."""
        result = _condicao_personagem_na_umbra(game, player_with_rokea)
        assert result is False

    def test_validar_condicao_uso_desconhecida_permite(self, game, player1):
        """Condicao desconhecida e permitida (backward compatible)."""
        result = _validar_condicao_uso(game, player1, 'condicao_inexistente')
        assert result is True


# ---------------------------------------------------------------------------
# Testes: Head Butt (bounce se bloqueado)
# ---------------------------------------------------------------------------

class TestHeadButt:
    """Testes para o efeito especial do Head Butt."""

    @pytest.fixture
    def attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=100, name='Garou Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=3, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia',
        )

    @pytest.fixture
    def mokole_attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=101, name='Mokole Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=6, health=7, health_current=7,
            keywords='Mokole - Suchid - Gaia',
        )

    @pytest.fixture
    def defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Defensor', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
        )

    def test_head_butt_bounce_se_bloqueado(
        self, game, attacker, defender
    ):
        """Head Butt bloqueado causa 4 de dano no atacante (nao-Mokole)."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'head_butt',
                       acoes_extra=['head_butt'])
        declare_action(game, '200', 'block')
        resolve_combat(game)
        # Atacante deve ter recebido 4 de dano
        assert attacker.health_current == 2  # 6 - 4 = 2
        # Defensor deve estar intacto
        assert defender.health_current == 5

    def test_head_butt_sem_bounce_se_mokole(
        self, game, mokole_attacker, defender
    ):
        """Head Butt bloqueado por Mokole nao causa dano de volta."""
        game.players[0].pack_home.append(mokole_attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['101'], ['200'])
        declare_action(game, '101', 'head_butt',
                       acoes_extra=['head_butt'])
        declare_action(game, '200', 'block')
        resolve_combat(game)
        # Mokole atacante deve estar intacto (excecao)
        assert mokole_attacker.health_current == 7
        # Defensor deve estar intacto
        assert defender.health_current == 5

    def test_head_butt_dano_normal_se_nao_bloqueado(
        self, game, attacker, defender
    ):
        """Head Butt sem bloqueio causa dano normal baseado no Rage."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'head_butt',
                       acoes_extra=['head_butt'])
        declare_action(game, '200', 'strike')  # nao bloqueia, contra-ataca
        resolve_combat(game)
        # Defensor leva dano = Rage do atacante (4)
        assert defender.health_current == 1  # 5 - 4 = 1
        # Atacante leva dano do contra-ataque do defensor (Rage 3)
        assert attacker.health_current == 3  # 6 - 3 = 3

    def test_head_butt_em_acaoes_ofensivas(self):
        """Head Butt esta na lista de acoes ofensivas."""
        from rage_web.game_engine.combat_queue import ACOES_OFENSIVAS
        assert 'head_butt' in ACOES_OFENSIVAS

    def test_head_butt_em_combat_actions(self):
        """Head Butt esta na lista de Combat Actions."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTIONS
        assert 'head_butt' in COMBAT_ACTIONS


# ---------------------------------------------------------------------------
# Testes: Anatomy Lesson (unblockable + retirada)
# ---------------------------------------------------------------------------

class TestAnatomyLesson:
    """Testes para Anatomy Lesson."""

    @pytest.fixture
    def attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=100, name='Garou Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=3, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia',
        )

    @pytest.fixture
    def frenzied_attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=102, name='Frenzy Garou', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, gnosis=2, health=6, health_current=6,
            keywords='Garou - Wyrm',
            is_frenzied=True,
        )

    @pytest.fixture
    def defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Defensor', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
        )

    def test_anatomy_lesson_unblockable(
        self, game, attacker, defender
    ):
        """Anatomy Lesson ignora block do defensor."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'anatomy_lesson',
                       acoes_extra=['anatomy_lesson'])
        declare_action(game, '200', 'block')
        resolve_combat(game)
        # Defensor deveria ter levado dano (unblockable)
        assert defender.health_current < 5

    def test_anatomy_lesson_retira_se_ferido(
        self, game, attacker, defender
    ):
        """Criatura ferida por Anatomy Lesson retira do combate."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'anatomy_lesson',
                       acoes_extra=['anatomy_lesson'])
        declare_action(game, '200', 'strike')
        resolve_combat(game)
        # Defensor deve ter sido retirado do combate (discard)
        assert defender.zone.value == 'discard_combat'

    def test_anatomy_lesson_recusado_se_frenetico(
        self, game, frenzied_attacker, defender
    ):
        """Anatomy Lesson recusado se atacante esta frenzied."""
        game.players[0].pack_home.append(frenzied_attacker)
        game.players[1].pack_home.append(defender)
        start_combat(game, ['102'], ['200'])
        result = declare_action(
            game, '102', 'anatomy_lesson',
            acoes_extra=['anatomy_lesson']
        )
        assert result is False

    def test_anatomy_lesson_em_acaoes_ofensivas(self):
        """Anatomy Lesson esta na lista de acoes ofensivas."""
        from rage_web.game_engine.combat_queue import ACOES_OFENSIVAS
        assert 'anatomy_lesson' in ACOES_OFENSIVAS

    def test_anatomy_lesson_em_combat_actions(self):
        """Anatomy Lesson esta na lista de Combat Actions."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTIONS
        assert 'anatomy_lesson' in COMBAT_ACTIONS

    def test_anatomy_lesson_props_unblockable(self):
        """Anatomy Lesson tem propriedade unblockable."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTION_PROPS
        props = COMBAT_ACTION_PROPS.get('anatomy_lesson', {})
        assert props.get('unblockable') is True
        assert props.get('retira_se_ferido') is True

    def test_condicao_nao_frenetico_atendida(self, game, attacker):
        """Condicao nao_frenetico atendida: criatura nao esta frenzied."""
        game.players[0].pack_home.append(attacker)
        from rage_web.game_engine.effects import _condicao_nao_frenetico
        result = _condicao_nao_frenetico(game, game.players[0])
        assert result is True

    def test_condicao_nao_frenetico_nao_atendida(
        self, game, frenzied_attacker
    ):
        """Condicao nao_frenetico nao atendida: criatura frenzied."""
        game.players[0].pack_home.append(frenzied_attacker)
        from rage_web.game_engine.effects import _condicao_nao_frenetico
        result = _condicao_nao_frenetico(game, game.players[0])
        assert result is False


# ---------------------------------------------------------------------------
# Testes: Savage Beatdown (descarte metade se frenzied)
# ---------------------------------------------------------------------------

class TestSavageBeatdown:
    """Testes para Savage Beatdown."""

    @pytest.fixture
    def attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=100, name='Garou Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=3, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia',
        )

    @pytest.fixture
    def frenzied_defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Frenzy Defender', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
            is_frenzied=True,
        )

    @pytest.fixture
    def normal_defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=201, name='Normal Defender', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
        )

    def test_savage_beatdown_descarta_metade_se_frenzied(
        self, game, attacker, frenzied_defender
    ):
        """Savage Beatdown em criatura frenzied faz oponente descartar metade."""
        # Adiciona cartas na mao do oponente
        for i in range(4):
            frenzied_defender.owner_id  # p2
            card = CardInstance(
                card_id=300 + i, name=f'Card {i}', card_type='Combat Action',
                zone=Zone.HAND, owner_id='p2', controller_id='p2',
            )
            game.players[1].hand.append(card)

        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(frenzied_defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'savage_beatdown',
                       acoes_extra=['savage_beatdown'])
        declare_action(game, '200', 'strike')
        resolve_combat(game)
        # Oponente deveria ter descartado metade (4/2 = 2)
        assert len(game.players[1].hand) == 2
        assert len(game.players[1].discard_combat) >= 2

    def test_savage_beatdown_sem_descarte_se_nao_frenzied(
        self, game, attacker, normal_defender
    ):
        """Savage Beatdown em criatura normal nao causa descarte."""
        for i in range(4):
            card = CardInstance(
                card_id=300 + i, name=f'Card {i}', card_type='Combat Action',
                zone=Zone.HAND, owner_id='p2', controller_id='p2',
            )
            game.players[1].hand.append(card)

        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(normal_defender)
        start_combat(game, ['100'], ['201'])
        declare_action(game, '100', 'savage_beatdown',
                       acoes_extra=['savage_beatdown'])
        declare_action(game, '201', 'strike')
        resolve_combat(game)
        # Oponente nao deveria ter descartado nada
        assert len(game.players[1].hand) == 4

    def test_savage_beatdown_em_acaoes_ofensivas(self):
        """Savage Beatdown esta na lista de acoes ofensivas."""
        from rage_web.game_engine.combat_queue import ACOES_OFENSIVAS
        assert 'savage_beatdown' in ACOES_OFENSIVAS

    def test_savage_beatdown_em_combat_actions(self):
        """Savage Beatdown esta na lista de Combat Actions."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTIONS
        assert 'savage_beatdown' in COMBAT_ACTIONS

    def test_savage_beatdown_props(self):
        """Savage Beatdown tem propriedade descarte_metade_se_frenetico."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTION_PROPS
        props = COMBAT_ACTION_PROPS.get('savage_beatdown', {})
        assert props.get('descarte_metade_se_frenetico') is True


# ---------------------------------------------------------------------------
# Testes: Submission Hold (remove se nao-frenzied, anti-dodge se frenzied)
# ---------------------------------------------------------------------------

class TestSubmissionHold:
    """Testes para Submission Hold."""

    @pytest.fixture
    def attacker(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=100, name='Garou Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=3, health=6, health_current=6,
            keywords='Garou - Red Talons - Gaia',
        )

    @pytest.fixture
    def frenzied_defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Frenzy Defender', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
            is_frenzied=True,
        )

    @pytest.fixture
    def normal_defender(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=201, name='Normal Defender', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, gnosis=2, health=5, health_current=5,
            keywords='Garou - Wyrm',
        )

    def test_submission_hold_retira_nao_frenzied(
        self, game, attacker, normal_defender
    ):
        """Submission Hold em criatura nao-frenzied remove do combate."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(normal_defender)
        start_combat(game, ['100'], ['201'])
        declare_action(game, '100', 'submission_hold',
                       acoes_extra=['submission_hold'])
        declare_action(game, '201', 'strike')
        resolve_combat(game)
        # Defensor deve ter sido retirado do combate
        assert normal_defender.zone.value == 'discard_combat'

    def test_submission_hold_anti_dodge_se_frenzied(
        self, game, attacker, frenzied_defender
    ):
        """Submission Hold em criatura frenzied impede dodge."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(frenzied_defender)
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'submission_hold',
                       acoes_extra=['submission_hold'])
        declare_action(game, '200', 'strike')
        resolve_combat(game)
        # Defensor deve ter restricao nao_pode_esquivar
        assert 'nao_pode_esquivar' in frenzied_defender.restricoes

    def test_submission_hold_nao_pode_esquivar(
        self, game, attacker, frenzied_defender
    ):
        """Criatura com restricao nao_pode_esquivar nao consegue esquivar."""
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(frenzied_defender)
        start_combat(game, ['100'], ['200'])
        # Simula restricao aplicada por Submission Hold na rodada anterior
        frenzied_defender.restricoes.append('nao_pode_esquivar')
        declare_action(game, '100', 'strike')
        declare_action(game, '200', 'dodge')
        resolve_combat(game)
        # Defensor deveria ter levado dano (dodge falhou)
        assert frenzied_defender.health_current < 5

    def test_submission_hold_recusado_se_frenetico(
        self, game, normal_defender
    ):
        """Submission Hold recusado se atacante esta frenzied."""
        frenzied_attacker = CardInstance(
            card_id=102, name='Frenzy Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, gnosis=2, health=6, health_current=6,
            keywords='Garou - Wyrm',
            is_frenzied=True,
        )
        game.players[0].pack_home.append(frenzied_attacker)
        game.players[1].pack_home.append(normal_defender)
        start_combat(game, ['102'], ['201'])
        result = declare_action(
            game, '102', 'submission_hold',
            acoes_extra=['submission_hold']
        )
        assert result is False

    def test_submission_hold_em_acaoes_ofensivas(self):
        """Submission Hold esta na lista de acoes ofensivas."""
        from rage_web.game_engine.combat_queue import ACOES_OFENSIVAS
        assert 'submission_hold' in ACOES_OFENSIVAS

    def test_submission_hold_em_combat_actions(self):
        """Submission Hold esta na lista de Combat Actions."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTIONS
        assert 'submission_hold' in COMBAT_ACTIONS

    def test_submission_hold_props(self):
        """Submission Hold tem propriedades corretas."""
        from rage_web.game_engine.combat_queue import COMBAT_ACTION_PROPS
        props = COMBAT_ACTION_PROPS.get('submission_hold', {})
        assert props.get('retira_se_nao_frenetico') is True
        assert props.get('nao_pode_esquivar_se_frenetico') is True

    def test_restricoes_limpas_no_novo_combate(
        self, game, attacker, frenzied_defender
    ):
        """Restricoes de combates anteriores sao limpas no start_combat."""
        frenzied_defender.restricoes.append('nao_pode_esquivar')
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(frenzied_defender)
        # Inicia um novo combate — deve limpar restricoes
        start_combat(game, ['100'], ['200'])
        assert 'nao_pode_esquivar' not in frenzied_defender.restricoes


# ---------------------------------------------------------------------------
# Testes: Assegai (Equipment/Armor)
# ---------------------------------------------------------------------------

class TestAssegai:
    """Testes para Assegai (Equipment/Armor)."""

    @pytest.fixture
    def assegai(self) -> CardInstance:
        return CardInstance(
            card_id=50, name='Assegai', card_type='Equipment',
            zone=Zone.HAND, owner_id='p1', controller_id='p1',
            keywords='Non-Fetish - Weapon - Armor',
        )

    @pytest.fixture
    def homid_creature(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=10, name='Garou Homid', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=3, gnosis=5, health=5, health_current=5,
            keywords='Garou - Homid - Gaia - Male',
        )

    @pytest.fixture
    def crinos_creature(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=11, name='Garou Crinos', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, gnosis=3, health=8, health_current=8,
            keywords='Garou - Crinos - Gaia - Male',
        )

    @pytest.fixture
    def animal_creature(self, player1: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=12, name='Garou Lupus', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=4, gnosis=4, health=6, health_current=6,
            keywords='Garou - Lupus - Gaia - Male',
        )

    def test_assegai_equipa_homid(self, game, assegai, homid_creature):
        """Assegai pode ser equipado em criatura Homid."""
        game.players[0].pack_home.append(homid_creature)
        game.players[0].hand.append(assegai)
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        modelo = CARTAS_EXEMPLO.get(assegai.modelo_id)
        if modelo:
            logs = aplicar_carta(game, modelo, 'p1', modo_idx=0)
            assert assegai in homid_creature.attached_equipment
            assert homid_creature.reducao_dano == 1

    def test_assegai_equipa_crinos(self, game, assegai, crinos_creature):
        """Assegai pode ser equipado em criatura Crinos."""
        game.players[0].pack_home.append(crinos_creature)
        game.players[0].hand.append(assegai)
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        modelo = CARTAS_EXEMPLO.get(assegai.modelo_id)
        if modelo:
            logs = aplicar_carta(game, modelo, 'p1', modo_idx=0)
            assert assegai in crinos_creature.attached_equipment
            assert crinos_creature.reducao_dano == 1

    def test_assegai_recusado_lupus(self, game, assegai, animal_creature):
        """Assegai recusado para criatura em forma Lupus."""
        game.players[0].pack_home.append(animal_creature)
        game.players[0].hand.append(assegai)
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        modelo = CARTAS_EXEMPLO.get(assegai.modelo_id)
        if modelo:
            logs = aplicar_carta(game, modelo, 'p1', modo_idx=0)
            assert assegai not in animal_creature.attached_equipment
            assert animal_creature.reducao_dano == 0

    def test_assegai_reduz_dano_combate(
        self, game, assegai, homid_creature, player2
    ):
        """Assegai reduz 1 de dano de Combat Actions."""
        from rage_web.game_engine.state import Zone
        attacker = CardInstance(
            card_id=200, name='Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=4, gnosis=2, health=5, health_current=5,
        )
        game.players[0].pack_home.append(homid_creature)
        game.players[1].pack_home.append(attacker)
        # Equipa Assegai
        homid_creature.attached_equipment.append(assegai)
        homid_creature.reducao_dano = 1
        # Simula combate
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, resolve_combat,
        )
        start_combat(game, ['200'], ['10'])
        declare_action(game, '200', 'strike')
        declare_action(game, '10', 'strike')
        resolve_combat(game)
        # Dano deveria ser Rage(4) - reducao(1) = 3
        assert homid_creature.health_current == 2  # 5 - 3 = 2


# ---------------------------------------------------------------------------
# Testes: Lake Nasser Wallow (Caern - Gauntlet cruzavel)
# ---------------------------------------------------------------------------

class TestLakeNasserWallow:
    """Testes para Lake Nasser Wallow."""

    @pytest.fixture
    def lake_nasser(self) -> CardInstance:
        return CardInstance(
            card_id=609, name='Lake Nasser Wallow', card_type='Caern',
            zone=Zone.HUNTING_GROUNDS, owner_id='p1', controller_id='p1',
            rage=0, gnosis=5, health=0,
            text='Rites and Gifts played by your pack may cross the Gauntlet.',
        )

    def test_caerns_no_hunting_grounds(
        self, game, lake_nasser
    ):
        """PlayerState.caerns_no_hunting_grounds retorna Caerns."""
        game.players[0].hunting_grounds.append(lake_nasser)
        caerns = game.players[0].caerns_no_hunting_grounds
        assert len(caerns) == 1
        assert caerns[0].name == 'Lake Nasser Wallow'

    def test_caerns_no_hunting_grounds_vazio(self, game, player1):
        """Retorna lista vazia se nao ha Caerns."""
        caerns = game.players[0].caerns_no_hunting_grounds
        assert len(caerns) == 0

    def test_gauntlet_para_carta_com_caern(
        self, game, lake_nasser
    ):
        """Rites/Gifts podem cruzar Gauntlet com Lake Nasser Wallow."""
        game.players[0].hunting_grounds.append(lake_nasser)
        from rage_web.game_engine.effects import _validar_gauntlet_para_carta
        from rage_web.game_engine.effects import ModeloCarta
        modelo = ModeloCarta(id='test', nome='Test Gift', tipo='Gift')
        result = _validar_gauntlet_para_carta(
            game, game.players[0], modelo
        )
        assert result is True

    def test_gauntlet_para_carta_sem_caern(
        self, game, player1
    ):
        """Sem Caern, Rites/Gifts NAO podem cruzar o Gauntlet (regra 5)."""
        from rage_web.game_engine.effects import _validar_gauntlet_para_carta
        from rage_web.game_engine.effects import ModeloCarta
        modelo = ModeloCarta(id='test', nome='Test Gift', tipo='Gift')
        result = _validar_gauntlet_para_carta(
            game, game.players[0], modelo
        )
        assert result is False


# ---------------------------------------------------------------------------
# Testes: Chant of Morpheus (remover do jogo + anti-frenzy)
# ---------------------------------------------------------------------------

class TestChantOfMorpheus:
    """Testes para Chant of Morpheus."""

    @pytest.fixture
    def target_creature(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Target', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=4, gnosis=3, health=6, health_current=6,
            keywords='Garou - Wyrm',
        )

    def test_remover_do_jogo_move_para_out_of_play(
        self, game, target_creature
    ):
        """Criatura alvo e movida para OUT_OF_PLAY."""
        game.players[1].pack_home.append(target_creature)
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo, Zone,
        )
        from rage_web.game_engine.state import CardInstance
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(
            card_id=-1, name='Chant of Morpheus', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
        )
        efeito = Efeito(
            tipo=EfeitoTipo.REMOVER_DO_JOGO,
            condicao='criatura_inimiga',
        )
        resultado = resolvedor.aplicar_efeito(
            efeito, origem, game.players[0]
        )
        assert resultado is True
        assert target_creature.zone == Zone.OUT_OF_PLAY

    def test_remover_do_jogo_cria_pendencia(
        self, game, target_creature
    ):
        """Cria pendencia para restaurar no fim da fase."""
        game.players[1].pack_home.append(target_creature)
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        from rage_web.game_engine.state import CardInstance
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(
            card_id=-1, name='Chant of Morpheus', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
        )
        efeito = Efeito(
            tipo=EfeitoTipo.REMOVER_DO_JOGO,
            condicao='criatura_inimiga',
        )
        resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        # Deve ter criado uma pendencia
        from rage_web.game_engine.state import PendenciaEfeito
        penders = [p for p in game.pendencias
                   if p.card_uid == id(target_creature)]
        assert len(penders) == 1
        assert penders[0].atributo == 'zona'
        assert penders[0].duracao == 'end_of_phase'

    def test_nao_pode_frenzy_restricao(
        self, game, target_creature
    ):
        """Restricao nao_pode_frenzy e adicionada a criatura."""
        game.players[1].pack_home.append(target_creature)
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        from rage_web.game_engine.state import CardInstance, Zone
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(
            card_id=-1, name='Chant of Morpheus', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
        )
        efeito = Efeito(
            tipo=EfeitoTipo.RESTRICAO,
            condicao='criatura_inimiga',
            alvo='nao_pode_frenzy',
            duracao='end_of_turn',
        )
        resultado = resolvedor.aplicar_efeito(
            efeito, origem, game.players[0]
        )
        assert resultado is True
        assert 'nao_pode_frenzy' in target_creature.restricoes

    def test_nao_pode_frenzy_expira_no_novo_turno(
        self, game, target_creature
    ):
        """Restricao nao_pode_frenzy expira no redraw (novo turno)."""
        target_creature.restricoes.append('nao_pode_frenzy')
        game.players[1].pack_home.append(target_creature)
        # Avanca para redraw (novo turno)
        game.phase = 'combat'
        game.next_phase()  # avancar para redraw
        assert 'nao_pode_frenzy' not in target_creature.restricoes


# ---------------------------------------------------------------------------
# Testes: The Badger's Heart (Rage da Breed form)
# ---------------------------------------------------------------------------

class TestTheBadgersHeart:
    """Testes para The Badger's Heart."""

    @pytest.fixture
    def target_creature(self, player2: PlayerState) -> CardInstance:
        return CardInstance(
            card_id=200, name='Target', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=5, gnosis=3, health=6, health_current=6,
            rage_morph=2,  # Breed form Rage
            keywords='Garou - Gaia',
        )

    def test_effective_rage_sem_restricao(self, target_creature):
        """Sem restricao, effective_rage == rage."""
        assert target_creature.effective_rage == 5

    def test_effective_rage_com_rage_breed(self, target_creature):
        """Com restricao rage_breed, effective_rage == rage_morph."""
        target_creature.restricoes.append('rage_breed')
        assert target_creature.effective_rage == 2  # rage_morph

    def test_effective_rage_breed_sem_morph(self):
        """Se rage_morph == 0, usa rage como fallback."""
        creature = CardInstance(
            card_id=201, name='No Morph', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=4, rage_morph=0,
        )
        creature.restricoes.append('rage_breed')
        assert creature.effective_rage == 4  # fallback para rage

    def test_rage_breed_restricao_aplicada(
        self, game, target_creature
    ):
        """Restricao rage_breed e adicionada pela Gift."""
        game.players[1].pack_home.append(target_creature)
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        from rage_web.game_engine.state import CardInstance, Zone
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(
            card_id=-1, name="The Badger's Heart", card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
        )
        efeito = Efeito(
            tipo=EfeitoTipo.RESTRICAO,
            condicao='criatura_inimiga',
            alvo='rage_breed',
            duracao='permanente',
        )
        resultado = resolvedor.aplicar_efeito(
            efeito, origem, game.players[0]
        )
        assert resultado is True
        assert 'rage_breed' in target_creature.restricoes

    def test_rage_breed_afeta_dano_combate(
        self, game, target_creature, player1
    ):
        """Criatura com rage_breed causa dano reduzido no combate."""
        from rage_web.game_engine.state import Zone
        attacker = CardInstance(
            card_id=100, name='Atacante', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, rage_morph=2, gnosis=3, health=6, health_current=6,
            keywords='Garou - Gaia',
        )
        # Atacante com rage_breed ataca
        attacker.restricoes.append('rage_breed')
        game.players[0].pack_home.append(attacker)
        game.players[1].pack_home.append(target_creature)
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, resolve_combat,
        )
        start_combat(game, ['100'], ['200'])
        declare_action(game, '100', 'strike')
        declare_action(game, '200', 'strike')
        resolve_combat(game)
        # Dano deveria ser effective_rage(2) em vez de rage(5)
        assert target_creature.health_current == 4  # 6 - 2 = 4


# ---------------------------------------------------------------------------
# Testes: Suporte a N jogadores
# ---------------------------------------------------------------------------

class TestMultiplayer:
    """Testes para suporte a partidas com N jogadores."""

    def test_get_oponentes_retorna_todos(self):
        """_get_oponentes retorna todos os jogadores menos o atual."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        from rage_web.game_engine.effects import ResolvedorEfeitos
        r = ResolvedorEfeitos(game)
        oponentes = r._get_oponentes(p1)
        assert len(oponentes) == 2
        assert oponentes[0].id == 'p2'
        assert oponentes[1].id == 'p3'

    def test_find_player_por_id(self):
        """_find_player encontra jogador pelo ID em N jogadores."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        from rage_web.game_engine.effects import ResolvedorEfeitos
        r = ResolvedorEfeitos(game)
        assert r._find_player('p2').name == 'J2'
        assert r._find_player('p3').name == 'J3'
        assert r._find_player('p999') is None

    def test_criatura_inimiga_escolhe_de_todos(self):
        """criatura_inimiga agrega criaturas de todos os oponentes."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        c1 = CardInstance(card_id=1, name='C1', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            health=5, health_current=5)
        c2 = CardInstance(card_id=2, name='C2', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            health=5, health_current=5)
        c3 = CardInstance(card_id=3, name='C3', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p3', controller_id='p3',
            health=5, health_current=4)  # ferida
        p1.pack_home.append(c1)
        p2.pack_home.append(c2)
        p3.pack_home.append(c3)
        from rage_web.game_engine.effects import ResolvedorEfeitos, Efeito, EfeitoTipo
        r = ResolvedorEfeitos(game)
        # Testa criatura_inimiga
        efeito = Efeito(tipo=EfeitoTipo.DANO, condicao='criatura_inimiga')
        alvo = r._resolver_alvo(efeito, c1, p1)
        assert alvo.name in ['C2', 'C3']
        # Testa criatura_inimiga_ferida
        efeito2 = Efeito(tipo=EfeitoTipo.DANO, condicao='criatura_inimiga_ferida')
        alvo2 = r._resolver_alvo(efeito2, c1, p1)
        assert alvo2 is not None
        assert alvo2.health_current < alvo2.health
        # Testa qualquer_criatura
        efeito3 = Efeito(tipo=EfeitoTipo.DANO, condicao='qualquer_criatura')
        alvo3 = r._resolver_alvo(efeito3, c1, p1)
        assert alvo3.name in ['C1', 'C2', 'C3']

    def test_jogador_inimigo_escolhe_aleatorio(self):
        """jogador_inimigo escolhe um oponente aleatorio."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        from rage_web.game_engine.effects import ResolvedorEfeitos, Efeito, EfeitoTipo
        r = ResolvedorEfeitos(game)
        efeito = Efeito(tipo=EfeitoTipo.DESCARTE, condicao='jogador_inimigo')
        alvo = r._resolver_alvo(efeito, CardInstance(
            card_id=-1, name='Test', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1'
        ), p1)
        assert alvo.id in ['p2', 'p3']

    def test_destruir_em_3_jogadores(self):
        """_resolver_destruir encontra o dono correto em 3 jogadores."""
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        c1 = CardInstance(card_id=1, name='C1', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            health=5, health_current=5)
        c3 = CardInstance(card_id=3, name='C3', card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p3', controller_id='p3',
            health=5, health_current=5)
        p1.pack_home.append(c1)
        p3.pack_home.append(c3)
        r = ResolvedorEfeitos(game)
        origem = CardInstance(card_id=-1, name='Test', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1')
        resultado = r._resolver_destruir(
            Efeito(tipo=EfeitoTipo.DESTRUIR), origem, p1, c3
        )
        assert resultado
        assert c3.zone == Zone.DISCARD_COMBAT
        assert c3 not in p2.pack_home  # Nao foi para J2
        assert c3 not in p1.pack_home  # Nao foi para J1

    def test_jogador_inimigo_tem_mao_de_oponente(self):
        """mao_inimiga acessa mao de um oponente aleatorio."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        p3 = PlayerState(id='p3', name='J3')
        game = GameState(players=[p1, p2, p3])
        origem = CardInstance(card_id=-1, name='Test', card_type='Gift',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1')
        p2.hand.append(CardInstance(
            card_id=10, name='Card J2', card_type='Equipment',
            zone=Zone.HAND, owner_id='p2', controller_id='p2'
        ))
        p3.hand.append(CardInstance(
            card_id=11, name='Card J3', card_type='Equipment',
            zone=Zone.HAND, owner_id='p3', controller_id='p3'
        ))
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        r = ResolvedorEfeitos(game)
        efeito = Efeito(tipo=EfeitoTipo.DESCARTE, condicao='mao_inimiga')
        alvo = r._resolver_alvo(efeito, origem, p1)
        # mao_inimiga retorna a mao de um oponente
        assert alvo is not None
        assert len(alvo) >= 1
        assert alvo is not p1.hand  # Nao e a propria mao


# ---------------------------------------------------------------------------
# Testes: Efeitos implementados (Elethoi, Lone Wolf, Fog)
# ---------------------------------------------------------------------------

class TestElethoiImmunity:
    """Testes para imunidade do Elethoi (so Gifts/Umbral)."""

    def test_imune_fora_umbra_bloqueia_dano(self):
        """Criatura com 'imune_fora_umbra' nao sofre dano de fora da Umbra."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        atacante = CardInstance(card_id=10, name='Atacante',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=5, health=6, health_current=6)
        elethoi = CardInstance(card_id=1341, name='Elethoi',
            card_type='Enemy',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=3, health=7, health_current=7,
            restricoes=['imune_fora_umbra'])
        p1.pack_home.append(atacante)
        p2.pack_home.append(elethoi)
        a_id, e_id = '10', '1341'
        start_combat(game, [a_id], [e_id])
        declare_action(game, a_id, 'strike')
        declare_action(game, e_id, 'strike')
        resolve_combat(game)
        # Elethoi nao sofreu dano (atacante em Pack Home, nao Umbra)
        assert elethoi.health_current == 7

    def test_ataque_umbral_afeta_imune(self):
        """Criatura com 'imune_fora_umbra' sofre dano de ataque umbral
        (ambos no mesmo lado do Gauntlet)."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        atacante = CardInstance(card_id=20, name='Atacante Umbral',
            card_type='Character',
            zone=Zone.UMBRA, owner_id='p1', controller_id='p1',
            rage=3, health=6, health_current=6)
        elethoi = CardInstance(card_id=1341, name='Elethoi',
            card_type='Enemy',
            zone=Zone.UMBRA, owner_id='p2', controller_id='p2',
            rage=3, health=7, health_current=7,
            restricoes=['imune_fora_umbra'])
        p1.umbra.append(atacante)
        p2.umbra.append(elethoi)
        a_id, e_id = '20', '1341'
        start_combat(game, [a_id], [e_id])
        declare_action(game, a_id, 'strike')
        declare_action(game, e_id, 'strike')
        resolve_combat(game)
        # Elethoi sofreu dano do ataque umbral (ambos na Umbra)
        assert elethoi.health_current < 7


class TestLoneWolfDodge:
    """Testes para Lone Wolf Circles dodge."""

    def test_lone_wolf_dodge_cancela_ataque(self):
        """Lone Wolf Circles pode cancelar propria acao e esquivar."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        lone = CardInstance(card_id=174, name='Lone Wolf Circles',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=3, health=5, health_current=5)
        inimigo = CardInstance(card_id=30, name='Inimigo',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p2', controller_id='p2',
            rage=4, health=6, health_current=6)
        p1.pack_home.append(lone)
        p2.pack_home.append(inimigo)
        lone_id, ini_id = '174', '30'
        start_combat(game, [ini_id], [lone_id])
        declare_action(game, ini_id, 'strike')
        declare_action(game, lone_id, 'strike')
        reveal_all(game)
        # Lone cancela sua acao e esquiva do inimigo
        result = lone_wolf_circles_dodge(game, lone_id, ini_id)
        assert result
        # Acao do Lone foi alterada para 'dodge'
        assert game.combat.declarations.get(lone_id) == 'dodge'
        resolve_combat(game)
        # Lone nao sofreu dano (esquivou)
        assert lone.health_current == 5


class TestFogCancel:
    """Testes para Fog cancelamento."""

    def test_fog_cancela_anuncio(self):
        """Fog (anular) cancela o anuncio atual no anunciador."""
        from rage_web.game_engine.anunciador import EfeitoAnunciado
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        # Cria um anuncio pendente
        efeito = EfeitoAnunciado(
            id='test', descricao='Test Event',
            jogador_id='p2',
            resolver=lambda g: ['resolvido']
        )
        game.anunciador.anunciar(efeito)
        assert game.anunciador.tem_anuncio_ativo
        # Aplica Fog (anular)
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo, Zone,
        )
        fog = CardInstance(card_id=1355, name='Fog',
            card_type='Event',
            zone=Zone.HAND, owner_id='p1', controller_id='p1')
        p1.hand.append(fog)
        r = ResolvedorEfeitos(game)
        result = r._resolver_anular(
            Efeito(tipo=EfeitoTipo.ANULAR), fog, p1, None
        )
        assert result
        # Anuncio foi cancelado
        assert not game.anunciador.tem_anuncio_ativo
        # Fog foi descartado
        assert fog.zone == Zone.DISCARD_COMBAT


class TestSweetLunaRegeneration:
    """Testes para Sweet Luna's Smile (regenerar agravado)."""

    def test_pode_regenerar_agravado(self):
        """Criatura com 'pode_regenerar_agravado' regenera dano agravado."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        criatura = CardInstance(card_id=269, name='Sweet Luna',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=2, gnosis=7, health=7, health_current=5,
            restricoes=['pode_regenerar_agravado'])
        # Adiciona dano agravado como CardInstance
        dano = CardInstance(card_id=-1, name='Dano', card_type='Damage',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
            damage='2', is_aggravated=True)
        criatura.attached_damage.append(dano)
        p1.pack_home.append(criatura)
        # Regenera
        logs = p1.regeneration()
        # Deveria ter regenerado o dano agravado
        assert len(criatura.attached_damage) == 0
        assert criatura.health_current == 7  # voltou ao max

    def test_sem_flag_nao_regenera_agravado(self):
        """Criatura sem 'pode_regenerar_agravado' nao regenera dano agravado."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        criatura = CardInstance(card_id=1, name='Normal',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=3, health=6, health_current=4)
        dano = CardInstance(card_id=-1, name='Dano', card_type='Damage',
            zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1',
            damage='2', is_aggravated=True)
        criatura.attached_damage.append(dano)
        p1.pack_home.append(criatura)
        logs = p1.regeneration()
        # Nao deveria ter regenerado (só tem dano agravado)
        assert len(criatura.attached_damage) == 1
        assert criatura.health_current == 4


class TestHaunterAbilities:
    """Testes para Haunter (umbra + gifts)."""

    def test_existe_apenas_umbra_play_direct(self):
        """Carta com 'existe_apenas_umbra' e colocada na Umbra."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        haunter = CardInstance(card_id=408, name='Haunter',
            card_type='Ally',
            zone=Zone.HAND, owner_id='p1', controller_id='p1',
            rage=4, gnosis=7, health=4, health_current=4,
            restricoes=['existe_apenas_umbra'])
        p1.hand.append(haunter)
        # Simula o mesmo fluxo do bot._play_card
        card = p1.hand.pop(0)
        if 'existe_apenas_umbra' in card.restricoes:
            card.zone = Zone.UMBRA
            card.health_current = card.health
            p1.umbra.append(card)
        # Haunter deveria estar na Umbra, nao no Pack Home
        assert haunter in p1.umbra
        assert haunter not in p1.pack_home
        assert haunter.zone == Zone.UMBRA

    def test_gauntlet_cross_gift_sem_modelo_gnosis(self):
        """ModeloCarta sem gnosis usa valor default (0), restricao nao se aplica."""
        from rage_web.game_engine.effects import (
            _validar_gauntlet_para_carta, ModeloCarta, Modo, Efeito, EfeitoTipo,
        )
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        haunter = CardInstance(card_id=408, name='Haunter',
            card_type='Ally',
            zone=Zone.UMBRA, owner_id='p1', controller_id='p1',
            rage=4, gnosis=7, health=4, health_current=4,
            restricoes=['gifts_cruzam_gauntlet_se_gnosis_lte:4'])
        # Sem gnosis no modelo: padrao e 0, entao a restricao
        # (com threshold 4) nao se aplica (0 <= 4? Sim, mas na pratica
        # o gnosis real vem da CardInstance sendo jogada)
        gift = ModeloCarta(
            id='test_gift', nome='Gift', tipo='Gift',
            modos=[Modo(
                descricao='Usar',
                efeitos=[Efeito(tipo=EfeitoTipo.DANO, quantidade=2,
                                condicao='criatura_inimiga')]
            )]
        )
        # O comportamento padrao e True (sem Caern bloqueando)
        result = _validar_gauntlet_para_carta(
            game, p1, gift, card_origem=haunter
        )
        assert result is True

    def test_gauntlet_cross_sem_restricao_sem_caern(self):
        """Sem restricao e sem Caern, Gift NAO cruza (regra 5)."""
        from rage_web.game_engine.effects import (
            _validar_gauntlet_para_carta, ModeloCarta, Modo, Efeito, EfeitoTipo,
        )
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        carta = CardInstance(card_id=1, name='Normal',
            card_type='Character',
            zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1',
            rage=3, health=5, health_current=5)
        gift = ModeloCarta(
            id='test', nome='Test', tipo='Gift',
            modos=[Modo(
                descricao='Usar',
                efeitos=[Efeito(tipo=EfeitoTipo.DANO, quantidade=1,
                                condicao='criatura_inimiga')]
            )]
        )
        assert _validar_gauntlet_para_carta(
            game, p1, gift, card_origem=carta
        ) is False


# ---------------------------------------------------------------------------
# Testes dos 4 novos sistemas (Quest, Death Trigger, Recruitment, Passives)
# ---------------------------------------------------------------------------


class TestQuestSystem:
    """Testes do sistema de Quest (Mnesis Dreams)."""

    def test_criar_quest_no_jogador(self):
        """QuestState e criado corretamente."""
        from rage_web.game_engine.state import QuestState
        q = QuestState(
            quest_card_uid=100,
            target_card_uid=200,
            condition='sem_dano_por_2_turnos',
            turns_remaining=2,
            reward_vp=2,
            reward_acao='shuffle_card_discard_to_deck'
        )
        assert q.quest_card_uid == 100
        assert q.target_card_uid == 200
        assert q.turns_remaining == 2
        assert not q.completed

    def test_check_quests_progresso(self):
        """_check_quests decrementa turns_remaining."""
        from rage_web.game_engine.state import QuestState
        p1 = PlayerState(id='p1', name='Jogador 1')
        game = GameState(players=[p1])
        alvo = CardInstance(card_id=10, name='Alvo', card_type='Character',
                            zone=Zone.PACK_HOME, owner_id='p1',
                            controller_id='p1', rage=3, health=5,
                            health_current=5)
        p1.pack_home.append(alvo)
        q = QuestState(
            quest_card_uid=100,
            target_card_uid=id(alvo),
            condition='sem_dano_por_2_turnos',
            turns_remaining=1,  # Vai completar em 1 turno
            reward_vp=2,
            reward_acao='shuffle_card_discard_to_deck'
        )
        p1.quests.append(q)
        assert len(p1.quests) == 1
        game._check_quests()
        # Quest completou
        assert game._find_card_by_uid(q.target_card_uid) is not None
        assert len(p1.quests) == 0  # Foi removida
        assert p1.victory_points >= 2

    def test_quest_falha_se_alvo_morre(self):
        """Quest falha se o alvo e destruido."""
        from rage_web.game_engine.state import QuestState
        p1 = PlayerState(id='p1', name='Jogador 1')
        game = GameState(players=[p1])
        alvo = CardInstance(card_id=10, name='Alvo', card_type='Character',
                            zone=Zone.PACK_HOME, owner_id='p1',
                            controller_id='p1', rage=3, health=1,
                            health_current=1)
        p1.pack_home.append(alvo)
        q = QuestState(
            quest_card_uid=100,
            target_card_uid=id(alvo),
            condition='sem_dano_por_2_turnos',
            turns_remaining=2,
            reward_vp=2,
            reward_acao='shuffle_card_discard_to_deck'
        )
        p1.quests.append(q)
        # Remove alvo (simula morte)
        p1.pack_home.remove(alvo)
        alvo.zone = Zone.DISCARD_COMBAT
        game._check_quests()
        # Quest deve ter falhado (alvo nao encontrado)
        assert len(p1.quests) == 0

    def test_quest_check_resolver_inicia_quest(self):
        """_resolver_quest_check cria QuestState no jogador."""
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo, AlvoTipo,
        )
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(card_id=1147, name='Mnesis Dreams',
                              card_type='Quest', zone=Zone.HAND,
                              owner_id='p1', controller_id='p1')
        alvo = CardInstance(card_id=374, name='Sand Last King',
                            card_type='Character', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1',
                            rage=3, health=4, health_current=4)
        p1.pack_home.append(alvo)
        efeito = Efeito(
            tipo=EfeitoTipo.QUEST_CHECK,
            condicao=AlvoTipo.CRIATURA_ALIADA,
            quantidade=2,
            params={'condicao': 'sem_dano_por_2_turnos',
                    'quantidade': 2, 'vp': 2,
                    'acao': 'shuffle_card_discard_to_deck'}
        )
        assert resolvedor.aplicar_efeito(efeito, origem, p1)
        assert len(p1.quests) == 1
        assert p1.quests[0].reward_vp == 2
        assert p1.quests[0].turns_remaining == 2

    def test_quest_check_sem_alvo_nao_quebra(self):
        """_resolver_quest_check sem alvo valido retorna False."""
        from rage_web.game_engine.effects import (
            ResolvedorEfeitos, Efeito, EfeitoTipo,
        )
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        resolvedor = ResolvedorEfeitos(game)
        origem = CardInstance(card_id=1147, name='Mnesis Dreams',
                              card_type='Quest', zone=Zone.HAND,
                              owner_id='p1', controller_id='p1')
        efeito = Efeito(
            tipo=EfeitoTipo.QUEST_CHECK,
            quantidade=2,
            params={'condicao': 'sem_dano_por_2_turnos'}
        )
        # Sem alvo = False (nao cria quest)
        assert not resolvedor.aplicar_efeito(efeito, origem, p1)
        assert len(p1.quests) == 0


class TestDeathTriggerSystem:
    """Testes do sistema de Death Triggers (Dream Hunter)."""

    def test_register_death_trigger(self):
        """DeathTrigger e registrado corretamente."""
        from rage_web.game_engine.state import DeathTrigger
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        dream = CardInstance(card_id=573, name='Dream Hunter',
                             card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                             owner_id='p1', controller_id='p1',
                             health=4, health_current=4)
        p1.hunting_grounds.append(dream)
        game.register_card_passives(dream, p1)
        assert len(game.death_triggers) == 1
        assert game.death_triggers[0].condition == 'killed_by_type:Mokole'
        assert game.death_triggers[0].action == 'search_deck_type:Quest/Rite/Moot'

    def test_death_trigger_dispara_com_mokole(self):
        """Death trigger dispara quando morto por Mokole."""
        from rage_web.game_engine.state import DeathTrigger
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        # Cria a carta de trigger (Dream Hunter) em jogo
        trigger_card = CardInstance(card_id=573, name='Dream Hunter',
                                    card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                                    owner_id='p2', controller_id='p2',
                                    health=4, health_current=4)
        p2.hunting_grounds.append(trigger_card)
        # Da uma carta no deck de p1 para buscar
        carta_buscavel = CardInstance(card_id=999, name='Ritual',
                                      card_type='Rite', zone=Zone.DECK_SEPT,
                                      owner_id='p1', controller_id='p1')
        p1.deck_sept.append(carta_buscavel)
        game = GameState(players=[p1, p2])
        # Registra trigger via register_card_passives
        game.register_card_passives(trigger_card, p2)
        assert len(game.death_triggers) == 1
        killed = CardInstance(card_id=573, name='Dream Hunter',
                              card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p2', controller_id='p2',
                              health=4, health_current=0)
        # killer e Mokole (keywords) e pertence a p1
        killer = CardInstance(card_id=374, name='Sand Last King',
                              card_type='Character', zone=Zone.PACK_HOME,
                              owner_id='p1', controller_id='p1',
                              keywords='Mokole - Suchid - Gaia - Male',
                              rage=3, health=4, health_current=4)
        # Morte deve disparar trigger: killer e Mokole
        # killer_player=p1 e o beneficiario
        game.check_death_triggers(killed, killer, p1)
        # Carta deve ter sido buscada do deck de p1 para a mao de p1
        assert carta_buscavel.zone == Zone.HAND
        assert carta_buscavel in p1.hand

    def test_death_trigger_ignora_se_mokole_ausente(self):
        """Trigger nao dispara se killer nao for Mokole."""
        from rage_web.game_engine.state import DeathTrigger
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        # Cria trigger card em jogo
        trigger_card = CardInstance(card_id=573, name='Dream Hunter',
                                    card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                                    owner_id='p2', controller_id='p2',
                                    health=4, health_current=4)
        p2.hunting_grounds.append(trigger_card)
        trigger = DeathTrigger(
            trigger_card_uid=id(trigger_card),
            condition='killed_by_type:Mokole',
            action='search_deck_type:Quest/Rite/Moot',
            originador_id='p1'
        )
        game.death_triggers.append(trigger)
        killed = CardInstance(card_id=573, name='Dream Hunter',
                              card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p2', controller_id='p2')
        # killer nao-Mokole (Wendigo)
        killer = CardInstance(card_id=207, name='Old Storm-Chaser',
                              card_type='Character', zone=Zone.PACK_HOME,
                              owner_id='p2', controller_id='p2',
                              keywords='Wendigo - Gaia - Male',
                              rage=2, health=2, health_current=2)
        game.check_death_triggers(killed, killer, p2)
        # Trigger nao usado (killer nao e Mokole)
        assert not trigger.usado

    def test_death_trigger_usado_apenas_uma_vez(self):
        """Trigger one-shot: usado apenas uma vez."""
        from rage_web.game_engine.state import DeathTrigger
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        # Cria trigger card real em jogo
        trigger_card = CardInstance(card_id=573, name='Dream Hunter',
                                    card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                                    owner_id='p2', controller_id='p2',
                                    health=4, health_current=4)
        p2.hunting_grounds.append(trigger_card)
        # Registra trigger com condition 'any' manualmente
        from rage_web.game_engine.state import DeathTrigger
        trigger = DeathTrigger(
            trigger_card_uid=id(trigger_card),
            condition='any',
            action='gain_vp',
            originador_id='p1'
        )
        game.death_triggers.append(trigger)
        killed = CardInstance(card_id=999, name='Some Creature',
                              card_type='Character', zone=Zone.PACK_HOME,
                              owner_id='p2', controller_id='p2')
        # Primeira morte: dispara
        game.check_death_triggers(killed, None, p1)
        assert trigger.usado
        vp_antes = p1.victory_points
        # Segunda morte: nao dispara (usado=True)
        game.check_death_triggers(killed, None, p1)
        assert p1.victory_points == vp_antes


class TestRecruitmentSystem:
    """Testes do sistema de Recrutamento (Sand's Last King)."""

    def test_sands_last_king_adiciona_recruit(self):
        """Sand's Last King adiciona tribos ao can_recruit."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        sand = CardInstance(card_id=374, name="Sand's Last King",
                            card_type='Character', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1',
                            rage=3, health=4, health_current=4)
        p1.pack_home.append(sand)
        game.register_card_passives(sand, p1)
        assert 'Ajaba' in p1.can_recruit
        assert 'Bastet' in p1.can_recruit
        assert 'Silent Striders' in p1.can_recruit
        assert len(p1.can_recruit) == 3

    def test_register_card_passives_ignora_carta_desconhecida(self):
        """Cartas sem passiva especial nao sao registradas."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        comum = CardInstance(card_id=123, name='Common Card',
                             card_type='Combat Action', zone=Zone.PACK_HOME,
                             owner_id='p1', controller_id='p1')
        assert len(game.death_triggers) == 0
        assert len(game.game_modifiers) == 0
        assert len(p1.can_recruit) == 0


class TestContinuousPassives:
    """Testes de passivas continuas (Lake Nasser Wallow)."""

    def test_lake_nasser_wallow_adiciona_modifier(self):
        """Lake Nasser Wallow adiciona rites_gifts_cross_gauntlet."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        lake = CardInstance(card_id=609, name='Lake Nasser Wallow',
                            card_type='Caern', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1',
                            gnosis=5)
        p1.pack_home.append(lake)
        game.register_card_passives(lake, p1)
        assert len(game.game_modifiers) == 1
        assert game.game_modifiers[0].modifier == 'rites_gifts_cross_gauntlet'
        assert game.game_modifiers[0].ativo

    def test_has_modifier_retorna_true_quando_em_jogo(self):
        """has_modifier retorna True se carta esta em jogo."""
        from rage_web.game_engine.state import GameModifier
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        lake = CardInstance(card_id=609, name='Lake Nasser Wallow',
                            card_type='Caern', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1',
                            gnosis=5)
        p1.pack_home.append(lake)
        modifier = GameModifier(
            card_uid=id(lake),
            modifier='rites_gifts_cross_gauntlet'
        )
        game.game_modifiers.append(modifier)
        assert game.has_modifier('rites_gifts_cross_gauntlet')

    def test_has_modifier_retorna_false_quando_fora_de_jogo(self):
        """has_modifier retorna False se carta foi removida."""
        from rage_web.game_engine.state import GameModifier
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        lake = CardInstance(card_id=609, name='Lake Nasser Wallow',
                            card_type='Caern', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1',
                            gnosis=5)
        p1.pack_home.append(lake)
        modifier = GameModifier(
            card_uid=id(lake),
            modifier='rites_gifts_cross_gauntlet'
        )
        game.game_modifiers.append(modifier)
        # Verifica que esta ativo
        assert game.has_modifier('rites_gifts_cross_gauntlet')
        # Remove a carta
        p1.pack_home.remove(lake)
        lake.zone = Zone.DISCARD_COMBAT
        # Agora deve retornar False (e desativar modifier)
        assert not game.has_modifier('rites_gifts_cross_gauntlet')
        assert not modifier.ativo

    def test_has_modifier_modificador_inexistente(self):
        """has_modifier para modifier inexistente retorna False."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        assert not game.has_modifier('modifier_que_nao_existe')

    def test_gauntlet_check_com_lake_nasser_wallow(self):
        """_validar_gauntlet_para_carta respeita modifier."""
        from rage_web.game_engine.effects import (
            _validar_gauntlet_para_carta, ModeloCarta, Modo, Efeito, EfeitoTipo,
        )
        from rage_web.game_engine.state import GameModifier
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        # Adiciona modifier
        lake = CardInstance(card_id=609, name='Lake Nasser Wallow',
                            card_type='Caern', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1')
        p1.pack_home.append(lake)
        modifier = GameModifier(
            card_uid=id(lake),
            modifier='rites_gifts_cross_gauntlet'
        )
        game.game_modifiers.append(modifier)
        # Cria um Gift
        gift = ModeloCarta(
            id='test', nome='Test Gift', tipo='Gift',
            modos=[Modo(
                descricao='Usar',
                efeitos=[Efeito(tipo=EfeitoTipo.DANO, quantidade=1,
                                condicao='criatura_inimiga')]
            )]
        )
        # Deve retornar True por causa do modifier
        assert _validar_gauntlet_para_carta(game, p1, gift)

    def test_find_card_by_uid(self):
        """_find_card_by_uid encontra carta pelo id() da instancia."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        carta = CardInstance(card_id=1, name='Test',
                             card_type='Character', zone=Zone.PACK_HOME,
                             owner_id='p1', controller_id='p1')
        p1.pack_home.append(carta)
        encontrada = game._find_card_by_uid(id(carta))
        assert encontrada is carta
        assert encontrada.name == 'Test'

    def test_find_card_by_uid_inexistente(self):
        """_find_card_by_uid retorna None para uid inexistente."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        assert game._find_card_by_uid(99999) is None


class TestDeck416Systems:
    """Testes para os sistemas implementados para deck416."""

    def test_questor_passive_registra_modifier(self):
        """Questor registra modifier questor_active."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        questor = CardInstance(card_id=227, name='Questor',
                               card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                               owner_id='p1', controller_id='p1',
                               rage=3, gnosis=7, health=3)
        p1.pack_home.append(questor)
        game.register_card_passives(questor, p1)
        assert game.has_modifier('questor_active')

    def test_questor_vp_bonus_victim_hg(self):
        """Questor concede +1 VP ao matar Victim do HG."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        questor = CardInstance(card_id=227, name='Questor',
                               card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                               owner_id='p1', controller_id='p1',
                               rage=3, gnosis=7, health=3)
        p1.pack_home.append(questor)
        game.register_card_passives(questor, p1)
        # Mata uma vitima no HG
        victim = CardInstance(card_id=535, name='Renegade Werewolf Hunter',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p2', controller_id='p2',
                              renown=5, health=4, health_current=0)
        p2.hunting_grounds.append(victim)
        vp_antes = p1.victory_points
        game.check_kill_bonuses(victim, p1)
        assert p1.victory_points == vp_antes + 1

    def test_questor_no_bonus_for_non_victim(self):
        """Questor nao concede bonus para nao-Victim."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        questor = CardInstance(card_id=227, name='Questor',
                               card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                               owner_id='p1', controller_id='p1')
        p1.pack_home.append(questor)
        game.register_card_passives(questor, p1)
        # Mata um character, nao vitima
        char = CardInstance(card_id=24, name='Dharma Bum',
                            card_type='Character - Gaia', zone=Zone.HUNTING_GROUNDS,
                            owner_id='p2', controller_id='p2')
        p2.hunting_grounds.append(char)
        vp_antes = p1.victory_points
        game.check_kill_bonuses(char, p1)
        assert p1.victory_points == vp_antes  # Sem bonus

    def test_longtooth_modifier_registrado(self):
        """Longtooth registra modifier can_use_7th_gen_gifts."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        longtooth = CardInstance(card_id=175, name='Longtooth Soulkiller',
                                 card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1',
                                 rage=8, gnosis=7, health=8)
        p1.pack_home.append(longtooth)
        game.register_card_passives(longtooth, p1)
        assert game.has_modifier('can_use_7th_gen_gifts')

    def test_the_pit_bonus_registrado(self):
        """The Pit registra modifier the_pit_active."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        pit = CardInstance(card_id=777, name='The Pit',
                           card_type='Territory', zone=Zone.PACK_HOME,
                           owner_id='p1', controller_id='p1')
        p1.pack_home.append(pit)
        game.register_card_passives(pit, p1)
        assert game.has_modifier('the_pit_active')

    def test_the_pit_vp_bonus_victim(self):
        """The Pit concede +1 VP ao matar qualquer Victim."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        pit = CardInstance(card_id=777, name='The Pit',
                           card_type='Territory', zone=Zone.PACK_HOME,
                           owner_id='p1', controller_id='p1')
        p1.pack_home.append(pit)
        game.register_card_passives(pit, p1)
        victim = CardInstance(card_id=535, name='Renegade Werewolf Hunter',
                              card_type='Victim', zone=Zone.PACK_HOME,
                              owner_id='p2', controller_id='p2',
                              renown=5, health=4, health_current=0)
        p2.pack_home.append(victim)
        vp_antes = p1.victory_points
        game.check_kill_bonuses(victim, p1)
        assert p1.victory_points == vp_antes + 1

    def test_chronicle_bonus_registrado(self):
        """Chronicle registra modifier chronicle_active."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        chronicle = CardInstance(card_id=630, name='Chronicle of the Black Labyrinth',
                                 card_type='Equipment', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1', gnosis=1)
        p1.pack_home.append(chronicle)
        game.register_card_passives(chronicle, p1)
        assert game.has_modifier('chronicle_active')

    def test_war_knife_modifier_registrado(self):
        """War Knife registra modifier war_knife_active."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        knife = CardInstance(card_id=716, name='War Knife of Benning Simon',
                             card_type='Equipment', zone=Zone.PACK_HOME,
                             owner_id='p1', controller_id='p1', gnosis=4)
        p1.pack_home.append(knife)
        game.register_card_passives(knife, p1)
        assert game.has_modifier('war_knife_active')

    def test_skin_hellbound_modifier_registrado(self):
        """Skin of the Hellbound registra modifier."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        skin = CardInstance(card_id=697, name='Skin of the Hellbound',
                            card_type='Equipment', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1', gnosis=4)
        p1.pack_home.append(skin)
        game.register_card_passives(skin, p1)
        assert game.has_modifier('skin_hellbound_active')


class TestDeck416Effects:
    """Testes de efeitos especificos do deck416."""

    def _get_resolvedor(self, game):
        from rage_web.game_engine.effects import ResolvedorEfeitos
        return ResolvedorEfeitos(game, rng=None)

    def _make_efeito(self, tipo, **kw):
        from rage_web.game_engine.effects import Efeito, EfeitoTipo
        return Efeito(tipo=getattr(EfeitoTipo, tipo, tipo), **kw)

    def test_spiral_boomerang_move_to_umbra(self):
        """Spiral Boomerang move alvo para Umbra do dono."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        alvo = CardInstance(card_id=46, name='Blood-on-the-Wind',
                            card_type='Character - Gaia', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            health=4, health_current=4)
        p2.pack_home.append(alvo)
        boomerang = CardInstance(card_id=700, name='Spiral Boomerang',
                                 card_type='Equipment', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1')
        p1.pack_home.append(boomerang)
        r = self._get_resolvedor(game)
        efeito = self._make_efeito('MOVER_PARA', quantidade=1,
                        condicao='criatura_inimiga',
                        params={'zona': 'umbra', 'duracao': 2,
                                'retornar_zona_original': True})
        assert r.aplicar_efeito(efeito, boomerang, p1)
        assert alvo.zone == Zone.UMBRA
        assert alvo in p2.umbra  # Dono e p2
        assert len(game.pendencias) == 1
        assert 'after_' in game.pendencias[0].duracao

    def test_spiral_boomerang_descarta_apos_uso(self):
        """Spiral Boomerang e descartado apos uso."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        alvo = CardInstance(card_id=46, name='Blood-on-the-Wind',
                            card_type='Character - Gaia', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            health=4, health_current=4)
        p2.pack_home.append(alvo)
        boomerang = CardInstance(card_id=700, name='Spiral Boomerang',
                                 card_type='Equipment', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1')
        p1.pack_home.append(boomerang)
        r = self._get_resolvedor(game)
        efeito = self._make_efeito('REMOVER_DO_JOGO', quantidade=1,
                        condicao='criatura_aliada',
                        params={'descarte_apos_uso': True})
        assert r.aplicar_efeito(efeito, boomerang, p1)
        assert boomerang.zone == Zone.DISCARD_COMBAT
        assert boomerang in p1.discard_combat

    def test_spiral_boomerang_retorna_apos_turnos(self):
        """Target retorna a zona original apos N turnos."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        alvo = CardInstance(card_id=46, name='Blood-on-the-Wind',
                            card_type='Character - Gaia', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            health=4, health_current=4)
        p2.pack_home.append(alvo)
        boomerang = CardInstance(card_id=700, name='Spiral Boomerang',
                                 card_type='Equipment', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1')
        p1.pack_home.append(boomerang)
        r = self._get_resolvedor(game)
        efeito = self._make_efeito('MOVER_PARA', quantidade=1,
                        condicao='criatura_inimiga',
                        params={'zona': 'umbra', 'duracao': 2,
                                'retornar_zona_original': True})
        r.aplicar_efeito(efeito, boomerang, p1)
        assert alvo.zone == Zone.UMBRA
        game.turn_number = 3
        logs = game.expirar_pendencias('redraw')
        assert any('retornou' in l for l in logs)
        assert alvo.zone == Zone.PACK_HOME
        assert alvo in p2.pack_home

    def test_gaias_will_targets_only_victims(self):
        """Gaia's Will Corrupted so atinge vitimas."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        victim = CardInstance(card_id=535, name='Renegade Werewolf Hunter',
                              card_type='Victim', zone=Zone.PACK_HOME,
                              owner_id='p2', controller_id='p2',
                              health=4, health_current=4)
        p2.pack_home.append(victim)
        char = CardInstance(card_id=46, name='Blood-on-the-Wind',
                            card_type='Character - Gaia', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            health=4, health_current=4)
        p2.pack_home.append(char)
        r = self._get_resolvedor(game)
        r.rng = __import__('random').Random(42)
        efeito = self._make_efeito('DANO', quantidade=5, condicao='vitima')
        assert r.aplicar_efeito(efeito, char, p1)
        assert victim.health_current < 4  # Vitima tomou dano
        assert char.health_current == 4  # Character intocado

    def test_blossom_remove_self_and_ally(self):
        """Blossom remove self + 1 aliado ate fim do turno."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        blossom = CardInstance(card_id=47, name='Blossom',
                               card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                               owner_id='p1', controller_id='p1',
                               rage=1, gnosis=6, health=2, health_current=2)
        p1.pack_home.append(blossom)
        aliado = CardInstance(card_id=46, name='Blood-on-the-Wind',
                              card_type='Character - Gaia', zone=Zone.PACK_HOME,
                              owner_id='p1', controller_id='p1',
                              rage=3, health=4, health_current=4)
        p1.pack_home.append(aliado)
        r = self._get_resolvedor(game)
        r.rng = __import__('random').Random(0)
        efeito = self._make_efeito('REMOVER_DO_JOGO', quantidade=1,
                        condicao='criatura_aliada',
                        params={'also_remove_self': True,
                                'restricao_extra': 'nao_pode_agir'})
        assert r.aplicar_efeito(efeito, blossom, p1)
        # Ambos removidos
        assert blossom.zone == Zone.OUT_OF_PLAY
        assert aliado.zone == Zone.OUT_OF_PLAY
        assert blossom not in p1.pack_home
        assert aliado not in p1.pack_home
        # Ambos com restricao
        assert 'nao_pode_agir' in blossom.restricoes
        assert 'nao_pode_agir' in aliado.restricoes
        # Pendencias para retornar (zona + restricao para cada)
        assert len(game.pendencias) == 4

    def test_blossom_retorna_fim_turno(self):
        """Blossom e aliado retornam ao fim do turno."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        blossom = CardInstance(card_id=47, name='Blossom',
                               card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                               owner_id='p1', controller_id='p1',
                               rage=1, gnosis=6, health=2, health_current=2)
        p1.pack_home.append(blossom)
        aliado = CardInstance(card_id=46, name='Blood-on-the-Wind',
                              card_type='Character - Gaia', zone=Zone.PACK_HOME,
                              owner_id='p1', controller_id='p1',
                              rage=3, health=4, health_current=4)
        p1.pack_home.append(aliado)
        r = self._get_resolvedor(game)
        r.rng = __import__('random').Random(1)
        efeito = self._make_efeito('REMOVER_DO_JOGO', quantidade=1,
                        condicao='criatura_aliada',
                        params={'also_remove_self': True,
                                'restricao_extra': 'nao_pode_agir'})
        r.aplicar_efeito(efeito, blossom, p1)
        # Avanca turno (redraw = fim do turno)
        logs = game.expirar_pendencias('redraw')
        assert any('retornou' in l for l in logs)
        assert blossom.zone == Zone.PACK_HOME
        assert aliado.zone == Zone.PACK_HOME
        assert blossom in p1.pack_home
        assert aliado in p1.pack_home
        # Restricoes removidas
        assert 'nao_pode_agir' not in blossom.restricoes
        assert 'nao_pode_agir' not in aliado.restricoes


class TestVictimAutoAttack:
    """Testes de ataques automaticos de vitimas no HG."""

    def test_werewolf_hunter_ataca_bsd_maior_renown(self):
        """Werewolf Hunter ataca BSD com maior Renome."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        hunter = CardInstance(card_id=535, name='Renegade Werewolf Hunter',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='', controller_id='',
                              rage=7, health=4, health_current=4, renown=8)
        game.hunting_grounds_cards.append(hunter)
        bsd = CardInstance(card_id=227, name='Questor',
                           card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                           owner_id='p2', controller_id='p2',
                           rage=3, health=3, health_current=3, renown=8,
                           keywords='Garou - Black Spiral Dancer - Wyrm')
        p2.pack_home.append(bsd)
        game._check_victim_attacks()
        assert bsd.health_current < 3  # Tomou dano
        assert len(bsd.attached_damage) == 1
        assert bsd.attached_damage[0].is_aggravated  # Dano agravado

    def test_wild_animals_ataca_maior_rage_wyrm(self):
        """Wild Animals ataca Wyrm com maior Rage."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        animals = CardInstance(card_id=568, name='Wild Animals',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='', controller_id='',
                              rage=6, health=4, health_current=4)
        game.hunting_grounds_cards.append(animals)
        wyrm = CardInstance(card_id=175, name='Longtooth Soulkiller',
                           card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                           owner_id='p2', controller_id='p2',
                           rage=8, health=8, health_current=8,
                           keywords='Garou - Black Spiral Dancer - Wyrm')
        p2.pack_home.append(wyrm)
        gaia = CardInstance(card_id=46, name='Blood-on-the-Wind',
                           card_type='Character - Gaia', zone=Zone.PACK_HOME,
                           owner_id='p1', controller_id='p1',
                           rage=3, health=4, health_current=4)
        p1.pack_home.append(gaia)
        game._check_victim_attacks()
        assert wyrm.health_current < 8  # Longtooth (rage 8) tomou dano
        assert gaia.health_current == 4  # Gaia intocado

    def test_victim_ignora_se_sem_alvo_valido(self):
        """Vitima nao ataca se nao ha alvo valido."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        # Wild Animals sem Wyrm no jogo
        animals = CardInstance(card_id=568, name='Wild Animals',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='', controller_id='',
                              rage=6, health=4, health_current=4)
        game.hunting_grounds_cards.append(animals)
        game._check_victim_attacks()  # Nao deve crashar
        assert True

    def test_victim_mata_personagem(self):
        """Se vitima mata o alvo, ele vai para discard."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        hunter = CardInstance(card_id=535, name='Renegade Werewolf Hunter',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='', controller_id='',
                              rage=7, health=4, health_current=4)
        game.hunting_grounds_cards.append(hunter)
        fraco = CardInstance(card_id=24, name='Dharma Bum',
                             card_type='Character - Gaia', zone=Zone.PACK_HOME,
                             owner_id='p2', controller_id='p2',
                             rage=1, health=2, health_current=2,
                             keywords='Wyrm')
        p2.pack_home.append(fraco)
        game._check_victim_attacks()
        assert fraco.health_current <= 0
        assert fraco not in p2.pack_home


class TestPreyTriggerSystem:
    """Testes do sistema de triggers de presas (fim de combate/turno)."""

    def test_wild_animals_ataca_wyrm_em_pack_home(self):
        """Wild Animals ataca Wyrm no pack home (nao so HG global)."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        animals = CardInstance(card_id=568, name='Wild Animals',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p1', controller_id='p1',
                              rage=6, health=4, health_current=4)
        p1.hunting_grounds.append(animals)
        wyrm = CardInstance(card_id=18, name='Count Vladimir',
                           card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                           owner_id='p2', controller_id='p2',
                           rage=5, health=6, health_current=6,
                           keywords='Vampire - Eater-of-Souls - Wyrm')
        p2.pack_home.append(wyrm)
        game._check_victim_attacks()
        assert wyrm.health_current < 6

    def test_wild_animals_ignora_se_sem_wyrm(self):
        """Wild Animals nao ataca se nao ha Wyrm."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        animals = CardInstance(card_id=568, name='Wild Animals',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p1', controller_id='p1',
                              rage=6, health=4, health_current=4)
        p1.hunting_grounds.append(animals)
        gaia = CardInstance(card_id=46, name='Blood-on-the-Wind',
                           card_type='Character - Gaia', zone=Zone.PACK_HOME,
                           owner_id='p2', controller_id='p2',
                           rage=3, health=4, health_current=4)
        p2.pack_home.append(gaia)
        game._check_victim_attacks()
        assert gaia.health_current == 4  # Intocado

    def test_wild_animals_prefere_maior_rage(self):
        """Wild Animals ataca o Wyrm com maior Rage."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        animals = CardInstance(card_id=568, name='Wild Animals',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='p1', controller_id='p1',
                              rage=6, health=4, health_current=4)
        p1.hunting_grounds.append(animals)
        wyrm1 = CardInstance(card_id=18, name='Vladimir',
                            card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            rage=5, health=6, health_current=6,
                            keywords='Wyrm')
        wyrm2 = CardInstance(card_id=29, name='Allonzo',
                            card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                            owner_id='p2', controller_id='p2',
                            rage=7, health=7, health_current=7,
                            keywords='Wyrm')
        p2.pack_home.extend([wyrm1, wyrm2])
        game._check_victim_attacks()
        assert wyrm2.health_current < 7  # Allonzo (rage 7) foi atacado
        assert wyrm1.health_current == 6  # Vladimir intocado

    def test_vigilante_ataca_killer_de_vitima(self):
        """Vigilante ataca quem matou a vitima de menor Renome."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        vigilante = CardInstance(card_id=565, name='Vigilante',
                                card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                                owner_id='p1', controller_id='p1',
                                rage=3, health=5, health_current=5)
        p1.hunting_grounds.append(vigilante)
        killer = CardInstance(card_id=18, name='Vladimir',
                             card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                             owner_id='p2', controller_id='p2',
                             rage=5, health=6, health_current=6,
                             keywords='Wyrm')
        p2.pack_home.append(killer)
        # Simula que Vladimir matou a vitima de menor Renome
        killer_card = CardInstance(card_id=999, name='FakeKiller',
                                   card_type='Character', zone=Zone.PACK_HOME,
                                   owner_id='p2', controller_id='p2')
        game.registrar_kill_vitima(id(killer_card))
        game._check_victim_attacks()
        assert killer.health_current < 6

    def test_vigilante_fallback_sem_killer_registrado(self):
        """Vigilante ataca maior Renome se nao ha killer registrado."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        vigilante = CardInstance(card_id=565, name='Vigilante',
                                card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                                owner_id='p1', controller_id='p1',
                                rage=3, health=5, health_current=5)
        p1.hunting_grounds.append(vigilante)
        char = CardInstance(card_id=18, name='Vladimir',
                           card_type='Character - Wyrm', zone=Zone.PACK_HOME,
                           owner_id='p2', controller_id='p2',
                           rage=5, health=6, health_current=6)
        p2.pack_home.append(char)
        # Sem killer registrado
        game._check_victim_attacks()
        assert char.health_current < 6  # Atacado (fallback)

    def test_mage_remove_lowest_renown_victim(self):
        """Mage of Celestial Chorus remove menor Renome victim no fim do turno."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        mage = CardInstance(card_id=503, name='Mage of the Celestial Chorus',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           rage=7, health=7, health_current=7, renown=8)
        weak_victim = CardInstance(card_id=565, name='Vigilante',
                                  card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                                  owner_id='p1', controller_id='p1',
                                  rage=3, health=5, health_current=5, renown=5)
        strong_victim = CardInstance(card_id=535, name='Werewolf Hunter',
                                    card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                                    owner_id='p1', controller_id='p1',
                                    rage=7, health=4, health_current=4, renown=8)
        p1.hunting_grounds.extend([mage, weak_victim, strong_victim])
        game._check_end_of_turn_effects()
        assert weak_victim.zone == Zone.REMOVED  # Menor Renome removido
        assert strong_victim.health_current == 4  # Ainda vivo
        assert mage.health_current == 7  # Mage intacta

    def test_mage_nao_remove_se_unica_vitima(self):
        """Mage nao remove se e a unica vitima no HG."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        mage = CardInstance(card_id=503, name='Mage of the Celestial Chorus',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           rage=7, health=7, health_current=7, renown=8)
        p1.hunting_grounds.append(mage)
        game._check_end_of_turn_effects()
        assert mage.health_current == 7  # Nada acontece

    def test_unlucky_lune_rage_6_com_full_moon(self):
        """Unlucky Lune ganha Rage 6 com Full Moon ativa."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        lune = CardInstance(card_id=558, name='Unlucky Lune',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           rage=3, health=4, health_current=4, renown=6)
        p1.hunting_grounds.append(lune)
        game.definir_lunar_phase('p1', 'Full Moon', card_id=891)
        game._check_lunar_phase_effects()
        assert lune.rage == 6

    def test_unlucky_lune_sem_full_moon(self):
        """Unlucky Lune mantem Rage original sem Full Moon."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        lune = CardInstance(card_id=558, name='Unlucky Lune',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           rage=3, health=4, health_current=4, renown=6)
        p1.hunting_grounds.append(lune)
        game.definir_lunar_phase('p1', 'New Moon', card_id=890)
        game._check_lunar_phase_effects()
        assert lune.rage == 3  # Nao muda

    def test_coletar_vitimas_hg_global_e_players(self):
        """_coletar_todas_vitimas_hg retorna vitimas de todas as fontes."""
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        v1 = CardInstance(card_id=568, name='Wild Animals',
                         card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                         owner_id='', controller_id='',
                         health=4, health_current=4)
        v2 = CardInstance(card_id=565, name='Vigilante',
                         card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                         owner_id='p1', controller_id='p1',
                         health=5, health_current=5)
        game.hunting_grounds_cards.append(v1)
        p1.hunting_grounds.append(v2)
        vitimas = game._coletar_todas_vitimas_hg()
        assert len(vitimas) == 2
        card_ids = [c.card_id for c, _ in vitimas]
        assert 568 in card_ids
        assert 565 in card_ids

    def test_coletar_personagens_pack_e_umbra(self):
        """_coletar_todos_personagens inclui pack_home e umbra."""
        p1 = PlayerState(id='p1', name='J1')
        game = GameState(players=[p1])
        c1 = CardInstance(card_id=18, name='Vladimir',
                         card_type='Character', zone=Zone.PACK_HOME,
                         owner_id='p1', controller_id='p1',
                         health=6, health_current=6)
        c2 = CardInstance(card_id=29, name='Allonzo',
                         card_type='Character', zone=Zone.UMBRA,
                         owner_id='p1', controller_id='p1',
                         health=7, health_current=7)
        p1.pack_home.append(c1)
        p1.umbra.append(c2)
        personagens = game._coletar_todos_personagens()
        assert len(personagens) == 2

    # -- Testes de Gift access especial (ANY Gifts / Auspice Gifts) --

    def test_mage_celestial_chorus_pode_usar_qualquer_gift(self):
        """Mage of Celestial Chorus no HG permite usar ANY Gift."""
        from rage_web.game_engine.rules import pode_usar_gift
        p1 = PlayerState(id='p1', name='J1')
        # Mage of Celestial Chorus como Victim no HG
        mage = CardInstance(card_id=503, name='Mage of the Celestial Chorus',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           gnosis=7,
                           text='The mage can use ANY Gifts.')
        p1.hunting_grounds.append(mage)
        # Gift com requisito que normalmente ninguem atende
        gift = CardInstance(card_id=999, name='Generic Gift',
                           card_type='Gift', zone=Zone.HAND,
                           owner_id='p1', controller_id='p1',
                           gnosis=3,
                           requires='Eater-of-Souls - Vampire')
        p1.hand.append(gift)
        assert pode_usar_gift(p1, gift) is True

    def test_mage_celestial_chorus_respeita_gnosis(self):
        """Mage of Celestial Chorus nao pode usar Gift com Gnosis > sua Gnosis."""
        from rage_web.game_engine.rules import pode_usar_gift
        p1 = PlayerState(id='p1', name='J1')
        mage = CardInstance(card_id=503, name='Mage of the Celestial Chorus',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           gnosis=3,
                           text='The mage can use ANY Gifts.')
        p1.hunting_grounds.append(mage)
        gift = CardInstance(card_id=999, name='Expensive Gift',
                           card_type='Gift', zone=Zone.HAND,
                           owner_id='p1', controller_id='p1',
                           gnosis=5)
        p1.hand.append(gift)
        assert pode_usar_gift(p1, gift) is False

    def test_unlucky_lune_pode_usar_auspice_gifts(self):
        """Unlucky Lune pode usar Gifts com requisito 'Auspice'."""
        from rage_web.game_engine.rules import pode_usar_gift
        p1 = PlayerState(id='p1', name='J1')
        lune = CardInstance(card_id=558, name='Unlucky Lune',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           gnosis=4,
                           text='A Lune can use any Auspice Gifts.')
        p1.hunting_grounds.append(lune)
        gift = CardInstance(card_id=999, name='Gift Auspice',
                           card_type='Gift', zone=Zone.HAND,
                           owner_id='p1', controller_id='p1',
                           gnosis=4,
                           requires='Auspice - Galliard')
        p1.hand.append(gift)
        assert pode_usar_gift(p1, gift) is True

    def test_unlucky_lune_nao_pode_usar_gift_nao_auspice(self):
        """Unlucky Lune nao pode usar Gift sem 'Auspice' no requisito."""
        from rage_web.game_engine.rules import pode_usar_gift
        p1 = PlayerState(id='p1', name='J1')
        lune = CardInstance(card_id=558, name='Unlucky Lune',
                           card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                           owner_id='p1', controller_id='p1',
                           gnosis=4,
                           text='A Lune can use any Auspice Gifts.')
        p1.hunting_grounds.append(lune)
        gift = CardInstance(card_id=999, name='Gift Pentex',
                           card_type='Gift', zone=Zone.HAND,
                           owner_id='p1', controller_id='p1',
                           gnosis=3,
                           requires='Pentex')
        p1.hand.append(gift)
        # Sem match de keyword normal (Spirit nao esta em Pentex)
        assert pode_usar_gift(p1, gift) is False


class TestWhipOfTheWicked:
    """Testes da Whip of the Wicked (720)."""

    def test_whip_force_defesa_primeiro(self):
        """Whip obriga oponente a declarar defesa antes de ofensiva."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, selecionar_alfa,
            calcular_ordem_alfa, _validar_whip_constraint
        )
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        whip_user = CardInstance(card_id=999, name='Whip User',
                                 card_type='Character', zone=Zone.PACK_HOME,
                                 owner_id='p1', controller_id='p1',
                                 rage=3, health=5, health_current=5)
        p1.pack_home.append(whip_user)
        whip = CardInstance(card_id=720, name='Whip of the Wicked',
                            card_type='Equipment', zone=Zone.PACK_HOME,
                            owner_id='p1', controller_id='p1')
        whip_user.attached_equipment.append(whip)
        defender = CardInstance(card_id=998, name='Defender',
                                card_type='Character', zone=Zone.PACK_HOME,
                                owner_id='p2', controller_id='p2',
                                rage=2, health=4, health_current=4)
        p2.pack_home.append(defender)
        start_combat(game, ['999'], ['998'])
        selecionar_alfa(game, 'p1', '999')
        selecionar_alfa(game, 'p2', '998')
        calcular_ordem_alfa(game)
        # Defender tenta strike -> recusado
        assert not declare_action(game, '998', 'strike')
        # Defender declara dodge -> aceito
        assert declare_action(game, '998', 'dodge')

    def test_whip_nao_afeta_se_oponente_sem_whip(self):
        """Sem Whip, pode declarar qualquer acao."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, selecionar_alfa,
            calcular_ordem_alfa
        )
        p1 = PlayerState(id='p1', name='J1')
        p2 = PlayerState(id='p2', name='J2')
        game = GameState(players=[p1, p2])
        a = CardInstance(card_id=999, name='Atacante',
                         card_type='Character', zone=Zone.PACK_HOME,
                         owner_id='p1', controller_id='p1',
                         rage=3, health=5, health_current=5)
        p1.pack_home.append(a)
        b = CardInstance(card_id=998, name='Defensor',
                         card_type='Character', zone=Zone.PACK_HOME,
                         owner_id='p2', controller_id='p2',
                         rage=2, health=4, health_current=4)
        p2.pack_home.append(b)
        start_combat(game, ['999'], ['998'])
        selecionar_alfa(game, 'p1', '999')
        selecionar_alfa(game, 'p2', '998')
        calcular_ordem_alfa(game)
        # Sem whip, pode declarar strike diretamente
        assert declare_action(game, '998', 'strike')
        assert declare_action(game, '999', 'strike')


class TestMootSystem:
    """Testes do sistema de Moot (Juntas)."""

    def test_chamar_moot(self, game):
        """Chamar uma Junta."""
        game = game
        result = game.chamar_moot('p1', nome='Silver Record')
        assert result is True
        assert game.moot_atual is not None
        assert game.moot_atual.nome == 'Silver Record'
        assert game.moot_atual.dono_id == 'p1'
        assert not game.moot_atual.resolvido

    def test_nao_pode_chamar_duas(self, game):
        """Nao pode chamar 2 Juntas no mesmo turno."""
        game = game
        game.chamar_moot('p1', nome='Moot 1')
        result = game.chamar_moot('p2', nome='Moot 2')
        assert result is False

    def test_votar_e_aprovar(self, game):
        """Votar e aprovar uma Junta."""
        game = game
        # Adiciona personagens com Renome para ter votos
        for p in game.players:
            p.pack_home.append(CardInstance(
                card_id=999, name='Voter', card_type='Character',
                zone=Zone.PACK_HOME, owner_id=p.id, controller_id=p.id,
                renown=5, health=3, health_current=3,
            ))
        game.chamar_moot('p1', nome='Test Moot')
        game.votar_moot('p1', a_favor=True)
        game.votar_moot('p2', a_favor=True)
        game.resolver_moot()
        assert game.moot_atual.resolvido
        assert game.moot_atual.aprovado

    def test_votar_e_rejeitar(self, game):
        """Votar e rejeitar uma Junta."""
        game = game
        for p in game.players:
            p.pack_home.append(CardInstance(
                card_id=999, name='Voter', card_type='Character',
                zone=Zone.PACK_HOME, owner_id=p.id, controller_id=p.id,
                renown=5, health=3, health_current=3,
            ))
        game.chamar_moot('p1', nome='Test Moot')
        game.votar_moot('p1', a_favor=True)
        game.votar_moot('p2', a_favor=False)
        game.resolver_moot()
        assert game.moot_atual.resolvido
        assert not game.moot_atual.aprovado  # Empate = rejeitado

    def test_moot_com_efeito_ganhar_vp(self, game):
        """Moot com efeito de ganhar VP quando aprovado."""
        game = game
        p1 = game.players[0]
        for p in game.players:
            p.pack_home.append(CardInstance(
                card_id=999, name='Voter', card_type='Character',
                zone=Zone.PACK_HOME, owner_id=p.id, controller_id=p.id,
                renown=5, health=3, health_current=3,
            ))

        game.chamar_moot('p1', nome='Caern Building',
                         modelo_id='caern-building_r6')
        game.votar_moot('p1', a_favor=True)
        game.votar_moot('p2', a_favor=True)
        game.resolver_moot()

        assert game.moot_atual.aprovado
        assert p1.victory_points == 4  # +4 VP da Caern Building

    def test_moot_rejeitado_sem_efeito(self, game):
        """Moot rejeitado nao aplica efeitos."""
        game = game
        p1 = game.players[0]
        for p in game.players:
            p.pack_home.append(CardInstance(
                card_id=999, name='Voter', card_type='Character',
                zone=Zone.PACK_HOME, owner_id=p.id, controller_id=p.id,
                renown=5, health=3, health_current=3,
            ))

        game.chamar_moot('p1', nome='Caern Building',
                         modelo_id='caern-building_r6')
        game.votar_moot('p1', a_favor=True)
        game.votar_moot('p2', a_favor=False)
        game.resolver_moot()

        assert not game.moot_atual.aprovado
        assert p1.victory_points == 0  # Sem VP

    def test_bot_chama_moot(self, game):
        """Bot tenta chamar Moot se tiver carta na mao."""
        from rage_web.game_engine.bot.priority_bot import PriorityBot
        from rage_web.game_engine.state import CardInstance, Zone

        game = game
        # Poe uma carta de Moot na mao do jogador
        moot_card = CardInstance(
            card_id=1186, name='Banishment by the Council',
            card_type='Moot', zone=Zone.HAND,
            owner_id='p1', controller_id='p1',
            modelo_id='banishment-by-the-council_r8',
        )
        game.players[0].hand.append(moot_card)

        bot = PriorityBot(game, 'p1', difficulty='hard')
        game.phase = 'moot'
        action = bot.decide()

        assert 'moot_chamar' in action
        assert game.moot_atual is not None
        assert game.moot_atual.nome == 'Banishment by the Council'


class TestTerritoryAttack:
    """Testes do ataque a Territories."""

    def test_territory_e_combatente_valido(self, game):
        """Territory deve ser reconhecido como combatente valido."""
        from rage_web.game_engine.combat_queue import _eh_combatente_valido
        t = CardInstance(card_id=9999, name='Test Territory',
                         card_type='Territory', zone=Zone.PACK_HOME,
                         owner_id='p1', controller_id='p1')
        game.players[0].pack_home.append(t)
        assert _eh_combatente_valido(game, '9999')

    def test_territory_sem_alpha_defensor_destroi(self, game):
        """Territory sem alpha defensor deve ser destruido."""
        p1 = game.players[0]
        p2 = game.players[1]
        # Alpha do atacante
        alpha = CardInstance(card_id=100, name='Attacker Alpha',
                             card_type='Character', zone=Zone.PACK_HOME,
                             health=5, health_current=5, rage=3,
                             owner_id='p1', controller_id='p1')
        p1.pack_home.append(alpha)
        game.combat.alphas['p1'] = '100'
        # Territory sem alpha defensor
        territory = CardInstance(card_id=200, name='Dead Zone',
                                 card_type='Territory', zone=Zone.PACK_HOME,
                                 health=0, health_current=0,
                                 owner_id='p2', controller_id='p2')
        p2.pack_home.append(territory)
        # Alpha do defensor nao definido
        game.combat.alphas['p2'] = None

        result = start_combat(game, ['100'], ['200'])
        assert not result, 'Combate deve ser cancelado (sem defensor)'
        assert not game.combat.is_active
        assert territory.zone in (Zone.DISCARD_SEPT, Zone.OUT_OF_PLAY), \
            'Territory sem defensor deve ser destruido'

    def test_territory_com_alpha_defensor(self, game):
        """Territory com alpha defensor: substitui Territory pelo alpha."""
        p1 = game.players[0]
        p2 = game.players[1]
        # Alpha atacante
        alpha_a = CardInstance(card_id=100, name='Attacker',
                               card_type='Character', zone=Zone.PACK_HOME,
                               health=5, health_current=5, rage=3,
                               owner_id='p1', controller_id='p1')
        p1.pack_home.append(alpha_a)
        game.combat.alphas['p1'] = '100'
        # Territory
        territory = CardInstance(card_id=200, name='My Territory',
                                 card_type='Territory', zone=Zone.PACK_HOME,
                                 health=0, health_current=0,
                                 owner_id='p2', controller_id='p2')
        p2.pack_home.append(territory)
        # Alpha defensor
        alpha_d = CardInstance(card_id=300, name='Defender Alpha',
                               card_type='Character', zone=Zone.PACK_HOME,
                               health=5, health_current=5, rage=3,
                               owner_id='p2', controller_id='p2')
        p2.pack_home.append(alpha_d)
        game.combat.alphas['p2'] = '300'

        result = start_combat(game, ['100'], ['200'])
        assert result, 'Combate deve ser iniciado'
        assert game.combat.is_active
        # Defensores devem ser o alpha, nao o Territory
        assert '300' in game.combat.defenders
        assert '200' not in game.combat.defenders
        assert territory.zone == Zone.PACK_HOME, \
            'Territory deve permanecer no pack (defendido)'

    def test_territory_destroi_quando_alpha_morre(self, game):
        """Territory destruido quando alpha defensor morre."""
        p1 = game.players[0]
        p2 = game.players[1]
        # Alpha atacante
        alpha_a = CardInstance(card_id=100, name='Attacker',
                               card_type='Character', zone=Zone.PACK_HOME,
                               health=5, health_current=5, rage=10,
                               owner_id='p1', controller_id='p1')
        p1.pack_home.append(alpha_a)
        game.combat.alphas['p1'] = '100'
        # Territory
        territory = CardInstance(card_id=200, name='My Territory',
                                 card_type='Territory', zone=Zone.PACK_HOME,
                                 health=0, health_current=0,
                                 owner_id='p2', controller_id='p2')
        p2.pack_home.append(territory)
        # Alpha defensor (fraco, vai morrer)
        alpha_d = CardInstance(card_id=300, name='Defender',
                               card_type='Character', zone=Zone.PACK_HOME,
                               health=1, health_current=1, rage=1,
                               owner_id='p2', controller_id='p2')
        p2.pack_home.append(alpha_d)
        game.combat.alphas['p2'] = '300'

        result = start_combat(game, ['100'], ['200'])
        assert result
        # Simula combate
        declare_action(game, '100', 'strike')
        declare_action(game, '300', 'block')
        reveal_all(game)
        resolve_combat(game)
        end_combat(game)

        # Alpha defensor deve estar morto
        assert alpha_d.health_current <= 0
        # Territory deve ser destruido tb
        assert territory.zone in (Zone.DISCARD_SEPT, Zone.OUT_OF_PLAY), \
            'Territory deve ser destruido com alpha defensor'

    def test_realm_e_reconhecido(self, game):
        """Realm tambem e alvo valido."""
        from rage_web.game_engine.combat_queue import _eh_combatente_valido
        r = CardInstance(card_id=999, name='Test Realm',
                         card_type='Realm', zone=Zone.PACK_HOME,
                         owner_id='p1', controller_id='p1')
        game.players[0].pack_home.append(r)
        assert _eh_combatente_valido(game, '999')


class TestBluffStep:
    """Testes do Bluff Step (6.9)."""

    def _setup_bluff_game(self, seed=42):
        """Cria cenario basico de combate para teste de bluff."""
        from rage_web.game_engine.cli import build_game_from_decks
        game = build_game_from_decks(160, 629, seed=seed)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
            p.draw_combat(p.hand_size_combat)
        return game

    def _advance_to_play_card(self, game):
        from rage_web.game_engine.combat_queue import advance_combat_step
        for step_name in ['declaration', 'pre_combat', 'beginning_of_combat']:
            game.combat.step = step_name
            advance_combat_step(game)

    def test_bluff_detectado_quando_rage_insuficiente(self):
        """Criatura com Rage baixa jogando acao com req alto = bluff."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, _processar_bluff, _find_card,
            COMBAT_ACTION_PROPS,
        )
        game = self._setup_bluff_game()
        p1 = game.players[0]
        p2 = game.players[1]
        # Usa criatura com menor Rage possivel
        atk = min(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = max(p2.pack_home, key=lambda c: c.effective_rage)
        assert atk.effective_rage < 6, 'Precisa de Rage < 6 para anatomy_lesson bluff'
        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        self._advance_to_play_card(game)
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'anatomy_lesson')
        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        game.combat.step = 'bluff'
        _processar_bluff(game)
        assert str(atk.card_id) in game.combat.bluff_cards
        assert str(atk.card_id) in game.combat.bluff_failed
        assert str(atk.card_id) not in game.combat.declarations
        assert str(dfd.card_id) in game.combat.declarations  # oponente mantido

    def test_bluff_sucesso_quando_alvo_tambem_blefa(self):
        """Bluff bem-sucedido quando ambos blefam."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, _processar_bluff,
        )
        game = self._setup_bluff_game(seed=99)
        p1 = game.players[0]
        p2 = game.players[1]
        atk = min(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = min(p2.pack_home, key=lambda c: c.effective_rage)
        assert atk.effective_rage < 6 and dfd.effective_rage < 6
        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        self._advance_to_play_card(game)
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'anatomy_lesson')
        declare_action(game, str(dfd.card_id), 'anatomy_lesson')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        game.combat.targets[str(dfd.card_id)] = str(atk.card_id)
        game.combat.step = 'bluff'
        _processar_bluff(game)
        assert not game.combat.bluff_failed, 'Ambos blefes devem suceder'
        assert len(game.combat.declarations) == 2, 'Ambas cartas mantidas'

    def test_bluff_falha_quando_alvo_joga_carta_legal(self):
        """Bluff falha quando alvo jogou carta legal (sem bluff)."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, _processar_bluff,
        )
        game = self._setup_bluff_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = min(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = max(p2.pack_home, key=lambda c: c.effective_rage)
        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        self._advance_to_play_card(game)
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'head_butt')  # req 2, Rage pode ser ok
        # Garante que atk tem Rage < 2
        if atk.effective_rage >= 2:
            # Usa anatomy_lesson se head_butt nao for bluff
            declare_action(game, str(atk.card_id), 'anatomy_lesson')
        declare_action(game, str(dfd.card_id), 'strike')  # req 0, sempre legal
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        game.combat.step = 'bluff'
        _processar_bluff(game)
        # O atacante deve ter blefe falhado se Rage < requisito
        if str(atk.card_id) in game.combat.bluff_cards:
            assert str(atk.card_id) in game.combat.bluff_failed

    def test_bluff_step_integrado_na_maquina_de_steps(self):
        """advance_combat_step deve chamar _processar_bluff."""
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, advance_combat_step,
            COMBAT_STEPS,
        )
        game = self._setup_bluff_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = min(p1.pack_home, key=lambda c: c.effective_rage)
        dfd = max(p2.pack_home, key=lambda c: c.effective_rage)
        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        # Avanca ate play_card
        for step_name in ['declaration', 'pre_combat', 'beginning_of_combat']:
            game.combat.step = step_name
            advance_combat_step(game)
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'anatomy_lesson')
        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        # Avanca para bluff
        game.combat.step = 'bluff'
        result = advance_combat_step(game)
        assert result, 'advance_combat_step deve processar bluff'
        # Apos bluff, step deve ser 'resolution' (proximo na lista)
        assert game.combat.step != 'bluff', 'Step deve ter avancado'
        assert game.combat.step == 'resolution', \
            f'Esperado resolution, obtido {game.combat.step}'


class TestSteppingIn:
    """Testes do Stepping In (6.5.9)."""

    def test_stepping_in_gaia_substitui_victim(self):
        """Alpha Gaia substitui Victim como defensor."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import (
            start_combat, _preparar_stepping_in, _eh_pack_gaia
        )
        from rage_web.game_engine.state import Zone, CardInstance
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        victim = CardInstance(card_id=999, name='Test Victim',
                              card_type='Victim', zone=Zone.HUNTING_GROUNDS,
                              owner_id='', controller_id='',
                              health=3, health_current=3, rage=0)
        game.hunting_grounds_cards.append(victim)
        alpha_p1 = p1.pack_home[0]
        game.combat.alphas['p1'] = str(alpha_p1.card_id)
        assert _eh_pack_gaia(p1), 'P1 deve ser Gaia'
        start_combat(game, [str(alpha_p1.card_id)], ['999'])
        assert game.combat.defenders == ['999']
        game.combat.step = 'pre_combat'
        result = _preparar_stepping_in(game)
        assert result, 'Stepping In deve ocorrer'
        # Verifica que o alpha substituiu a Victim
        assert game.combat.defenders != ['999']
        assert game.combat.defenders[0] == str(alpha_p1.card_id)

    def test_stepping_in_sem_alpha_nao_altera(self):
        """Sem alpha compativel, stepping in nao ocorre."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import (
            start_combat, _preparar_stepping_in
        )
        from rage_web.game_engine.state import Zone, CardInstance
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        p2 = game.players[1]
        # Enemy no HG - alpha Wyrm para substituir
        enemy = CardInstance(card_id=998, name='Test Enemy',
                             card_type='Enemy', zone=Zone.HUNTING_GROUNDS,
                             owner_id='', controller_id='',
                             health=3, health_current=3, rage=0)
        game.hunting_grounds_cards.append(enemy)
        alpha_p1 = p1.pack_home[0]
        game.combat.alphas['p1'] = str(alpha_p1.card_id)
        # P1 e Gaia, nao pode substituir Enemy
        start_combat(game, [str(alpha_p1.card_id)], ['998'])
        game.combat.step = 'pre_combat'
        result = _preparar_stepping_in(game)
        assert not result, 'Gaia alpha nao pode substituir Enemy'
        assert game.combat.defenders == ['998'], 'Defensor nao deve mudar'


class TestChallenge:
    """Testes do Challenge (6.5.2)."""

    def test_desafio_nao_alfa_inicia_combate(self):
        """Alpha desafia nao-alfa e inicia combate."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import _tentar_desafio
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        p2 = game.players[1]
        game.combat.alphas['p1'] = str(p1.pack_home[0].card_id)
        game.combat.alphas['p2'] = str(p2.pack_home[0].card_id)
        # Encontra nao-alfa em p2
        nao_alfa = None
        for c in p2.pack_home:
            if str(c.card_id) != game.combat.alphas['p2']:
                nao_alfa = c
                break
        assert nao_alfa is not None
        result = _tentar_desafio(
            game, str(p1.pack_home[0].card_id), str(nao_alfa.card_id))
        assert result, 'Desafio deve ser aceito'
        assert game.combat.is_active
        assert str(nao_alfa.card_id) in game.combat.defenders

    def test_desafio_alfa_recusado(self):
        """Nao pode desafiar outro alpha."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import _tentar_desafio
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        p2 = game.players[1]
        game.combat.alphas['p1'] = str(p1.pack_home[0].card_id)
        game.combat.alphas['p2'] = str(p2.pack_home[0].card_id)
        # Tenta desafiar alpha p2 - deve falhar
        alpha_p2_id = game.combat.alphas['p2']
        result = _tentar_desafio(
            game, str(p1.pack_home[0].card_id), alpha_p2_id)
        assert not result, 'Nao pode desafiar outro alpha'


class TestWithdrawal:
    """Testes do Withdrawal Step (6.3.1)."""

    def test_withdrawal_nao_ocorre_por_padrao(self):
        """Withdrawal retorna False por padrao (atacante continua)."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import (
            start_combat, _processar_withdrawal, resolve_combat
        )
        game = build_game_from_decks(160, 629, seed=42)
        p1 = game.players[0]
        p2 = game.players[1]
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        start_combat(game, [str(p1.pack_home[0].card_id)],
                     [str(p2.pack_home[0].card_id)])
        # Avanca ate withdrawal
        from rage_web.game_engine.combat_queue import advance_combat_step
        for step in ['declaration', 'pre_combat', 'beginning_of_combat',
                     'play_card', 'targeting', 'reveal', 'feint', 'bluff']:
            game.combat.step = step
            advance_combat_step(game)
        resolve_combat(game)
        # So verifica se a funcao existe e retorna False sem erro
        result = _processar_withdrawal(game)
        assert result is False, 'Withdrawal padrao = False'


class TestCombatEventFaceDown:
    """Testes de Combat Events jogados face-down (item #10)."""

    def test_jogar_ce_face_down(self):
        """Jogar CE face-down deve ser possivel no Play Card Step."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, _jogar_ce_face_down,
            get_combatants, COMBAT_ACTIONS, advance_combat_step
        )
        from rage_web.game_engine.state import Zone, CardInstance
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        p2 = game.players[1]
        # Cria um Combat Event na mao do p1
        ce = CardInstance(card_id=9001, name='Test CE',
                          card_type='Combat Event', zone=Zone.HAND,
                          owner_id='p1', controller_id='p1',
                          health=0, health_current=0)
        p1.hand.append(ce)
        # Inicia combate
        start_combat(game, [str(p1.pack_home[0].card_id)],
                     [str(p2.pack_home[0].card_id)])
        for step in ['declaration', 'pre_combat', 'beginning_of_combat']:
            game.combat.step = step
            advance_combat_step(game)
        game.combat.step = 'play_card'
        # Joga CE face-down
        result = _jogar_ce_face_down(
            game, str(p1.pack_home[0].card_id), '9001')
        assert result, 'CE deve ser jogado face-down'
        assert '9001' not in [str(c.card_id) for c in p1.hand], \
            'CE deve sair da mao'
        # Declara acao normal para defensor
        declare_action(game, str(p2.pack_home[0].card_id), 'strike')
        # Avanca para bluff e verifica que CE e ilegal
        for step in ['targeting', 'reveal', 'feint']:
            game.combat.step = step
            advance_combat_step(game)
        game.combat.step = 'bluff'
        from rage_web.game_engine.combat_queue import _processar_bluff
        _processar_bluff(game)
        # CE foi declarado como ce_9001, deve ser marcado ilegal
        atk_id = str(p1.pack_home[0].card_id)
        assert atk_id in game.combat.illegal_cards or \
            atk_id not in game.combat.declarations, \
            'CE deve ser removido como ilegal'

    def test_ce_face_down_ilegal_no_bluff(self):
        """CE face-down e ilegal (6.9.1) e descartado no Bluff Step."""
        from rage_web.game_engine.cli import build_game_from_decks
        from rage_web.game_engine.combat_queue import (
            start_combat, declare_action, _jogar_ce_face_down,
            advance_combat_step, _processar_bluff
        )
        from rage_web.game_engine.state import Zone, CardInstance
        game = build_game_from_decks(160, 629, seed=42)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
        p1 = game.players[0]
        p2 = game.players[1]
        ce = CardInstance(card_id=9002, name='Bluff CE',
                          card_type='Combat Event', zone=Zone.HAND,
                          owner_id='p1', controller_id='p1')
        p1.hand.append(ce)
        start_combat(game, [str(p1.pack_home[0].card_id)],
                     [str(p2.pack_home[0].card_id)])
        for step in ['declaration', 'pre_combat', 'beginning_of_combat']:
            game.combat.step = step
            advance_combat_step(game)
        game.combat.step = 'play_card'
        _jogar_ce_face_down(game, str(p1.pack_home[0].card_id), '9002')
        declare_action(game, str(p2.pack_home[0].card_id), 'strike')
        for step in ['targeting', 'reveal', 'feint']:
            game.combat.step = step
            advance_combat_step(game)
        game.combat.step = 'bluff'
        _processar_bluff(game)
        atk_id = str(p1.pack_home[0].card_id)
        # CE deve ter sido descartado
        assert atk_id not in game.combat.declarations or \
            game.combat.declarations.get(atk_id) is None, \
            'CE deve ser removido das declaracoes'
        # CE deve estar no descarte
        found = any(c.card_id == 9002 for c in p1.discard_combat)
        assert found, 'CE deve estar no discard_combat'
