import logging
import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from slugify import slugify

from rage_web.helpers.forms import CardForm, CharacterCardForm, EquipmentCardForm
from rage_web.models.card import Card
import rage_web.ext.repository as rep


bp = Blueprint(
    "cards", 
    __name__, 
    template_folder="templates",
    static_folder="static",
    url_prefix="/cards")

@bp.get('/new-character')
def new_character():
    form = CharacterCardForm()
    return render_template('cards/character.html', form=form)

@bp.get('/new-equipment')
def new_equipment():
    form = EquipmentCardForm()
    return render_template('cards/equipment.html', form=form)

@bp.get('/new-card')
def new_card():
    form = CardForm()
    return render_template('cards/card.html', form=form)

@bp.post('/new-character')
def save_new_character():
    form = CharacterCardForm()
    if form.validate_on_submit():
        card = Card()
        card.name = form.name.data
        card.tipo = form.tipo.data
        card.rage = form.rage.data
        card.gnosis = form.gnosis.data
        card.health = form.health.data
        card.text = form.text.data
        rep.save_card(card)
        flash('Personagem salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.post('/new-equipment')
def save_equipment():
    form = EquipmentCardForm()
    if form.validate_on_submit():
        card = Card()
        card.name = form.name.data
        card.tipo = form.tipo.data
        card.gnosis = form.gnosis.data
        card.requires = form.requires.data
        card.text = form.text.data
        rep.save_card(card)
        flash('Equipamento salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.get('/card/<id>')
def read_card(id):
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)
    if card.tipo == 'Character':
        form = CharacterCardForm()
        form.id.data = card.id
        form.name.data = card.name
        form.tipo.data = card.tipo
        form.rage.data = card.rage
        form.gnosis.data = card.gnosis
        form.health.data = card.health
        form.text.data = card.text
        return render_template('cards/character.html', form=form)
    elif card.tipo == 'Equipment':
        form = EquipmentCardForm()
        form.id.data = card.id
        form.name.data = card.name
        form.tipo.data = card.tipo
        form.gnosis.data = card.gnosis
        form.requires.data = card.requires
        form.text.data = card.text
        return render_template('cards/equipment.html', form=form)
    else:
        form = CardForm()
        form.id.data = card.id
        form.tipo.data = card.tipo
        form.name.data = card.name
        form.text.data = card.text
        return render_template('cards/card.html', form=form)

@bp.post('/character')
def save_character():
    form = CharacterCardForm()
    if form.validate_on_submit():
        if form.id.data:
            card = rep.find_card_by_id(form.id.data)
            if card is None:
                abort(404)
            card.name = form.name.data
            card.tipo = form.tipo.data
            card.rage = form.rage.data
            card.gnosis = form.gnosis.data
            card.health = form.health.data
            card.text = form.text.data
        else:
            card = Card()
            card.name = form.name.data
            card.tipo = form.tipo.data
            card.rage = form.rage.data
            card.gnosis = form.gnosis.data
            card.health = form.health.data
            card.text = form.text.data
        rep.save_card(card)
        flash(f'{card.name} salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.post('/card')
def save_card():
    form = CardForm()
    if form.validate_on_submit():
        if form.id.data:
            card = rep.find_card_by_id(form.id.data)
            if card is None:
                abort(404)
            card.name = form.name.data
            card.tipo = form.tipo.data
            card.text = form.text.data
        else:
            card = Card()
            card.name = form.name.data
            card.tipo = form.tipo.data
            card.text = form.text.data
        rep.save_card(card)
        flash('Card salvo.')
    current_app.logger.error(form.errors)
    return redirect(url_for('cards.search'))

@bp.get('/delete-card/<id>')
def delete_card(id):
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)
    rep.delete_card(card)
    flash('Card excluído.')
    return redirect(url_for('cards.search'))

@bp.get('/new')
def new():
    return render_template('cards/new.html')

@bp.get('/search')
def search():
    query = request.args.get('q', '')
    tipo = request.args.get('tipo', '')
    expansion = request.args.get('expansion', '')
    form = CardForm()

    cards = rep.search_cards(query=query, tipo=tipo, expansion=expansion,
                             limit=200)
    tipos = rep.get_tipos()
    expansoes = rep.get_expansions()

    return render_template('cards/search.html',
                           cards=cards, form=form,
                           tipos=tipos, expansoes=expansoes,
                           filtro_query=query,
                           filtro_tipo=tipo,
                           filtro_expansion=expansion)
