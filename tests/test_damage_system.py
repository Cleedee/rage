"""Testes do sistema de dano revisado (Item #15, refatorado).

Regra 6.4 atualizada:
- Ataques basicos (strike, claw, anatomy_lesson) NAO criam damage cards.
  O dano e acumulado em basic_damage_taken.
- Combat Actions reais (Surprise Attack, etc) sao anexadas via damage_cards.
- total_dano = soma(damage_cards) + basic_damage_taken
"""
import pytest
from rage_web.game_engine.state import (
    CardInstance, Zone, anexar_dano,
)
from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, resolve_combat, end_combat,
    COMBAT_ACTIONS,
)


class TestDamageSystemRework:
    """Testes do sistema de dano revisado."""

    def _make_creature(self, health=6, rage=4, gnosis=3,
                       name='Test Creature') -> CardInstance:
        return CardInstance(
            card_id=999,
            name=name,
            card_type='Character',
            zone=Zone.PACK_HOME,
            owner_id='p1',
            controller_id='p1',
            rage=rage,
            gnosis=gnosis,
            health=health,
            health_current=health,
            damage='',
        )

    def test_total_dano_vazio(self):
        """Sem dano, total_dano = 0."""
        c = self._make_creature()
        assert c.total_dano == 0
        assert c.health_current == c.health

    def test_basic_damage_acumula(self):
        """Ataques basicos acumulam em basic_damage_taken."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 3, 'p1')
        assert c.total_dano == 3
        assert c.basic_damage_taken == 3
        assert c.health_current == 7
        anexar_dano(c, c, 2, 'p1')
        assert c.total_dano == 5
        assert c.basic_damage_taken == 5
        assert c.health_current == 5

    def test_sync_health_apos_curar_basic_damage(self):
        """Reduzir basic_damage_taken e chamar sync_health corrige HP."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 4, 'p1')
        assert c.health_current == 6
        # Cura manual: reduz basic_damage_taken
        c.basic_damage_taken = max(0, c.basic_damage_taken - 2)
        c.sync_health()
        assert c.total_dano == 2
        assert c.health_current == 8

    def test_sync_health_apos_cura_parcial_com_card(self):
        """Remover damage card (Combat Action) e sync_health."""
        c = self._make_creature(health=10)

        # Cria um CardInstance mock de Combat Action para anexar
        combat_card = CardInstance(
            card_id=1319, name='Surprise Attack',
            card_type='Combat Action', zone=Zone.OUT_OF_PLAY,
            owner_id='p1', controller_id='p1',
            damage='3',
        )
        anexar_dano(c, c, 3, 'p1', carta_combate=combat_card)
        assert c.total_dano == 3

        combat_card2 = CardInstance(
            card_id=312, name='Dodge',
            card_type='Combat Action', zone=Zone.OUT_OF_PLAY,
            owner_id='p1', controller_id='p1',
            damage='5',
        )
        anexar_dano(c, c, 5, 'p1', carta_combate=combat_card2)
        assert c.total_dano == 8
        assert c.health_current == 2

        # Remove a damage card de menor valor (3)
        menor = min(c.damage_cards, key=lambda d: int(d.damage or '0'))
        assert int(menor.damage or '0') == 3
        c.damage_cards.remove(menor)
        c.sync_health()
        assert c.total_dano == 5
        assert c.health_current == 5

    def test_basic_e_combat_misturados(self):
        """Danos basicos e Combat Actions somam corretamente."""
        c = self._make_creature(health=10)

        # Dano basico
        anexar_dano(c, c, 2, 'p1')
        assert c.total_dano == 2
        assert c.basic_damage_taken == 2

        # Combat Action
        combat_card = CardInstance(
            card_id=1319, name='Surprise Attack',
            card_type='Combat Action', zone=Zone.OUT_OF_PLAY,
            owner_id='p1', controller_id='p1',
            damage='3',
        )
        anexar_dano(c, c, 3, 'p1', carta_combate=combat_card)
        assert c.total_dano == 5  # 2 basic + 3 combat card
        assert len(c.damage_cards) == 1
        assert c.basic_damage_taken == 2
        assert c.health_current == 5

    def test_morte_por_dano_acumulado(self):
        """Morte quando total_dano >= health."""
        c = self._make_creature(health=5)
        anexar_dano(c, c, 3, 'p1')
        assert c.health_current == 2
        anexar_dano(c, c, 2, 'p1')
        assert c.health_current == 0  # 3+2=5 >= 5

    def test_cura_remove_basic_primeiro_quando_sem_cards(self):
        """Se nao ha damage_cards, cura reduz basic_damage_taken."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 5, 'p1')
        assert c.total_dano == 5
        assert c.health_current == 5
        # Cura manual
        c.basic_damage_taken = max(0, c.basic_damage_taken - 3)
        c.sync_health()
        assert c.total_dano == 2
        assert c.health_current == 8

    def test_anexar_dano_com_agravado(self):
        """Dano agravado em Combat Action marcado corretamente."""
        c = self._make_creature(health=10)
        combat_card = CardInstance(
            card_id=1319, name='Surprise Attack',
            card_type='Combat Action', zone=Zone.OUT_OF_PLAY,
            owner_id='p1', controller_id='p1',
        )
        anexar_dano(c, c, 4, 'p1',
                    is_aggravated=True, carta_combate=combat_card)
        assert combat_card.is_aggravated
        # Dano basico nao tem is_aggravated
        anexar_dano(c, c, 2, 'p1', is_aggravated=True)
        assert c.total_dano == 6
        # Aggravated damage cards sao filtradas na regeneracao
        nao_agravadas = [d for d in c.damage_cards if not d.is_aggravated]
        assert len(nao_agravadas) == 0

    def test_crinos_flip_mantem_dano_total(self):
        """Flip para Crinos recalcula health mas preserva total_dano."""
        c = CardInstance(
            card_id=999,
            name='Test Crinos',
            card_type='Character',
            zone=Zone.PACK_HOME,
            owner_id='p1',
            controller_id='p1',
            rage=3, health=4, gnosis=3,
            health_current=4,
            rage_morph=6, health_morph=8, gnosis_morph=5,
        )
        # Toma 2 de dano basico
        anexar_dano(c, c, 2, 'p1')
        assert c.health_current == 2
        assert c.total_dano == 2
        anexar_dano(c, c, 1, 'p1')
        assert c.health_current == 1
        assert c.total_dano == 3
        # Agora em Crinos, health_current = health_morph - total_dano
        c.is_crinos = True
        c.restricoes.append('health_breed')
        c.sync_health()
        assert c.health_current == 5  # 8 - 3
        assert c.total_dano == 3  # Damage cards preservadas


class TestDamageSystemIntegration:
    """Testes de integracao do sistema de dano."""

    def _setup_game(self, seed=42):
        from rage_web.game_engine.cli import build_game_from_decks
        game = build_game_from_decks(160, 629, seed=seed)
        for p in game.players:
            for c in p.pack_home:
                game.register_card_passives(c, p)
            p.draw_combat(p.hand_size_combat)
        return game

    def test_combat_end_syncs_all_creatures(self):
        """Apos end_combat, sync_health e chamado em todas criaturas."""
        game = self._setup_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = p1.pack_home[0]
        dfd = p2.pack_home[0]

        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'strike')
        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        resolve_combat(game)
        end_combat(game)

        # Todas as criaturas devem ter health_current sincronizado
        for p in game.players:
            for c in p.pack_home:
                if c.health_current <= 0:
                    continue
                assert c.health_current == c.health - c.total_dano, \
                    f'{c.name} health_current={c.health_current} != {c.health - c.total_dano}'

    def test_damage_card_consistency_after_combat(self):
        """Damage cards apos combate: apenas Combat Actions aparecem."""
        game = self._setup_game()
        p1 = game.players[0]
        p2 = game.players[1]
        atk = p1.pack_home[0]
        dfd = p2.pack_home[0]

        start_combat(game, [str(atk.card_id)], [str(dfd.card_id)])
        game.combat.step = 'play_card'
        declare_action(game, str(atk.card_id), 'strike')
        declare_action(game, str(dfd.card_id), 'strike')
        game.combat.targets[str(atk.card_id)] = str(dfd.card_id)
        resolve_combat(game)

        # Verifica: criaturas com dano tem basic_damage_taken > 0 ou damage_cards
        total_com_dano = 0
        for p in game.players:
            for c in p.pack_home + p.hunting_grounds + p.umbra:
                if c.total_dano > 0:
                    total_com_dano += 1
                    # Nao deve haver damage cards virtuais com card_id = atacante
                    for dc in c.damage_cards:
                        # Se e um card de combate real, deve ter card_type='Combat Action'
                        if dc.card_type == 'Damage Card':
                            pytest.fail(f'Damage card virtual encontrada: {dc.name}')
        assert total_com_dano > 0, 'Nenhum dano aplicado'
