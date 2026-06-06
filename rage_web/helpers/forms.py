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
    text = TextAreaField('Text')
    submit = SubmitField("SAVE")


class CardEditForm(FlaskForm):
    """Formulario universal de edicao de carta com todos os campos."""
    id = HiddenField()
    name = StringField('Name', validators=[DataRequired()])
    tipo = StringField('Type', validators=[DataRequired()])
    expansion = StringField('Expansion')
    rage = IntegerField('Rage', default=0)
    gnosis = IntegerField('Gnosis', default=0)
    health = IntegerField('Health', default=0)
    renown = IntegerField('Renown', default=0)
    damage = StringField('Damage')
    requires = StringField('Requires')
    keyword = StringField('Keywords')
    text = TextAreaField('Text')
    notes = TextAreaField('Notes')
    errata = TextAreaField('Errata')
    sealed = StringField('Sealed')
    rage_morph = IntegerField('Rage (Crinos)', default=0)
    gnosis_morph = IntegerField('Gnosis (Crinos)', default=0)
    health_morph = IntegerField('Health (Crinos)', default=0)
    submit = SubmitField("Salvar")


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
    renown_cap = IntegerField('Limite de Renome', default=20)
    submit = SubmitField('SAVE')
