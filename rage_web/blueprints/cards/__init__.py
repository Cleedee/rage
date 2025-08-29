import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for
from rage_web.helpers.forms import CardForm, CharacterCardForm, EquipmentCardForm
from rage_web.models.card import Card


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
        card = Card(
            name=form.name.data,
            tipo='Character',
            rage=form.rage.data,
            gnosis=form.gnosis.data,
            health=form.health.data,
            text=form.text.data
        )
        card.save()
        flash('Personagem salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.post('/new-equipment')
def save_equipment():
    form = EquipmentCardForm()
    if form.validate_on_submit():
        card = Card(
            name=form.name.data,
            tipo='Equipment',
            gnosis=form.gnosis.data,
            requires=form.requires.data,
            text=form.text.data
        )
        card.save()
        flash('Equipamento salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.get('/card/<id>')
def read_card(id):
    card = Card.get(id)
    if card.tipo == 'Character':
        form = CharacterCardForm()
        form.id.data = card.pk
        form.name.data = card.name
        form.rage.data = card.rage
        form.gnosis.data = card.gnosis
        form.health.data = card.health
        form.text.data = card.text
        return render_template('cards/character.html', form=form)
    elif card.tipo == 'Equipment':
        form = EquipmentCardForm()
        form.id.data = card.pk
        form.name.data = card.name
        form.gnosis.data = card.gnosis
        form.requires.data = card.requires
        form.text.data = card.text
        return render_template('cards/equipment.html', form=form)
    else:
        form = CardForm()
        form.id.data = card.pk
        form.tipo.data = card.tipo
        form.name.data = card.name
        form.text.data = card.text
        return render_template('cards/card.html', form=form)

@bp.post('/character')
def save_character():
    form = CharacterCardForm()
    if form.validate_on_submit():
        if form.id.data:
            card = Card.get(form.id.data)
            card.name = form.name.data
            card.rage = form.rage.data
            card.gnosis = form.gnosis.data
            card.health = form.health.data
            card.text = form.text.data
        else:
            card = Card(
                name = form.name.data,
                rage = form.rage.data,
                gnosis = form.gnosis.data,
                health = form.health.data,
                text = form.text.data
            )
        card.save()
        flash(f'{card.name} salvo.')
    logging.error(form.errors)
    return redirect(url_for('home.index'))

@bp.post('/card')
def save_card():
    form = CardForm()
    if form.validate_on_submit():
        if form.id.data:
            card = Card.get(form.id.data)
            card.name = form.name.data
            card.tipo = form.tipo.data
            card.text = form.text.data
        else:
            card = Card(
                name=form.name.data,
                tipo=form.tipo.data,
                text=form.text.data
            )
        card.save()
        flash('Card salvo.')
    return redirect(url_for('cards.search'))

@bp.delete('/card/<id>')
def delete_card(id):
    card = Card.get(id)
    card.expire(0)
    flash('Card excluído.')
    cards = Card.find().all()
    return render_template('cards/snippet_cards.html', cards=cards)

@bp.get('/new')
def new():
    return render_template('cards/new.html')

@bp.get('/search')
def search():
    form = CardForm()
    cards = Card.find().all()
    return render_template('cards/search.html', cards=cards, form=form)
