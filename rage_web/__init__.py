import os

from flask import Flask, render_template, send_from_directory, session
from flask_migrate import Migrate

from rage_web.config import configs

migrate = Migrate()


def page_not_found(e):
    return render_template('errors/404.html'), 404


def internal_server_error(e):
    return render_template('errors/500.html'), 500


def create_app(name_config='production'):

    app = Flask(__name__)

    name_config = os.environ.get("ENVIRONMENT") or name_config
    app.config.from_object(configs.get(name_config))

    from rage_web.ext.database import db

    db.init_app(app)
    migrate.init_app(app, db)

    from rage_web.ext import cli
    cli.init_app(app)

    from rage_web.blueprints.home import raiz
    from rage_web.blueprints.cards import bp as cards
    from rage_web.blueprints.decks import bp as decks
    from rage_web.game_engine.api import api_bp
    from rage_web.blueprints.game import bp as game_bp
    from rage_web.blueprints.tutorial import tutorial_bp
    from rage_web.blueprints.tournaments import tournaments_bp
    from rage_web.blueprints.analysis import bp as analysis_bp
    from rage_web.blueprints.auth import bp as auth_bp
    from rage_web.blueprints.games import bp as games_bp

    app.register_blueprint(raiz)
    app.register_blueprint(cards)
    app.register_blueprint(decks)
    app.register_blueprint(api_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(tutorial_bp)
    app.register_blueprint(tournaments_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(games_bp)

    # Error handlers
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_server_error)

    # Injeta dados do usuário Telegram nos templates
    from rage_web.blueprints.auth import inject_telegram_user
    app.context_processor(inject_telegram_user)

    # Disponibiliza helpers em todos os templates
    @app.context_processor
    def inject_helpers():
        from rage_web.ext.repository import get_card_image_url, \
            get_original_image_url, agrupar_cartas_do_deck
        return dict(
            get_card_image_url=get_card_image_url,
            get_original_image_url=get_original_image_url,
            agrupar_cartas_do_deck=agrupar_cartas_do_deck,
        )

    # Servir imagens originais (LackeyCCG)
    @app.route('/instance/images/<path:filename>')
    def card_image(filename):
        return send_from_directory(
            os.path.join(app.instance_path, 'images'),
            filename
        )

    # Servir fan images (upload do usuario)
    @app.route('/instance/fan_images/<path:filename>')
    def fan_image(filename):
        return send_from_directory(
            os.path.join(app.instance_path, 'fan_images'),
            filename
        )

    return app
