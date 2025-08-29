import os

class Config(object):
    SECRET_KEY = os.environ.get("SECRET_KEY") or "mysecretkey1234567890"

class ProductionConfig(Config): ...


configs = {
    "default": Config,
    "production": ProductionConfig,
}
