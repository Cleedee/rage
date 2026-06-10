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

import copy
import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from rage_web.game_engine.state import (
    CardInstance, GameState, GameModifier, PendenciaEfeito,
    PlayerState, Zone, anexar_dano, descartar_anexos,
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
    IMPEDIR_ACOES = 'impedir_acoes'  # Alvo nao pode tomar acoes
    IMPEDIR_RETIRADA = 'impedir_retirada'  # Alvo nao pode fugir/escapar do combate
    CANCELAR_ACAO = 'cancelar_acao'  # Cancelar Action card como interrupt
    ATAQUE_IMEDIATO = 'ataque_imediato'  # Atacar imediatamente apos combate
    REMOVER_DO_COMBATE = 'remover_do_combate'  # Remover criatura do combate em andamento
    FORCAR_BLUFF = 'forcar_bluff'  # Proxima Combat Action do alvo e bluff
    IMPEDIR_FRENZY = 'impedir_frenzy'  # Ninguem pode frenzir (global)
    OLHAR_TOPO_DECK = 'olhar_topo_deck'  # Olhar topo do deck do oponente
    DESCARTAR_MAO_COMBATE = 'descartar_mao_combate'  # Oponente descarta toda mao de combate
    REGISTRAR_TRIGGER_COMBATE = 'registrar_trigger_combate'  # Registrar trigger de combate (ex: Tzinzie)
    # Efeitos de setup / passivos
    EQUIPAR_INICIAL = 'equipar_inicial'  # Comeca o jogo com equipamento (Bannion)
    FILTRAR_REDRAW = 'filtrar_redraw'  # Fim do Redraw: descarta + compra (Buggerhead)
    COMPRAR_QUANDO_ATACADO = 'comprar_quando_atacado'  # Compra quando atacado (Mother Larissa)
    REMOVER_DO_DESCARTE = 'remover_do_descarte'  # Remove carta do descarte (Quari Filth)
    BUSCAR_COPIAS = 'buscar_copias'  # Busca copias do deck e joga (Mosquito Swarm)
    AUTO_PACK_ATTACK = 'auto_pack_attack'  # Auto pack attack/defend (Mosquito Swarm)
    ACAO_EXTRA_POR_RODADA = 'acao_extra_por_rodada'  # Ação extra de combate por rodada (Devilwhip)
    IMUNE_COMBATE_RAGE = 'imune_combate_rage'  # Imune a combat actions de certo Rage (Dhul Fiqar)
    MODIFICAR_ATRIBUTO_PASSIVO = 'modificar_atributo_passivo'  # Buff passivo persistente (John)
    MODIFICAR_GAUNTLET = 'modificar_gauntlet'  # Modifica o Gauntlet (Shadow-Weaver)
    # Efeitos de Moot (Juntas)
    MOOT_REMOVER_PERSONAGEM = 'moot_remover_personagem'  # Remove personagem do jogo (Skindancer, Winter Wolf)
    MOOT_GANHAR_VP = 'moot_ganhar_vp'  # Ganha VP por Moot aprovado (Silver Record, Legendary Leadership)
    MOOT_RESTRICAO_GLOBAL = 'moot_restricao_global'  # Restricao global (Tribal War, Litany's Guidance)
    MOOT_REBAIXAR_FORMA = 'moot_rebaixar_forma'  # Reverte a forma breed (The Stolen Wolf)
    MOOT_CONSTRUIR_CAERN = 'moot_construir_caern'  # Constrói um Caern (Caern Building)


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
    # Campos extras do JSON que nao mapeiam diretamente
    # (ex: 'vp', 'acao' para quest_check)
    params: dict = field(default_factory=dict)

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

        # Valida Gauntlet: verifica se o tipo de efeito pode cruzar
        # o Gauntlet para o alvo (regra 5 - Umbra)
        if not self._validar_gauntlet_efeito(origem, jogador, alvo):
            nome_alvo = getattr(alvo, 'name', str(alvo))
            self.log.append(
                f'Gauntlet: {origem.name} nao pode atingir '
                f'{nome_alvo} (lados diferentes do Gauntlet)'
            )
            return False

        # Armazena ultimo alvo para condicao_estado
        self._ultimo_alvo = alvo if not isinstance(alvo, list) else (alvo[0] if alvo else None)

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
    EfeitoTipo.COMBAR_ACAO: self._resolver_combar_acao,
    EfeitoTipo.IMPEDIR_ACOES: self._resolver_impedir_acoes,
    EfeitoTipo.IMPEDIR_RETIRADA: self._resolver_impedir_retirada,
    EfeitoTipo.CANCELAR_ACAO: self._resolver_cancelar_acao,
    EfeitoTipo.ATAQUE_IMEDIATO: self._resolver_ataque_imediato,
    EfeitoTipo.REMOVER_DO_COMBATE: self._resolver_remover_do_combate,
    EfeitoTipo.FORCAR_BLUFF: self._resolver_forcar_bluff,
    EfeitoTipo.IMPEDIR_FRENZY: self._resolver_impedir_frenzy,
    EfeitoTipo.OLHAR_TOPO_DECK: self._resolver_olhar_topo_deck,
    EfeitoTipo.DESCARTAR_MAO_COMBATE: self._resolver_descartar_mao_combate,
    EfeitoTipo.REGISTRAR_TRIGGER_COMBATE: self._resolver_registrar_trigger_combate,
    EfeitoTipo.EQUIPAR: self._resolver_equipar,
    EfeitoTipo.MODIFICAR_REDUCAO_DANO: self._resolver_modificar_reducao_dano,
    EfeitoTipo.DESCARTAR_METADE_MAO: self._resolver_descartar_metade_mao,
    EfeitoTipo.REMOVER_DO_JOGO: self._resolver_remover_do_jogo,
            EfeitoTipo.EQUIPAR_INICIAL: self._resolver_equipar_inicial,
            EfeitoTipo.FILTRAR_REDRAW: self._resolver_filtrar_redraw,
            EfeitoTipo.COMPRAR_QUANDO_ATACADO: self._resolver_comprar_quando_atacado,
            EfeitoTipo.REMOVER_DO_DESCARTE: self._resolver_remover_do_descarte,
            EfeitoTipo.BUSCAR_COPIAS: self._resolver_buscar_copias,
            EfeitoTipo.AUTO_PACK_ATTACK: self._resolver_auto_pack_attack,
            EfeitoTipo.ACAO_EXTRA_POR_RODADA: self._resolver_acao_extra_por_rodada,
            EfeitoTipo.IMUNE_COMBATE_RAGE: self._resolver_imune_combate_rage,
            EfeitoTipo.MODIFICAR_ATRIBUTO_PASSIVO: self._resolver_modificar_atributo_passivo,
            EfeitoTipo.MODIFICAR_GAUNTLET: self._resolver_modificar_gauntlet,
            # Efeitos de Moot
            EfeitoTipo.MOOT_REMOVER_PERSONAGEM: self._resolver_moot_remover_personagem,
            EfeitoTipo.MOOT_GANHAR_VP: self._resolver_moot_ganhar_vp,
            EfeitoTipo.MOOT_RESTRICAO_GLOBAL: self._resolver_moot_restricao_global,
            EfeitoTipo.MOOT_REBAIXAR_FORMA: self._resolver_moot_rebaixar_forma,
            EfeitoTipo.MOOT_CONSTRUIR_CAERN: self._resolver_moot_construir_caern,
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

        # Normaliza atalhos
        mapa_aliases = {
            'jogador': 'jogador_aliado',
            'inimigo': 'criatura_inimiga',
            'aliado': 'criatura_aliada',
            'self': 'self',
        }
        condicao = mapa_aliases.get(condicao, condicao)

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

        def _vitimas_inimigas() -> list[CardInstance]:
            """Agrega apenas criaturas do tipo Victim de todos os oponentes."""
            resultado = []
            for op in oponentes:
                for c in op.pack_home + op.hunting_grounds:
                    if c.card_type and 'Victim' in c.card_type:
                        resultado.append(c)
            return resultado

        def _criatura_especifica(cid: str) -> Optional[CardInstance]:
            """Encontra uma criatura pelo card_id em qualquer zona."""
            for p in self.game.players:
                for c in p.pack_home + p.umbra + p.hunting_grounds:
                    if str(c.card_id) == cid:
                        return c
            return None

        # Moot effects: escolher alvo mais ameaçador (maior Renome)
        def _criaturas_inimigas_moot() -> Optional[CardInstance]:
            """Para Moots: escolhe a criatura inimiga de maior Renome."""
            alvos = _criaturas_inimigas()
            if not alvos:
                return None
            return max(alvos, key=lambda c: c.renown)

        resolvedores_alvo = {
            'criatura_inimiga': lambda: self._escolher_criatura(
                _criaturas_inimigas()
            ),
            'criatura_inimiga_moot': lambda: _criaturas_inimigas_moot(),
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
            'vitima': lambda: self._escolher_criatura(
                _vitimas_inimigas()
            ),
            'ally_inimigo': lambda: self._escolher_criatura(
                [c for op in oponentes for c in op.pack_home
                 if c.card_type and 'Ally' in c.card_type]
            ),
            'acao': lambda: 'acao',  # Alvo generico para cancelar_acao
            'packmates': lambda: [c for c in jogador.pack_home
                                  if str(c.card_id) != str(origem.card_id)],
            'combat_descarte': lambda: self._escolher_carta_descarte(jogador),
            'combat_descarte_inimigo': lambda: self._escolher_carta_descarte(
                self._escolher_jogador(self._get_oponentes(jogador))
            ) if self._get_oponentes(jogador) else None,
            'deck_sept_proprio': lambda: jogador.deck_sept,
            'deck_combate_proprio': lambda: jogador.deck_combate,
            # Aliases/abreviacoes (compatibilidade com JSONs simplificados)
            'inimigo': lambda: self._escolher_criatura(
                _criaturas_inimigas()
            ),
            'self': lambda: origem,
            'aliado': lambda: self._escolher_criatura(
                jogador.pack_home
            ),
        }

        # Alvo especifico por card_id (vindo de efeito params)
        alvo_id = efeito.params.get('alvo_id') if hasattr(efeito, 'params') else None
        if alvo_id:
            return _criatura_especifica(alvo_id)

        resolvedor = resolvedores_alvo.get(condicao)
        if resolvedor:
            return resolvedor()
        return None

    def _validar_gauntlet_efeito(self, origem: CardInstance,
                                   jogador: PlayerState,
                                   alvo: Any) -> bool:
        """Valida se um efeito pode cruzar o Gauntlet para o alvo.

        Regra (5 - Umbra): Actions, Gifts, Rites, Combat Actions,
        Past Lives, Quests e special abilities NAO podem cruzar o
        Gauntlet. Events/Totems/Caerns/Territories afetam ambos os lados.

        A verificacao usa a ZONA DA CRIATURA ORIGEM (quem joga a carta)
        e a ZONA DO ALVO — se estao no mesmo lado, nao ha cruzamento.

        Returns:
            True se o efeito pode cruzar (ou não precisa).
        """
        tipo = (origem.card_type or '').lower()

        # Events, Totems afetam ambos os lados (regra 5)
        if tipo in ('event', 'event - totem', 'totem'):
            return True

        # Caerns e Territórios existem em ambos os lados (regra 5)
        if tipo in ('caern', 'territory', 'realm'):
            return True

        # Tipos que NÃO podem cruzar o Gauntlet
        tipos_que_nao_cruzam = {
            'action', 'gift', 'past life', 'quest', 'rite',
            'combat action', 'combat event',
        }
        if tipo not in tipos_que_nao_cruzam:
            return True

        # Para tipos que não cruzam: verifica se origem e alvo estão
        # no mesmo lado do Gauntlet (nesse caso, não há cruzamento)
        if isinstance(alvo, CardInstance):
            if self._mesmo_lado_gauntlet_por_zona(origem, alvo):
                return True
            # Se estão em lados diferentes, verifica permissões especiais
            if _gauntlet_permite_cruzar(self.game, jogador, None, None):
                return True
            return False

        # Alvo não é CardInstance (ex: jogador, mão, deck) — permite
        return True

    def _mesmo_lado_gauntlet_por_zona(self, origem: CardInstance,
                                      alvo: CardInstance) -> bool:
        """Verifica se a criatura origem e o alvo estão no mesmo lado do Gauntlet.

        Usa as ZONAS das criaturas:
        - PACK_HOME = mundo físico
        - UMBRA = Umbra
        - HUNTING_GROUNDS / OUT_OF_PLAY / DISCARD = ambos os lados
        """
        def _lado(card: CardInstance) -> int:
            if card.zone == Zone.UMBRA:
                return -1  # Umbra
            elif card.zone == Zone.PACK_HOME:
                return 1   # mundo físico
            else:
                return 0   # ambos os lados (HG, descarte, etc)

        lado_origem = _lado(origem)
        lado_alvo = _lado(alvo)

        # Se qualquer um está em ambos os lados, podem interagir
        if lado_origem == 0 or lado_alvo == 0:
            return True

        # Mesmo lado = podem interagir
        return lado_origem == lado_alvo

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

    def _escolher_carta_descarte(self, jogador: Optional[PlayerState]
                                 ) -> Optional[dict]:
        """Escolhe uma carta aleatoria do descarte de combate."""
        if not jogador or not jogador.discard_combat:
            return None
        carta = self.rng.choice(jogador.discard_combat)
        return {'jogador': jogador, 'carta': carta, 'indice': jogador.discard_combat.index(carta)}

    def _get_oponentes(self, jogador: PlayerState) -> list[PlayerState]:
        """Retorna lista de todos os jogadores que nao sao o atual.

        Suporta partidas com N jogadores.
        Regra 2.3: jogadores eliminados nao podem ser alvos.
        """
        return [p for p in self.game.players
                if p.id != jogador.id and not p.eliminado]

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
            # Verifica flip para Crinos
            from rage_web.game_engine.combat_queue import _flipar_para_crinos
            _flipar_para_crinos(self.game, alvo)
            # Processa morte (fora de combate)
            if alvo.health_current <= 0:
                from rage_web.game_engine.combat_queue import _processar_morte
                dono_origem = None
                for p in self.game.players:
                    if p.id == jogador.id:
                        dono_origem = p
                        break
                _processar_morte(self.game, alvo, origem,
                                 dono_origem, em_combate=False)
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

            # Death triggers
            self.game.check_death_triggers(alvo, origem, jogador)

            # Marca dano em quests
            for p in self.game.players:
                for q in p.quests:
                    if q.target_card_uid == id(alvo) and not q.completed:
                        q.completed = True
                        q.failed_due_to_death = True
                        self.game.add_log(
                            f'  Quest falhou: {alvo.name} '
                            f'(alvo da quest) foi destruido'
                        )

            return True
        return False

    def _resolver_remover_do_jogo(self, efeito: Efeito,
                                   origem: CardInstance,
                                   jogador: PlayerState, alvo) -> bool:
        """Remove uma criatura do jogo temporariamente.

        A criatura e movida para OUT_OF_PLAY e uma pendencia e criada
        para restaura-la no fim da proxima fase.

        Usado por Chant of Morpheus e efeitos similares.

        Se params['descarte_apos_uso'] for True, move para DISCARD_COMBAT
        (usado por equipamentos descartaveis como Spiral Boomerang).
        """
        if not isinstance(alvo, CardInstance):
            return False

        params = efeito.params or {}
        descarte = params.get('descarte_apos_uso')
        also_self = params.get('also_remove_self')
        restricao = params.get('restricao_extra', '')

        if descarte:
            for p in self.game.players:
                for lista in (p.pack_home, p.hunting_grounds,
                              p.umbra, p.hand):
                    if alvo in lista:
                        lista.remove(alvo)
                        break
            alvo.zone = Zone.DISCARD_COMBAT
            dono = self._find_player(alvo.owner_id) or jogador
            dono.discard_combat.append(alvo)
            self.game.add_log(
                f'{alvo.name} foi descartado (descarte apos uso)'
            )
            return True

        def _remover_um(card: CardInstance) -> bool:
            zona_original = card.zone
            if zona_original == Zone.OUT_OF_PLAY:
                if restricao and restricao not in card.restricoes:
                    card.restricoes.append(restricao)
                return True
            if zona_original not in (Zone.PACK_HOME, Zone.HUNTING_GROUNDS,
                                     Zone.UMBRA):
                return False
            _remove_creature(self.game, card)
            card.zone = Zone.OUT_OF_PLAY
            dono_out = self._find_player(card.owner_id) or jogador
            if card not in dono_out.out_of_play:
                dono_out.out_of_play.append(card)
            if restricao and restricao not in card.restricoes:
                card.restricoes.append(restricao)
            from rage_web.game_engine.state import PendenciaEfeito
            # Usa 'end_of_turn' se Blossom, 'end_of_phase' para outros (Chant)
            duracao_pend = 'end_of_turn' if also_self else 'end_of_phase'
            pendencia = PendenciaEfeito(
                card_uid=id(card),
                atributo='zona',
                delta=0,
                duracao=duracao_pend,
                valor_str=zona_original.value,
                turno_aplicado=self.game.turn_number,
                fase_aplicada=self.game.phase,
            )
            if restricao:
                pend2 = PendenciaEfeito(
                    card_uid=id(card),
                    atributo='restricao',
                    delta=0,
                    duracao=duracao_pend,
                    valor_str=restricao,
                    turno_aplicado=self.game.turn_number,
                    fase_aplicada=self.game.phase,
                )
                self.game.pendencias.append(pend2)
            self.game.pendencias.append(pendencia)
            verb = 'turno' if also_self else 'fase'
            self.game.add_log(
                f'{card.name} foi removido do jogo ate o fim do {verb}'
            )
            return True

        ok = _remover_um(alvo)

        if also_self:
            if origem is alvo:
                # Alvo foi o proprio Blossom - precisa remover outro
                # Escolhe outra criatura aliada (nao Blossom)
                outros = [c for c in jogador.pack_home
                          if c is not origem and c.zone != Zone.OUT_OF_PLAY]
                if outros:
                    outro = self._escolher_criatura(outros)
                    if outro:
                        ok = _remover_um(outro) or ok
            else:
                ok = _remover_um(origem) or ok

        return ok

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
        """Compra cartas do deck de combate.

        Suporta params:
        - por_packmate: bool — compra N cartas por packmate
        - zona: str — 'deck_combate' (padrao) ou 'deck_sept'
        """
        qtd = efeito.quantidade or 1
        por_packmate = efeito.params.get('por_packmate', False)
        zona = efeito.params.get('zona', 'deck_combate')

        if por_packmate:
            # Conta packmates (aliados em pack_home, excluindo origem)
            packmates = [c for c in jogador.pack_home
                        if str(c.card_id) != str(origem.card_id)]
            qtd = qtd * len(packmates)
            self.game.add_log(
                f'{len(packmates)} packmate(s): comprando {qtd} carta(s)'
            )

        if zona == 'deck_sept':
            jogador.draw_sept(qtd)
        else:
            jogador.draw_combat(qtd)
        self.game.add_log(f'{jogador.name} comprou {qtd} carta(s) de {zona}')
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
        """Move uma criatura entre zonas.

        Suporta params:
        - 'zona': nome da zona destino ('umbra', 'hunting_grounds', etc)
        - 'duracao': numero de turnos antes de retornar (ex: 2)
        - 'retornar_zona_original': bool, se deve voltar para zona original
        """
        if not isinstance(alvo, CardInstance):
            return False

        zona_destino = (efeito.params.get('zona') if efeito.params
                        else None) or efeito.alvo or efeito.condicao or 'hunting_grounds'
        zonas = {
            'hunting_grounds': Zone.HUNTING_GROUNDS,
            'umbra': Zone.UMBRA,
            'pack_home': Zone.PACK_HOME,
            'descarte': Zone.DISCARD_COMBAT,
        }
        nova_zona = zonas.get(zona_destino)
        if not nova_zona:
            return False

        # Salva zona original antes de mover
        zona_original = alvo.zone

        # Remove da lista de origem (todos os jogadores)
        for p in self.game.players:
            for lista in (p.pack_home, p.hunting_grounds,
                          p.umbra, p.hand):
                if alvo in lista:
                    lista.remove(alvo)
                    break

        # Adiciona na lista de destino do DONO do alvo (nao do jogador atual)
        dono_alvo = self._find_player(alvo.owner_id) or jogador
        map_destino = {
            Zone.PACK_HOME: dono_alvo.pack_home,
            Zone.UMBRA: dono_alvo.umbra,
            Zone.HUNTING_GROUNDS: dono_alvo.hunting_grounds,
            Zone.DISCARD_COMBAT: dono_alvo.discard_combat,
        }
        lista_destino = map_destino.get(nova_zona)
        if lista_destino is not None:
            lista_destino.append(alvo)

        alvo.zone = nova_zona
        self.game.add_log(f'{alvo.name} movido para {zona_destino}')

        # Se tem duracao, cria pendencia para retornar
        duracao = int(efeito.params.get('duracao', 0)) if efeito.params else 0
        if duracao > 0:
            from rage_web.game_engine.state import PendenciaEfeito
            zona_retorno = zona_original.value if (efeito.params.get('retornar_zona_original')
                           and zona_original in zonas.values()) else Zone.PACK_HOME.value
            pendencia = PendenciaEfeito(
                card_uid=id(alvo),
                atributo='zona',
                delta=0,
                duracao=f'after_{self.game.turn_number + duracao}_turns',
                turno_aplicado=self.game.turn_number,
                fase_aplicada=self.game.phase,
                valor_str=zona_retorno,
            )
            self.game.pendencias.append(pendencia)
            self.game.add_log(
                f'{alvo.name} retornara em {duracao} turno(s)'
            )

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
        """Adiciona uma restricao temporaria a uma criatura.

        Suporta params:
        - restricao: str — nome da restricao (se nao usar efeito.alvo)
        - exceto: list[str] — tipos que ignoram a restricao
        - duracao: str — duracao da restricao
        """
        restricao = efeito.params.get('restricao', efeito.alvo or '')
        exceto = efeito.params.get('exceto', [])
        duracao = efeito.duracao or efeito.params.get('duracao', 'permanente_ate_cancelar')

        if not restricao:
            return False

        # Se tem exceto, verifica se o alvo se qualifica
        if exceto:
            # Verifica se a origem (quem recebe a restricao) e do tipo exceto
            if hasattr(origem, 'card_type') and origem.card_type:
                for tipo in exceto:
                    if tipo.lower() in origem.card_type.lower():
                        self.game.add_log(
                            f'{origem.name} e {tipo}: ignorando restricao "{restricao}"'
                        )
                        return True  # Nao aplica restricao, mas consideramos sucesso

        if isinstance(alvo, CardInstance):
            if restricao not in alvo.restricoes:
                alvo.restricoes.append(restricao)
                if duracao and duracao != 'permanente_ate_cancelar':
                    self.game.pendencias.append(PendenciaEfeito(
                        card_uid=id(alvo), atributo='restricao',
                        delta=0, valor_str=restricao,
                        duracao=duracao,
                        turno_aplicado=self.game.turn_number,
                        fase_aplicada=self.game.phase,
                    ))
                self.game.add_log(
                    f'{alvo.name} recebeu restricao "{restricao}"'
                    f'{" ate " + duracao if duracao else ""}'
                )
                return True
        elif isinstance(alvo, list):
            for c in alvo:
                if restricao not in c.restricoes:
                    c.restricoes.append(restricao)
            self.game.add_log(
                f'{len(alvo)} criatura(s) receberam restricao "{restricao}"'
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
        alvo_ct = (alvo.card_type or '').lower()
        alvo_name = (alvo.name or '').lower()
        alvo_text = f'{alvo_name} {alvo_ct} {alvo_kw}'

        # ── 1. Fetish / Bane Fetish alignment restriction ──
        # Fetish: apenas Gaia podem equipar
        # Bane Fetish: apenas Wyrm podem equipar
        # (alguns cards sao ambos - 'Fetish - Bane Fetish' - podem ambos)
        # Nota: 'Non-Fetish' contem 'Fetish' mas NAO e Fetish
        eh_non_fetish = 'non-fetish' in kw
        eh_fetish = not eh_non_fetish and ('gaia fetish' in kw
                    or ('fetish' in kw and 'bane fetish' not in kw))
        eh_bane_fetish = not eh_non_fetish and 'bane fetish' in kw
        eh_ambos = not eh_non_fetish and 'gaia fetish' in kw and 'bane fetish' in kw

        if not eh_ambos and not eh_non_fetish:
            # Gaia Fetish: alvo deve ser Gaia
            if eh_fetish and 'gaia' not in alvo_text:
                self.game.add_log(
                    f'{equipamento.name} e Fetish (Gaia), mas '
                    f'{alvo.name} nao e Gaia'
                )
                return False
            # Bane Fetish: alvo deve ser Wyrm
            if eh_bane_fetish and 'wyrm' not in alvo_text:
                self.game.add_log(
                    f'{equipamento.name} e Bane Fetish (Wyrm), mas '
                    f'{alvo.name} nao e Wyrm'
                )
                return False

        # ── 2. Gnosis requirement for Fetish/Bane Fetish ──
        gnosis_req = equipamento.gnosis or 0
        if gnosis_req > 0 and alvo.gnosis < gnosis_req:
            self.game.add_log(
                f'{equipamento.name} requer Gnosis {gnosis_req}, mas '
                f'{alvo.name} tem Gnosis {alvo.gnosis}'
            )
            return False

        # ── 3. Keyword requirement validation (requires field) ──
        requires = (equipamento.requires or '').strip()
        if requires:
            # Ignora formatos especiais que nao sao keywords
            # Ex: 'Gnosis 2' (ja validado acima), '(Crinos form)' (validado abaixo)
            req_lower = requires.lower()

            # Se comeca com '(' e termina com ')', e formato especial (nao keyword)
            if not (req_lower.startswith('(') and req_lower.endswith(')')):
                # E uma keyword normal - verifica Rage FOO Rule
                opcoes = [p.strip() for p in requires.split(' - ')]
                from rage_web.game_engine.rules import _opcao_matches_char
                from rage_web.game_engine.state import Zone
                if not any(_opcao_matches_char(o, alvo_text, alvo.gnosis)
                           for o in opcoes):
                    self.game.add_log(
                        f'{equipamento.name} requer "{requires}", mas '
                        f'{alvo.name} nao atende '
                        f'(keywords: {alvo.keywords})'
                    )
                    return False

        # ── 4. Form restrictions (parentheses format) ──
        # Formatos:
        #   '(Homid Form)'  → keyword 'Homid' deve estar presente
        #   '(Crinos form)' → keyword 'Crinos' deve estar presente
        #   '(Not Animal form)' → keyword 'Animal' nao deve estar presente
        #   '(Garou)'       → keyword 'Garou' deve estar presente
        #   '(Silent Strider)' → texto 'silent strider' deve estar presente
        if requires:
            req_lower = requires.lower()
            if req_lower.startswith('(') and req_lower.endswith(')'):
                req_clean = req_lower.strip('()').strip()

                # Verifica se e 'Not X form' (negacao)
                if req_clean.startswith('not '):
                    # Extrai a keyword apos 'Not ' e antes de ' form' (se houver)
                    forma_text = req_clean[4:].strip()
                    if forma_text.endswith(' form'):
                        forma_text = forma_text[:-5].strip()
                    if forma_text in alvo_text:
                        self.game.add_log(
                            f'{equipamento.name} requer que nao esteja '
                            f'em forma {forma_text}, mas '
                            f'{alvo.name} esta'
                        )
                        return False
                else:
                    # Forma positiva: extrai keyword antes de ' form' (se houver)
                    forma_text = req_clean
                    if forma_text.endswith(' form'):
                        forma_text = forma_text[:-5].strip()
                    if forma_text not in alvo_text:
                        self.game.add_log(
                            f'{equipamento.name} requer "{req_clean}", '
                            f'mas {alvo.name} nao atende'
                        )
                        return False

        # ── 5. Weapon/Armor limit (1 each) ──
        eh_weapon = 'weapon' in kw
        eh_armor = 'armor' in kw
        for eq in alvo.attached_equipment:
            eq_kw = (eq.keywords or '').lower()
            if eh_weapon and 'weapon' in eq_kw:
                self.game.add_log(
                    f'{alvo.name} ja tem uma arma ({eq.name})'
                )
                return False
            if eh_armor and 'armor' in eq_kw:
                self.game.add_log(
                    f'{alvo.name} ja tem uma armadura ({eq.name})'
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

        Suporta params:
        - atributos: list[str] — ex: ['rage', 'gnosis']
        - minimo: int — valor minimo do atributo
        - duracao: str — 'ate_fim_combate', 'permanente', etc.
        - escolha: str — 'dono_caern' (escolhe qual atributo modificar)
        - filtro_tipo: str — 'Wyrm' ou 'non_Wyrm'
        - limite_afetar_mesmo_alvo: int
        - trocar_forma: bool — para Shapeshift
        """
        atributos = efeito.params.get('atributos', ['rage'])
        quantidade = efeito.quantidade or 1
        minimo = int(efeito.params.get('minimo', 0))
        duracao = efeito.params.get('duracao', 'ate_fim_combate')
        escolha = efeito.params.get('escolha', '')
        filtro_tipo = efeito.params.get('filtro_tipo', '')
        limite = int(efeito.params.get('limite_afetar_mesmo_alvo', 0))
        trocar_forma = efeito.params.get('trocar_forma', False)

        if trocar_forma:
            # Shapeshift: alterna entre breed e Crinos
            if hasattr(origem, 'is_crinos'):
                origem.is_crinos = not origem.is_crinos
                forma = 'Crinos' if origem.is_crinos else 'breed'
                self.game.add_log(
                    f'{origem.name} mudou para forma {forma}'
                )
                return True
            self.game.add_log(f'{origem.name}: Shapeshift (stub)')
            return True

        # Determina alvos com base em filtro_tipo
        alvos = []
        if isinstance(alvo, CardInstance):
            alvos = [alvo]
        elif isinstance(alvo, list):
            alvos = alvo
        elif isinstance(alvo, PlayerState):
            # Aplica a todas as criaturas do jogador
            alvos = alvo.pack_home

        if not alvos:
            return False

        # Aplica filtro_tipo se especificado
        if filtro_tipo:
            if filtro_tipo == 'Wyrm':
                alvos = [c for c in alvos if c.card_type and 'Wyrm' in c.card_type]
            elif filtro_tipo == 'non_Wyrm':
                alvos = [c for c in alvos if not c.card_type or 'Wyrm' not in c.card_type]

        if not alvos:
            self.game.add_log(f'{origem.name}: nenhum alvo valido (filtro={filtro_tipo})')
            return False

        # Se escolha == 'dono_caern', o dono escolhe qual atributo
        attrs_a_modificar = list(atributos)
        if escolha == 'dono_caern' and len(atributos) > 1:
            # Por enquanto, escolhe o primeiro (Rage) como padrao
            # TODO: UI para escolha do jogador
            attrs_a_modificar = [atributos[0]]

        for c in alvos:
            # Verifica limite_afetar_mesmo_alvo
            if limite > 0:
                chave = f'{origem.name}_mod_{c.name}'
                vezes = getattr(self.game, '_mod_counter', {}).get(chave, 0)
                if vezes >= limite:
                    self.game.add_log(
                        f'{c.name}: limite de {limite} modificacoes atingido'
                    )
                    continue
                if not hasattr(self.game, '_mod_counter'):
                    self.game._mod_counter = {}
                self.game._mod_counter[chave] = vezes + 1

            for attr in attrs_a_modificar:
                if attr == 'rage':
                    novo = max(minimo, c.rage + quantidade)
                    delta = novo - c.rage
                    c.rage = novo
                elif attr == 'gnosis':
                    novo = max(minimo, c.gnosis + quantidade)
                    delta = novo - c.gnosis
                    c.gnosis = novo
                elif attr == 'health':
                    novo = max(1, c.health + quantidade)
                    delta = novo - c.health
                    c.health = novo
                    c.health_current = max(1, c.health_current + delta)
                else:
                    continue

                # Se duracao for temporaria, registra pendencia para reverter
                if duracao and duracao != 'permanente':
                    from rage_web.game_engine.state import PendenciaEfeito
                    self.game.pendencias.append(PendenciaEfeito(
                        card_uid=id(c),
                        atributo=attr,
                        delta=-delta,
                        duracao=duracao,
                        turno_aplicado=self.game.turn_number,
                        fase_aplicada=self.game.phase,
                    ))

                self.game.add_log(
                    f'{c.name}: {attr} {"+" if delta >= 0 else ""}{delta} '
                    f'= {getattr(c, attr)} ({duracao})'
                )

        return True

    def _resolver_usar_gift(self, efeito: Efeito,
                              origem: CardInstance,
                              jogador: PlayerState, alvo) -> bool:
        """Usa um Gift atraves de outro card (ex: Haunter).

        Busca um Gift na mao do jogador com o tipo especificado
        e aplica seus efeitos como se tivesse sido jogado.
        """
        gift_tipo = efeito.params.get('tipo_gift', '').lower()
        gift_id = efeito.params.get('card_id', 0)

        # Procura gift na mao ou no sept deck
        encontrado = None
        for c in jogador.hand:
            if c.card_id == gift_id:
                encontrado = c
                break
            if gift_tipo and gift_tipo in c.card_type.lower():
                encontrado = c
                break
        if not encontrado:
            for c in jogador.deck_sept:
                if c.card_id == gift_id:
                    encontrado = c
                    break
                if gift_tipo and gift_tipo in c.card_type.lower():
                    encontrado = c
                    break

        if not encontrado:
            self.game.add_log(
                f'{origem.name}: nenhum Gift encontrado'
            )
            return True

        # Aplica o Gift como se tivesse sido jogado
        if encontrado.zone == Zone.HAND:
            jogador.hand.remove(encontrado)
        elif encontrado.zone == Zone.DECK_SEPT:
            jogador.deck_sept.remove(encontrado)
        encontrado.zone = Zone.OUT_OF_PLAY
        jogador.discard_sept.append(encontrado)
        self.game.add_log(
            f'{origem.name} usou {encontrado.name} (via efeito)'
        )
        return True

    def _resolver_quest_check(self, efeito: Efeito,
                                origem: CardInstance,
                                jogador: PlayerState, alvo) -> bool:
        """Inicia uma quest no jogador.

        Usado por Mnesis Dreams: cria QuestState que conta turnos
        sem dano. Se completar, da VP + shuffle card do discard.

        Parametros do JSON (acessiveis via efeito.params):
        - 'condicao': tipo de condicao ('sem_dano_por_2_turnos')
        - 'quantidade': numero de turnos (2)
        - 'vp': VP concedido ao completar (2)
        - 'acao': acao ao completar ('shuffle_card_discard_to_deck')
        """
        from rage_web.game_engine.state import QuestState, Zone

        quantidade = max(1, int(efeito.params.get('quantidade', 2)))
        condicao = efeito.params.get('condicao', 'sem_dano_por_2_turnos')
        vp = int(efeito.params.get('vp', 2))
        acao = efeito.params.get('acao', '')

        # Alvo: o proprio personagem alvo (passado via efeito)
        if not alvo or not hasattr(alvo, 'card_id'):
            self.game.add_log(f'{origem.name}: alvo invalido para quest')
            return False

        # Valida: so pode uma quest por personagem
        for q in jogador.quests:
            if q.target_card_uid == id(alvo):
                self.game.add_log(
                    f'{alvo.name} ja tem uma quest ativa!')
                return False

        # Valida: alvo deve ser do proprio pack
        if alvo not in jogador.pack_home and alvo not in jogador.umbra:
            self.game.add_log(
                f'{origem.name}: quest so pode ser jogada em membros do pack')
            return False

        # Valida: Prey (Victim/Enemy) nao pode fazer Quests
        ct_alvo = (alvo.card_type or '').lower()
        if 'victim' in ct_alvo or 'enemy' in ct_alvo:
            self.game.add_log(
                f'{origem.name}: Presa ({alvo.card_type}) '
                f'nao pode fazer Quests')
            return False

        # Valida: Past Lives sao Unique (so 1 copia em jogo)
        ct_origem = (origem.card_type or '').lower()
        if 'past life' in ct_origem or ct_origem == 'past life':
            for c in jogador.pack_home + jogador.hunting_grounds:
                if c.card_id == origem.card_id and id(c) != id(origem):
                    self.game.add_log(
                        f'{origem.name}: Past Life unica '
                        f'(ja tem uma copia em jogo)')
                    return False

        # Cria quest state no jogador
        quest = QuestState(
            quest_card_uid=id(origem),
            target_card_uid=id(alvo),
            condition=condicao,
            turns_remaining=quantidade,
            reward_vp=vp,
            reward_acao=acao
        )
        jogador.quests.append(quest)

        # Mantem a carta de quest em jogo (pack_home) como marcador
        # enquanto a quest estiver ativa
        if origem.zone == Zone.HAND:
            origem.zone = Zone.PACK_HOME
            jogador.pack_home.append(origem)

        # Past Life: recalcula sept hand size (reduz em 1 por Past Life)
        ct_origem = (origem.card_type or '').lower()
        if 'past life' in ct_origem or ct_origem == 'past life':
            self.game._recalcular_past_life_hand_size(jogador)

        self.game.add_log(
            f'{jogador.name} iniciou quest {origem.name} '
            f'em {alvo.name} ({quantidade} turnos sem dano)'
        )
        return True

    # ── Novos resolvedores deck484 ──────────────────────────────────

    def _resolver_combar_acao(self, efeito: Efeito,
                               origem: CardInstance,
                               jogador: PlayerState, alvo) -> bool:
        """Encadeia uma acao apos a anterior (Combar).

        Usado por: Head or Gut? (119) que da +1 VP se matar.
        A acao encadeada e resolvida via se_sucesso.
        """
        # O combar_acao em si nao faz nada; os efeitos
        # encadeados estao em se_sucesso/se_fracasso e serao
        # resolvidos pelo fluxo em aplicar_carta.
        # Retorna True para indicar que o encadeamento pode prosseguir.
        self.game.add_log(f'{origem.name}: combar_acao')
        return True

    def _resolver_impedir_acoes(self, efeito: Efeito,
                                 origem: CardInstance,
                                 jogador: PlayerState, alvo) -> bool:
        """Impede o alvo de tomar acoes.

        Usado por: Laughter of the Soul, Mangle, Amber Eyes,
        Whispering Campaign.
        Adiciona uma pendencia que impede acoes do alvo.
        Se params.restricao especificar um tipo (ex: 'pack_action'),
        so essa acao especifica e impedida.

        Suporta params:
        - condicao: str — 'alvo_gnosis_menor' para condicional
        - valor_comparacao: int — valor de Gnosis para comparar
        - tipo_acao: str — tipo de acao a impedir
        """
        condicao_param = efeito.params.get('condicao', '')
        valor_comp = int(efeito.params.get('valor_comparacao', 0))

        # Verifica condicao: alvo_gnosis_menor
        if condicao_param == 'alvo_gnosis_menor':
            if isinstance(alvo, CardInstance):
                gnosis_alvo = alvo.gnosis
                if gnosis_alvo >= valor_comp:
                    self.game.add_log(
                        f'{origem.name}: {alvo.name} tem Gnosis {gnosis_alvo}'
                        f' >= {valor_comp}, condicao nao atendida'
                    )
                    return False
            elif isinstance(alvo, list):
                alvos_validos = [c for c in alvo if c.gnosis < valor_comp]
                if not alvos_validos:
                    self.game.add_log(
                        f'{origem.name}: nenhum alvo com Gnosis < {valor_comp}'
                    )
                    return False
                alvo = alvos_validos

        restricao = efeito.params.get('restricao', 'nao_pode_agir')
        duracao = efeito.duracao or efeito.params.get('duracao', 'proximo_round')

        if isinstance(alvo, CardInstance):
            if restricao not in alvo.restricoes:
                alvo.restricoes.append(restricao)
                if duracao and duracao != 'permanente':
                    self.game.pendencias.append(PendenciaEfeito(
                        card_uid=id(alvo), atributo='restricao',
                        delta=0, valor_str=restricao,
                        duracao=duracao,
                        turno_aplicado=self.game.turn_number,
                        fase_aplicada=self.game.phase,
                    ))
                self.game.add_log(
                    f'{origem.name}: {alvo.name} impedido de agir '
                    f'({restricao}, {duracao})'
                )
            return True
        if isinstance(alvo, list):
            for c in alvo:
                if restricao not in c.restricoes:
                    c.restricoes.append(restricao)
                    if duracao and duracao != 'permanente':
                        self.game.pendencias.append(PendenciaEfeito(
                            card_uid=id(c), atributo='restricao',
                            delta=0, valor_str=restricao,
                            duracao=duracao,
                            turno_aplicado=self.game.turn_number,
                            fase_aplicada=self.game.phase,
                        ))
            self.game.add_log(
                f'{origem.name}: {len(alvo)} criatura(s) impedida(s) '
                f'({restricao}, {duracao})'
            )
            return True
        return False

    def _resolver_impedir_retirada(self, efeito: Efeito,
                                    origem: CardInstance,
                                    jogador: PlayerState, alvo) -> bool:
        """Impede o alvo de fugir/escapar/withdraw do combate.

        Usado por: Bar the Way, Ootani Oil Bane.
        """
        if isinstance(alvo, CardInstance):
            alvo.restricoes.append('nao_pode_escapar')
            self.game.add_log(
                f'{origem.name}: {alvo.name} impedido de escapar do combate'
            )
            return True
        # Se alvo for multiplo (packmates, lista)
        if isinstance(alvo, list):
            for c in alvo:
                c.restricoes.append('nao_pode_escapar')
            self.game.add_log(
                f'{origem.name}: {len(alvo)} criatura(s) impedida(s) de escapar'
            )
            return True
        return False

    def _resolver_cancelar_acao(self, efeito: Efeito,
                                 origem: CardInstance,
                                 jogador: PlayerState, alvo) -> bool:
        """Cancela uma Action card como interrupt.

        Usado por: Dominance.
        A carta cancelada vai para o descarte. A origem vai pro VP.
        """
        # Se tem alvo, cancela o alvo (marca como cancelado)
        if isinstance(alvo, CardInstance):
            alvo.restricoes.append('cancelado')
            # Move alvo pro descarte do dono
            dono_alvo = self._find_player(alvo)
            if dono_alvo:
                alvo.zone = Zone.DISCARD_COMBAT
                dono_alvo.discard_combat.append(alvo)
                self.game.add_log(
                    f'{origem.name}: cancelou {alvo.name}'
                )
        # Origem vai pro VP
        origem.zone = Zone.VICTORY_PILE
        jogador.victory_pile.append(origem)
        self.game.add_log(
            f'{origem.name} foi pro VP (cancelou action)'
        )
        return True

    def _resolver_ataque_imediato(self, efeito: Efeito,
                                   origem: CardInstance,
                                   jogador: PlayerState, alvo) -> bool:
        """Ataca imediatamente um participante apos combate.

        Usado por: Sense of the Prey.
        O usuario descarta este Gift e ataca outro participante.
        """
        if not isinstance(alvo, CardInstance):
            return False

        # Inicia combate imediato entre origem e alvo
        # Marca que este combate e sequencia de um anterior
        self.game.add_log(
            f'{origem.name}: ataque imediato contra {alvo.name}!'
        )

        # Aplica dano baseado na Rage da origem
        dano_base = origem.effective_rage
        alvo_dono = self._find_player(alvo)

        if alvo_dono:
            from rage_web.game_engine.combat_queue import apply_damage
            apply_damage(self.game, origem, alvo, dano_base)

        return True

    def _resolver_remover_do_combate(self, efeito: Efeito,
                                      origem: CardInstance,
                                      jogador: PlayerState, alvo) -> bool:
        """Remove criaturas do combate em andamento.

        Usado por: Whole Nine Yards (remove packmates).
        Spring the Trap (inverte: adiciona packmate ao combate).
        """
        if efeito.params.get('acao') == 'entrar':
            # Spring the Trap: packmate entra no combate
            if isinstance(alvo, CardInstance):
                alvo.restricoes.append('entrou_no_combate')
                self.game.add_log(
                    f'{origem.name}: {alvo.name} entrou no combate'
                )
            elif isinstance(alvo, list):
                for c in alvo:
                    c.restricoes.append('entrou_no_combate')
                self.game.add_log(
                    f'{origem.name}: {len(alvo)} packmate(s) entrou(ram)'
                    f' no combate'
                )
            return True

        # Whole Nine Yards: packmates removidos ate fim do combate
        if isinstance(alvo, list):
            for c in alvo:
                if hasattr(c, 'zone'):
                    c.zone = Zone.OUT_OF_PLAY
            self.game.add_log(
                f'{origem.name}: {len(alvo)} packmate(s) removido(s) '
                f'do combate'
            )
            return True
        if isinstance(alvo, CardInstance):
            alvo.zone = Zone.OUT_OF_PLAY
            self.game.add_log(
                f'{origem.name}: {alvo.name} removido do combate'
            )
            return True
        return False

    def _resolver_forcar_bluff(self, efeito: Efeito,
                                origem: CardInstance,
                                jogador: PlayerState, alvo) -> bool:
        """Proxima Combat Action do alvo e bluff.

        Usado por: Psychotic Hallucinations.
        A proxima acao declarada pelo alvo neste combate
        sera revelada como bluff (oposta ao declarado).
        """
        if isinstance(alvo, CardInstance):
            alvo.restricoes.append('proxima_acao_bluff')
            self.game.add_log(
                f'{origem.name}: {alvo.name} — proxima acao e bluff'
            )
            return True
        return False

    def _resolver_impedir_frenzy(self, efeito: Efeito,
                                  origem: CardInstance,
                                  jogador: PlayerState, alvo) -> bool:
        """Impede que qualquer jogador frenzia.

        Usado por: New Moon.
        Adiciona modificador global 'impede_frenzy' no jogo.
        """
        self.game.game_modifiers.add('impede_frenzy')
        if efeito.params.get('ragabash_gnosis_bonus'):
            # +1 Gnosis para Ragabash
            for p in self.game.players:
                for c in p.pack_home:
                    keywords = (c.keywords or '').lower()
                    if 'ragabash' in keywords:
                        c.gnosis += 1
                        self.game.add_log(
                            f'{c.name} +1 Gnosis (Ragabash - New Moon)'
                        )
        self.game.add_log(f'{origem.name}: ninguem pode frenzir (New Moon)')
        return True

    # ──────────────────────────────────────────────
    # OLHAR_TOPO_DECK
    # ──────────────────────────────────────────────
    def _resolver_olhar_topo_deck(self, efeito: Efeito,
                                   origem: CardInstance,
                                   jogador: PlayerState,
                                   alvo=None) -> bool:
        """Olha o topo do combat deck do alvo.

        Termite Mounds (780): olha topo 3 do combat deck de um oponente.
        """
        if alvo is None:
            alvo = self._resolver_alvo(efeito, origem, jogador)
        if not alvo:
            return False
        alvo_jogador = alvo if isinstance(alvo, PlayerState) else self._find_player(alvo)
        if not alvo_jogador:
            return False
        qtd = int(getattr(efeito, 'quantidade', 0) or 3)
        topo = alvo_jogador.deck_combat[:qtd]
        nomes = [c.name for c in topo]
        self.game.add_log(
            f'{origem.name}: topo {qtd} do combat deck de '
            f'{alvo_jogador.name}: {nomes}'
        )
        # Marca como usado para 1x/turno
        self.game.used_effects.append(id(origem))
        return True

    # ──────────────────────────────────────────────
    # DESCARTAR_MAO_COMBATE
    # ──────────────────────────────────────────────
    def _resolver_descartar_mao_combate(self, efeito: Efeito,
                                         origem: CardInstance,
                                         jogador: PlayerState,
                                         alvo=None) -> bool:
        """Alvo descarta toda a mao de combate.

        Dust Storm (1360): descarta combate hand.
        """
        if alvo is None:
            alvo = self._resolver_alvo(efeito, origem, jogador)
        if not alvo:
            return False
        alvo_jogador = alvo if isinstance(alvo, PlayerState) else self._find_player(alvo)
        if not alvo_jogador:
            return False
        mao = alvo_jogador.hand[:]
        descartadas = []
        for c in mao:
            c.zone = Zone.DISCARD_COMBAT
            alvo_jogador.discard_combat.append(c)
            descartadas.append(c.name)
        if mao:
            alvo_jogador.hand.clear()
        self.game.add_log(
            f'{origem.name}: {alvo_jogador.name} descartou '
            f'{len(descartadas)} cartas da mao de combate'
        )
        return True

    # ──────────────────────────────────────────────
    # REGISTRAR_TRIGGER_COMBATE
    # ──────────────────────────────────────────────
    def _resolver_registrar_trigger_combate(self, efeito: Efeito,
                                             origem: CardInstance,
                                             jogador: PlayerState,
                                             alvo=None) -> bool:
        """Registra um trigger que acontece durante o combate.

        Tzinzie (1348): no inicio do combate, nomeia uma Combat Action.
        Quando oponente revela essa acao, descarta uma carta da mao.
        """
        if efeito.params and efeito.params.get('trigger') == 'tzinzie':
            modifier = GameModifier(
                card_uid=id(origem),
                modifier='tzinzie_active'
            )
            self.game.game_modifiers.append(modifier)
            self.game.add_log(
                f'{origem.name}: Tzinzie ativo - nomeia Combat Action '
                f'no inicio do combate'
            )
        return True

    # -------------------------------------------------------------------
    # Resolvedores de Setup / Passivos / Trigger
    # -------------------------------------------------------------------

    def _resolver_equipar_inicial(self, efeito: Efeito,
                                    origem: CardInstance,
                                    jogador: PlayerState, alvo) -> bool:
        """Equipa uma carta no inicio do jogo (Grandfather Bannion).

        Remove copias do equipamento do sept deck e anexa aos
        personagens.
        params:
        - 'equipamento_nome': nome do equipamento
        - 'equipamento_id': card_id do equipamento
        - 'qtd': quantidade por personagem (padrao 1)
        """
        params = efeito.params or {}
        equip_nome = params.get('equipamento_nome', '.38 Special')
        equip_id_str = params.get('equipamento_id', '610')
        equip_id = int(equip_id_str) if equip_id_str else 610

        # Busca o equipamento no sept deck
        equip_encontrados = []
        restantes = []
        for carta in jogador.deck_sept:
            if carta.card_id == equip_id:
                equip_encontrados.append(carta)
            else:
                restantes.append(carta)

        if not equip_encontrados:
            self.game.add_log(
                f'{origem.name}: equipamento "{equip_nome}" (id={equip_id}) '
                f'nao encontrado no sept deck ({len(jogador.deck_sept)} cards)'
            )
            return False

        jogador.deck_sept = restantes

        # Equipa em todos os personagens (1 equipamento cada)
        num_personagens = len(jogador.pack_home)
        idx = 0
        for c in jogador.pack_home:
            if idx < len(equip_encontrados):
                eq = equip_encontrados[idx]
                c.attached_equipment.append(eq)
                idx += 1
                self.game.add_log(
                    f'  {c.name} equipado com {eq.name}'
                )

        self.game.add_log(
            f'{origem.name}: equipou {idx}x {equip_nome} na pack ({num_personagens} chars)'
        )
        return idx > 0

    def _resolver_filtrar_redraw(self, efeito: Efeito,
                                  origem: CardInstance,
                                  jogador: PlayerState, alvo) -> bool:
        """Filtro opcional no Redraw: descarta e compra 1 sept card.

        Usado por Buggerhead: permite descartar 1 sept card da mao
        e comprar 1 do sept deck, uma vez por turno.
        """
        params = efeito.params or {}
        qtd = params.get('quantidade', 1)
        zona = params.get('zona', 'deck_sept')
        usado_key = f'{origem.card_id}_usou_filtro_turno'

        # Verifica se ja usou no turno
        turno_atual = self.game.turn_number
        if getattr(jogador, usado_key, 0) >= turno_atual:
            return False

        # Nao pode filtrar se mao estiver vazia
        mao = jogador.hand
        if len(mao) < qtd:
            return False

        # Descarta N cartas
        descartadas = 0
        for _ in range(qtd):
            if mao:
                carta = mao.pop(0)
                jogador.discard_sept.append(carta)
                descartadas += 1

        # Compra N cartas
        deck = jogador.deck_sept if zona == 'deck_sept' else jogador.deck_combate
        compradas = 0
        for _ in range(qtd):
            if deck:
                carta = deck.pop(0)
                jogador.hand.append(carta)
                compradas += 1

        # Marca uso
        setattr(jogador, usado_key, turno_atual)

        self.game.add_log(
            f'{origem.name}: filtrou {descartadas}/{compradas} cartas (turno {turno_atual})'
        )
        return descartadas > 0 and compradas > 0

    def _resolver_comprar_quando_atacado(self, efeito: Efeito,
                                          origem: CardInstance,
                                          jogador: PlayerState, alvo) -> bool:
        """Compra combat cards quando este personagem e alvo de ataque.

        Usado por Mother Larissa.
        """
        params = efeito.params or {}
        qtd = params.get('quantidade', 2)
        usado_key = f'{origem.card_id}_comprou_ataque_turno'
        turno_atual = self.game.turn_number

        # So ativa se alvo for o proprio personagem
        if alvo is not origem:
            return False

        # Verifica se ja usou no turno
        if getattr(jogador, usado_key, 0) >= turno_atual:
            return False

        # Compra combat cards
        deck = jogador.deck_combate
        compradas = 0
        for _ in range(qtd):
            if deck:
                carta = deck.pop(0)
                jogador.hand_combate.append(carta)
                compradas += 1

        setattr(jogador, usado_key, turno_atual)

        self.game.add_log(
            f'{origem.name}: comprou {compradas} combat cards (alvo de ataque)'
        )
        return compradas > 0

    def _resolver_remover_do_descarte(self, efeito: Efeito,
                                       origem: CardInstance,
                                       jogador: PlayerState, alvo) -> bool:
        """Remove uma carta do descarte de combate.

        Usado por Quari Filth: durante Resource Phase, remove
        um combat card do descarte do jogo.
        """
        if not isinstance(alvo, dict):
            return False

        jogador_alvo = alvo.get('jogador')
        carta = alvo.get('carta')
        indice = alvo.get('indice')

        if not jogador_alvo or not carta or indice is None:
            return False

        if 0 <= indice < len(jogador_alvo.discard_combat):
            removida = jogador_alvo.discard_combat.pop(indice)
            self.game.add_log(
                f'{origem.name}: removeu {removida.name} do descarte de {jogador_alvo.name}'
            )
            return True

        return False

    def _resolver_buscar_copias(self, efeito: Efeito,
                                 origem: CardInstance,
                                 jogador: PlayerState, alvo) -> bool:
        """Busca copias desta carta no deck e as joga.

        Usado por Mosquito Swarm: busca todas as copias no sept deck
        e as coloca em jogo.
        """
        params = efeito.params or {}
        carta_id = params.get('carta_id') or str(getattr(origem, 'card_id', ''))
        nome_carta = params.get('nome') or getattr(origem, 'name', '')

        if not carta_id and not nome_carta:
            return False

        # Busca no sept deck
        encontradas = []
        restantes = []
        for carta in jogador.deck_sept:
            cid = str(getattr(carta, 'card_id', ''))
            cname = getattr(carta, 'name', '')
            if (carta_id and cid == carta_id) or (nome_carta and nome_carta.lower() in cname.lower()):
                encontradas.append(carta)
            else:
                restantes.append(carta)

        if not encontradas:
            self.game.add_log(
                f'{origem.name}: nenhuma copia encontrada no sept deck'
            )
            return False

        jogador.deck_sept = restantes

        # Poe em jogo (pack_home para aliados)
        for carta in encontradas:
            carta.zone = Zone.PACK_HOME
            jogador.pack_home.append(carta)

        self.game.add_log(
            f'{origem.name}: buscou e jogou {len(encontradas)} copias do sept deck'
        )
        return True

    def _resolver_auto_pack_attack(self, efeito: Efeito,
                                    origem: CardInstance,
                                    jogador: PlayerState, alvo) -> bool:
        """Registra auto pack attack/defend para esta carta.

        Usado por Mosquito Swarm: pode automaticamente pack attack
        e defend com outras copias.
        """
        # Inicializa dicionario de triggers se nao existir
        if not hasattr(self.game, '_auto_pack_triggers'):
            self.game._auto_pack_triggers = {}
        if not isinstance(getattr(self.game, '_auto_pack_triggers', None), dict):
            self.game._auto_pack_triggers = {}

        trigger_id = f'auto_pack_{origem.card_uid}_{origem.card_id}'
        self.game._auto_pack_triggers[trigger_id] = {
            'card_uid': origem.card_uid,
            'card_id': str(getattr(origem, 'card_id', '')),
            'player_id': jogador.id,
        }

        self.game.add_log(f'{origem.name}: registrado auto pack attack/defend')
        return True

    def _resolver_acao_extra_por_rodada(self, efeito: Efeito,
                                         origem: CardInstance,
                                         jogador: PlayerState, alvo) -> bool:
        """Permite uma acao de combate extra por rodada.

        Usado por Devilwhip (Rg2 ou menos) e Improvised Weapon (2 danos).
        params:
        - 'max_rage': rage maximo da acao extra
        - 'qtd_acoes': numero de acoes extras
        - 'unblockable': bool
        """
        params = efeito.params or {}
        max_rage = params.get('max_rage', 2)
        qtd = params.get('qtd_acoes', 1)
        usado_key = f'{origem.card_uid}_acao_extra_rodada'

        # Marca disponibilidade no personagem equipado
        rodada_atual = getattr(self.game, 'combat_round', 0)
        if getattr(origem, usado_key, -1) >= rodada_atual:
            return False

        setattr(origem, usado_key, rodada_atual)
        setattr(origem, 'acoes_extras_disponiveis',
                getattr(origem, 'acoes_extras_disponiveis', 0) + qtd)
        setattr(origem, 'acoes_extras_max_rage', max_rage)

        self.game.add_log(
            f'{origem.name}: +{qtd} acao(es) extra(s) (Rg<={max_rage})'
        )
        return True

    def _resolver_imune_combate_rage(self, efeito: Efeito,
                                      origem: CardInstance,
                                      jogador: PlayerState, alvo) -> bool:
        """Adiciona imunidade a combat actions de certo Rage.

        Usado por Dhul Fiqar: imune a Rg1 ou menos.
        params:
        - 'max_rage': rage maximo para imunidade
        """
        params = efeito.params or {}
        max_rage = params.get('max_rage', 1)

        # Adiciona modifier de reducao de dano
        modifier_id = f'imune_rg{max_rage}_{origem.card_uid}'
        modifier = GameModifier(
            modifier_id=modifier_id,
            attribute='damage_reduction',
            value=999,  # Imune
            condition=f'combat_action_rage<={max_rage}',
            duration='permanente_ate_cancelar',
            source=origem.name,
        )
        # So adiciona se ainda nao tem
        ja_existe = False
        for m in jogador.modifiers:
            if m.modifier_id == modifier_id:
                ja_existe = True
                break
        if not ja_existe:
            jogador.modifiers.append(modifier)

        # Checa condicao de bônus por tribo
        if params.get('bonus_tribo'):
            tribo = params.get('bonus_tribo', '').lower()
            raca = getattr(origem, 'keyword', '')
            if tribo and tribo in raca.lower():
                modifier_bonus = GameModifier(
                    modifier_id=f'{modifier_id}_bonus_rage',
                    attribute='rage',
                    value=params.get('bonus_rage', 1),
                    duration='permanente_ate_cancelar',
                    source=f'{origem.name}: {tribo}',
                )
                jogador.modifiers.append(modifier_bonus)
                self.game.add_log(
                    f'{origem.name}: +{params.get("bonus_rage", 1)} Rage '
                    f'({tribo})'
                )

        self.game.add_log(
            f'{origem.name}: imune a combat actions Rg<={max_rage}'
        )
        return True

    def _resolver_modificar_atributo_passivo(self, efeito: Efeito,
                                              origem: CardInstance,
                                              jogador: PlayerState,
                                              alvo) -> bool:
        """Adiciona buff passivo persistente.

        Usado por John Hidden-Moon: packmates +1 Rage em pack attacks.
        params:
        - 'atributos': lista de atributos
        - 'valor': valor do bonus
        - 'condicao': condicao para ativar ('pack_attack', etc)
        - 'alvos': 'packmates' (padrao) ou 'self'
        """
        params = efeito.params or {}
        atributos = params.get('atributos', ['rage'])
        valor = params.get('valor', 1)
        condicao = params.get('condicao', 'pack_attack')
        alvos = params.get('alvos', 'packmates')
        duracao = 'permanente_ate_cancelar'

        modifier_id = f'passivo_{condicao}_{origem.card_uid}'

        # Verifica se ja existe
        for m in jogador.modifiers:
            if m.modifier_id == modifier_id:
                return True

        modifier = GameModifier(
            modifier_id=modifier_id,
            attribute=','.join(atributos),
            value=valor,
            condition=condicao,
            duration=duracao,
            source=f'{origem.name}: {params.get("descricao", "buff passivo")}',
        )
        jogador.modifiers.append(modifier)

        self.game.add_log(
            f'{origem.name}: buff passivo {atributos}+{valor} ({condicao})'
        )
        return True

    def _resolver_modificar_gauntlet(self, efeito: Efeito,
                                      origem: CardInstance,
                                      jogador: PlayerState, alvo) -> bool:
        """Modifica o valor do Gauntlet.

        Usado por Shadow-Weaver: pack step sideways como se
        fosse Gauntlet 1 Caern.
        """
        params = efeito.params or {}
        valor = params.get('valor', 1)
        duracao = params.get('duracao', 'permanente_ate_cancelar')

        modifier_id = f'gauntlet_{origem.card_uid}'

        for m in jogador.modifiers:
            if m.modifier_id == modifier_id:
                return True

        modifier = GameModifier(
            modifier_id=modifier_id,
            attribute='gauntlet',
            value=valor,
            duration=duracao,
            source=origem.name,
        )
        jogador.modifiers.append(modifier)

        self.game.add_log(
            f'{origem.name}: Gauntlet ajustado para {valor}'
        )
        return True

    # -------------------------------------------------------------------
    # Resolvedores de Efeitos de Moot (Juntas)
    # -------------------------------------------------------------------

    def _resolver_moot_remover_personagem(self, efeito: Efeito,
                                            origem: CardInstance,
                                            jogador: PlayerState,
                                            alvo) -> bool:
        """Remove um personagem do jogo (Skindancer, Winter Wolf)."""
        if not isinstance(alvo, CardInstance):
            return False
        renown_min = efeito.params.get('renown_min', 0)
        renown_max = efeito.params.get('renown_max', 99)
        if not (renown_min <= alvo.renown <= renown_max):
            self.game.add_log(
                f'{alvo.name} (Ren {alvo.renown}) nao atende ao '
                f'requisito de Renome ({renown_min}-{renown_max})'
            )
            return False
        dono_alvo = self._find_player(alvo.owner_id)
        if dono_alvo:
            descartar_anexos(alvo, dono_alvo)
            for zone_list in (dono_alvo.pack_home, dono_alvo.hunting_grounds,
                              dono_alvo.umbra):
                if alvo in zone_list:
                    zone_list.remove(alvo)
                    break
            dono_alvo.discard_sept.append(alvo)
            alvo.zone = Zone.DISCARD_SEPT
            self.game.add_log(
                f'[Moot] {alvo.name} foi removido do jogo!'
            )
            vp = efeito.params.get('vp', 0)
            if efeito.params.get('vp_por_renown', False):
                vp += alvo.renown
            if vp > 0:
                jogador.victory_points += vp
                self.game.add_log(
                    f'{jogador.name} ganhou {vp} VP ({jogador.victory_points})'
                )
            return True
        return False

    def _resolver_moot_ganhar_vp(self, efeito: Efeito, origem: CardInstance,
                                  jogador: PlayerState, alvo) -> bool:
        """Ganha VP por Moot aprovado (Silver Record, Legendary Leadership)."""
        vp = efeito.params.get('vp', 1)
        vp_por_char = efeito.params.get('vp_por_personagem', 0)
        if vp_por_char > 0:
            num_chars = len([c for c in jogador.pack_home if c.health_current > 0])
            vp += vp_por_char * num_chars
        jogador.victory_points += vp
        self.game.add_log(
            f'[Moot] {jogador.name} ganhou {vp} VP ({jogador.victory_points})'
        )
        return True

    def _resolver_moot_restricao_global(self, efeito: Efeito,
                                         origem: CardInstance,
                                         jogador: PlayerState,
                                         alvo) -> bool:
        """Aplica restricao global (Tribal War, Litany's Guidance)."""
        restricao = efeito.params.get('restricao', 'moot_global')
        descricao = efeito.params.get('descricao', 'Efeito de Moot ativo')
        modifier = GameModifier(
            card_uid=id(origem),
            modifier=restricao,
            ativo=True,
        )
        self.game.game_modifiers.append(modifier)
        self.game.add_log(f'[Moot] {descricao}')
        return True

    def _resolver_moot_rebaixar_forma(self, efeito: Efeito,
                                       origem: CardInstance,
                                       jogador: PlayerState,
                                       alvo) -> bool:
        """Reverte personagem a forma breed (The Stolen Wolf)."""
        if not isinstance(alvo, CardInstance):
            return False
        forma = efeito.params.get('forma', 'breed')
        forma_nome = {'breed': 'Breed', 'lupus': 'Lupus', 'homid': 'Homid'}.get(forma, forma)
        restricao = f'forma_forcada_{forma}'
        if restricao not in alvo.restricoes:
            alvo.restricoes.append(restricao)
        self.game.add_log(f'[Moot] {alvo.name} revertido a forma {forma_nome}!')
        return True

    def _resolver_moot_construir_caern(self, efeito: Efeito,
                                        origem: CardInstance,
                                        jogador: PlayerState,
                                        alvo) -> bool:
        """Constroi um Caern (Caern Building)."""
        gnosis = efeito.params.get('gnosis', 1)
        caern = CardInstance(
            card_id=0, name='Caern (Moot)', card_type='Caern',
            owner_id=jogador.id, controller_id=jogador.id,
            zone=Zone.PACK_HOME,
            rage=0, gnosis=gnosis, health=gnosis,
            health_current=gnosis, renown=0,
        )
        jogador.pack_home.append(caern)
        self.game.add_log(f'[Moot] Caern construido! (Gn {gnosis})')
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
        'fase_umbra_mokole':
            lambda: _condicao_fase_umbra_mokole(game, jogador),
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


def _condicao_fase_umbra_mokole(game: GameState,
                                 jogador: 'PlayerState') -> bool:
    """Verifica se a fase atual e Umbra e ha personagem Mokole no pack."""
    if game.phase != 'umbra':
        return False
    for c in jogador.pack_home:
        keywords = (c.keywords or '').lower()
        if 'mokole' in keywords and 'Character' in (c.card_type or ''):
            return True
    return False


def _validar_gauntlet_para_carta(game: GameState, jogador: 'PlayerState',
                                 modelo: 'ModeloCarta',
                                 card_origem: Optional['CardInstance'] = None,
                                 alvo: Optional['CardInstance'] = None
                                 ) -> bool:
    """Valida se uma carta pode cruzar o Gauntlet para seu alvo.

    Regra (5 - Umbra):
    - Events (incluindo Totems) afetam ambos os lados do Gauntlet.
    - Caerns e Territórios existem em ambos os lados.
    - Actions, Gifts, Past Lives, Quests, Rites, Combat Actions
      e special abilities NAO podem cruzar o Gauntlet.
    - Exceções: Caerns/habilidades que explicitamente permitem cruzar
      (ex: Lake Nasser Wallow, Haunter).

    Se o alvo está no mesmo lado do Gauntlet que o jogador,
    não há cruzamento e a carta pode ser usada normalmente.

    Args:
        game: Estado da partida.
        jogador: Jogador usando a carta.
        modelo: Modelo da carta sendo usada.
        card_origem: Instancia da carta que esta usando o Gift.
        alvo: A criatura alvo da carta (se conhecido).

    Returns:
        True se a carta pode ser usada (Gauntlet permitido ou nao aplicavel).
    """
    tipo = (modelo.tipo or '').lower()

    # Events e Totems afetam ambos os lados do Gauntlet (regra 5)
    if tipo in ('event', 'event - totem', 'totem'):
        return True

    # Caerns e Territórios existem em ambos os lados (regra 5)
    if tipo in ('caern', 'territory', 'realm'):
        return True

    # Se o alvo está no mesmo lado do Gauntlet, não há cruzamento
    if alvo is not None:
        if _mesmo_lado_gauntlet_para_carta(game, jogador, alvo):
            return True

    # Verifica se ha permissao especial para cruzar o Gauntlet
    if _gauntlet_permite_cruzar(game, jogador, modelo, card_origem):
        return True

    # Cartas que nao podem cruzar o Gauntlet:
    # Actions, Gifts, Past Lives, Quests, Rites, Combat Actions
    tipos_que_nao_cruzam = {
        'action', 'gift', 'past life', 'quest', 'rite',
        'combat action', 'combat event',
    }
    if tipo in tipos_que_nao_cruzam:
        return False

    # Outros tipos (Characters, Equipment, etc.) - permitem
    return True


def _mesmo_lado_gauntlet_para_carta(game: GameState, jogador: 'PlayerState',
                                    alvo: 'CardInstance') -> bool:
    """Verifica se o jogador e o alvo estão no mesmo lado do Gauntlet.

    - Pack Home = mundo fisico
    - Umbra = Umbra
    - Hunting Grounds / Caern / Territory / Spirit = ambos os lados
    """
    # Determina o lado do jogador (baseado na zona dos seus personagens)
    jogador_umbra = any(c.zone == Zone.UMBRA for c in jogador.umbra)
    jogador_fisico = any(c.zone == Zone.PACK_HOME for c in jogador.pack_home)

    # Determina o lado do alvo
    if alvo.zone == Zone.UMBRA:
        alvo_umbra = True
        alvo_fisico = False
    elif alvo.zone == Zone.PACK_HOME:
        alvo_umbra = False
        alvo_fisico = True
    else:
        # Hunting Grounds, OUT_OF_PLAY, etc. = ambos os lados
        alvo_umbra = True
        alvo_fisico = True

    # Se ambos estão no mesmo lado (ou um está em ambos), OK
    if jogador_umbra and alvo_umbra:
        return True
    if jogador_fisico and alvo_fisico:
        return True
    if not jogador_umbra and not jogador_fisico:
        # Jogador sem personagens em jogo - permite
        return True
    return False


def _gauntlet_permite_cruzar(game: GameState, jogador: 'PlayerState',
                             modelo: 'ModeloCarta',
                             card_origem: Optional['CardInstance'] = None
                             ) -> bool:
    """Verifica se ha permissao especial para cruzar o Gauntlet.

    - Lake Nasser Wallow: Rites/Gifts cruzam Gauntlet globalmente.
    - Haunter: Gifts com Gnosis <= 4 podem cruzar.
    - Outros Caerns com habilidade de cruzar.
    """
    tipo = (modelo.tipo or '').lower() if modelo else ''

    # Verifica modificador global (ex: Lake Nasser Wallow)
    if game.has_modifier('rites_gifts_cross_gauntlet'):
        if tipo in ('rite', 'gift'):
            return True

    # Verifica se o jogador tem Caern que permite cruzar Gauntlet
    caerns = jogador.caerns_no_hunting_grounds if hasattr(jogador, 'caerns_no_hunting_grounds') else []
    for caern in caerns:
        texto = (caern.text or '').lower()
        if 'gauntlet' in texto and 'cross' in texto:
            return True

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

    return False


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

    # NOTA: A validacao de Gauntlet e feita durante a aplicacao
    # de cada efeito (em aplicar_efeito), quando o alvo e conhecido.
    # Isso permite verificar se o alvo esta no mesmo lado do Gauntlet.

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

        # Verifica condicao_estado para efeitos condicionais
        condicao_atendida = True
        if efeito.condicao_estado and resultado:
            if efeito.condicao_estado == 'alvo_destruido':
                # Verifica se o alvo foi destruido (health <= 0 ou foi pro VP)
                ultimo_alvo = getattr(resolvedor, '_ultimo_alvo', None)
                if ultimo_alvo is not None:
                    if hasattr(ultimo_alvo, 'health_current'):
                        condicao_atendida = ultimo_alvo.health_current <= 0
                    if hasattr(ultimo_alvo, 'zone'):
                        condicao_atendida = condicao_atendida or (
                            ultimo_alvo.zone in (Zone.VICTORY_PILE, Zone.DISCARD_COMBAT, Zone.DISCARD_SEPT)
                        )
                else:
                    condicao_atendida = False
            elif efeito.condicao_estado == 'se_desviado':
                # Verifica se o ataque foi desviado (por marcacao no resolvedor)
                condicao_atendida = getattr(resolvedor, '_ataque_desviado', False)

        if resultado and efeito.se_sucesso and condicao_atendida:
            for sub in efeito.se_sucesso:
                resolvedor.aplicar_efeito(sub, origem, jogador)
        elif not resultado and efeito.se_fracasso:
            for sub in efeito.se_fracasso:
                resolvedor.aplicar_efeito(sub, origem, jogador)

    # Move a carta para o descarte apropriado apos uso (se ainda
    # nao foi movida por um efeito, ex: equipar)
    if card_origem and card_origem.zone == Zone.HAND:
        ct = (modelo.tipo or '').lower()

        # Permanent Gifts permanecem em jogo
        if 'gift' in ct:
            from rage_web.game_engine.rules import gift_eh_permanente
            if gift_eh_permanente(card_origem):
                card_origem.zone = Zone.PACK_HOME
                jogador.pack_home.append(card_origem)
                game.add_log(f'{card_origem.name}: Gift permanente em jogo')
            else:
                # Gift temporario: descarta
                card_origem.zone = Zone.DISCARD_SEPT
                jogador.discard_sept.append(card_origem)
        elif 'combat action' in ct or 'combat event' in ct:
            card_origem.zone = Zone.DISCARD_COMBAT
            jogador.discard_combat.append(card_origem)
        elif 'event' in ct:
            # Events permanecem em jogo (nao sao descartados)
            # Regra: Duration Variable, Cannot be discarded voluntarily
            card_origem.zone = Zone.PACK_HOME
            jogador.pack_home.append(card_origem)
            game.add_log(f'{card_origem.name}: Evento em jogo')
        elif 'equipment' not in ct:
            # Action, Quest: descarte de sept
            card_origem.zone = Zone.DISCARD_SEPT
            jogador.discard_sept.append(card_origem)
        # Equipment: fica equipado (resolvido por _resolver_equipar)

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
            condicao_uso=m.get('condicao_uso'),
        ))
    return ModeloCarta(
        id=dados['id'],
        nome=dados['nome'],
        tipo=dados.get('tipo', 'event'),
        modos=modos,
    )


def _efeito_from_json(e: dict) -> Efeito:
    """Converte um dict de efeito JSON para Efeito (recursivo)."""
    # Campos conhecidos do Efeito
    campos_conhecidos = {
        'tipo', 'condicao_alvo', 'alvo', 'quantidade', 'duracao',
        'se_sucesso', 'se_fracasso', 'condicao_estado',
    }
    # Se o JSON ja tem um campo 'params', usa ele diretamente
    # E campos extras de primeiro nivel tambem vao para params
    params_json = e.get('params', {}) or {}
    if isinstance(params_json, dict):
        params = dict(params_json)
    else:
        params = {}
    # Campos extras de primeiro nivel viram params
    for k, v in e.items():
        if k not in campos_conhecidos and k not in ('tipo', 'params'):
            params[k] = v
    # Converte duracao para string se vier como int do JSON
    duracao_val = e.get('duracao', '')
    if not isinstance(duracao_val, str):
        duracao_val = str(duracao_val) if duracao_val else ''
    return Efeito(
        tipo=e['tipo'],
        condicao=e.get('condicao_alvo'),
        alvo=e.get('alvo'),
        quantidade=e.get('quantidade', 0),
        duracao=duracao_val,
        se_sucesso=[_efeito_from_json(s) for s in e.get('se_sucesso', [])],
        se_fracasso=[_efeito_from_json(f) for f in e.get('se_fracasso', [])],
        condicao_estado=e.get('condicao_estado'),
        params=params,
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
