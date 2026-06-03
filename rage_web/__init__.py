import os

from flask import Flask, send_from_directory, session
from flask_migrate import Migrate

from rage_web.config import configs

migrate = Migrate()


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

    app.register_blueprint(raiz)
    app.register_blueprint(cards)
    app.register_blueprint(decks)

    # Disponibiliza helpers em todos os templates
    @app.context_processor
    def inject_helpers():
        from rage_web.ext.repository import get_card_image_url, \
            agrupar_cartas_do_deck
        return dict(
            get_card_image_url=get_card_image_url,
            agrupar_cartas_do_deck=agrupar_cartas_do_deck,
        )

    # Servir imagens das cartas de instance/images/
    @app.route('/instance/images/<path:filename>')
    def card_image(filename):
        return send_from_directory(
            os.path.join(app.instance_path, 'images'),
            filename
        )

    return app
