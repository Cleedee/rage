"""Testes do sistema de efeitos de carta."""

import pytest

from rage_web.game_engine.effects import (
    ModeloCarta, Modo, Efeito, EfeitoTipo, AlvoTipo,
    ResolvedorEfeitos, aplicar_carta, CARTAS_EXEMPLO,
)
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.state import CardInstance, Zone


@pytest.fixture
def game():
    return create_sample_game(seed=42)


@pytest.fixture
def resolvedor(game):
    return ResolvedorEfeitos(game)


class TestModeloCarta:
    def test_criacao_golpe_misericordia(self):
        """Cria o modelo da carta exemplo."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        assert carta.id == 'golpe_misericordia'
        assert carta.nome == 'Golpe de Misericórdia'
        assert len(carta.modos) == 3

    def test_modo_por_indice(self):
        """Acessa modo por indice."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        modo = carta.modo_por_indice(0)
        assert modo is not None
        assert 'ferida' in modo.descricao.lower()

    def test_modo_invalido_retorna_none(self):
        """Indice invalido retorna None."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        assert carta.modo_por_indice(99) is None

    def test_toque_curativo(self):
        """Carta de cura."""
        carta = CARTAS_EXEMPLO['toque_curativo']
        assert carta.tipo == 'gift'
        assert carta.modos[0].efeitos[0].quantidade == 3


class TestResolvedorEfeitos:
    def test_dano_em_criatura(self, game, resolvedor):
        """Dano reduz vida de criatura."""
        criatura = game.players[0].pack_home[0]
        health_antes = criatura.health_current
        efeito = Efeito(tipo=EfeitoTipo.DANO, quantidade=2,
                        condicao='criatura_aliada')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert criatura.health_current == max(0, health_antes - 2)

    def test_dano_sem_alvo_nao_quebra(self, game, resolvedor):
        """Dano sem alvo retorna False."""
        efeito = Efeito(tipo=EfeitoTipo.DANO, quantidade=5,
                        condicao='criatura_inimiga_ferida')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')
        # Nenhuma criatura inimiga ferida
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert not resultado

    def test_curar_criatura(self, game, resolvedor):
        """Cura restaura vida."""
        criatura = game.players[0].pack_home[0]
        criatura.health_current = 1  # Ferido
        efeito = Efeito(tipo=EfeitoTipo.CURAR, quantidade=3,
                        condicao='criatura_aliada_ferida')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert criatura.health_current > 1

    def test_destruir_criatura_inimiga(self, game, resolvedor):
        """Destruir remove criatura do pack."""
        inimigo = game.players[1].pack_home[0]
        efeito = Efeito(tipo=EfeitoTipo.DESTRUIR,
                        condicao='criatura_inimiga')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert inimigo not in game.players[1].pack_home
        assert inimigo.zone == Zone.DISCARD_COMBAT

    def test_descarte_mao_inimiga(self, game, resolvedor):
        """Descarte remove cartas da mao do oponente."""
        opp = game.players[1]
        antes = len(opp.hand)
        efeito = Efeito(tipo=EfeitoTipo.DESCARTE, quantidade=2,
                        condicao='jogador_inimigo')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert len(opp.hand) == antes - 2

    def test_descarte_mao_menos_4(self, game, resolvedor):
        """Descarta ate resto 4."""
        opp = game.players[1]
        # Enche a mao
        while len(opp.hand) < 10:
            opp.draw_combat(1)
        antes = len(opp.hand)
        efeito = Efeito(tipo=EfeitoTipo.DESCARTE,
                        quantidade='mao_oponente_menos_4',
                        condicao='jogador_inimigo')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert len(opp.hand) == min(4, antes)

    def test_comprar_carta(self, game, resolvedor):
        """Comprar adiciona carta a mao."""
        p = game.players[0]
        antes = len(p.hand)
        deck_antes = len(p.deck_combat)
        efeito = Efeito(tipo=EfeitoTipo.COMPRAR, quantidade=2)
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, p)
        assert resultado
        assert len(p.hand) == antes + 2
        assert len(p.deck_combat) == deck_antes - 2

    def test_tapar_criatura(self, game, resolvedor):
        """Tapar marca criatura como tapped."""
        criatura = game.players[0].pack_home[0]
        efeito = Efeito(tipo=EfeitoTipo.TAPAR,
                        condicao='criatura_aliada')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert criatura.is_tapped

    def test_ganhar_vp(self, game, resolvedor):
        """Ganhar VP incrementa contador."""
        p = game.players[0]
        vp_antes = p.victory_points
        efeito = Efeito(tipo=EfeitoTipo.GANHAR_VP, quantidade=3)
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, p)
        assert resultado
        assert p.victory_points == vp_antes + 3


class TestAplicarCartaCompleta:
    def test_golpe_misericordia_dano(self, game):
        """Aplica modo dano do Golpe de Misericordia."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        criatura = game.players[1].pack_home[0]

        logs = aplicar_carta(game, carta, 'p1', modo_idx=2)  # modo dano
        assert len(logs) > 0

    def test_golpe_misericordia_destruir(self, game):
        """Aplica modo destruir do Golpe de Misericordia."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']

        # Fere uma criatura inimiga primeiro
        inimigo = game.players[1].pack_home[0]
        inimigo.health_current = 1

        logs = aplicar_carta(game, carta, 'p1', modo_idx=0)  # modo destruir
        assert len(logs) > 0
        assert inimigo.zone == Zone.DISCARD_COMBAT

    def test_toque_curativo_cura(self, game):
        """Aplica Toque Curativo."""
        carta = CARTAS_EXEMPLO['toque_curativo']

        # Fere uma criatura aliada
        aliado = game.players[0].pack_home[0]
        aliado.health_current = 1

        logs = aplicar_carta(game, carta, 'p1', modo_idx=0)
        assert len(logs) > 0
        assert aliado.health_current > 1

    def test_carta_inexistente(self, game):
        """Modo invalido nao quebra."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        logs = aplicar_carta(game, carta, 'p1', modo_idx=99)
        assert len(logs) == 1
        assert 'invalido' in logs[0].lower()

    def test_jogador_inexistente(self, game):
        """Jogador invalido nao quebra."""
        carta = CARTAS_EXEMPLO['golpe_misericordia']
        logs = aplicar_carta(game, carta, 'inexistente', modo_idx=0)
        assert 'nao encontrado' in logs[0]
