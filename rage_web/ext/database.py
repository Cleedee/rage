
from flask_sqlalchemy import SQLAlchemy

from rage_web.ext.base import Base

db = SQLAlchemy(model_class=Base)
