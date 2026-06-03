import logging

from flask import Blueprint, abort, flash, redirect, render_template, url_for, current_app

from rage_web.helpers.forms import DeckForm
from rage_web.models.deck import Deck
import rage_web.ext.repository as rep

bp = Blueprint(
    "decks", 
    __name__, 
    template_folder="templates",
    static_folder="static",
    url_prefix="/decks")

@bp.get('/search')
def search():
    form = DeckForm()
    decks = rep.find_all_decks()
    current_app.logger.info('Total de decks: ' + str(len(decks)))
    return render_template('decks/search.html', decks=decks, form=form)


@bp.get('/deck/<id>')
def read_deck(id):
    form = DeckForm()
    deck = rep.find_deck_by_id(id)
    if deck:
        form.id.data = deck.id
        form.name.data = deck.name
        form.description.data = deck.description
        return render_template('decks/deck.html', form=form)
    else:
        flash('Deck não encontrado.')
        return redirect(url_for('decks.search'))

@bp.get('/new')
def new():
    form = DeckForm()
    return render_template('decks/deck.html', form=form)

@bp.post('/deck')
def save():
    form = DeckForm()
    if form.validate_on_submit():
        if form.id.data:
            current_app.logger.info('Alterando deck')
            deck = rep.find_deck_by_id(form.id.data)
            if deck is None:
                abort(404)
            deck.name = form.name.data
            deck.description = form.description.data
        else:
            current_app.logger.info('Criando novo deck')
            deck = Deck()
            deck.name = form.name.data
            deck.description = form.description.data
        rep.save_deck(deck)
        current_app.logger.info('PK deck: ' + str(deck.id))
        flash('Deck salvo.')
        return redirect(url_for('decks.search'))
    current_app.logger.error(form.errors)
    return render_template('decks/deck.html', form=form)

@bp.get('/delete_deck/<id>')
def delete_deck(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)
    rep.delete_deck(deck)
    flash('Deck removido.')
    return redirect(url_for('decks.search'))
