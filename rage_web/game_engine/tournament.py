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
        # Se der empate, tenta novamente com seeds diferentes
        vencedor = None
        tentativas = 0
        max_tentativas = 10
        seed_atual = match.seed

        while tentativas < max_tentativas:
            try:
                vencedor = run_match(
                    seed=seed_atual,
                    deck1_id=p1.deck_id,
                    deck2_id=p2.deck_id,
                    difficulty_p1=p1.difficulty,
                    difficulty_p2=p2.difficulty,
                    delay=0,
                )
            except Exception as e:
                print(f'[TORNEIO] Erro na partida {match.id} '
                      f'(seed={seed_atual}): {e}')
                vencedor = 'error'

            # Se nao for empate, aceita
            if vencedor not in ('draw', 'timeout', 'stuck', 'error'):
                break

            # Empate: tenta proximo seed
            tentativas += 1
            seed_atual += 1
            print(f'[TORNEIO] Partida {match.id} ({p1.player_name} vs '
                  f'{p2.player_name}) empatou (seed={seed_atual - 1}). '
                  f'Tentativa {tentativas}/{max_tentativas}...')

        match.seed = seed_atual

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
            # error / timeout / stuck: empate tecnico apos N tentativas
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


# ===================================================================
# Formato: Grupos + Mata-mata
# ===================================================================


def distribuir_grupos(tournament_id: int) -> None:
    """Distribui jogadores ativos uniformemente entre os grupos.

    Usa distribuição em serpentina para balancear: o jogador mais
    bem ranqueado vai para o grupo 1, o segundo para o grupo 2,
    etc., invertendo a ordem a cada volta.
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t or t.num_groups < 2:
        return

    ativos = [p for p in t.players if p.active]
    # Na primeira distribuicao (round 0 ou 1 - fase de grupos),
    # ordena aleatoriamente para evitar grupos deterministicos.
    # Em redistribuicoes, ordena por score.
    if t.current_round <= 1:
        random.shuffle(ativos)
    else:
        ativos.sort(key=lambda p: (-p.score, p.id))

    # Distribuição em serpentina
    grupo = 0
    direcao = 1
    for p in ativos:
        p.group = grupo + 1
        grupo += direcao
        if grupo >= t.num_groups:
            grupo = t.num_groups - 1
            direcao = -1
        elif grupo < 0:
            grupo = 0
            direcao = 1

    db.session.commit()


def _pairings_round_robin(jogadores: list[TournamentPlayer]) -> list[tuple]:
    """Gera pares de uma rodada de round-robin usando o método círculo.

    O algoritmo fixa o primeiro jogador e rotaciona os demais.
    Para número ímpar, o último jogador fica de BYE.

    Retorna lista de (p1, p2, is_bye).
    """
    ids = [p.id for p in jogadores]
    n = len(ids)

    # Se ímpar, adiciona um dummy (BYE)
    if n % 2 != 0:
        ids.append(None)
        n += 1

    # Método círculo: fixa o primeiro, rotaciona os outros
    metade = n // 2
    pares = []
    for rodada in range(n - 1):
        for i in range(metade):
            p1 = ids[i]
            p2 = ids[n - 1 - i]
            if p1 is not None and p2 is not None:
                pares.append((p1, p2, False))
            elif p1 is not None:
                pares.append((p1, None, True))
            elif p2 is not None:
                pares.append((p2, None, True))
        # Rotaciona: mantém o primeiro fixo, rotaciona o resto
        ultimo = ids.pop()
        ids.insert(1, ultimo)

    return pares


def _buscar_jogador_por_id(players: list, pid: int) -> Optional[TournamentPlayer]:
    """Busca um TournamentPlayer pelo ID na lista."""
    for p in players:
        if p.id == pid:
            return p
    return None


def iniciar_fase_grupos(tournament_id: int) -> list[TournamentMatch]:
    """Gera TODAS as partidas de round-robin dentro de cada grupo.

    Cada grupo joga todos contra todos. Para N jogadores, são
    N*(N-1)/2 partidas por grupo. Todas são geradas de uma vez
    para simplificar o fluxo.

    Returns:
        Lista de todos os TournamentMatch da fase de grupos.
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t or t.formato != 'groups_knockout':
        return []

    if t.status == 'open':
        t.status = 'active'

    t.current_round = 1

    # Distribui jogadores nos grupos (sempre redistribui,
    # ignorando grupos anteriores de importacao)
    for p in t.players:
        if p.active:
            p.group = 0
    distribuir_grupos(tournament_id)

    matches_criados = []
    match_id_counter = [1]  # mutable para closure

    for grupo_num in range(1, t.num_groups + 1):
        jogadores = [p for p in t.players if p.active and p.group == grupo_num]
        if len(jogadores) < 2:
            continue

        ids = [p.id for p in jogadores]
        n = len(ids)

        # Gera todos os pares únicos (round-robin completo)
        # Usa método círculo: N-1 rodadas, cada uma com N/2 pares
        if n % 2 != 0:
            ids.append(None)  # dummy BYE
            n += 1

        metade = n // 2
        ja_criados: set[tuple[int, int]] = set()

        for _ in range(n - 1):
            for i in range(metade):
                p1 = ids[i]
                p2 = ids[n - 1 - i]
                if p1 is not None and p2 is not None:
                    # Evita duplicatas (p1, p2) e (p2, p1)
                    par = (min(p1, p2), max(p1, p2))
                    if par not in ja_criados:
                        ja_criados.add(par)
                        match = TournamentMatch(
                            tournament_id=tournament_id,
                            round_number=1,
                            player1_id=p1,
                            player2_id=p2,
                            seed=random.randint(0, 2**31),
                            status='pending',
                        )
                        db.session.add(match)
                        matches_criados.append(match)
            # Rotaciona: mantém primeiro fixo, move o último para depois do primeiro
            ultimo = ids.pop()
            ids.insert(1, ultimo)

    db.session.commit()
    return matches_criados


def _classificacao_grupo(tournament_id: int, grupo: int) -> list[dict]:
    """Retorna classificação dos jogadores em um grupo específico."""
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return []

    jogadores = [p for p in t.players if p.group == grupo]
    jogadores.sort(key=lambda p: (-p.score, -p.sos, p.id))

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
        })
    return result


def _group_stage_complete(tournament_id: int) -> bool:
    """Verifica se todas as partidas da fase de grupos foram concluídas."""
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return False

    # Descobre quantos jogadores por grupo
    for grupo_num in range(1, t.num_groups + 1):
        jogadores = [p for p in t.players if p.group == grupo_num]
        n = len(jogadores)
        if n < 2:
            continue

        # Total de partidas necessárias: n*(n-1)/2
        total_necessario = n * (n - 1) // 2
        if n % 2 != 0:
            # Número ímpar: ainda n*(n-1)/2, mas algumas rodadas têm BYE
            pass

        # Partidas realizadas neste grupo
        realizadas = 0
        for m in t.matches:
            if m.status != 'completed':
                continue
            p1_grupo = 0
            p2_grupo = 0
            for p in t.players:
                if p.id == m.player1_id:
                    p1_grupo = p.group
                if p.id == m.player2_id:
                    p2_grupo = p.group
            if p1_grupo == grupo_num and p2_grupo == grupo_num:
                realizadas += 1

        if realizadas < total_necessario:
            return False

    return True


def avancar_para_mata_mata(tournament_id: int) -> list[TournamentMatch]:
    """Gera o bracket do mata-mata com base na classificação dos grupos.

    1. Pega os melhores de cada grupo (top N).
    2. Cria chaveamento cruzado: 1º Grupo A vs 2º Grupo B, etc.
    3. Gera as partidas da primeira rodada do mata-mata.

    Returns:
        Lista de TournamentMatch da primeira rodada do mata-mata.
    """
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return []

    t.group_stage_finished = True
    t.current_round += 1
    prox_round = t.current_round

    # Coleta os classificados de cada grupo
    classificados: list[dict] = []  # cada dict: {player, grupo, posicao}
    for grupo_num in range(1, t.num_groups + 1):
        ranking = _classificacao_grupo(tournament_id, grupo_num)
        for pos, r in enumerate(ranking, 1):
            if pos <= t.advance_per_group:
                player = _buscar_jogador_por_id(t.players, r['id'])
                if player:
                    classificados.append({
                        'player': player,
                        'grupo': grupo_num,
                        'posicao': pos,
                    })

    # Para 2 grupos: chaveamento cruzado padrão
    # A1 vs B2, B1 vs A2, A3 vs B4, B3 vs A4...
    matches_criados = []
    n_avancam = len(classificados)

    if n_avancam < 2:
        db.session.commit()
        return []

    # Garante que n_avancam é potência de 2
    import math
    prox_pot2 = 2 ** math.ceil(math.log2(n_avancam))
    n_byes = prox_pot2 - n_avancam

    # Ordena classificados por (grupo, posicao)
    # Para chaveamento padrão: intercala 1os vs 2os de grupos opostos
    # A1, B1, A2, B2, A3, B3, A4, B4...
    grupos_pares = t.num_groups // 2
    bracket_order = []
    for pos in range(1, t.advance_per_group + 1):
        for g in range(1, t.num_groups + 1):
            for c in classificados:
                if c['grupo'] == g and c['posicao'] == pos:
                    bracket_order.append(c)
                    break

    # Intercala: 1o vs último, 2o vs penúltimo... (padrão torneios)
    matches_data = []
    usados = set()
    i, j = 0, len(bracket_order) - 1
    while i < j:
        if i in usados:
            i += 1
            continue
        if j in usados:
            j -= 1
            continue
        matches_data.append((bracket_order[i]['player'], bracket_order[j]['player']))
        usados.add(i)
        usados.add(j)
        i += 1
        j -= 1

    # Se sobrou 1 (n_avancam ímpar), ganha BYE
    restantes = [c for idx, c in enumerate(bracket_order) if idx not in usados]
    for c in restantes:
        c['player'].score += PTS_VITORIA
        match = TournamentMatch(
            tournament_id=tournament_id,
            round_number=prox_round,
            player1_id=c['player'].id,
            player2_id=None,
            score_p1=PTS_VITORIA,
            score_p2=0.0,
            winner_id=c['player'].id,
            is_draw=False,
            status='completed',
        )
        db.session.add(match)
        matches_criados.append(match)

    # BYEs para completar potência de 2
    # (já tratado pelo chaveamento acima)

    for p1, p2 in matches_data:
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

    # Salva bracket JSON
    bracket_info = []
    for c in classificados:
        bracket_info.append({
            'player_id': c['player'].id,
            'player_name': c['player'].player_name,
            'grupo': c['grupo'],
            'posicao': c['posicao'],
        })
    t.bracket_json = json.dumps(bracket_info)

    db.session.commit()
    return matches_criados


def gerar_rodada_mata_mata(tournament_id: int) -> list[TournamentMatch]:
    """Gera a próxima rodada do mata-mata (single elimination).

    Emparelha vencedores da rodada anterior.
    Se só resta 1 partida pendente (final), retorna vazio.

    Returns:
        Lista de TournamentMatch da próxima rodada, ou lista vazia
        se o torneio deve encerrar.
    """
    from rage_web.game_engine.match import run_match

    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return []

    t.current_round += 1
    prox_round = t.current_round

    # Pega vencedores da rodada anterior (matches completed da última rodada)
    rodada_anterior = t.current_round - 1
    matches_anteriores = [
        m for m in t.matches
        if m.round_number == rodada_anterior and m.status == 'completed'
    ]

    vencedores = []
    for m in matches_anteriores:
        if m.winner_id:
            vencedores.append(m.winner_id)

    # Se só tem 1 vencedor, é o campeão
    if len(vencedores) <= 1:
        return []

    # Emparelha vencedores
    matches_criados = []
    for i in range(0, len(vencedores), 2):
        if i + 1 < len(vencedores):
            match = TournamentMatch(
                tournament_id=tournament_id,
                round_number=prox_round,
                player1_id=vencedores[i],
                player2_id=vencedores[i + 1],
                seed=random.randint(0, 2**31),
                status='pending',
            )
            db.session.add(match)
            matches_criados.append(match)
        else:
            # Número ímpar: BYE (não deve ocorrer com potência de 2)
            p = db.session.get(TournamentPlayer, vencedores[i])
            if p:
                p.score += PTS_VITORIA
                match = TournamentMatch(
                    tournament_id=tournament_id,
                    round_number=prox_round,
                    player1_id=vencedores[i],
                    player2_id=None,
                    score_p1=PTS_VITORIA,
                    score_p2=0.0,
                    winner_id=vencedores[i],
                    is_draw=False,
                    status='completed',
                )
                db.session.add(match)
                matches_criados.append(match)

    db.session.commit()
    return matches_criados
