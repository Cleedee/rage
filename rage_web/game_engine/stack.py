"""Pilha de resolucao (stack) e sistema de prioridade.

Fluxo:
1. Jogador anuncia uma carta -> vai para a pilha
2. Prioridade passa para o oponente (pode responder)
3. Quando ambos passam consecutivamente, o topo da pilha resolve
4. Apos resolucao, prioridade volta ao jogador ativo

Uso:
    stack = Pilha()
    stack.push(acaõ)
    stack.push(resposta)
    stack.resolver_proximo()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from rage_web.game_engine.state import GameState, PlayerState


class TipoItemPilha(str, Enum):
    """Tipos de item que podem ir na pilha."""
    CARTA = 'carta'                  # Uma carta sendo jogada
    HABILIDADE = 'habilidade'       # Habilidade ativada/desencadeada
    ATAQUE = 'ataque'               # Declaracao de ataque
    ACOES_COMBATE = 'acoes_combate' # Acoes de combate (strike/block/etc)
    EFEITO_CONTINUO = 'efeito'      # Efeito continuo entrando/atualizando
    ESPECIAL = 'especial'           # Acoes especiais


@dataclass
class ItemPilha:
    """Um item na pilha de resolucao."""
    tipo: TipoItemPilha
    descricao: str
    jogador_id: str
    carta_id: Optional[str] = None         # ID da carta (se aplicavel)
    modelo_id: Optional[str] = None        # ID do modelo de efeitos
    modo_idx: Optional[int] = None          # Modo escolhido (para modais)
    dados: dict[str, Any] = field(default_factory=dict)

    # Callback de resolucao (chamado quando o item resolve)
    resolver: Optional[Callable[[GameState], list[str]]] = None

    # Callback de anulacao (chamado se o item for anulado)
    ao_anular: Optional[Callable[[GameState], None]] = None

    # Se ja passou pela escolha de modo
    modo_escolhido: bool = False

    def __post_init__(self):
        if isinstance(self.tipo, str):
            self.tipo = TipoItemPilha(self.tipo)

    def esta_esperando_modo(self) -> bool:
        """True se o item e uma carta modal que ainda nao escolheu modo."""
        return (self.tipo == TipoItemPilha.CARTA
                and self.modelo_id is not None
                and self.modo_idx is None
                and not self.modo_escolhido)


class PrioridadeStatus(str, Enum):
    """Status do sistema de prioridade."""
    ESPERANDO_ACAO = 'esperando_acao'       # Jogador ativo decide o que fazer
    ESPERANDO_RESPOSTA = 'esperando_resposta'  # Oponente pode responder
    RESOLVENDO = 'resolvendo'                # Resolvendo o topo da pilha
    ESPERANDO_MODO = 'esperando_modo'        # Jogador precisa escolher modo
    FINALIZADO = 'finalizado'                # Fase de acao encerrada


@dataclass
class Pilha:
    """Pilha de resolucao com controle de prioridade.

    A pilha segue o modelo LIFO (Last In, First Out):
    itens adicionados depois resolvem primeiro.
    """
    itens: list[ItemPilha] = field(default_factory=list)
    prioridade: PrioridadeStatus = PrioridadeStatus.ESPERANDO_ACAO
    passos_consecutivos: int = 0  # Quantos passaram seguidos
    jogador_ativo_id: str = ''
    prompt_atual: Optional[dict] = None  # Prompt pendente (ex: escolha modo)

    @property
    def topo(self) -> Optional[ItemPilha]:
        """Retorna o item no topo da pilha, sem remover."""
        if self.itens:
            return self.itens[-1]
        return None

    @property
    def vazia(self) -> bool:
        return len(self.itens) == 0

    @property
    def tamanho(self) -> int:
        return len(self.itens)

    def empilhar(self, item: ItemPilha) -> None:
        """Adiciona um item no topo da pilha.

        A prioridade e resetada: o oponente do jogador que
        adicionou o item ganha prioridade para responder.
        """
        self.itens.append(item)
        self.passos_consecutivos = 0
        self.prioridade = PrioridadeStatus.ESPERANDO_RESPOSTA

    def passar(self, game: GameState) -> str:
        """Jogador atual passa a prioridade.

        Returns:
            'resolve' se ambos passaram e o topo deve resolver.
            'espera' se o outro jogador ganha prioridade.
            'fim' se a pilha esta vazia e ambos passaram.
        """
        self.passos_consecutivos += 1

        if self.passos_consecutivos >= 2:
            # Ambos passaram consecutivamente
            if not self.vazia:
                return 'resolve'
            else:
                self.prioridade = PrioridadeStatus.FINALIZADO
                return 'fim'

        # Troca prioridade para o outro jogador
        if self.prioridade == PrioridadeStatus.ESPERANDO_ACAO:
            self.prioridade = PrioridadeStatus.ESPERANDO_RESPOSTA
        elif self.prioridade == PrioridadeStatus.ESPERANDO_RESPOSTA:
            self.prioridade = PrioridadeStatus.ESPERANDO_ACAO

        return 'espera'

    def resolver_topo(self, game: GameState) -> list[str]:
        """Resolve o item no topo da pilha.

        Se o item e uma carta modal sem modo escolhido,
        retorna um prompt em vez de resolver.

        Returns:
            Lista de mensagens de log da resolucao.
        """
        if not self.itens:
            return ['Pilha vazia']

        item = self.itens[-1]

        # Carta modal sem modo escolhido?
        if item.esta_esperando_modo():
            self.prioridade = PrioridadeStatus.ESPERANDO_MODO
            self.prompt_atual = self._criar_prompt_modo(item)
            return [f'AGUARDANDO: escolha modo para {item.descricao}']

        # Executa o callback de resolucao
        if item.resolver:
            logs = item.resolver(game)
        else:
            logs = [f'Resolvendo: {item.descricao}']

        # Remove da pilha
        self.itens.pop()
        self.passos_consecutivos = 0
        self.prioridade = PrioridadeStatus.ESPERANDO_ACAO
        self.prompt_atual = None

        return logs

    def anular_topo(self, game: GameState) -> list[str]:
        """Anula o item no topo da pilha (sem resolver)."""
        if not self.itens:
            return ['Pilha vazia']

        item = self.itens.pop()
        if item.ao_anular:
            item.ao_anular(game)

        self.passos_consecutivos = 0
        self.prioridade = PrioridadeStatus.ESPERANDO_ACAO
        return [f'{item.descricao} foi anulado']

    def escolher_modo(self, modo_idx: int) -> Optional[str]:
        """Define o modo escolhido para o item no topo.

        So funciona se o item esta esperando modo.

        Args:
            modo_idx: Indice do modo escolhido.

        Returns:
            Mensagem de erro ou None se sucesso.
        """
        if self.prioridade != PrioridadeStatus.ESPERANDO_MODO:
            return 'Nao esta aguardando escolha de modo'

        item = self.topo
        if not item or not item.esta_esperando_modo():
            return 'Nenhuma carta aguardando modo'

        item.modo_idx = modo_idx
        item.modo_escolhido = True
        self.prioridade = PrioridadeStatus.ESPERANDO_ACAO
        self.prompt_atual = None
        return None

    def reiniciar(self):
        """Reseta a pilha (fim de turno/fase)."""
        self.itens.clear()
        self.prioridade = PrioridadeStatus.ESPERANDO_ACAO
        self.passos_consecutivos = 0
        self.prompt_atual = None

    def _criar_prompt_modo(self, item: ItemPilha) -> dict:
        """Cria um prompt de escolha de modo para uma carta."""
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        modelo = CARTAS_EXEMPLO.get(item.modelo_id or '')
        if not modelo:
            return {'erro': 'Modelo nao encontrado'}

        return {
            'tipo': 'escolher_modo',
            'carta': item.descricao,
            'jogador_id': item.jogador_id,
            'modos': [
                {
                    'indice': i,
                    'descricao': m.descricao,
                    'efeitos': [e.tipo for e in m.efeitos],
                }
                for i, m in enumerate(modelo.modos)
            ],
        }


# -----------------------------------------------------------------------
# Acoes de alto nivel
# -----------------------------------------------------------------------

def anunciar_carta(game: GameState, jogador_id: str, carta_id: str,
                   modelo_id: str, modo_idx: Optional[int] = None) -> ItemPilha:
    """Anuncia (coloca na pilha) uma carta sendo jogada.

    O item na pilha conterá os dados para resolver quando chegar
    sua vez. Se a carta tiver modos.length > 1 e modo_idx nao
    for informado, a resolucao pausara para escolha.

    Args:
        game: Estado da partida.
        jogador_id: ID do jogador que esta jogando a carta.
        carta_id: ID da instancia da carta (CardInstance.card_id).
        modelo_id: ID do modelo de efeitos.
        modo_idx: Modo escolhido (None se precisa escolher).

    Returns:
        O ItemPilha criado.
    """
    # Procura a carta na mao do jogador
    jogador = None
    for p in game.players:
        if p.id == jogador_id:
            jogador = p
            break

    nome_carta = carta_id
    for c in jogador.hand:
        if str(c.card_id) == carta_id or c.modelo_id == modelo_id:
            nome_carta = c.name
            break

    def _resolver(game: GameState) -> list[str]:
        """Callback de resolucao da carta."""
        from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta
        modelo = CARTAS_EXEMPLO.get(modelo_id)
        if not modelo:
            return [f'Modelo {modelo_id} nao encontrado']

        modo = modo_idx if item.modo_escolhido else 0
        logs = aplicar_carta(game, modelo, jogador_id, modo_idx=modo or 0)
        game.add_log(f'{jogador.name} usou {nome_carta} (pilha)')
        return logs

    item = ItemPilha(
        tipo=TipoItemPilha.CARTA,
        descricao=nome_carta,
        jogador_id=jogador_id,
        carta_id=carta_id,
        modelo_id=modelo_id,
        modo_idx=modo_idx,
        modo_escolhido=modo_idx is not None or False,
        resolver=_resolver,
    )

    game.pilha.empilhar(item)
    game.add_log(f'{jogador.name} anunciou {nome_carta}')
    return item


def obter_acoes_validas(game: GameState, jogador_id: str) -> dict:
    """Retorna as acoes que o jogador pode realizar no momento.

    Considera o estado da pilha e da prioridade.
    """
    pilha = game.pilha
    acoes = {
        'jogador_id': jogador_id,
        'prioridade': pilha.prioridade.value,
        'pilha_tamanho': pilha.tamanho,
        'acoes_disponiveis': [],
        'prompt': pilha.prompt_atual,
    }

    if pilha.prioridade == PrioridadeStatus.ESPERANDO_MODO:
        acoes['acoes_disponiveis'].append('escolher_modo')
        return acoes

    if pilha.prioridade == PrioridadeStatus.ESPERANDO_ACAO:
        # Jogador ativo pode jogar cartas ou passar
        acoes['acoes_disponiveis'].extend([
            'jogar_carta',
            'passar',
        ])
        if not pilha.vazia:
            acoes['acoes_disponiveis'].append('passar')

    elif pilha.prioridade == PrioridadeStatus.ESPERANDO_RESPOSTA:
        # Oponente pode responder ou passar
        acoes['acoes_disponiveis'].extend([
            'responder',
            'passar',
        ])

    if pilha.prioridade in (PrioridadeStatus.ESPERANDO_ACAO,
                             PrioridadeStatus.ESPERANDO_RESPOSTA):
        acoes['acoes_disponiveis'].extend([
            'ver_pilha',
            'status',
        ])

    return acoes
