from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import HiddenField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired

class PictureForm(FlaskForm):
    id = HiddenField()
    card_id = HiddenField()
    side = IntegerField('Side', validators=[DataRequired()])
    version = StringField('Version', validators=[DataRequired()])
    image = FileField('Image', validators=[DataRequired()])
    submit = SubmitField("SAVE")


class CardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    tipo = StringField('Type', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SAVE")

class CharacterCardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    tipo = StringField('Type', validators=[DataRequired()])
    rage = IntegerField('Rage', validators=[DataRequired()])
    gnosis = IntegerField('Gnosis', validators=[DataRequired()])
    health = IntegerField('Health', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SAVE")

class EquipmentCardForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    tipo = StringField('Type', validators=[DataRequired()])
    gnosis = IntegerField('Gnosis', validators=[DataRequired()])
    requires = StringField('Requires', validators=[DataRequired()])
    text = TextAreaField('Text', validators=[DataRequired()])
    submit = SubmitField("SAVE")

class DeckForm(FlaskForm):
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('SAVE')
