import logging
import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
from slugify import slugify

from rage_web.helpers.forms import CardForm, CardEditForm, CharacterCardForm, EquipmentCardForm
from rage_web.models.card import Card
import rage_web.ext.repository as rep


bp = Blueprint(
    "cards", 
    __name__, 
    template_folder="templates",
    static_folder="static",
    url_prefix="/cards")


@bp.post('/<id>/upload-fan')
def upload_fan(id):
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)

    if 'fan_image' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('cards.view_card', id=card.id))

    file = request.files['fan_image']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('cards.view_card', id=card.id))

    if file:
        ext = os.path.splitext(file.filename)[1] or '.jpg'
        safe_name = secure_filename(f"fan_{card.id}_{card.name}{ext}")

        dest_dir = os.path.join(current_app.instance_path, 'fan_images')
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, safe_name)
        file.save(dest_path)

        if card.fan_image and os.path.exists(os.path.join(dest_dir, card.fan_image)):
            os.remove(os.path.join(dest_dir, card.fan_image))

        card.fan_image = safe_name
        rep.save_card(card)
        flash(f'Imagem alternativa salva para {card.name}.')
        return redirect(url_for('cards.view_card', id=card.id))

    flash('Erro ao fazer upload.')
    return redirect(url_for('cards.view_card', id=card.id))


@bp.post('/<id>/remove-fan')
def remove_fan(id):
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)

    if card.fan_image:
        dest_dir = os.path.join(current_app.instance_path, 'fan_images')
        old_path = os.path.join(dest_dir, card.fan_image)
        if os.path.exists(old_path):
            os.remove(old_path)
        card.fan_image = ''
        rep.save_card(card)
        flash('Imagem alternativa removida.')

    return redirect(url_for('cards.view_card', id=card.id))


@bp.get('/new/character')
def new_character():
    form = CharacterCardForm()
    return render_template('cards/character.html', form=form)

@bp.get('/new/equipment')
def new_equipment():
    form = EquipmentCardForm()
    return render_template('cards/equipment.html', form=form)

@bp.get('/new/generic')
def new_card():
    form = CardForm()
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

@bp.post('/equipment')
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

@bp.post('/generic')
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

@bp.get('/<id>')
def read_card(id):
    """Pagina de edicao da carta (usa formulario universal)."""
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)
    form = CardEditForm(obj=card)
    form.id.data = card.id
    return render_template('cards/edit.html', form=form, card=card)

@bp.route('/<id>/delete', methods=['GET', 'POST'])
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

@bp.get('/<id>/view')
def view_card(id):
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)

    # Decks que contem esta carta
    decks = rep.find_decks_with_card(card)

    return render_template('cards/detail.html', card=card, decks=decks)


@bp.post('/<id>')
def save_card_edit(id):
    """Salva edicao completa de uma carta."""
    card = rep.find_card_by_id(id)
    if card is None:
        abort(404)

    form = CardEditForm()
    if form.validate_on_submit():
        card.name = form.name.data
        card.tipo = form.tipo.data
        card.expansion = form.expansion.data or ''
        card.rage = form.rage.data or 0
        card.gnosis = form.gnosis.data or 0
        card.health = form.health.data or 0
        card.renown = form.renown.data or 0
        card.damage = form.damage.data or ''
        card.requires = form.requires.data or ''
        card.keyword = form.keyword.data or ''
        card.text = form.text.data or ''
        card.notes = form.notes.data or ''
        card.errata = form.errata.data or ''
        card.sealed = form.sealed.data or ''
        card.rage_morph = form.rage_morph.data or 0
        card.gnosis_morph = form.gnosis_morph.data or 0
        card.health_morph = form.health_morph.data or 0
        rep.save_card(card)
        flash(f'{card.name} salvo.')
        return redirect(url_for('cards.view_card', id=card.id))

    current_app.logger.error(form.errors)
    flash('Erro ao salvar. Verifique os campos.')
    return render_template('cards/edit.html', form=form, card=card)


@bp.get('/search')
def search():
    query = request.args.get('q', '')
    tipo = request.args.get('tipo', '')
    expansion = request.args.get('expansion', '')
    tags = request.args.get('tags', '')
    form = CardForm()

    cards = rep.search_cards(query=query, tipo=tipo, expansion=expansion,
                             tags=tags, limit=200)
    tipos = rep.get_tipos()
    expansoes = rep.get_expansions()
    all_tags = rep.get_all_tags()

    return render_template('cards/search.html',
                           cards=cards, form=form,
                           tipos=tipos, expansoes=expansoes, all_tags=all_tags,
                           filtro_query=query,
                           filtro_tipo=tipo,
                           filtro_expansion=expansion,
                           filtro_tags=tags)
