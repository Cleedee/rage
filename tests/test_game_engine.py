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
    _mesmo_lado_gauntlet,
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
        """Sem Caern, Rites/Gifts funcionam normalmente (True por padrao)."""
        from rage_web.game_engine.effects import _validar_gauntlet_para_carta
        from rage_web.game_engine.effects import ModeloCarta
        modelo = ModeloCarta(id='test', nome='Test Gift', tipo='Gift')
        result = _validar_gauntlet_para_carta(
            game, game.players[0], modelo
        )
        assert result is True


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
