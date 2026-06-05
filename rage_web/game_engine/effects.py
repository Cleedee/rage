"""Sistema de efeitos de carta para o motor de jogo.

Cada carta pode ter modos (escolha do jogador), condicoes de alvo,
e efeitos encadeados.

Exemplo de carta neste formato:
```json
{
  "id": "golpe_misericordia",
  "nome": "Golpe de Misericórdia",
  "tipo": "combate",
  "custo_acoes": 1,
  "modos": [
    {
      "descricao": "Matar uma criatura ferida",
      "efeitos": [
        { "tipo": "destruir", "condicao_alvo": "criatura_inimiga_ferida" }
      ]
    }
  ]
}
```
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from rage_web.game_engine.state import (
    CardInstance, GameState, PendenciaEfeito, PlayerState, Zone,
    anexar_dano, descartar_anexos,
)
from rage_web.game_engine.combat_queue import _remove_creature


# -----------------------------------------------------------------------
# Tipos de efeito
# -----------------------------------------------------------------------

class EfeitoTipo(str, Enum):
    """Tipos de efeito que uma carta pode ter."""
    DANO = 'dano'
    CURAR = 'curar'
    DESTRUIR = 'destruir'
    DESCARTE = 'descarte'
    COMPRAR = 'comprar'
    TAPAR = 'tapar'
    DESTAPAR = 'destapar'
    MODIFICAR_RAGE = 'modificar_rage'
    MODIFICAR_GNOSIS = 'modificar_gnosis'
    MODIFICAR_VIDA = 'modificar_vida'
    MOVER_PARA = 'mover_para'
    REMOVER_DO_JOGO = 'remover_do_jogo'
    GANHAR_VP = 'ganhar_vp'
    PERDER_VP = 'perder_vp'
    COMBAR_ACAO = 'combar_acao'       # Encadear outra acao
    REDIRECIONAR = 'redirecionar'     # Redirecionar ataque
    ANULAR = 'anular'                 # Anular acao/ataque
    FUGIR = 'fugir'
    INICIAR_COMBATE = 'iniciar_combate'
    RESTRICAO = 'restringir'  # Adicionar restricao temporaria a criatura
    COMPRAR_ATE = 'comprar_ate'  # Comprar ate ter N cartas na mao
    EQUIPAR = 'equipar'  # Anexar equipamento a uma criatura
    MODIFICAR_REDUCAO_DANO = 'modificar_reducao_dano'  # Modificar reducao de dano passiva
    DESCARTAR_METADE_MAO = 'descartar_metade_mao'  # Oponente descarta metade da mao (arred. cima)
    MODIFICAR_ATRIBUTO = 'modificar_atributo'  # Modificar multiplos atributos (ex: +1 Rage/Gnosis/Health)
    USAR_GIFT = 'usar_gift'  # Usar um Gift atraves de outro card
    QUEST_CHECK = 'quest_check'  # Verificar condicao de quest


# -----------------------------------------------------------------------
# Condicoes de alvo
# -----------------------------------------------------------------------

class AlvoTipo(str, Enum):
    """Tipos de alvo que um efeito pode ter."""
    CRIATURA_INIMIGA = 'criatura_inimiga'
    CRIATURA_ALIADA = 'criatura_aliada'
    CRIATURA_QUALQUER = 'qualquer_criatura'
    CRIATURA_INIMIGA_FERIDA = 'criatura_inimiga_ferida'
    CRIATURA_ALIADA_FERIDA = 'criatura_aliada_ferida'
    JOGADOR_INIMIGO = 'jogador_inimigo'
    JOGADOR_ALIADO = 'jogador_aliado'
    MAO_INIMIGA = 'mao_inimiga'
    MAO_ALIADA = 'mao_aliada'
    DECK_COMBATE = 'deck_combate'
    DECK_SEPT = 'deck_sept'
    DISCARTE = 'descarte'
    HUNTING_GROUNDS = 'hunting_grounds'
    QUALQUER_ALVO = 'qualquer_alvo'


# -----------------------------------------------------------------------
# Estrutura de dados
# -----------------------------------------------------------------------

@dataclass
class Efeito:
    """Um efeito unico de carta."""
    tipo: EfeitoTipo
    alvo: Optional[str] = None
    quantidade: int = 0
    condicao: Optional[str] = None  # Nome da funcao de resolucao de alvo
    modo_idx: int = 0  # Indice do modo (para cartas modais)
    duracao: str = ''  # 'end_of_turn', 'end_of_combat', 'end_of_phase', ''
    se_sucesso: list[Efeito] = field(default_factory=list)
    se_fracasso: list[Efeito] = field(default_factory=list)
    condicao_estado: Optional[str] = None  # Condicao de estado do jogo
    # Ex: 'alvo_frenetico' — so aplica se_sucesso se condicao for verdadeira

    def __post_init__(self):
        if isinstance(self.tipo, str):
            self.tipo = EfeitoTipo(self.tipo)


@dataclass
class Modo:
    """Um modo de uso de uma carta (cartas modais)."""
    descricao: str
    efeitos: list[Efeito] = field(default_factory=list)
    condicao_uso: Optional[str] = None


@dataclass
class ModeloCarta:
    """Modelo de carta com efeitos estruturados."""
    id: str
    nome: str
    tipo: str
    modos: list[Modo] = field(default_factory=list)

    def modo_por_indice(self, idx: int) -> Optional[Modo]:
        if 0 <= idx < len(self.modos):
            return self.modos[idx]
        return None


# -----------------------------------------------------------------------
# Resolvedor de efeitos
# -----------------------------------------------------------------------

class ResolvedorEfeitos:
    """Resolve efeitos de carta no estado do jogo.

    Uso:
        resolvedor = ResolvedorEfeitos(jogo)
        resolvedor.aplicar_efeito(efeito, origem, jogador_alvo)
    """

    def __init__(self, game: GameState, rng: Optional[random.Random] = None):
        self.game = game
        self.rng = rng or game.rng
        self.log: list[str] = []

    def aplicar_efeito(self, efeito: Efeito, origem: CardInstance,
                       jogador: PlayerState) -> bool:
        """Aplica um efeito no estado do jogo.

        Args:
            efeito: O efeito a ser aplicado.
            origem: A carta que originou o efeito.
            jogador: O jogador que controla a carta.

        Returns:
            True se o efeito foi aplicado com sucesso.
        """
        resolvedor = self._get_resolvedor(efeito.tipo)
        if not resolvedor:
            self.log.append(f'Efeito desconhecido: {efeito.tipo}')
            return False

        alvo = self._resolver_alvo(efeito, origem, jogador)
        if alvo is None and efeito.tipo not in (EfeitoTipo.DESCARTE,
                                                  EfeitoTipo.COMPRAR,
                                                  EfeitoTipo.GANHAR_VP,
                                                  EfeitoTipo.PERDER_VP):
            self.log.append(f'Sem alvo valido para {efeito.tipo.value}')
            return False

        resultado = resolvedor(efeito, origem, jogador, alvo)
        if resultado:
            if isinstance(alvo, list):
                nome_alvo = f'{len(alvo)} cartas'
            else:
                nome_alvo = getattr(alvo, 'name', str(alvo or jogador.name))
            self.log.append(
                f'{origem.name}: {efeito.tipo.value} em {nome_alvo}'
            )
        return resultado

    def _get_resolvedor(self, tipo: EfeitoTipo
                        ) -> Optional[Callable]:
        """Retorna a funcao resolvedora para um tipo de efeito."""
        resolvedores = {
            EfeitoTipo.DANO: self._resolver_dano,
            EfeitoTipo.CURAR: self._resolver_curar,
            EfeitoTipo.DESTRUIR: self._resolver_destruir,
            EfeitoTipo.DESCARTE: self._resolver_descarte,
            EfeitoTipo.COMPRAR: self._resolver_comprar,
            EfeitoTipo.TAPAR: self._resolver_tapar,
            EfeitoTipo.DESTAPAR: self._resolver_destapar,
            EfeitoTipo.MODIFICAR_RAGE: self._resolver_modificar_rage,
            EfeitoTipo.MODIFICAR_GNOSIS: self._resolver_modificar_gnosis,
            EfeitoTipo.MODIFICAR_VIDA: self._resolver_modificar_vida,
            EfeitoTipo.MOVER_PARA: self._resolver_mover_para,
            EfeitoTipo.GANHAR_VP: self._resolver_ganhar_vp,
            EfeitoTipo.PERDER_VP: self._resolver_perder_vp,
            EfeitoTipo.ANULAR: self._resolver_anular,
            EfeitoTipo.RESTRICAO: self._resolver_restringir,
            EfeitoTipo.COMPRAR_ATE: self._resolver_comprar_ate,
            EfeitoTipo.FUGIR: self._resolver_fugir,
    EfeitoTipo.MODIFICAR_ATRIBUTO: self._resolver_modificar_atributo,
    EfeitoTipo.USAR_GIFT: self._resolver_usar_gift,
    EfeitoTipo.QUEST_CHECK: self._resolver_quest_check,
            EfeitoTipo.EQUIPAR: self._resolver_equipar,
            EfeitoTipo.MODIFICAR_REDUCAO_DANO: self._resolver_modificar_reducao_dano,
            EfeitoTipo.DESCARTAR_METADE_MAO: self._resolver_descartar_metade_mao,
            EfeitoTipo.REMOVER_DO_JOGO: self._resolver_remover_do_jogo,
        }
        return resolvedores.get(tipo)

    def _resolver_alvo(self, efeito: Efeito, origem: CardInstance,
                       jogador: PlayerState) -> Any:
        """Resolve o alvo do efeito baseado na condicao.

        Suporta partidas com N jogadores: alvos inimigos sao
        agregados de todos os oponentes.
        """
        condicao = efeito.condicao or efeito.alvo
        if not condicao:
            return jogador  # Default: proprio jogador

        oponentes = self._get_oponentes(jogador)

        def _criaturas_inimigas() -> list[CardInstance]:
            """Agrega criaturas de todos os oponentes."""
            resultado = []
            for op in oponentes:
                resultado.extend(op.pack_home)
            return resultado

        def _criaturas_inimigas_feridas() -> list[CardInstance]:
            """Agrega criaturas feridas de todos os oponentes."""
            resultado = []
            for op in oponentes:
                for c in op.pack_home:
                    if c.health_current < c.health:
                        resultado.append(c)
            return resultado

        def _umbra_inimiga() -> list[CardInstance]:
            """Agrega criaturas na Umbra de todos os oponentes."""
            resultado = []
            for op in oponentes:
                resultado.extend(op.umbra)
            return resultado

        def _todas_criaturas() -> list[CardInstance]:
            """Agrega criaturas de todos os jogadores."""
            resultado = list(jogador.pack_home)
            for op in oponentes:
                resultado.extend(op.pack_home)
            return resultado

        resolvedores_alvo = {
            'criatura_inimiga': lambda: self._escolher_criatura(
                _criaturas_inimigas()
            ),
            'criatura_aliada': lambda: self._escolher_criatura(
                jogador.pack_home
            ),
            'qualquer_criatura': lambda: self._escolher_criatura(
                _todas_criaturas()
            ),
            'criatura_inimiga_ferida': lambda: self._escolher_criatura(
                _criaturas_inimigas_feridas()
            ),
            'criatura_aliada_ferida': lambda: self._escolher_criatura(
                [c for c in jogador.pack_home
                 if c.health_current < c.health]
            ),
            'jogador_inimigo': lambda: self._escolher_jogador(
                oponentes
            ),
            'jogador_aliado': lambda: jogador,
            'mao_inimiga': lambda: self._escolher_jogador(
                oponentes
            ).hand,
            'mao_aliada': lambda: jogador.hand,
            'hunting_grounds': lambda: 'hg',
            'umbra_aliada': lambda: self._escolher_criatura(
                jogador.umbra
            ),
            'umbra_inimiga': lambda: self._escolher_criatura(
                _umbra_inimiga()
            ),
        }

        resolvedor = resolvedores_alvo.get(condicao)
        if resolvedor:
            return resolvedor()
        return None

    def _escolher_jogador(self, jogadores: list[PlayerState]
                           ) -> Optional[PlayerState]:
        """Escolhe um jogador aleatorio da lista."""
        if not jogadores:
            return None
        return self.rng.choice(jogadores)

    def _escolher_criatura(self, criaturas: list[CardInstance
                           ]) -> Optional[CardInstance]:
        """Escolhe uma criatura da lista."""
        if not criaturas:
            return None
        return self.rng.choice(criaturas)

    def _get_oponentes(self, jogador: PlayerState) -> list[PlayerState]:
        """Retorna lista de todos os jogadores que nao sao o atual.

        Suporta partidas com N jogadores.
        """
        return [p for p in self.game.players if p.id != jogador.id]

    def _find_player(self, player_id: str) -> Optional[PlayerState]:
        """Encontra um jogador pelo ID."""
        for p in self.game.players:
            if p.id == player_id:
                return p
        return None

    def _get_oponente(self, jogador: PlayerState) -> PlayerState:
        """[DEPRECATED] Retorna o primeiro oponente.

        Mantido para compatibilidade, mas prefira _get_oponentes().
        Para 2 jogadores, equivale ao unico oponente.
        """
        oponentes = self._get_oponentes(jogador)
        return oponentes[0] if oponentes else jogador

    # ------------------------------------------------------------------
    # Resolvedores individuais
    # ------------------------------------------------------------------

    def _resolver_dano(self, efeito: Efeito, origem: CardInstance,
                       jogador: PlayerState, alvo) -> bool:
        """Aplica dano a um alvo e anexa damage card (regra 6.4)."""
        qtd = efeito.quantidade or 2
        if isinstance(alvo, CardInstance):
            anexar_dano(alvo, origem, qtd, jogador.id)
            self.game.add_log(
                f'{alvo.name} sofreu {qtd} de dano '
                f'({alvo.health_current}/{alvo.health})'
            )
            return True
        elif isinstance(alvo, PlayerState):
            self.game.add_log(
                f'{alvo.name} sofreu {qtd} de dano direto'
            )
            return True
        return False

    def _resolver_curar(self, efeito: Efeito, origem: CardInstance,
                        jogador: PlayerState, alvo) -> bool:
        """Cura uma criatura."""
        qtd = efeito.quantidade or 2
        if isinstance(alvo, CardInstance):
            cura_real = min(qtd, alvo.health - alvo.health_current)
            alvo.health_current += cura_real
            self.game.add_log(
                f'{alvo.name} curou {cura_real} '
                f'({alvo.health_current}/{alvo.health})'
            )
            return True
        return False

    def _resolver_destruir(self, efeito: Efeito, origem: CardInstance,
                          jogador: PlayerState, alvo) -> bool:
        """Remove uma criatura do jogo.

        Suporta N jogadores: encontra o dono da criatura pelo owner_id.
        """
        if isinstance(alvo, CardInstance):
            # Descarta cartas anexadas (regra 6.4.2)
            dono_alvo = self._find_player(alvo.owner_id)
            if dono_alvo:
                descartar_anexos(alvo, dono_alvo)
            # Remove da zona atual
            alvo.zone = Zone.DISCARD_COMBAT
            if alvo in jogador.pack_home:
                jogador.pack_home.remove(alvo)
            else:
                # Procura em todos os jogadores
                for op in self._get_oponentes(jogador):
                    if alvo in op.pack_home:
                        op.pack_home.remove(alvo)
                        break
                    if alvo in op.hunting_grounds:
                        op.hunting_grounds.remove(alvo)
                        break
                    if alvo in op.umbra:
                        op.umbra.remove(alvo)
                        break
            self.game.add_log(f'{alvo.name} foi destruido')
            return True
        return False

    def _resolver_remover_do_jogo(self, efeito: Efeito,
                                   origem: CardInstance,
                                   jogador: PlayerState, alvo) -> bool:
        """Remove uma criatura do jogo temporariamente.

        A criatura e movida para OUT_OF_PLAY e uma pendencia e criada
        para restaura-la no fim da proxima fase.

        Usado por Chant of Morpheus e efeitos similares.
        """
        if not isinstance(alvo, CardInstance):
            return False

        # Salva a zona original para restaurar depois
        zona_original = alvo.zone

        # Remove da zona atual
        _remove_creature(self.game, alvo)

        # Move para OUT_OF_PLAY
        alvo.zone = Zone.OUT_OF_PLAY

        # Cria pendencia para restaurar no fim da proxima fase
        from rage_web.game_engine.state import PendenciaEfeito
        pendencia = PendenciaEfeito(
            card_uid=id(alvo),
            atributo='zona',
            delta=0,
            duracao='end_of_phase',
            valor_str=zona_original.value,
            turno_aplicado=self.game.turn_number,
            fase_aplicada=self.game.phase,
        )
        self.game.pendencias.append(pendencia)

        self.game.add_log(
            f'{alvo.name} foi removido do jogo ate o fim da proxima fase'
        )
        return True

    def _resolver_descarte(self, efeito: Efeito, origem: CardInstance,
                          jogador: PlayerState, alvo) -> bool:
        """Faz um jogador descartar cartas."""
        qtd = efeito.quantidade or 1
        alvo_jogador = alvo if isinstance(alvo, PlayerState) else jogador

        if qtd in ('mao_menos_4', 'mao_oponente_menos_4'):
            qtd = max(0, len(alvo_jogador.hand) - 4)
            if qtd == 0:
                return False

        descartadas = alvo_jogador.hand[:qtd]
        for c in descartadas:
            c.zone = Zone.DISCARD_COMBAT
            alvo_jogador.hand.remove(c)
            alvo_jogador.discard_combat.append(c)

        self.game.add_log(
            f'{alvo_jogador.name} descartou {len(descartadas)} carta(s)'
        )
        return True

    def _resolver_comprar(self, efeito: Efeito, origem: CardInstance,
                         jogador: PlayerState, alvo) -> bool:
        """Compra cartas do deck de combate."""
        qtd = efeito.quantidade or 1
        jogador.draw_combat(qtd)
        self.game.add_log(f'{jogador.name} comprou {qtd} carta(s)')
        return True

    def _resolver_comprar_ate(self, efeito: Efeito, origem: CardInstance,
                              jogador: PlayerState, alvo) -> bool:
        """Compra cartas ate ter N na mao.

        Se efeito.alvo == 'combate', conta apenas cartas de combate.
        Senao conta a mao inteira.
        """
        qtd_alvo = efeito.quantidade or 5
        tipo_mao = efeito.alvo or ''

        if tipo_mao == 'combate':
            atuais = len(jogador._cartas_combate())
            draw_fn = jogador.draw_combat
        else:
            atuais = len(jogador.hand)
            draw_fn = jogador.draw_combat

        needed = max(0, qtd_alvo - atuais)
        if needed > 0:
            draw_fn(needed)
            self.game.add_log(
                f'{jogador.name} comprou {needed} carta(s) '
                f'para ter {qtd_alvo} na mao'
            )
        return True

    def _resolver_tapar(self, efeito: Efeito, origem: CardInstance,
                       jogador: PlayerState, alvo) -> bool:
        """Tapa uma criatura."""
        if isinstance(alvo, CardInstance):
            alvo.is_tapped = True
            self.game.add_log(f'{alvo.name} foi tapado')
            return True
        return False

    def _resolver_destapar(self, efeito: Efeito, origem: CardInstance,
                          jogador: PlayerState, alvo) -> bool:
        """Destapa uma criatura."""
        if isinstance(alvo, CardInstance):
            alvo.is_tapped = False
            self.game.add_log(f'{alvo.name} foi destapado')
            return True
        return False

    def _resolver_modificar_rage(self, efeito: Efeito, origem: CardInstance,
                                jogador: PlayerState, alvo) -> bool:
        """Modifica o Rage de uma criatura."""
        if isinstance(alvo, CardInstance):
            alvo.rage = max(0, alvo.rage + efeito.quantidade)
            if efeito.duracao:
                self.game.pendencias.append(PendenciaEfeito(
                    card_uid=id(alvo), atributo='rage',
                    delta=efeito.quantidade, duracao=efeito.duracao,
                    turno_aplicado=self.game.turn_number,
                    fase_aplicada=self.game.phase,
                ))
            sinal = '+' if efeito.quantidade >= 0 else ''
            self.game.add_log(
                f'{alvo.name} rage {sinal}{efeito.quantidade}'
            )
            return True
        return False

    def _resolver_modificar_gnosis(self, efeito: Efeito, origem: CardInstance,
                                  jogador: PlayerState, alvo) -> bool:
        """Modifica o Gnosis de uma criatura."""
        if isinstance(alvo, CardInstance):
            alvo.gnosis = max(0, alvo.gnosis + efeito.quantidade)
            if efeito.duracao:
                self.game.pendencias.append(PendenciaEfeito(
                    card_uid=id(alvo), atributo='gnosis',
                    delta=efeito.quantidade, duracao=efeito.duracao,
                    turno_aplicado=self.game.turn_number,
                    fase_aplicada=self.game.phase,
                ))
            return True
        return False

    def _resolver_modificar_vida(self, efeito: Efeito, origem: CardInstance,
                                jogador: PlayerState, alvo) -> bool:
        """Modifica a vida maxima de uma criatura."""
        if isinstance(alvo, CardInstance):
            alvo.health = max(1, alvo.health + efeito.quantidade)
            if efeito.duracao:
                self.game.pendencias.append(PendenciaEfeito(
                    card_uid=id(alvo), atributo='health',
                    delta=efeito.quantidade, duracao=efeito.duracao,
                    turno_aplicado=self.game.turn_number,
                    fase_aplicada=self.game.phase,
                ))
            return True
        return False

    def _resolver_mover_para(self, efeito: Efeito, origem: CardInstance,
                            jogador: PlayerState, alvo) -> bool:
        """Move uma criatura entre zonas (listas do PlayerState + zone tag)."""
        if not isinstance(alvo, CardInstance):
            return False
        zona_destino = efeito.alvo or efeito.condicao or 'hunting_grounds'
        zonas = {
            'hunting_grounds': Zone.HUNTING_GROUNDS,
            'umbra': Zone.UMBRA,
            'pack_home': Zone.PACK_HOME,
            'descarte': Zone.DISCARD_COMBAT,
        }
        nova_zona = zonas.get(zona_destino)
        if not nova_zona:
            return False

        # Remove da lista de origem (todos os jogadores)
        for p in self.game.players:
            for lista in (p.pack_home, p.hunting_grounds,
                          p.umbra, p.hand):
                if alvo in lista:
                    lista.remove(alvo)
                    break

        # Adiciona na lista de destino
        map_destino = {
            Zone.PACK_HOME: jogador.pack_home,
            Zone.UMBRA: jogador.umbra,
            Zone.HUNTING_GROUNDS: jogador.hunting_grounds,
            Zone.DISCARD_COMBAT: jogador.discard_combat,
        }
        lista_destino = map_destino.get(nova_zona)
        if lista_destino is not None:
            lista_destino.append(alvo)

        alvo.zone = nova_zona
        self.game.add_log(f'{alvo.name} movido para {zona_destino}')
        return True

    def _resolver_ganhar_vp(self, efeito: Efeito, origem: CardInstance,
                           jogador: PlayerState, alvo) -> bool:
        """Ganha Vitoria Points."""
        qtd = efeito.quantidade or 1
        jogador.victory_points += qtd
        self.game.add_log(
            f'{jogador.name} ganhou {qtd} VP ({jogador.victory_points})'
        )
        return True

    def _resolver_perder_vp(self, efeito: Efeito, origem: CardInstance,
                           jogador: PlayerState, alvo) -> bool:
        """Perde Vitoria Points."""
        qtd = efeito.quantidade or 1
        jogador.victory_points = max(0, jogador.victory_points - qtd)
        self.game.add_log(
            f'{jogador.name} perdeu {qtd} VP ({jogador.victory_points})'
        )
        return True

    def _resolver_restringir(self, efeito: Efeito, origem: CardInstance,
                            jogador: PlayerState, alvo) -> bool:
        """Adiciona uma restricao temporaria a uma criatura."""
        if not isinstance(alvo, CardInstance) or not efeito.alvo:
            return False
        if efeito.alvo not in alvo.restricoes:
            alvo.restricoes.append(efeito.alvo)
            if efeito.duracao:
                self.game.pendencias.append(PendenciaEfeito(
                    card_uid=id(alvo), atributo='restricao',
                    delta=0, valor_str=efeito.alvo,
                    duracao=efeito.duracao,
                    turno_aplicado=self.game.turn_number,
                    fase_aplicada=self.game.phase,
                ))
            self.game.add_log(
                f'{alvo.name} recebeu restricao "{efeito.alvo}"'
                f'{" ate " + efeito.duracao if efeito.duracao else ""}'
            )
            return True
        return False

    def _resolver_anular(self, efeito: Efeito, origem: CardInstance,
                        jogador: PlayerState, alvo) -> bool:
        """Anula uma acao ou ataque.

        Integra com o anunciador para cancelar o efeito anunciado
        atualmente. Se for um Combat Event, o efeito e anulado e
        a carta de origem (Fog) e descartada.
        """
        anunciador = self.game.anunciador
        if anunciador and anunciador.tem_anuncio_ativo:
            # Verifica se o anuncio atual e um Combat Event
            anuncio = anunciador.anuncio_atual
            anunciador.anular(self.game, jogador.id)
            self.game.add_log(
                f'{origem.name} anulou {anuncio.descricao} '
                f'de {anuncio.jogador_id}'
            )
            # Descarta a carta de origem (Fog) se for um Event
            if origem.card_type == 'Event':
                origem.zone = Zone.DISCARD_COMBAT
                jogador.discard_combat.append(origem)
                self.game.add_log(f'{origem.name} foi descartado')
        else:
            self.game.add_log(f'{origem.name} anulou uma acao')
        return True

    def _resolver_fugir(self, efeito: Efeito, origem: CardInstance,
                        jogador: PlayerState, alvo) -> bool:
        """Forca uma criatura a fugir do combate.

        Suporta N jogadores: encontra o dono da criatura pelo owner_id.
        """
        if isinstance(alvo, CardInstance):
            dono_alvo = self._find_player(alvo.owner_id)
            alvo.zone = Zone.DISCARD_COMBAT
            # Remove da zona atual (procura em todos os jogadores)
            for p in self.game.players:
                for zone_list in (p.pack_home, p.hunting_grounds,
                                  p.umbra):
                    if alvo in zone_list:
                        zone_list.remove(alvo)
                        break
            # Adiciona ao descarte do dono
            if dono_alvo:
                dono_alvo.discard_combat.append(alvo)
            else:
                # Fallback: descarte do jogador atual
                jogador.discard_combat.append(alvo)
            self.game.add_log(f'{alvo.name} foi forcado a fugir do combate')
            return True
        return False

    def _resolver_descartar_metade_mao(self, efeito: Efeito,
                                         origem: CardInstance,
                                         jogador: PlayerState,
                                         alvo) -> bool:
        """Faz um oponente descartar metade da mao (arredondado para cima).

        Usado por cartas como Savage Beatdown quando danificam
        uma criatura frenzied.
        Suporta N jogadores: se alvo for um PlayerState, usa ele;
        senao escolhe um oponente aleatorio.
        """
        if isinstance(alvo, PlayerState):
            oponente = alvo
        else:
            oponentes = self._get_oponentes(jogador)
            if not oponentes:
                return False
            oponente = self._escolher_jogador(oponentes)
        mao = oponente.hand
        if not mao:
            self.game.add_log(f'{oponente.name} nao tem cartas na mao')
            return True
        import math
        qtd = math.ceil(len(mao) / 2)
        descartadas = mao[:qtd]
        for c in descartadas:
            c.zone = Zone.DISCARD_COMBAT
            mao.remove(c)
            oponente.discard_combat.append(c)
        self.game.add_log(
            f'{oponente.name} descartou {len(descartadas)} carta(s) '
            f'(metade da mao, arred. cima)'
        )
        return True

    def _resolver_equipar(self, efeito: Efeito, origem: CardInstance,
                          jogador: PlayerState, alvo) -> bool:
        """Anexa um equipamento a uma criatura.

        A origem deve ser a carta de equipamento real (vinda da mao).
        Valida restricoes de forma do equipamento (ex: Assegai requer
        Homid ou Crinos).
        """
        if not isinstance(alvo, CardInstance):
            return False

        # Valida restricoes de forma do equipamento
        if not self._validar_restricoes_equipamento(origem, alvo):
            return False

        origem.zone = Zone.OUT_OF_PLAY
        alvo.attached_equipment.append(origem)
        self.game.add_log(f'{origem.name} equipado em {alvo.name}')
        return True

    def _validar_restricoes_equipamento(self, equipamento: CardInstance,
                                        alvo: CardInstance) -> bool:
        """Valida restricoes de forma/requisito de um equipamento.

        Args:
            equipamento: O equipamento sendo equipado.
            alvo: A criatura que recebera o equipamento.

        Returns:
            True se o equipamento pode ser equipado.
        """
        kw = (equipamento.keywords or '').lower()
        alvo_kw = (alvo.keywords or '').lower()

        # Assegai e similares: requer Homid ou Crinos
        if 'weapon' in kw and 'assegai' in equipamento.name.lower():
            if 'homid' not in alvo_kw and 'crinos' not in alvo_kw:
                self.game.add_log(
                    f'{equipamento.name} so pode ser usado em forma '
                    f'Homid ou Crinos ({alvo.name}: {alvo.keywords})'
                )
                return False

        return True

    def _resolver_modificar_reducao_dano(self, efeito: Efeito,
                                          origem: CardInstance,
                                          jogador: PlayerState,
                                          alvo) -> bool:
        """Modifica a reducao de dano passiva de uma criatura."""
        if not isinstance(alvo, CardInstance):
            return False
        qtd = efeito.quantidade or 0
        alvo.reducao_dano = max(0, alvo.reducao_dano + qtd)
        self.game.add_log(
            f'{alvo.name} agora tem reducao de dano {alvo.reducao_dano}')
        return True

    def _resolver_modificar_atributo(self, efeito: Efeito,
                                       origem: CardInstance,
                                       jogador: PlayerState,
                                       alvo) -> bool:
        """Modifica multiplos atributos (Rage, Gnosis, Health).

        Usado por cartas como Sweet Luna's Smile (+1 todos os
        atributos enquanto Lunar Phase em jogo).

        Nota: efeito continuo condicional - implementacao futura.
        """
        self.game.add_log(
            f'{origem.name} modificou atributos (pendente: buff condicional)'
        )
        return True

    def _resolver_usar_gift(self, efeito: Efeito,
                              origem: CardInstance,
                              jogador: PlayerState, alvo) -> bool:
        """Usa um Gift atraves de outro card (ex: Haunter).

        Nota: implementacao futura require sistema de gifts.
        """
        self.game.add_log(
            f'{origem.name} usou um Gift (pendente)'
        )
        return True

    def _resolver_quest_check(self, efeito: Efeito,
                                origem: CardInstance,
                                jogador: PlayerState, alvo) -> bool:
        """Verifica condicao de quest e aplica recompensa.

        Usado por Mnesis Dreams: espera 2 turnos sem dano.

        Nota: implementacao futura require sistema de triggers.
        """
        self.game.add_log(
            f'{origem.name} quest check pendente'
        )
        return True


# -----------------------------------------------------------------------
# Validadores de condicao_uso
# -----------------------------------------------------------------------
# Cada validador recebe (game, jogador) e retorna True se a condicao
# foi atendida.


def _validar_condicao_uso(game: GameState, jogador: 'PlayerState',
                          condicao: str) -> bool:
    """Valida se a condicao de uso de um modo foi atendida.

    Args:
        game: Estado da partida.
        jogador: Jogador que esta usando a carta.
        condicao: Nome da condicao a validar.

    Returns:
        True se a condicao foi atendida (ou se nao ha validador).
    """
    validadores = {
        'atacante_rokea_ou_mokole_nao_homid':
            lambda: _condicao_rokea_mokole_nao_homid(game, jogador),
        'personagem_na_umbra':
            lambda: _condicao_personagem_na_umbra(game, jogador),
        'nao_frenetico':
            lambda: _condicao_nao_frenetico(game, jogador),
    }
    validador = validadores.get(condicao)
    if validador:
        return validador()
    # Condicao desconhecida: permite (backward compatible)
    return True


def _condicao_rokea_mokole_nao_homid(game: GameState,
                                     jogador: 'PlayerState') -> bool:
    """Verifica se ha uma criatura Rokea ou Mokole nao-Homid no pack.

    Usado pelo modo bonus do Tail Lash.
    """
    for c in jogador.pack_home:
        keywords = (c.keywords or '').lower()
        is_rokea = 'rokea' in keywords
        is_mokole = 'mokole' in keywords
        is_homid = 'homid' in keywords
        if (is_rokea or is_mokole) and not is_homid:
            return True
    return False


def _condicao_personagem_na_umbra(game: GameState,
                                  jogador: 'PlayerState') -> bool:
    """Verifica se ha um personagem na Umbra do jogador."""
    for c in jogador.umbra:
        if 'Character' in (c.card_type or ''):
            return True
    return False


def _validar_gauntlet_para_carta(game: GameState, jogador: 'PlayerState',
                                 modelo: 'ModeloCarta',
                                 card_origem: Optional['CardInstance'] = None
                                 ) -> bool:
    """Valida se um Rite/Gift pode cruzar o Gauntlet para seu alvo.

    Se o jogador tem um Caern como Lake Nasser Wallow no Hunting Grounds,
    Rites e Gifts podem cruzar o Gauntlet.

    Suporta Haunter: se a carta que esta usando o Gift tem a restricao
    'gifts_cruzam_gauntlet_se_gnosis_lte', Gifts com Gnosis <= valor
    podem cruzar o Gauntlet.

    Args:
        game: Estado da partida.
        jogador: Jogador usando a carta.
        modelo: Modelo da carta sendo usada.
        card_origem: Instancia da carta que esta usando o Gift.

    Returns:
        True se a carta pode ser usada (Gauntlet permitido ou nao aplicavel).
    """
    # Verifica se o jogador tem Caern que permite cruzar Gauntlet
    caerns = jogador.caerns_no_hunting_grounds
    for caern in caerns:
        texto = (caern.text or '').lower()
        if 'gauntlet' in texto and 'cross' in texto:
            return True  # Caern permite cruzar

    # Verifica se a origem tem restricao de cruzar Gauntlet
    # (ex: Haunter - gifts com Gnosis <=4 podem cruzar)
    if card_origem:
        for restricao in card_origem.restricoes:
            if restricao.startswith('gifts_cruzam_gauntlet_se_gnosis_lte:'):
                try:
                    threshold = int(restricao.split(':')[1])
                    gift_gnosis = getattr(modelo, 'gnosis', 0) or 0
                    if gift_gnosis <= threshold:
                        return True
                except (ValueError, IndexError):
                    pass

    # Sem Caern especial: Rites/Gifts funcionam normalmente
    return True


def _condicao_nao_frenetico(game: GameState,
                            jogador: 'PlayerState') -> bool:
    """Verifica se a criatura que esta jogando nao esta frenzied.

    Usado por Anatomy Lesson e outras Combat Actions que exigem
    que o atacante nao esteja em frenzy.
    """
    for c in jogador.pack_home:
        if c.is_frenzied:
            return False
    return True


# -----------------------------------------------------------------------
# API de alto nivel
# -----------------------------------------------------------------------

def aplicar_carta(game: GameState, modelo: ModeloCarta,
                  jogador_id: str, modo_idx: int = 0,
                  card_origem: Optional[CardInstance] = None) -> list[str]:
    """Aplica uma carta completa no jogo.

    Args:
        game: Estado da partida.
        modelo: Modelo da carta com efeitos.
        jogador_id: ID do jogador que esta usando a carta.
        modo_idx: Indice do modo escolhido (para cartas modais).
        card_origem: Instancia real da carta (para equipamentos que
                     precisam persistir). Se None, cria uma temporaria.

    Returns:
        Lista de mensagens de log da aplicacao.
    """
    jogador = None
    for p in game.players:
        if p.id == jogador_id:
            jogador = p
            break
    if not jogador:
        return ['Jogador nao encontrado']

    modo = modelo.modo_por_indice(modo_idx)
    if not modo:
        return ['Modo invalido']

    # Valida condicao_uso do modo (se houver)
    if modo.condicao_uso:
        if not _validar_condicao_uso(game, jogador, modo.condicao_uso):
            return [f'Condicao de uso nao atendida: {modo.condicao_uso}']

    # Valida Gauntlet para Rites e Gifts
    if modelo.tipo in ('Rite', 'Gift'):
        if not _validar_gauntlet_para_carta(game, jogador, modelo,
                                            card_origem=card_origem):
            return ['Gauntlet: a carta nao pode cruzar para o alvo']

    # Usa a carta real (se fornecida) ou cria temporaria
    if card_origem:
        origem = card_origem
    else:
        origem = CardInstance(
            card_id=-1, name=modelo.nome, card_type=modelo.tipo,
            zone=Zone.OUT_OF_PLAY, owner_id=jogador_id,
            controller_id=jogador_id,
        )

    resolvedor = ResolvedorEfeitos(game)
    for efeito in modo.efeitos:
        resultado = resolvedor.aplicar_efeito(efeito, origem, jogador)
        if resultado and efeito.se_sucesso:
            for sub in efeito.se_sucesso:
                resolvedor.aplicar_efeito(sub, origem, jogador)
        elif not resultado and efeito.se_fracasso:
            for sub in efeito.se_fracasso:
                resolvedor.aplicar_efeito(sub, origem, jogador)

    game.add_log(f'{jogador.name} usou {modelo.nome} ({modo.descricao})')
    return resolvedor.log


# -----------------------------------------------------------------------
# Cartas de exemplo (built-in)
# -----------------------------------------------------------------------

# -----------------------------------------------------------------------
# Carregamento de JSONs
# -----------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..',
                          'data', 'cards')
CARTAS_EXEMPLO: dict[str, ModeloCarta] = {}


def _json_para_modelo(dados: dict) -> ModeloCarta:
    """Converte dict de JSON para ModeloCarta."""
    modos = []
    for m in dados.get('modos', []):
        efeitos = []
        for e in m.get('efeitos', []):
            efeitos.append(_efeito_from_json(e))
        modos.append(Modo(
            descricao=m['descricao'],
            efeitos=efeitos,
        ))
    return ModeloCarta(
        id=dados['id'],
        nome=dados['nome'],
        tipo=dados.get('tipo', 'event'),
        modos=modos,
    )


def _efeito_from_json(e: dict) -> Efeito:
    """Converte um dict de efeito JSON para Efeito (recursivo)."""
    return Efeito(
        tipo=e['tipo'],
        condicao=e.get('condicao_alvo'),
        alvo=e.get('alvo'),
        quantidade=e.get('quantidade', 0),
        duracao=e.get('duracao', ''),
        se_sucesso=[_efeito_from_json(s) for s in e.get('se_sucesso', [])],
        se_fracasso=[_efeito_from_json(f) for f in e.get('se_fracasso', [])],
        condicao_estado=e.get('condicao_estado'),
    )


def _carregar_todos_json() -> dict[str, ModeloCarta]:
    """Carrega todas as cartas do diretorio data/cards/."""
    cartas = {}
    if not os.path.isdir(_DATA_DIR):
        return cartas
    for fname in sorted(os.listdir(_DATA_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(_DATA_DIR, fname)
        try:
            with open(path, encoding='utf-8') as f:
                dados = json.load(f)
            modelo = _json_para_modelo(dados)
            cartas[modelo.id] = modelo
        except Exception as exc:
            print(f'[effects] Erro ao carregar {fname}: {exc}')
    return cartas


# Carrega automaticamente na inicializacao do modulo
CARTAS_EXEMPLO.update(_carregar_todos_json())
