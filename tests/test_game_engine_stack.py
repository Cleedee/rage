"""Testes da pilha de resolucao e sistema de prioridade."""

import pytest

from rage_web.game_engine.stack import (
    Pilha, ItemPilha, TipoItemPilha,
    PrioridadeStatus, anunciar_carta, obter_acoes_validas,
)
from rage_web.game_engine.state import GameState, PlayerState
from rage_web.game_engine.cli import create_sample_game


@pytest.fixture
def pilha():
    return Pilha()


@pytest.fixture
def game():
    g = create_sample_game(seed=42)
    return g


class TestItemPilha:
    def test_criacao_basica(self):
        """Cria item de pilha simples."""
        item = ItemPilha(
            tipo='carta',
            descricao='Golpe de Misericórdia',
            jogador_id='p1',
        )
        assert item.tipo == TipoItemPilha.CARTA
        assert item.descricao == 'Golpe de Misericórdia'

    def test_esta_esperando_modo_true(self):
        """Carta modal sem modo escolhido aguarda."""
        item = ItemPilha(
            tipo='carta', descricao='Teste', jogador_id='p1',
            modelo_id='golpe_misericordia', modo_idx=None,
        )
        assert item.esta_esperando_modo()

    def test_esta_esperando_modo_false(self):
        """Carta com modo ja escolhido nao aguarda."""
        item = ItemPilha(
            tipo='carta', descricao='Teste', jogador_id='p1',
            modelo_id='golpe_misericordia', modo_idx=0,
            modo_escolhido=True,
        )
        assert not item.esta_esperando_modo()


class TestPilha:
    def test_pilha_vazia(self, pilha):
        """Pilha comeca vazia."""
        assert pilha.vazia
        assert pilha.tamanho == 0
        assert pilha.topo is None

    def test_empilhar(self, pilha):
        """Empilhar adiciona item no topo."""
        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1')
        pilha.empilhar(item)
        assert not pilha.vazia
        assert pilha.tamanho == 1
        assert pilha.topo is item

    def test_empilhar_muda_prioridade(self, pilha):
        """Apos empilhar, prioridade vira esperando_resposta."""
        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1')
        pilha.empilhar(item)
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_RESPOSTA

    def test_passar_para_resolver(self, pilha):
        """Dois passes consecutivos resolvem o topo."""
        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1',
                         resolver=lambda g: ['ok'])
        pilha.empilhar(item)
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_RESPOSTA

        r1 = pilha.passar(None)  # Oponente passa
        assert r1 == 'espera'

        r2 = pilha.passar(None)  # Jogador ativo passa
        assert r2 == 'resolve'

    def test_passar_pilha_vazia_fim(self, pilha):
        """Passar com pilha vazia finaliza."""
        r1 = pilha.passar(None)
        assert r1 == 'espera'
        r2 = pilha.passar(None)
        assert r2 == 'fim'
        assert pilha.prioridade == PrioridadeStatus.FINALIZADO

    def test_resolver_topo(self, pilha):
        """Resolver topo executa callback e remove da pilha."""
        logs = []

        def resolver(game):
            logs.append('resolvido')
            return ['Resolvido com sucesso']

        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1', resolver=resolver)
        pilha.empilhar(item)

        resultado = pilha.resolver_topo(None)
        assert 'sucesso' in resultado[0]
        assert logs == ['resolvido']
        assert pilha.vazia

    def test_resolver_modal_sem_modo(self, pilha):
        """Resolver carta modal sem modo retorna prompt."""
        item = ItemPilha(
            tipo='carta', descricao='Golpe de Misericórdia',
            jogador_id='p1',
            modelo_id='golpe_misericordia',
            modo_idx=None,
            modo_escolhido=False,
        )
        pilha.empilhar(item)
        resultado = pilha.resolver_topo(None)
        assert 'AGUARDANDO' in resultado[0]
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_MODO
        assert pilha.prompt_atual is not None

    def test_escolher_modo(self, pilha):
        """Escolher modo apos prompt funciona."""
        item = ItemPilha(
            tipo='carta', descricao='Golpe de Misericórdia',
            jogador_id='p1',
            modelo_id='golpe_misericordia',
            modo_idx=None,
            modo_escolhido=False,
        )
        pilha.empilhar(item)
        pilha.resolver_topo(None)
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_MODO

        erro = pilha.escolher_modo(2)  # Modo dano
        assert erro is None
        assert pilha.topo.modo_idx == 2
        assert pilha.topo.modo_escolhido
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_ACAO

    def test_anular_topo(self, pilha):
        """Anular remove da pilha sem resolver."""
        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1')
        pilha.empilhar(item)
        assert pilha.tamanho == 1

        logs = pilha.anular_topo(None)
        assert 'anulado' in logs[0]
        assert pilha.vazia

    def test_reiniciar(self, pilha):
        """Reiniciar limpa tudo."""
        item = ItemPilha(tipo='carta', descricao='Teste',
                         jogador_id='p1')
        pilha.empilhar(item)
        pilha.reiniciar()
        assert pilha.vazia
        assert pilha.prioridade == PrioridadeStatus.ESPERANDO_ACAO


class TestAnunciarCarta:
    def test_anunciar_cria_item(self, game):
        """Anunciar carta coloca item na pilha."""
        item = anunciar_carta(
            game, 'p1', 'carta_1', 'golpe_misericordia',
            modo_idx=None,
        )
        assert item is not None
        assert item.tipo == TipoItemPilha.CARTA
        assert game.pilha.tamanho == 1

    def test_anunciar_com_modo_escolhido(self, game):
        """Anunciar com modo ja escolhido."""
        item = anunciar_carta(
            game, 'p1', 'carta_1', 'golpe_misericordia',
            modo_idx=2,
        )
        assert item.modo_idx == 2
        assert item.modo_escolhido

    def test_obter_acoes_validas(self, game):
        """Acoes validas refletem estado da pilha."""
        acoes = obter_acoes_validas(game, 'p1')
        assert 'acoes_disponiveis' in acoes
        assert 'jogar_carta' in acoes['acoes_disponiveis']
        assert 'passar' in acoes['acoes_disponiveis']
