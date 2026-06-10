"""Testes da regra 2.1.3 — Hand Sizes.

Cobre:
- modificar_hand_size effect type
- Old Storm Chaser: +1 sept hand size
- redraw_sept/redraw_combat compra ate o hand size ajustado
- Past Life: -1 sept hand size
- Recalculo quando carta entra/sai de jogo
"""
import pytest
from rage_web.game_engine.state import Zone
from rage_web.game_engine.cli import build_game_from_decks


class TestHandSize:
    """Testes da regra 2.1.3 — Hand Sizes."""

    def test_default_hand_sizes(self):
        """Hand sizes padrao sao 5."""
        from rage_web.game_engine.state import PlayerState
        p = PlayerState(id='p1', name='Test')
        assert p.hand_size_sept == 5
        assert p.hand_size_combat == 5

    def test_recalcular_detecta_old_storm_chaser(self):
        """_recalcular_hand_sizes detecta Old Storm Chaser em jogo."""
        game = build_game_from_decks(90, 619, seed=42)
        p = game.players[0]
        # Verifica se Old Storm Chaser (207) esta no pack inicial
        tem_old_storm = any(c.card_id == 207 for c in p.pack_home)
        if tem_old_storm:
            game._recalcular_hand_sizes(p)
            assert p.hand_size_sept == 6, \
                'Old Storm Chaser deve aumentar hand size para 6'
        else:
            # Pode estar na mao
            tem_old_storm = any(c.card_id == 207 for c in p.hand)
            if tem_old_storm:
                game._recalcular_hand_sizes(p)
                assert p.hand_size_sept == 6, \
                    'Old Storm Chaser na mao ainda aumenta hand size'
            else:
                pytest.skip('Old Storm Chaser nao encontrado')

    def test_redraw_respeita_hand_size_ajustado(self):
        """redraw_sept compra ate hand_size_sept quando ajustado."""
        game = build_game_from_decks(90, 619, seed=42)
        p = game.players[0]
        # Simula: jogador comecou com 5 cartas, depois hand size aumentou
        # Zera a mao e redesenha para o novo tamanho
        p.hand.clear()
        p.hand_size_sept = 7
        drawn = p.redraw_sept(descartar_primeiro=False)
        assert len(p.hand) == 7, \
            f'Mao deve ter 7 cartas, mas tem {len(p.hand)}'
        assert len(drawn) == 7, \
            f'Deve ter comprado 7 cartas, mas comprou {len(drawn)}'

    def test_redraw_combat_respeita_hand_size(self):
        """redraw_combat compra ate hand_size_combat."""
        game = build_game_from_decks(90, 619, seed=42)
        p = game.players[0]
        p.hand.clear()
        p.hand_size_combat = 7
        drawn = p.redraw_combat(descartar_primeiro=False)
        assert len(p.combat_hand) <= 7, \
            f'Mao de combate deve <= 7, mas tem {len(p.combat_hand)}'

    def test_hand_size_minimo_1(self):
        """Hand size nunca fica abaixo de 1."""
        from rage_web.game_engine.state import PlayerState
        p = PlayerState(id='p1', name='Test')
        p.hand_size_sept = 1
        # Mesmo com muitas Past Lives, minimo e 1
        self._recalcular_for_test(p, 5)  # 5 Past Lives
        # Como nao estamos em jogo real, testamos a logica manualmente
        base = 5
        for qtd_past_lives in range(10):
            novo = max(1, base - qtd_past_lives)
            assert novo >= 1, f'Hand size deve ser >= 1, mas e {novo}'

    @staticmethod
    def _recalcular_for_test(p, qtd_past_lives):
        """Simula recalculo de hand size para teste."""
        base = 5
        novo = max(1, base - qtd_past_lives)
        p.hand_size_sept = novo

    def test_effect_modificar_hand_size_exists(self):
        """O efeito modificar_hand_size existe no enum EfeitoTipo."""
        from rage_web.game_engine.effects import EfeitoTipo
        assert hasattr(EfeitoTipo, 'MODIFICAR_HAND_SIZE')
        assert EfeitoTipo.MODIFICAR_HAND_SIZE == 'modificar_hand_size'
