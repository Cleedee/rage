from rage_web.ext.database import db

def init_app(app):
    @app.cli.command("init-database")
    def create_all():
        db.create_all()
