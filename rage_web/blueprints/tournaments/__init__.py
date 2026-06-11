"""Blueprint de Torneios — interface web para o sistema de torneios."""

from flask import Blueprint, render_template, redirect, url_for, request, flash

from rage_web.ext.database import db
from rage_web.models.tournament import (
    Tournament, TournamentPlayer, TournamentMatch,
)
from rage_web.game_engine.tournament import (
    criar_torneio, inscrever_jogador, gerar_empareamentos,
    executar_rodada, encerrar_torneio, classificacao,
)

tournaments_bp = Blueprint(
    'tournaments', __name__,
    template_folder='templates',
    url_prefix='/tournaments',
)


# ---------------------------------------------------------------------------
# Lista de torneios
# ---------------------------------------------------------------------------

@tournaments_bp.route('/')
def listar():
    """Lista todos os torneios."""
    torneios = Tournament.query.order_by(
        Tournament.created_at.desc()
    ).all()
    return render_template('tournaments/listar.html', torneios=torneios)


# ---------------------------------------------------------------------------
# Detalhes do torneio
# ---------------------------------------------------------------------------

@tournaments_bp.route('/<int:tournament_id>')
def detalhes(tournament_id: int):
    """Página de detalhes de um torneio."""
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return render_template('404.html'), 404

    ranking = classificacao(tournament_id)
    matches = TournamentMatch.query.filter_by(
        tournament_id=tournament_id
    ).order_by(
        TournamentMatch.round_number.desc(),
        TournamentMatch.id,
    ).all()

    return render_template(
        'tournaments/detalhes.html',
        torneio=t,
        ranking=ranking,
        matches=matches,
    )


# ---------------------------------------------------------------------------
# Criar torneio
# ---------------------------------------------------------------------------

@tournaments_bp.route('/novo', methods=['GET', 'POST'])
def novo():
    """Cria um novo torneio."""
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Nome é obrigatório.', 'danger')
            return render_template('tournaments/novo.html')

        formato = request.form.get('formato', 'swiss')
        max_rounds = int(request.form.get('max_rounds', 0))
        vp_to_win = int(request.form.get('vp_to_win', 0))

        t = criar_torneio(nome, formato, max_rounds, vp_to_win)
        flash(f'Torneio "{nome}" criado com sucesso!', 'success')
        return redirect(url_for('tournaments.detalhes', tournament_id=t.id))

    return render_template('tournaments/novo.html')


# ---------------------------------------------------------------------------
# Inscrever jogador
# ---------------------------------------------------------------------------

@tournaments_bp.route('/<int:tournament_id>/inscrever', methods=['GET', 'POST'])
def inscrever(tournament_id: int):
    """Inscreve um jogador no torneio."""
    t: Tournament = db.session.get(Tournament, tournament_id)
    if not t:
        return render_template('404.html'), 404

    if request.method == 'POST':
        player_name = request.form.get('player_name', '').strip()
        if not player_name:
            flash('Nome é obrigatório.', 'danger')
            return render_template('tournaments/inscrever.html', torneio=t)

        deck_id = request.form.get('deck_id', type=int)
        difficulty = request.form.get('difficulty', 'hard')
        is_bot = request.form.get('tipo', 'bot') == 'bot'

        tp = inscrever_jogador(
            tournament_id, player_name, deck_id, difficulty, is_bot,
        )
        flash(f'{player_name} inscrito com sucesso!', 'success')
        return redirect(url_for('tournaments.detalhes', tournament_id=tournament_id))

    from rage_web.models.deck import Deck
    decks = Deck.query.order_by(Deck.name).all()
    return render_template('tournaments/inscrever.html', torneio=t, decks=decks)


# ---------------------------------------------------------------------------
# Iniciar torneio / gerar rodada
# ---------------------------------------------------------------------------

@tournaments_bp.route('/<int:tournament_id>/iniciar', methods=['POST'])
def iniciar(tournament_id: int):
    """Inicia o torneio: gera a primeira rodada."""
    matches = gerar_empareamentos(tournament_id)
    if not matches:
        flash('Não foi possível gerar a primeira rodada.', 'warning')
    else:
        flash(f'Rodada 1 gerada com {len(matches)} partida(s)!', 'success')
    return redirect(url_for('tournaments.detalhes', tournament_id=tournament_id))


@tournaments_bp.route('/<int:tournament_id>/proxima-rodada', methods=['POST'])
def proxima_rodada(tournament_id: int):
    """Gera a próxima rodada."""
    matches = gerar_empareamentos(tournament_id)
    if not matches:
        flash('Todas as rodadas foram concluídas!', 'info')
    else:
        r = matches[0].round_number
        flash(f'Rodada {r} gerada com {len(matches)} partida(s)!', 'success')
    return redirect(url_for('tournaments.detalhes', tournament_id=tournament_id))


# ---------------------------------------------------------------------------
# Executar rodada (bots)
# ---------------------------------------------------------------------------

@tournaments_bp.route('/<int:tournament_id>/executar', methods=['POST'])
def executar(tournament_id: int):
    """Executa todas as partidas pendentes (bot vs bot)."""
    n = executar_rodada(tournament_id)
    flash(f'{n} partida(s) executadas!', 'success')
    return redirect(url_for('tournaments.detalhes', tournament_id=tournament_id))


# ---------------------------------------------------------------------------
# Encerrar torneio
# ---------------------------------------------------------------------------

@tournaments_bp.route('/<int:tournament_id>/encerrar', methods=['POST'])
def encerrar(tournament_id: int):
    """Encerra o torneio."""
    vencedor = encerrar_torneio(tournament_id)
    if vencedor:
        flash(f'Torneio encerrado! Vencedor: {vencedor.player_name}', 'success')
    else:
        flash('Torneio encerrado.', 'info')
    return redirect(url_for('tournaments.detalhes', tournament_id=tournament_id))
