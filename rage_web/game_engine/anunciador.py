"""Sistema de anuncio e resolucao de efeitos (Rage CCG).

Diferente de Magic, Rage nao tem pilha no sentido LIFO.
O fluxo e:

1. Jogador anuncia um efeito ofensivo (abertamente)
2. Os outros podem responder jogando cartas no proprio pack
3. Cartas de anulacao interrompem e cancelam o efeito
4. Se nao anulado, o efeito resolve

Regras (capitulo 3):
- Open Play: anuncia, espera atencao, outros respondem no proprio pack, resolve
- Cancelamento: interrompe o timing, pode cancelar cancelamento
- Multiplos efeitos: um por jogador, resolve em ordem de anuncio
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from rage_web.game_engine.state import GameState


class EstadoAnuncio(str, Enum):
    """Estado do sistema de anuncio."""
    LIVRE = 'livre'                    # Nenhum efeito pendente
    ANUNCIADO = 'anunciado'            # Efeito anunciado,aguardando resposta
    RESPONDENDO = 'respondendo'        # Alguem esta respondendo
    RESOLVENDO = 'resolvendo'          # Resolvendo o efeito
    AGUARDANDO_MODO = 'aguardando_modo' # Precisa escolher modo


@dataclass
class EfeitoAnunciado:
    """Um efeito que foi anunciado e esta aguardando resolucao.

    Diferente de uma pilha LIFO, efeitos em Rage sao simplesmente
    anunciados e resolvidos na ordem. O cancelamento interrompe
    o timing e anula o efeito alvo.
    """
    id: str
    descricao: str
    jogador_id: str
    carta_id: Optional[str] = None
    modelo_id: Optional[str] = None
    modo_idx: Optional[int] = None
    modo_escolhido: bool = False
    anulado: bool = False

    # Callback de resolucao
    resolver: Optional[Callable[[GameState], list[str]]] = None

    @property
    def aguardando_modo(self) -> bool:
        """True se e uma carta modal que ainda nao escolheu modo."""
        return (self.modelo_id is not None
                and self.modo_idx is None
                and not self.modo_escolhido)


@dataclass
class Anunciador:
    """Gerenciador de anuncios e resolucao.

    Em Rage, nao ha pilha LIFO. Efeitos sao anunciados,
    outros podem responder, e entao resolvem. Cancelamento
    interrompe o fluxo normal.
    """
    estado: EstadoAnuncio = EstadoAnuncio.LIVRE
    anuncio_atual: Optional[EfeitoAnunciado] = None
    prompt_atual: Optional[dict] = None
    ultimos_logs: list[str] = field(default_factory=list)

    @property
    def tem_anuncio_ativo(self) -> bool:
        return self.anuncio_atual is not None

    def anunciar(self, efeito: EfeitoAnunciado) -> bool:
        """Anuncia um efeito.

        O efeito fica pendente ate ser resolvido ou anulado.
        Outro jogador pode responder (jogar cartas no proprio pack)
        ou anular.

        Returns:
            True se o anuncio foi aceito.
        """
        if self.tem_anuncio_ativo:
            return False  # Ja tem um anuncio pendente
        self.anuncio_atual = efeito
        self.estado = EstadoAnuncio.ANUNCIADO
        return True

    def responder(self, game: GameState, efeito_resposta: EfeitoAnunciado
                  ) -> Optional[str]:
        """Outro jogador responde ao anuncio.

        Em Rage, a resposta so pode afetar o proprio pack do
        jogador que responde (nao pode anular diretamente a
        menos que seja uma carta de cancelamento).

        Se a resposta for uma anulacao, o efeito original e cancelado.

        Returns:
            Mensagem de erro ou None se sucesso.
        """
        if not self.tem_anuncio_ativo:
            return 'Nenhum efeito anunciado para responder'

        # No Rage, a resposta e simplesmente adicionada como
        # um novo efeito que resolve antes do original?
        # Nao exatamente. O efeito original fica esperando,
        # a resposta e processada, e depois o original resolve.
        # Para simplificar: a resposta vira o novo anuncio,
        # o original e resolvido depois.

        # Na verdade, em Rage, a resposta e simultanea - voce
        # joga cartas no seu pack em resposta ao anuncio.
        # Essas cartas resolvem imediatamente (nao vao pra pilha).

        # Simplificacao: apenas registramos que houve resposta
        self.estado = EstadoAnuncio.RESPONDENDO
        self.ultimos_logs.append(
            f'{efeito_resposta.jogador_id} respondeu a '
            f'{self.anuncio_atual.descricao}'
        )
        return None

    def anular(self, game: GameState, anulador_id: str) -> bool:
        """Anula o efeito anunciado atual.

        Cartas de cancelamento interrompem o timing normal.
        O efeito anulado nunca resolve.
        Pode-se cancelar um cancelamento.

        Returns:
            True se foi anulado.
        """
        if not self.tem_anuncio_ativo:
            return False

        self.anuncio_atual.anulado = True
        self.ultimos_logs.append(
            f'{anulador_id} anulou {self.anuncio_atual.descricao}'
        )
        self._limpar()
        return True

    def resolver(self, game: GameState) -> list[str]:
        """Resolve o efeito anunciado (se nao foi anulado).

        Returns:
            Lista de logs da resolucao.
        """
        if not self.tem_anuncio_ativo:
            return ['Nenhum efeito para resolver']

        efeito = self.anuncio_atual

        # Carta modal sem modo escolhido?
        if efeito.aguardando_modo:
            self.estado = EstadoAnuncio.AGUARDANDO_MODO
            self.prompt_atual = self._criar_prompt_modo(efeito)
            return [f'AGUARDANDO: escolha modo para {efeito.descricao}']

        if efeito.anulado:
            logs = [f'{efeito.descricao} foi anulado e nao resolveu']
        elif efeito.resolver:
            logs = efeito.resolver(game)
        else:
            logs = [f'Resolvendo: {efeito.descricao}']

        self.ultimos_logs.extend(logs)
        self._limpar()
        return logs

    def escolher_modo(self, modo_idx: int) -> Optional[str]:
        """Escolhe o modo para o anuncio atual.

        So funciona se o anuncio esta aguardando modo.

        Args:
            modo_idx: Indice do modo escolhido.

        Returns:
            Mensagem de erro ou None se sucesso.
        """
        if self.estado != EstadoAnuncio.AGUARDANDO_MODO:
            return 'Nao esta aguardando escolha de modo'

        if not self.anuncio_atual or not self.anuncio_atual.aguardando_modo:
            return 'Nenhum anuncio aguardando modo'

        self.anuncio_atual.modo_idx = modo_idx
        self.anuncio_atual.modo_escolhido = True
        self.estado = EstadoAnuncio.ANUNCIADO
        self.prompt_atual = None
        return None

    def _limpar(self):
        """Limpa o anuncio atual."""
        self.anuncio_atual = None
        self.estado = EstadoAnuncio.LIVRE
        self.prompt_atual = None

    def _criar_prompt_modo(self, efeito: EfeitoAnunciado) -> dict:
        """Cria prompt de escolha de modo."""
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        modelo = CARTAS_EXEMPLO.get(efeito.modelo_id or '')
        if not modelo:
            return {'erro': 'Modelo nao encontrado'}

        return {
            'tipo': 'escolher_modo',
            'carta': efeito.descricao,
            'jogador_id': efeito.jogador_id,
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
# API de alto nivel
# -----------------------------------------------------------------------

def anunciar_e_resolver(game: GameState, jogador_id: str,
                        carta_id: str, modelo_id: str,
                        modo_idx: Optional[int] = None) -> list[str]:
    """Atalho: anuncia e ja tenta resolver uma carta.

    Se a carta tiver modos > 1 e modo_idx nao informado,
    retorna AGUARDANDO_MODO em vez de resolver.

    Args:
        game: Estado da partida.
        jogador_id: ID do jogador.
        carta_id: ID da instancia da carta.
        modelo_id: ID do modelo de efeitos.
        modo_idx: Modo escolhido (None se precisa escolher).

    Returns:
        Lista de logs.
    """
    from rage_web.game_engine.effects import CARTAS_EXEMPLO, aplicar_carta

    modelo = CARTAS_EXEMPLO.get(modelo_id)
    if not modelo:
        return [f'Modelo {modelo_id} nao encontrado']

    def _resolver(game: GameState) -> list[str]:
        # Usa efeito.modo_idx se ja foi escolhido, senao usa parametro
        if efeito.modo_escolhido and efeito.modo_idx is not None:
            idx = efeito.modo_idx
        else:
            idx = modo_idx or 0
        from rage_web.game_engine.effects import aplicar_carta
        return aplicar_carta(game, modelo, jogador_id, modo_idx=idx)

    efeito = EfeitoAnunciado(
        id=carta_id,
        descricao=modelo.nome,
        jogador_id=jogador_id,
        carta_id=carta_id,
        modelo_id=modelo_id,
        modo_idx=modo_idx,
        modo_escolhido=modo_idx is not None,
        resolver=_resolver,
    )

    anunciador = game.anunciador
    if not anunciador.anunciar(efeito):
        return ['Ja ha um efeito pendente']

    # Tenta resolver (se modal sem modo, retorna prompt)
    return anunciador.resolver(game)
