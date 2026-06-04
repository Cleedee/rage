"""Testes do sistema de anuncio e resolucao (Rage CCG)."""

import pytest

from rage_web.game_engine.stack import (
    Anunciador, EfeitoAnunciado, EstadoAnuncio,
    anunciar_e_resolver,
)
from rage_web.game_engine.cli import create_sample_game
from rage_web.game_engine.state import GameState


@pytest.fixture
def anunciador():
    return Anunciador()


@pytest.fixture
def game():
    return create_sample_game(seed=42)


class TestEfeitoAnunciado:
    def test_criacao(self):
        """Cria efeito anunciado basico."""
        efeito = EfeitoAnunciado(
            id='carta_1', descricao='Golpe de Misericórdia',
            jogador_id='p1',
        )
        assert efeito.id == 'carta_1'
        assert not efeito.anulado

    def test_aguardando_modo_true(self):
        """Carta modal sem modo escolhido aguarda."""
        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
            modelo_id='golpe_misericordia',
        )
        assert efeito.aguardando_modo

    def test_aguardando_modo_false(self):
        """Carta com modo escolhido nao aguarda."""
        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
            modelo_id='golpe_misericordia',
            modo_idx=2, modo_escolhido=True,
        )
        assert not efeito.aguardando_modo


class TestAnunciador:
    def test_estado_inicial(self, anunciador):
        """Anunciador comeca livre."""
        assert anunciador.estado == EstadoAnuncio.LIVRE
        assert not anunciador.tem_anuncio_ativo

    def test_anunciar(self, anunciador):
        """Anunciar muda estado."""
        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
        )
        assert anunciador.anunciar(efeito)
        assert anunciador.tem_anuncio_ativo
        assert anunciador.estado == EstadoAnuncio.ANUNCIADO

    def test_anunciar_duas_vezes(self, anunciador):
        """Nao pode anunciar se ja tem um pendente."""
        e1 = EfeitoAnunciado(id='c1', descricao='Teste', jogador_id='p1')
        e2 = EfeitoAnunciado(id='c2', descricao='Teste2', jogador_id='p2')
        assert anunciador.anunciar(e1)
        assert not anunciador.anunciar(e2)

    def test_anular(self, anunciador):
        """Anular marca efeito como cancelado e limpa."""
        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
        )
        anunciador.anunciar(efeito)
        assert anunciador.anular(None, 'p2')
        assert efeito.anulado
        assert not anunciador.tem_anuncio_ativo

    def test_anular_sem_anuncio(self, anunciador):
        """Anular sem anuncio retorna False."""
        assert not anunciador.anular(None, 'p2')

    def test_resolver_sem_anuncio(self, anunciador):
        """Resolver sem anuncio retorna erro."""
        logs = anunciador.resolver(None)
        assert 'Nenhum' in logs[0]

    def test_resolver_com_callback(self, anunciador):
        """Resolver executa callback."""
        logs_resultado = []

        def resolver(game):
            logs_resultado.append('resolveu')
            return ['Resolvido']

        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
            resolver=resolver,
        )
        anunciador.anunciar(efeito)
        logs = anunciador.resolver(None)
        assert logs_resultado == ['resolveu']
        assert 'Resolvido' in logs[0]
        assert not anunciador.tem_anuncio_ativo

    def test_resolver_anulado(self, anunciador):
        """Resolver efeito anulado nao executa callback."""
        def resolver(game):
            return ['Nao deveria executar']

        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
            resolver=resolver,
        )
        anunciador.anunciar(efeito)
        anunciador.anular(None, 'p2')
        # Anular ja limpa, entao resolver nao faz nada
        logs = anunciador.resolver(None)
        assert 'Nenhum' in logs[0]

    def test_escolher_modo_antes_do_prompt(self, anunciador):
        """Escolher modo sem prompt da erro."""
        erro = anunciador.escolher_modo(0)
        assert erro is not None

    def test_ciclo_modal(self, anunciador):
        """Ciclo completo: anuncio -> prompt modo -> escolha -> resolve."""
        logs_resolver = []

        def resolver(game):
            logs_resolver.append('resolveu')
            return ['Resolvido']

        efeito = EfeitoAnunciado(
            id='c1', descricao='Golpe de Misericórdia',
            jogador_id='p1',
            modelo_id='golpe_misericordia',
            resolver=resolver,
        )
        anunciador.anunciar(efeito)

        # Tenta resolver -> AGUARDANDO_MODO
        logs = anunciador.resolver(None)
        assert 'AGUARDANDO' in logs[0]
        assert anunciador.estado == EstadoAnuncio.AGUARDANDO_MODO
        assert anunciador.prompt_atual is not None

        # Escolhe modo
        erro = anunciador.escolher_modo(2)
        assert erro is None
        assert anunciador.estado == EstadoAnuncio.ANUNCIADO

        # Agora resolve de verdade
        logs = anunciador.resolver(None)
        assert logs_resolver == ['resolveu']
        assert not anunciador.tem_anuncio_ativo

    def test_responder(self, anunciador):
        """Responder ao anuncio registra a resposta."""
        efeito = EfeitoAnunciado(
            id='c1', descricao='Teste', jogador_id='p1',
        )
        anunciador.anunciar(efeito)
        resposta = EfeitoAnunciado(
            id='c2', descricao='Resposta', jogador_id='p2',
        )
        erro = anunciador.responder(None, resposta)
        assert erro is None
        assert 'respondeu' in anunciador.ultimos_logs[-1]


class TestAnunciarEResolver:
    def test_anunciar_e_resolver_direto(self, game):
        """Anunciar e resolver carta com modo funciona."""
        logs = anunciar_e_resolver(
            game, 'p1', 'carta_1', 'furia_primitiva',
            modo_idx=0,
        )
        assert len(logs) > 0
        assert game.anunciador.estado == EstadoAnuncio.LIVRE

    def test_anunciar_modal_sem_modo(self, game):
        """Carta modal sem modo retorna prompt."""
        logs = anunciar_e_resolver(
            game, 'p1', 'carta_1', 'golpe_misericordia',
        )
        assert 'AGUARDANDO' in logs[0]
        assert game.anunciador.estado == EstadoAnuncio.AGUARDANDO_MODO

    def test_anunciar_modelo_inexistente(self, game):
        """Modelo inexistente retorna erro."""
        logs = anunciar_e_resolver(
            game, 'p1', 'carta_1', 'modelo_inexistente',
        )
        assert 'nao encontrado' in logs[0]
