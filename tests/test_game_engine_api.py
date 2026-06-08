"""Testes da API REST do motor de jogo."""

import json

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def game_id(client):
    """Cria uma partida de exemplo via API e retorna seu ID."""
    resp = client.post('/api/game/new', json={'seed': 42})
    assert resp.status_code == 201
    data = resp.get_json()
    game_id = data['game_id']

    # Adiciona um alvo no HG para testes de combate
    from rage_web.game_engine.state import Zone, CardInstance
    from rage_web.game_engine.api import _games
    game = _games.get(game_id)
    if game:
        vitima = CardInstance(
            card_id=9999, name='Victim Test', card_type='Victim',
            zone=Zone.HUNTING_GROUNDS, owner_id='global',
            controller_id='global', health=3, health_current=3,
        )
        game.hunting_grounds_cards.append(vitima)

    return game_id


class TestGameAPI:
    """Testes dos endpoints da API REST."""

    def test_new_game(self, client):
        """POST /api/game/new cria partida."""
        resp = client.post('/api/game/new', json={'seed': 42})
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'game_id' in data
        assert 'state' in data
        state = data['state']
        assert state['turn_number'] == 1
        assert state['phase'] == 'redraw'
        assert len(state['players']) == 2

    def test_new_game_default_seed(self, client):
        """POST /api/game/new sem body funciona."""
        resp = client.post('/api/game/new')
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'game_id' in data

    def test_get_game(self, client, game_id):
        """GET /api/game/<id> retorna estado."""
        resp = client.get(f'/api/game/{game_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['game_id'] == game_id
        assert 'state' in data

    def test_get_game_not_found(self, client):
        """GET /api/game/<id> com ID invalido."""
        resp = client.get('/api/game/inexistente')
        assert resp.status_code == 404

    def test_players(self, client, game_id):
        """GET /api/game/<id>/players lista jogadores."""
        resp = client.get(f'/api/game/{game_id}/players')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['players']) == 2
        assert data['players'][0]['name'] == 'Jogador 1'

    def test_legal_actions(self, client, game_id):
        """GET /api/game/<id>/legal-actions retorna acoes."""
        resp = client.get(f'/api/game/{game_id}/legal-actions')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'available' in data
        assert len(data['available']) > 0

    def test_draw_combat(self, client, game_id):
        """POST /api/game/<id>/draw compra carta de combate."""
        # Pega mao antes
        state_before = client.get(f'/api/game/{game_id}').get_json()['state']
        hand_before = state_before['players'][0]['hand']

        resp = client.post(f'/api/game/{game_id}/draw',
                           json={'deck': 'combat', 'count': 1})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['drawn']) == 1
        assert data['hand_count'] == len(hand_before) + 1

    def test_draw_sept(self, client, game_id):
        """POST /api/game/<id>/draw compra carta de sept."""
        resp = client.post(f'/api/game/{game_id}/draw',
                           json={'deck': 'sept', 'count': 2})
        assert resp.status_code == 200
        assert len(resp.get_json()['drawn']) == 2

    def test_play_card(self, client, game_id):
        """POST /api/game/<id>/play joga carta da mao."""
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        p0 = state['players'][0]
        pack_before = len(p0['pack_home'])

        resp = client.post(f'/api/game/{game_id}/play',
                           json={'hand_index': 0})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'played' in data
        new_state = data['state']
        assert len(new_state['players'][0]['pack_home']) == pack_before + 1

    def test_play_invalid_index(self, client, game_id):
        """POST /api/game/<id>/play com indice invalido."""
        resp = client.post(f'/api/game/{game_id}/play',
                           json={'hand_index': 999})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_attack_hunting_grounds(self, client, game_id):
        """POST /api/game/<id>/attack contra prey no hunting grounds."""
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        atk = state['players'][0]['pack_home'][0]
        atk_id = str(atk['card_id'])

        resp = client.post(f'/api/game/{game_id}/attack',
                           json={'attacker_id': atk_id})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['combat']['is_active'] or data['state']['combat']['is_active']
        # Verifica que o combate e contra um alvo especifico, nao 'hg'
        combat = data.get('combat') or data['state']['combat']
        assert 'hg' not in combat.get('defenders', [])

    def test_attack_creature(self, client, game_id):
        """POST /api/game/<id>/attack contra criatura."""
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        atk = state['players'][0]['pack_home'][0]
        opp = state['players'][1]['pack_home'][0]

        resp = client.post(f'/api/game/{game_id}/attack',
                           json={'attacker_id': str(atk['card_id']),
                                 'defender_id': str(opp['card_id'])})
        assert resp.status_code == 200

    def test_declare_and_cycle(self, client, game_id):
        """Ciclo completo de combate via API."""
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        atk = state['players'][0]['pack_home'][0]
        atk_id = str(atk['card_id'])

        # Ataca
        client.post(f'/api/game/{game_id}/attack',
                    json={'attacker_id': atk_id})

        # Declara
        resp = client.post(f'/api/game/{game_id}/declare',
                           json={'card_id': atk_id, 'action': 'strike'})
        assert resp.status_code == 200

        # Revela
        resp = client.post(f'/api/game/{game_id}/reveal')
        assert resp.status_code == 200
        assert resp.get_json()['combat']['step'] == 'reveal'

        # Resolve
        resp = client.post(f'/api/game/{game_id}/resolve')
        assert resp.status_code == 200

        # Encerra
        resp = client.post(f'/api/game/{game_id}/end-combat')
        assert resp.status_code == 200
        assert not resp.get_json()['state']['combat']['is_active']

    def test_feint_cycle(self, client, game_id):
        """Usa Feint via API."""
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        atk = state['players'][0]['pack_home'][0]
        atk_id = str(atk['card_id'])

        client.post(f'/api/game/{game_id}/attack',
                    json={'attacker_id': atk_id})
        client.post(f'/api/game/{game_id}/declare',
                    json={'card_id': atk_id, 'action': 'strike'})
        client.post(f'/api/game/{game_id}/reveal')

        # Feint
        resp = client.post(f'/api/game/{game_id}/feint',
                           json={'card_id': atk_id, 'new_action': 'block'})
        assert resp.status_code == 200

    def test_pass_turn(self, client, game_id):
        """POST /api/game/<id>/pass passa a vez."""
        state_before = client.get(f'/api/game/{game_id}').get_json()['state']
        cp_before = state_before['current_player_id']

        resp = client.post(f'/api/game/{game_id}/pass')
        assert resp.status_code == 200
        state_after = resp.get_json()['state']
        assert state_after['current_player_id'] != cp_before

    def test_next_phase(self, client, game_id):
        """POST /api/game/<id>/next avanca fase."""
        state_before = client.get(f'/api/game/{game_id}').get_json()['state']
        assert state_before['phase'] == 'redraw'

        resp = client.post(f'/api/game/{game_id}/next')
        assert resp.status_code == 200
        state_after = resp.get_json()['state']
        assert state_after['phase'] == 'regeneration'

    def test_use_card(self, client, game_id):
        """POST /api/game/<id>/use-card usa carta de efeito."""
        # Poe carta de efeito na mao do jogador atual
        state = client.get(f'/api/game/{game_id}').get_json()['state']
        p0 = state['players'][0]

        # Se nao tem carta de efeito na mao, usa PLAY pra criar contexto
        resp = client.post(f'/api/game/{game_id}/use-card',
                           json={'hand_index': 0, 'modo_idx': 0})
        # Pode falhar se a carta nao tem modelo, mas nao deve crashar
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'used' in data
            assert 'logs' in data

    def test_serialization(self, client, game_id):
        """Estado serializado contem campos esperados."""
        resp = client.get(f'/api/game/{game_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        state = data['state']

        # Campos obrigatorios
        assert 'id' in state
        assert 'turn_number' in state
        assert 'phase' in state
        assert 'current_player_id' in state
        assert 'players' in state
        assert 'combat' in state
        assert 'log' in state

        # Jogadores
        p = state['players'][0]
        assert 'id' in p
        assert 'name' in p
        assert 'hand' in p
        assert 'pack_home' in p
        assert 'deck_combat_count' in p
        assert 'deck_sept_count' in p

        # Cartas
        if p['pack_home']:
            card = p['pack_home'][0]
            assert 'card_id' in card
            assert 'name' in card
            assert 'rage' in card
            assert 'health_current' in card
