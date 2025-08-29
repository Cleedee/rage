
from flask import Blueprint, flash, redirect, render_template, url_for

from rage_web.helpers.forms import CardForm
from rage_web.models.card import Card

raiz = Blueprint(
    "home", 
    __name__, 
    template_folder="templates",
    static_folder="static",
    url_prefix="/")

@raiz.get('/')
def index():
    form = CardForm()
    cards = Card.find().all()
    return render_template('home/index.html', cards=cards, form=form)

@raiz.post('/')
def save_card():
    form = CardForm()
    if form.validate_on_submit():
        card = Card(
            name=form.name.data,
            tipo=form.tipo.data
        )
        card.save()
        flash('Card salvo.')
    return redirect(url_for('home.index'))
