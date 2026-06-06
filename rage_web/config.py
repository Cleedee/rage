import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "mysecretkey1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format(os.path.join(basedir, "database.db"))

class ProductionConfig(Config): ...

class TestingConfig(Config):
    TESTING = True


configs = {
    "default": Config,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
