"""Testes do CLI de debug do motor de jogo."""

import pytest

from rage_web.game_engine.cli import RageCLI, create_sample_game


@pytest.fixture
def cli():
    game = create_sample_game(seed=42)
    return RageCLI(game=game)


class TestRageCLI:
    def test_create_game(self):
        """Cria partida de exemplo com 2 jogadores."""
        game = create_sample_game(seed=42)
        assert len(game.players) == 2
        assert game.players[0].name == 'Jogador 1'
        assert game.players[1].name == 'Jogador 2'
        # Deve ter personagens no Pack Home
        assert len(game.players[0].pack_home) > 0
        assert len(game.players[1].pack_home) > 0
        # Mao inicial
        assert len(game.players[0].hand) > 0
        assert len(game.players[1].hand) > 0
        # Decks
        assert len(game.players[0].deck_combat) > 0
        assert len(game.players[0].deck_sept) > 0

    def test_status(self, cli):
        """STATUS nao deve dar erro."""
        cli.onecmd('STATUS')

    def test_draw_combat(self, cli):
        """DRAW compra carta do deck de combate."""
        before = len(cli.game.current_player.hand)
        cli.onecmd('DRAW')
        after = len(cli.game.current_player.hand)
        assert after == before + 1

    def test_draw_sept(self, cli):
        """DRAW sept compra carta do deck de sept."""
        before = len(cli.game.current_player.hand)
        cli.onecmd('DRAW sept')
        after = len(cli.game.current_player.hand)
        assert after == before + 1

    def test_draw_multiple(self, cli):
        """DRAW com quantidade."""
        before = len(cli.game.current_player.hand)
        cli.onecmd('DRAW 3')
        after = len(cli.game.current_player.hand)
        assert after == before + 3

    def test_play_card(self, cli):
        """PLAY joga carta da mao para o Pack Home."""
        cp = cli.game.current_player
        assert len(cp.hand) > 0
        before_pack = len(cp.pack_home)
        cli.onecmd('PLAY 0')
        assert len(cp.pack_home) == before_pack + 1

    def test_play_invalid_index(self, cli):
        """PLAY com indice invalido nao faz nada."""
        cp = cli.game.current_player
        before = len(cp.pack_home)
        cli.onecmd('PLAY 999')
        assert len(cp.pack_home) == before

    def test_play_non_numeric(self, cli):
        """PLAY com argumento nao numerico nao faz nada."""
        cp = cli.game.current_player
        before = len(cp.pack_home)
        cli.onecmd('PLAY abc')
        assert len(cp.pack_home) == before

    def test_attack_hunting_grounds(self, cli):
        """ATTACK sem defensor ataca hunting grounds."""
        cp = cli.game.current_player
        atk = cp.pack_home[0]
        atk_id = str(atk.card_id)
        cli.onecmd(f'ATTACK {atk_id}')
        assert cli.game.combat.is_active
        assert atk_id in cli.game.combat.attackers
        assert 'hg' in cli.game.combat.defenders

    def test_attack_creature(self, cli):
        """ATTACK com defensor ataca outra criatura."""
        cp = cli.game.current_player
        atk = cp.pack_home[0]
        # Pega uma criatura do oponente
        opponent = cli.game.players[1]
        opp = opponent.pack_home[0]
        cli.onecmd(f'ATTACK {atk.card_id} {opp.card_id}')
        assert cli.game.combat.is_active
        assert str(atk.card_id) in cli.game.combat.attackers
        assert str(opp.card_id) in cli.game.combat.defenders

    def test_declare_and_cycle(self, cli):
        """Ciclo completo via CLI."""
        cp = cli.game.current_player
        atk = cp.pack_home[0]
        atk_id = str(atk.card_id)

        # Inicia combate
        cli.onecmd(f'ATTACK {atk_id}')
        assert cli.game.combat.is_active

        # Declara acao
        cli.onecmd(f'DECLARE {atk_id} strike')
        assert cli.game.combat.declarations.get(atk_id) == 'strike'

        # Revela
        cli.onecmd('REVEAL')
        assert cli.game.combat.step == 'reveal'

        # Resolve
        cli.onecmd('RESOLVE')
        assert cli.game.combat.step == 'end'

        # Encerra
        cli.onecmd('ENDCOMBAT')
        assert not cli.game.combat.is_active

    def test_feint_cycle(self, cli):
        """Usa FEINT para trocar acao."""
        cp = cli.game.current_player
        atk = cp.pack_home[0]
        atk_id = str(atk.card_id)

        cli.onecmd(f'ATTACK {atk_id}')
        cli.onecmd(f'DECLARE {atk_id} strike')
        cli.onecmd('REVEAL')

        # Feint
        cli.onecmd(f'FEINT {atk_id} block')
        assert cli.game.combat.declarations.get(atk_id) == 'block'

    def test_pass_advances_player(self, cli):
        """PASS avanca para o proximo jogador."""
        assert cli.game.current_player.id == 'p1'
        cli.onecmd('PASS')
        assert cli.game.current_player.id == 'p2'

    def test_next_phase(self, cli):
        """NEXT avanca a fase."""
        assert cli.game.phase == 'gather'
        cli.onecmd('NEXT')
        assert cli.game.phase == 'action'

    def test_cards(self, cli):
        """CARDS lista cartas."""
        cli.onecmd('CARDS')

    def test_help(self, cli):
        """HELP mostra ajuda."""
        cli.onecmd('HELP')

    def test_help_command(self, cli):
        """HELP COMMAND mostra ajuda do comando."""
        cli.onecmd('HELP ATTACK')

    def test_save_and_load(self, cli):
        """SAVE e LOAD."""
        cli.onecmd('SAVE test_partida')
        import os
        path = f'/tmp/rage_saves/test_partida.json'
        assert os.path.exists(path)

        cli.game.turn_number = 99
        cli.onecmd('LOAD test_partida')
        assert cli.game.turn_number == 1  # Voltou ao valor salvo

    def test_quiet_mode(self, cli):
        """Comandos nao devem lancar excecoes."""
        for cmd in ['STATUS', 'DRAW', 'DRAW sept', 'CARDS', 'HELP', 'PASS',
                     'NEXT']:
            cli.onecmd(cmd)

    def test_invalid_attack(self, cli):
        """ATTACK com ID inexistente."""
        cli.onecmd('ATTACK 99999')
        assert not cli.game.combat.is_active

    def test_invalid_declare_before_combat(self, cli):
        """DECLARE sem combate."""
        cli.onecmd('DECLARE 500 strike')
        assert not cli.game.combat.is_active

    def test_use_effect_card(self, cli):
        """USE usa carta de efeito da mao."""
        cp = cli.game.current_player
        # Garante que tem carta com modelo_id na mao
        has_effect = any(c.modelo_id for c in cp.hand)
        if not has_effect:
            # Poe uma carta de efeito na mao
            from rage_web.game_engine.state import CardInstance, Zone
            card = CardInstance(
                card_id=999, name='Golpe de Misericórdia',
                card_type='combate', zone=Zone.HAND,
                owner_id=cp.id, controller_id=cp.id,
                modelo_id='golpe_misericordia',
            )
            cp.hand.append(card)
        idx = next(i for i, c in enumerate(cp.hand) if c.modelo_id)
        cli.onecmd(f'USE {idx}')
        # A carta foi removida da mao
        assert all(c.modelo_id != 'golpe_misericordia' or c not in cp.hand
                   for c in cp.hand)

    def test_use_non_effect_card(self, cli):
        """USE em carta sem modelo exibe mensagem."""
        cp = cli.game.current_player
        # Encontra carta sem modelo_id
        idx = None
        for i, c in enumerate(cp.hand):
            if not c.modelo_id:
                idx = i
                break
        if idx is not None:
            cli.onecmd(f'USE {idx}')  # Nao deve quebrar
