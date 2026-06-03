import os

from flask import Flask, session
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

    return app
