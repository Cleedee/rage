"""Helpers para exibicao de Gifts na interface."""

from rage_web.game_engine.effects import CARTAS_EXEMPLO

DURACOES_LEGENDAS = {
    'permanente': ('∞', 'Permanente', '#7b1fa2'),
    'ate_fim_combate': ('⏳', 'Até fim do combate', '#1565c0'),
    'ate_fim_turno': ('⏳', 'Até fim do turno', '#e65100'),
    'proximo_turno': ('⏳', 'Até próximo turno', '#e65100'),
    'proximo_round': ('⚡', 'Próximo round', '#c62828'),
    'proximo_ataque': ('⚔️', 'Próximo ataque', '#d84315'),
    'este_moot': ('🗳️', 'Este Moot', '#4a148c'),
    'enquanto_umbra': ('🌙', 'Enquanto na Umbra', '#1a237e'),
}

COR_FUNDO_GIFT = '#e3f2fd'
COR_BORDA_GIFT = '#90caf9'


def gift_duracao_info(modelo_id: str | None) -> dict | None:
    """Retorna informacoes sobre a duracao de um gift.

    Args:
        modelo_id: ID do modelo da carta (slug).

    Returns:
        dict com 'icone', 'label', 'cor' se tiver duracao, None se instantaneo.
    """
    if not modelo_id:
        return None
    modelo = CARTAS_EXEMPLO.get(modelo_id)
    if not modelo or not modelo.modos:
        return None
    for modo in modelo.modos:
        for efeito in (modo.efeitos or []):
            params = getattr(efeito, 'params', {}) or {}
            if isinstance(params, dict):
                duracao = params.get('duracao', '')
                if duracao in DURACOES_LEGENDAS:
                    icone, label, cor = DURACOES_LEGENDAS[duracao]
                    return {'icone': icone, 'label': label, 'cor': cor}
    return None


def gift_eh_instantaneo(modelo_id: str | None) -> bool:
    """Verifica se um gift e instantaneo (sem duracao)."""
    info = gift_duracao_info(modelo_id)
    return info is None
