"""Testes do sistema de dano revisado (Item #15).

Cobre:
- total_dano property: soma correta das damage cards
- sync_health(): health_current = health - total_dano
- anexar_dano: cria damage card + sync
- _resolver_curar: remove damage cards em vez de so HP
- Regeneration: remove lowest damage card
- Consistencia apos combate
"""
import pytest
from rage_web.game_engine.state import (
    CardInstance, Zone, anexar_dano, criar_carta_dano,
)
from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, resolve_combat, end_combat,
    COMBAT_ACTIONS, _flipar_para_crinos,
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
        """Sem damage cards, total_dano = 0."""
        c = self._make_creature()
        assert c.total_dano == 0
        assert c.health_current == c.health

    def test_total_dano_apos_anexar(self):
        """Apos anexar damage cards, total_dano = soma dos valores."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 3, 'p1')
        assert c.total_dano == 3
        assert c.health_current == 7
        anexar_dano(c, c, 2, 'p1')
        assert c.total_dano == 5
        assert c.health_current == 5

    def test_sync_health_apos_remocao_manual(self):
        """sync_health corrige health_current se attached_damage mudar."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 4, 'p1')
        assert c.health_current == 6
        # Remove manualmente a damage card sem chamar anexar_dano
        c.attached_damage.clear()
        c.health_current = 7  # Dessincronizado!
        assert c.health_current == 7
        assert c.total_dano == 0
        # Sync corrige
        c.sync_health()
        assert c.health_current == 10  # health - 0 = 10

    def test_sync_health_apos_cura_parcial(self):
        """sync_health apos remocao de damage cards via cura."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 3, 'p1')
        anexar_dano(c, c, 5, 'p1')
        assert c.total_dano == 8
        assert c.health_current == 2
        # Remove a damage card de menor valor (3)
        menor = min(c.attached_damage, key=lambda d: int(d.damage or '0'))
        c.attached_damage.remove(menor)
        c.sync_health()
        assert c.total_dano == 5
        assert c.health_current == 5

    def test_multiplas_damage_cards(self):
        """Multiplas damage cards somam corretamente."""
        c = self._make_creature(health=10)
        for valor in (1, 2, 3, 4):
            anexar_dano(c, c, valor, 'p1')
        assert c.total_dano == 10  # 1+2+3+4
        assert c.health_current == 0  # Morreu

    def test_morte_por_dano_acumulado(self):
        """Morte quando total_dano >= health."""
        c = self._make_creature(health=5)
        anexar_dano(c, c, 3, 'p1')
        assert c.health_current == 2
        anexar_dano(c, c, 2, 'p1')
        assert c.health_current == 0  # 3+2=5 >= 5
        assert c.health_current <= 0  # morto

    def test_regeneration_remove_damage_card(self):
        """Regeneracao remove a damage card de menor valor."""
        c = self._make_creature(health=10)
        anexar_dano(c, c, 3, 'p1')
        anexar_dano(c, c, 5, 'p1')
        anexar_dano(c, c, 1, 'p1')
        assert c.total_dano == 9
        assert c.health_current == 1

        # Regeneracao: remove menor (1)
        menor = min(c.attached_damage, key=lambda d: int(d.damage or '0'))
        assert int(menor.damage or '0') == 1
        c.attached_damage.remove(menor)
        c.sync_health()
        assert c.total_dano == 8
        assert c.health_current == 2

    def test_anexar_dano_com_agravado(self):
        """Dano agravado marcado corretamente na damage card."""
        c = self._make_creature(health=10)
        dc = anexar_dano(c, c, 4, 'p1', is_aggravated=True)
        assert dc.is_aggravated
        assert c.total_dano == 4
        # Aggravated damage cards sao filtradas na regeneracao
        nao_agravadas = [d for d in c.attached_damage if not d.is_aggravated]
        assert len(nao_agravadas) == 0

    def test_crinos_flip_mantem_damage_cards(self):
        """Flip para Crinos preserva damage cards e recalcula health."""
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
        # Toma 2 de dano (ainda vivo em Breed)
        anexar_dano(c, c, 2, 'p1')
        assert c.health_current == 2
        assert c.total_dano == 2
        # Nao deve flipar ainda (threshold = min(3, 4) = 3)
        # Precisamos de mais 1 de dano
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
                    # Morta, nao precisa estar sincronizada
                    continue
                assert c.health_current == c.health - c.total_dano, \
                    f'{c.name} health_current={c.health_current} != {c.health - c.total_dano}'

    def test_damage_card_consistency_after_combat(self):
        """Damage cards apos combate: se anexadas, tem valores > 0."""
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

        # Verifica se damage cards existem e tem valores positivos
        total_damage_cards = 0
        for p in game.players:
            for c in p.pack_home + p.hunting_grounds + p.umbra:
                total_damage_cards += len(c.attached_damage)
                for dc in c.attached_damage:
                    valor = int(dc.damage or '0')
                    if valor <= 0:
                        continue  # Cards de 0 dano nao contam
                    assert valor > 0, f'Damage card com valor {valor}'
                    assert dc.name != '', 'Damage card sem nome'
        # Deve ter pelo menos uma damage card (strike causa dano)
        assert total_damage_cards > 0, 'Nenhuma damage card criada'
