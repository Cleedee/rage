"""Blueprint do tutorial de gameplay."""

from flask import Blueprint, render_template, request

from rage_web.helpers.tutorial_engine import run_tutorial, tutorial_to_dict

tutorial_bp = Blueprint(
    'tutorial',
    __name__,
    template_folder='templates',
    url_prefix='/tutorial',
)


@tutorial_bp.route('/gameplay')
def gameplay():
    """Executa e exibe um tutorial de gameplay de 5 rodadas com 3 jogadores."""
    seed = request.args.get('seed', 42, type=int)
    vp = request.args.get('vp', default=None, type=int)

    # Decks padrão para o tutorial:
    # J1: Grimfang Moot (665) — deck de Moots, tema principal do tutorial
    # J2: Passos da Morte Ren20 (643) — deck de combate agressivo
    # J3: Questor (7) — deck de Kinfolk + Firearms
    deck_ids = [665, 643, 7]

    try:
        data = run_tutorial(deck_ids, seed=seed, max_turns=5, vp_to_win=vp)
        tutorial = tutorial_to_dict(data)
    except Exception as e:
        return render_template('errors/500.html', error=str(e)), 500

    return render_template(
        'tutorial/gameplay.html',
        jogadores=tutorial['jogadores'],
        turnos=tutorial['turnos'],
        resumo=tutorial['resumo'],
        regras=tutorial['regras'],
        seed=seed,
    )


@tutorial_bp.route('/')
def index():
    """Página inicial do tutorial com explicação das regras."""
    return render_template('tutorial/index.html')
