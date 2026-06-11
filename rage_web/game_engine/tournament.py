"""Motor de torneio Suíço para Rage CCG.

Gera empareamentos, calcula pontuações e desempates,
e executa partidas entre bots.
"""

import random
import json
from datetime import datetime, timezone
from typing import Optional

from rage_web.ext.database import db
from rage_web.models.tournament import (
    Tournament, TournamentPlayer, TournamentMatch,
)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PTS_VITORIA = 3.0
PTS_EMPATE = 1.0
PTS_DERROTA = 0.0


# ---------------------------------------------------------------------------
# Criação de torneio
# ---------------------------------------------------------------------------

def criar_torneio(
    nome: str,
    formato: str = 'swiss',
    max_rounds: int = 0,
    vp_to_win: int = 0,
    descricao: str = '',
) -> Tournament:
    """Cria um novo torneio no banco.

    Args:
        nome: Nome do torneio.
        formato: 'swiss' (padrão), 'single_elim', 'double_elim'.
        max_rounds: 0 = automático (log2(N) para suíço).
        vp_to_win: 0 = usar renown padrão do jogo.
        descricao: Descrição opcional.

    Returns:
        Tournament recém-criado.
    """
    t = Tournament(
        name=nome,
        formato=formato,
        status='open',
        max_rounds=max_rounds,
        vp_to_win=vp_to_win,
        description=descricao,
    )
    db.session.add(t)
    db.session.commit()
    return t


def inscrever_jogador(
    tournament_id: int,
    player_name: str,
    deck_id: Optional[int] = None,
    difficulty: str = 'hard',
    is_bot: bool = True,
) -> TournamentPlayer:
    """Inscreve um jogador (humano ou bot) no torneio.

    Args:
        tournament_id: ID do torneio.
        player_name: Nome do jogador/bot.
        deck_id: ID do deck (None para humanos que escolhem depois).
        difficulty: 'easy', 'medium', 'hard' (só para bots).
        is_bot: True se é um bot.

    Returns:
        TournamentPlayer recém-criado.
    """
    tp = TournamentPlayer(
        tournament_id=tournament_id,
        player_name=player_name,
        deck_id=deck_id,
        difficulty=difficulty,
        is_bot=is_bot,
    )
    db.session.add(tp)
    db.session.commit()
    return tp


# ---------------------------------------------------------------------------
# Empareamento Suíço
# ---------------------------------------------------------------------------

def _calcular_max_rounds(n_jogadores: int) -> int:
    """Calcula o número ideal de rodadas para um torneio suíço.

    Fórmula: ceil(log2(N)) para garantir um vencedor único.
    Mínimo 3 rodadas, máximo 9.
    """
    import math
    rounds = max(3, math.ceil(math.log2(n_jogadores)))
    return min(rounds, 9)


def gerar_empareamentos(tournament_id: int) -> list[TournamentMatch]:
    """Gera empareamentos da próxima rodada (Suíço).

    Algoritmo:
    1. Ordena jogadores por score (desc), SOS (desc), id (asc).
    2. Percorre a lista ordenada e emparelha cada jogador com o
       próximo disponível mais próximo na classificação,
       evitando rematches quando houver alternativa.
    3. Se todos os oponentes possíveis já enfrentaram o jogador,
       permite rematch como último recurso.
    4. Se sobrar um jogador (número ímpar), recebe BYE.

    Returns:
        Lista de TournamentMatch criados (status='pending').
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return []

    # Calcula max_rounds automático se não definido
    n_ativos = sum(1 for p in t.players if p.active)
    if t.max_rounds == 0:
        t.max_rounds = _calcular_max_rounds(n_ativos)
    t.current_round += 1
    prox_round = t.current_round

    if prox_round > t.max_rounds:
        return []  # Torneio já terminou

    # Muda status para 'active' na primeira rodada
    if t.status == 'open':
        t.status = 'active'

    # Coleta jogadores ativos e ordena por score (desc), SOS (desc), id
    ativos = [p for p in t.players if p.active]
    ativos.sort(key=lambda p: (-p.score, -p.sos, p.id))

    # Mapa de confrontos já realizados
    confrontos: dict[int, set[int]] = {}
    for m in t.matches:
        if m.player1_id and m.player2_id:
            confrontos.setdefault(m.player1_id, set()).add(m.player2_id)
            confrontos.setdefault(m.player2_id, set()).add(m.player1_id)

    matches_criados = []
    emparelhados: set[int] = set()
    pares: list[tuple[TournamentPlayer, TournamentPlayer]] = []

    # Emparelha sequencialmente: cada jogador busca o próximo
    # disponível na ordem, pulando rematches (mas permitindo
    # como último recurso se não houver alternativa.)
    for i, p in enumerate(ativos):
        if p.id in emparelhados:
            continue

        candidato: TournamentPlayer | None = None
        candidato_rematch: TournamentPlayer | None = None

        for j in range(i + 1, len(ativos)):
            q = ativos[j]
            if q.id in emparelhados:
                continue

            ja_se_encontraram = (
                p.id in confrontos and q.id in confrontos.get(p.id, set())
            )
            if not ja_se_encontraram:
                # Primeira opção: oponente que nunca enfrentou
                candidato = q
                break
            # Guarda fallback (rematch) se ainda não temos um
            if candidato_rematch is None:
                candidato_rematch = q

        # Se não achou oponente inédito, permite rematch
        if candidato is None:
            candidato = candidato_rematch

        if candidato is not None:
            pares.append((p, candidato))
            emparelhados.add(p.id)
            emparelhados.add(candidato.id)
        else:
            # Número ímpar de jogadores: este fica de BYE
            pass

    # Cria matches no banco
    for p1, p2 in pares:
        match = TournamentMatch(
            tournament_id=tournament_id,
            round_number=prox_round,
            player1_id=p1.id,
            player2_id=p2.id,
            seed=random.randint(0, 2**31),
            status='pending',
        )
        db.session.add(match)
        matches_criados.append(match)

    # BYE: jogador sem oponente ganha 3 pontos
    nao_emparelhados = [p for p in ativos if p.id not in emparelhados]
    for p in nao_emparelhados:
        p.score += PTS_VITORIA
        match = TournamentMatch(
            tournament_id=tournament_id,
            round_number=prox_round,
            player1_id=p.id,
            player2_id=None,
            score_p1=PTS_VITORIA,
            score_p2=0.0,
            winner_id=p.id,
            is_draw=False,
            status='completed',
        )
        db.session.add(match)
        matches_criados.append(match)

    db.session.commit()
    return matches_criados


# ---------------------------------------------------------------------------
# Execução de rodada (bots)
# ---------------------------------------------------------------------------

def executar_rodada(tournament_id: int) -> int:
    """Executa todas as partidas pendentes da rodada atual.

    Para partidas entre bots: usa run_match() do match.py.
    Partidas com humanos são ignoradas (aguardam resultado manual).

    Returns:
        Número de partidas executadas.
    """
    from rage_web.game_engine.match import run_match

    matches = TournamentMatch.query.filter(
        TournamentMatch.tournament_id == tournament_id,
        TournamentMatch.status == 'pending',
    ).all()

    executadas = 0
    for match in matches:
        if not match.player1_id:
            continue

        p1: TournamentPlayer = db.session.get(TournamentPlayer, match.player1_id)
        p2: TournamentPlayer = (
            db.session.get(TournamentPlayer, match.player2_id)
            if match.player2_id else None
        )

        if not p1 or not p2:
            # BYE já foi resolvido na criação
            continue

        if not p1.is_bot or not p2.is_bot:
            # Partida com humano: aguarda resultado manual
            continue

        # Executa partida bot vs bot
        try:
            vencedor = run_match(
                seed=match.seed,
                deck1_id=p1.deck_id,
                deck2_id=p2.deck_id,
                difficulty_p1=p1.difficulty,
                difficulty_p2=p2.difficulty,
                delay=0,
            )
        except Exception as e:
            print(f'[TORNEIO] Erro na partida {match.id}: {e}')
            vencedor = 'error'

        # Registra resultado
        if vencedor == 'p1':
            match.score_p1 = PTS_VITORIA
            match.score_p2 = PTS_DERROTA
            match.winner_id = p1.id
            match.is_draw = False
        elif vencedor == 'p2':
            match.score_p1 = PTS_DERROTA
            match.score_p2 = PTS_VITORIA
            match.winner_id = p2.id
            match.is_draw = False
        elif vencedor == 'draw':
            match.score_p1 = PTS_EMPATE
            match.score_p2 = PTS_EMPATE
            match.is_draw = True
        else:
            # error / timeout: empate técnico
            match.score_p1 = PTS_EMPATE
            match.score_p2 = PTS_EMPATE
            match.is_draw = True

        match.status = 'completed'
        db.session.commit()

        # Atualiza scores dos jogadores
        _recalcular_scores(tournament_id)
        executadas += 1

    return executadas


def _recalcular_scores(tournament_id: int) -> None:
    """Recalcula scores e SOS de todos os jogadores."""
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return

    # Zera scores
    for p in t.players:
        p.score = 0.0

    # Soma pontos dos matches completados
    for m in t.matches:
        if m.status != 'completed':
            continue
        if m.player1_id:
            p1 = db.session.get(TournamentPlayer, m.player1_id)
            if p1:
                p1.score += m.score_p1
        if m.player2_id:
            p2 = db.session.get(TournamentPlayer, m.player2_id)
            if p2:
                p2.score += m.score_p2

    # Calcula SOS (Sum of Opponents' Scores)
    for p in t.players:
        soma_opp = 0.0
        n_opp = 0
        for m in t.matches:
            if m.status != 'completed':
                continue
            if m.player1_id == p.id and m.player2_id:
                opp = db.session.get(TournamentPlayer, m.player2_id)
                if opp:
                    soma_opp += opp.score
                    n_opp += 1
            elif m.player2_id == p.id and m.player1_id:
                opp = db.session.get(TournamentPlayer, m.player1_id)
                if opp:
                    soma_opp += opp.score
                    n_opp += 1
        p.sos = soma_opp / max(n_opp, 1)

    db.session.commit()


# ---------------------------------------------------------------------------
# Encerramento
# ---------------------------------------------------------------------------

def encerrar_torneio(tournament_id: int) -> Optional[TournamentPlayer]:
    """Encerra um torneio e retorna o vencedor.

    O vencedor é o jogador com maior score (e maior SOS em caso de empate).

    Returns:
        TournamentPlayer vencedor, ou None se não houver.
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return None

    t.status = 'completed'

    # Ordena por score (desc) e SOS (desc)
    ranked = sorted(t.players, key=lambda p: (-p.score, -p.sos))
    vencedor = ranked[0] if ranked else None

    db.session.commit()
    return vencedor


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------

def classificacao(tournament_id: int) -> list[dict]:
    """Retorna a classificação atual do torneio.

    Returns:
        Lista de dicts com posição, nome, score, SOS, wins, losses, draws.
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return []

    jogadores = sorted(
        t.players,
        key=lambda p: (-p.score, -p.sos, -p.ext_sos, p.id),
    )

    result = []
    for pos, p in enumerate(jogadores, 1):
        result.append({
            'posicao': pos,
            'id': p.id,
            'nome': p.player_name,
            'score': p.score,
            'sos': round(p.sos, 2),
            'wins': p.wins,
            'losses': p.losses,
            'draws': p.draws,
            'is_bot': p.is_bot,
            'active': p.active,
        })
    return result
