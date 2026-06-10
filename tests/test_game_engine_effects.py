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

    def test_modificar_rage_criatura(self, game, resolvedor):
        """Modificar Rage altera o valor da criatura."""
        criatura = game.players[0].pack_home[0]
        rage_antes = criatura.rage
        efeito = Efeito(tipo=EfeitoTipo.MODIFICAR_RAGE,
                        quantidade=2,
                        condicao='criatura_aliada')
        origem = CardInstance(card_id=-1, name='Teste', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1',
                              controller_id='p1')

        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert criatura.rage == rage_antes + 2

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


class TestResolverModificarAtributo:
    def test_reduz_rage_gnosis(self, game):
        """Gooshy Gooze: oponente perde 1 Rage e 1 Gnosis no combate."""
        resolvedor = ResolvedorEfeitos(game)
        alvo = game.players[1].pack_home[0]
        rage_antes = alvo.rage
        gnosis_antes = alvo.gnosis
        efeito = Efeito(
            tipo=EfeitoTipo.MODIFICAR_ATRIBUTO,
            quantidade=-1,
            condicao='criatura_inimiga',
            params={'atributos': ['rage', 'gnosis'], 'minimo': 1, 'duracao': 'ate_fim_combate'}
        )
        origem = CardInstance(card_id=-1, name='Gooshy Gooze', card_type='Equipment',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert alvo.rage == max(1, rage_antes - 1)
        assert alvo.gnosis == max(1, gnosis_antes - 1)

    def test_aumenta_rage_uma_criatura(self, game):
        """modificar_atributo em uma criatura aliada."""
        resolvedor = ResolvedorEfeitos(game)
        p = game.players[0]
        rages_antes = {c.name: c.rage for c in p.pack_home}
        efeito = Efeito(
            tipo=EfeitoTipo.MODIFICAR_ATRIBUTO,
            quantidade=3,
            condicao='criatura_aliada',
            params={'atributos': ['rage'], 'minimo': 0, 'duracao': 'permanente'}
        )
        origem = CardInstance(card_id=-1, name='Beast-of-War', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, p)
        assert resultado
        # Exatamente uma criatura (escolhida aleatoriamente) ganhou +3 Rage
        modificadas = 0
        for c in p.pack_home:
            if c.rage == rages_antes[c.name] + 3:
                modificadas += 1
        assert modificadas == 1

    def test_filtro_wyrm(self, game):
        """Mass Pollution: so Wyrm ganha Gnosis."""
        resolvedor = ResolvedorEfeitos(game)
        p = game.players[0]
        # Marca todas como nao-Wyrm
        for c in p.pack_home:
            c.card_type = 'Character - Gaia'
        gnosis_antes = [c.gnosis for c in p.pack_home]
        
        efeito = Efeito(
            tipo=EfeitoTipo.MODIFICAR_ATRIBUTO,
            quantidade=1,
            condicao='criatura_aliada',
            params={'atributos': ['gnosis'], 'minimo': 0, 'duracao': 'permanente', 'filtro_tipo': 'Wyrm'}
        )
        origem = CardInstance(card_id=-1, name='Mass Pollution', card_type='Event',
                              zone=Zone.OUT_OF_PLAY, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, p)
        # Nenhuma criatura e Wyrm, filtro elimina -> fail
        assert not resultado
        for c, g_antes in zip(p.pack_home, gnosis_antes):
            assert c.gnosis == g_antes


class TestCondicaoEstado:
    def test_combar_acao_se_sucesso(self, game):
        """Head or Gut?: se matar, +1 VP via condicao_estado."""
        from rage_web.game_engine.effects import aplicar_carta
        from rage_web.game_engine.state import GameState, PlayerState
        # Simula alvo com 1 de vida
        alvo = game.players[1].pack_home[0]
        alvo.health_current = 1
        alvo.zone = Zone.PACK_HOME
        
        # Cria modelo Head or Gut? diretamente
        modelo = ModeloCarta(
            id='card_119',
            nome='Head or Gut?',
            tipo='Combat Action',
            modos=[
                Modo(
                    descricao='Causar 3 de dano',
                    efeitos=[
                        Efeito(tipo=EfeitoTipo.DANO, quantidade=3, condicao='criatura_inimiga'),
                        Efeito(
                            tipo=EfeitoTipo.COMBAR_ACAO,
                            condicao_estado='alvo_destruido',
                            se_sucesso=[
                                Efeito(tipo=EfeitoTipo.GANHAR_VP, quantidade=1, condicao='jogador_aliado')
                            ]
                        )
                    ]
                )
            ]
        )
        vp_antes = game.players[0].victory_points
        origem = CardInstance(card_id=119, name='Head or Gut?', card_type='Combat Action',
                              zone=Zone.HAND, owner_id='p1', controller_id='p1')
        game.players[0].hand.append(origem)
        
        aplicar_carta(game, modelo, game.players[0].id, modo_idx=0, card_origem=origem)
        assert game.players[0].victory_points >= vp_antes + 1


class TestComprarPorPackmate:
    def test_ass_whuppin_lynch_mob(self, game):
        """Ass Whuppin' Lynch Mob: compra por packmate."""
        resolvedor = ResolvedorEfeitos(game)
        p = game.players[0]
        deck_antes = len(p.deck_combat)
        packmates = [c for c in p.pack_home]
        
        efeito = Efeito(
            tipo=EfeitoTipo.COMPRAR,
            quantidade=1,
            condicao='jogador_aliado',
            params={'por_packmate': True}
        )
        origem = CardInstance(card_id=281, name='Ass Whuppin Lynch Mob', card_type='Combat Event',
                              zone=Zone.HAND, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, p)
        assert resultado
        # Deveria ter comprado 1 * (packmates count) cartas
        # packmates = todos menos origem (que nao esta em pack_home)
        expected = len(packmates)
        assert len(p.deck_combat) == deck_antes - expected


class TestResolverImpedirAcoes:
    def test_impedir_gnosis_menor(self, game):
        """Wailer: oponente com Gnosis menor nao pode agir."""
        resolvedor = ResolvedorEfeitos(game)
        # Cria alvo com Gnosis baixo
        alvo = game.players[1].pack_home[0]
        alvo.gnosis = 2
        
        efeito = Efeito(
            tipo=EfeitoTipo.IMPEDIR_ACOES,
            condicao='criatura_inimiga',
            params={
                'condicao': 'alvo_gnosis_menor',
                'valor_comparacao': 3,
                'restricao': 'nao_pode_combat_action',
                'duracao': 'proximo_round'
            }
        )
        origem = CardInstance(card_id=347, name='Wailer', card_type='Character - Wyrm',
                              zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        assert 'nao_pode_combat_action' in alvo.restricoes

    def test_impedir_gnosis_maior_nega(self, game):
        """Wailer: se Gnosis >= threshold, nao aplica restricao."""
        resolvedor = ResolvedorEfeitos(game)
        alvo = game.players[1].pack_home[0]
        alvo.gnosis = 5  # Maior que threshold 3
        
        efeito = Efeito(
            tipo=EfeitoTipo.IMPEDIR_ACOES,
            condicao='criatura_inimiga',
            params={
                'condicao': 'alvo_gnosis_menor',
                'valor_comparacao': 3,
                'restricao': 'nao_pode_combat_action',
                'duracao': 'proximo_round'
            }
        )
        origem = CardInstance(card_id=347, name='Wailer', card_type='Character - Wyrm',
                              zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert not resultado  # Condicao nao atendida
        assert 'nao_pode_combat_action' not in alvo.restricoes


class TestResolverRestringirExceto:
    def test_exceto_tipo(self, game):
        """Stench of Death: exceto=espirito,bane,metis."""
        resolvedor = ResolvedorEfeitos(game)
        alvo = game.players[1].pack_home[0]
        origem = game.players[0].pack_home[0]
        
        efeito = Efeito(
            tipo=EfeitoTipo.RESTRICAO,
            condicao='criatura_inimiga',
            params={
                'restricao': 'nao_pode_atacar_usuario',
                'exceto': ['Spirit', 'Bane', 'Metis'],
                'duracao': 'permanente_ate_cancelar'
            }
        )
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        assert resultado
        # O alvo (inimigo normal) recebe a restricao
        assert 'nao_pode_atacar_usuario' in alvo.restricoes

    def test_exceto_ignora_se_tipo_correto(self, game):
        """Stench of Death: se origem e Metis, restricao ignorada."""
        resolvedor = ResolvedorEfeitos(game)
        alvo = game.players[1].pack_home[0]
        alvo.card_type = 'Metis - Garou'
        
        efeito = Efeito(
            tipo=EfeitoTipo.RESTRICAO,
            condicao='criatura_inimiga',
            params={
                'restricao': 'nao_pode_atacar_usuario',
                'exceto': ['Spirit', 'Bane', 'Metis'],
                'duracao': 'permanente_ate_cancelar'
            }
        )
        # Origem e Metis, entao restricao nao se aplica ao alvo
        origem = CardInstance(card_id=-1, name='Test', card_type='Metis',
                              zone=Zone.PACK_HOME, owner_id='p1', controller_id='p1')
        resultado = resolvedor.aplicar_efeito(efeito, origem, game.players[0])
        # Como a origem e Metis, o efeito retorna True mas nao adiciona restricao
        assert resultado
        assert 'nao_pode_atacar_usuario' not in alvo.restricoes


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
