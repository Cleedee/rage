import os

from flask import Flask, session
from redis_om import Migrator

from rage_web.config import configs

def create_app(name_config='production'):

    app = Flask(__name__)

    @app.before_request
    def indexacao_redis():
        #if 'indexacao_redis' not in session:
        #    session['indexacao_redis'] = True
        #     Migrator().run()
        Migrator().run()

    name_config = os.environ.get("ENVIRONMENT") or name_config
    app.config.from_object(configs.get(name_config))
    
    from rage_web.blueprints.home import raiz
    from rage_web.blueprints.cards import bp as cards
    
    app.register_blueprint(raiz)
    app.register_blueprint(cards)

    return app
