import logging

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app

from rage_web.helpers.forms import DeckForm
from rage_web.models.deck import Deck
from rage_web.models.card import Card
import rage_web.ext.repository as rep

logger = logging.getLogger(__name__)

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
    # Conta cartas por deck
    deck_card_counts = {}
    for deck in decks:
        deck_card_counts[deck.id] = len(deck.cards)
    return render_template('decks/search.html', decks=decks,
                           deck_card_counts=deck_card_counts, form=form)


@bp.get('/deck/<id>')
def read_deck(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        flash('Deck não encontrado.')
        return redirect(url_for('decks.search'))

    form = DeckForm()
    form.id.data = deck.id
    form.name.data = deck.name
    form.description.data = deck.description

    cards = rep.deck_get_cards(deck)
    grupos = rep.agrupar_cartas_do_deck(cards)
    tipos = rep.get_tipos()
    expansoes = rep.get_expansions()

    return render_template('decks/deck.html', form=form, deck=deck,
                           cards=cards, grupos=grupos,
                           tipos=tipos, expansoes=expansoes)


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
        flash('Deck salvo.')
        return redirect(url_for('decks.read_deck', id=deck.id))
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


# --- Rotas para gerenciar cartas no deck ---

@bp.post('/deck/<id>/add-card')
def add_card(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)

    card_id = request.form.get('card_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)

    if not card_id:
        flash('Selecione uma carta.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    card = rep.find_card_by_id(card_id)
    if card is None:
        flash('Carta não encontrada.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    rep.deck_add_card(deck, card, quantity)
    flash(f'{card.name} adicionada ao deck.')

    # Se foi uma requisição HTMX, retorna snippet
    if request.headers.get('HX-Request'):
        cards = rep.deck_get_cards(deck)
        return render_template('decks/_card_list.html', deck=deck, cards=cards)

    return redirect(url_for('decks.read_deck', id=deck.id))


@bp.post('/deck/<id>/remove-card')
def remove_card(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)

    card_id = request.form.get('card_id', type=int)
    if not card_id:
        flash('Selecione uma carta.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    card = rep.find_card_by_id(card_id)
    if card is None:
        flash('Carta não encontrada.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    rep.deck_remove_card(deck, card)
    flash(f'{card.name} removida do deck.')

    if request.headers.get('HX-Request'):
        return render_template('decks/_card_list.html', deck=deck,
                               cards=rep.deck_get_cards(deck))

    return redirect(url_for('decks.read_deck', id=deck.id))


@bp.post('/deck/<id>/update-quantity')
def update_quantity(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)

    card_id = request.form.get('card_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)

    if not card_id:
        flash('Selecione uma carta.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    card = rep.find_card_by_id(card_id)
    if card is None:
        flash('Carta não encontrada.')
        return redirect(url_for('decks.read_deck', id=deck.id))

    rep.deck_update_quantity(deck, card, quantity)
    flash(f'Quantidade de {card.name} atualizada.')

    if request.headers.get('HX-Request'):
        return render_template('decks/_card_list.html', deck=deck,
                               cards=rep.deck_get_cards(deck))

    return redirect(url_for('decks.read_deck', id=deck.id))


@bp.route('/import', methods=['GET', 'POST'])
def import_deck():
    """Importa um deck a partir de texto colado ou upload."""
    from rage_web.ext.deck_importer import import_deck_from_text

    if request.method == 'POST':
        content = request.form.get('content', '')
        deck_name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not content.strip():
            flash('Cole o texto do deck primeiro.')
            return render_template('decks/import.html')

        try:
            stats = import_deck_from_text(content, deck_name=deck_name,
                                          description=description)
            if stats['encontradas'] > 0:
                flash(f'Deck importado com {stats["encontradas"]} cartas!')
                if stats['nao_encontradas'] > 0:
                    flash(f'{stats["nao_encontradas"]} cartas não encontradas.')
                return redirect(url_for('decks.read_deck', id=stats.get('deck_id')))
            else:
                flash('Nenhuma carta encontrada. Verifique o formato.')
        except Exception as e:
            flash(f'Erro ao importar: {e}')
            logger.exception('Erro na importação do deck')

    return render_template('decks/import.html')


@bp.get('/deck/<id>/search-cards')
def search_cards(id):
    """Busca cartas via HTMX para adicionar ao deck."""
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)

    query = request.args.get('q', '')
    tipo = request.args.get('tipo', '')
    expansion = request.args.get('expansion', '')

    cards = rep.search_cards(query=query, tipo=tipo, expansion=expansion,
                             limit=50)
    deck_card_ids = {c.id for c in deck.cards}

    return render_template('decks/_card_search.html', cards=cards,
                           deck=deck, deck_card_ids=deck_card_ids)
