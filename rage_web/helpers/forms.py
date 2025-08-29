from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class CardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    tipo = StringField('Type', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SALVAR")

class CharacterCardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    rage = IntegerField('Rage', validators=[DataRequired()])
    gnosis = IntegerField('Gnosis', validators=[DataRequired()])
    health = IntegerField('Health', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SALVAR")

class EquipmentCardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    gnosis = IntegerField('Gnosis', validators=[DataRequired()])
    requires = StringField('Requires', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SALVAR")
