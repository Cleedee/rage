import logging

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, current_app

from rage_web.helpers.forms import DeckForm
from rage_web.models.deck import Deck
from rage_web.models.card import Card
import rage_web.ext.repository as rep

logger = logging.getLogger(__name__)

# Tipos que vao para sept deck vs combat deck
_DECK_SEPT_TYPES = {
    'Event', 'Action', 'Territory', 'Caern', 'Quest',
    'Battlefield', 'Rite', 'Moot', 'Board Meeting',
    'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
    'Victim', 'Enemy',
    'Equipment', 'Equipment - Fetish - Bane Fetish',
}

COMBAT_DECK_MIN = 20
SEPT_DECK_MIN = 30


def _calcular_validade_deck(deck):
    """Retorna dict com contagem e validade do deck.

    Usa deck_get_cards para considerar quantity de cada carta.
    """
    cartas = rep.deck_get_cards(deck)
    n_sept = 0
    n_combat = 0
    for entry in cartas:
        card = entry['card']
        qty = entry['quantity']
        ct = (card.tipo or '').strip()
        if 'Character' in ct or 'character' in ct.lower():
            continue
        if ct in _DECK_SEPT_TYPES:
            n_sept += qty
        else:
            n_combat += qty
    return {
        'n_sept': n_sept,
        'n_combat': n_combat,
        'sept_ok': n_sept >= SEPT_DECK_MIN,
        'combat_ok': n_combat >= COMBAT_DECK_MIN,
        'valido': n_sept >= SEPT_DECK_MIN and n_combat >= COMBAT_DECK_MIN,
    }

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
    # Conta cartas e validade por deck
    deck_card_counts = {}
    deck_validade = {}
    for deck in decks:
        deck_card_counts[deck.id] = len(deck.cards)
        deck_validade[deck.id] = _calcular_validade_deck(deck)
    return render_template('decks/search.html', decks=decks,
                           deck_card_counts=deck_card_counts,
                           deck_validade=deck_validade, form=form)


@bp.get('/<id>')
def read_deck(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        flash('Deck não encontrado.')
        return redirect(url_for('decks.search'))

    form = DeckForm()
    form.id.data = deck.id
    form.name.data = deck.name
    form.description.data = deck.description
    form.renown_cap.data = deck.renown_cap or 20

    cards = rep.deck_get_cards(deck)
    grupos = rep.agrupar_cartas_do_deck(cards)
    total_combat = sum(e['quantity'] for e in grupos['combat'])
    total_sept = sum(e['quantity'] for e in grupos['sept'])
    total_chars = sum(e['quantity'] for e in grupos['characters'])
    total_renown = sum(
        (e['card'].renown or 0) * e['quantity']
        for e in grupos['characters']
    )
    tipos = rep.get_tipos()
    expansoes = rep.get_expansions()

    return render_template('decks/deck.html', form=form, deck=deck,
                           cards=cards, grupos=grupos,
                           total_combat=total_combat,
                           total_sept=total_sept,
                           total_chars=total_chars,
                           total_renown=total_renown,
                           tipos=tipos, expansoes=expansoes)


@bp.get('/new')
def new():
    form = DeckForm()
    form.renown_cap.data = 20
    return render_template('decks/deck.html', form=form)


@bp.post('')
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
            deck.renown_cap = form.renown_cap.data or 20
        else:
            current_app.logger.info('Criando novo deck')
            deck = Deck()
            deck.name = form.name.data
            deck.description = form.description.data
            deck.renown_cap = form.renown_cap.data or 20
        rep.save_deck(deck)

        # Validar composicao do deck apos salvar
        erros = _validar_deck(deck)
        if erros:
            for err in erros:
                flash(err, 'danger')
            # Se houver erros, carrega dados completos e re-renderiza
            cards = rep.deck_get_cards(deck)
            grupos = rep.agrupar_cartas_do_deck(cards)
            total_combat = sum(e['quantity'] for e in grupos['combat'])
            total_sept = sum(e['quantity'] for e in grupos['sept'])
            total_chars = sum(e['quantity'] for e in grupos['characters'])
            total_renown = sum(
                (e['card'].renown or 0) * e['quantity']
                for e in grupos['characters']
            )
            return render_template('decks/deck.html', form=form, deck=deck,
                                   cards=cards, grupos=grupos,
                                   total_combat=total_combat,
                                   total_sept=total_sept,
                                   total_chars=total_chars,
                                   total_renown=total_renown,
                                   tipos=rep.get_tipos(),
                                   expansoes=rep.get_expansions())

        flash('Deck salvo.')
        return redirect(url_for('decks.read_deck', id=deck.id))
    current_app.logger.error(form.errors)
    return render_template('decks/deck.html', form=form)


@bp.route('/<id>/delete', methods=['GET', 'POST'])
def delete_deck(id):
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)
    rep.delete_deck(deck)
    flash('Deck removido.')
    return redirect(url_for('decks.search'))


@bp.route('/delete-empty', methods=['POST'])
def delete_empty():
    """Apaga todos os decks que não têm nenhuma carta."""
    decks = rep.find_all_decks()
    apagados = 0
    for deck in decks:
        if len(deck.cards) == 0:
            rep.delete_deck(deck)
            apagados += 1
    if apagados:
        flash(f'{apagados} deck(s) vazio(s) removido(s).', 'success')
    else:
        flash('Nenhum deck vazio encontrado.', 'info')
    return redirect(url_for('decks.search'))


# --- Rotas para gerenciar cartas no deck ---

@bp.post('/<id>/add-card')
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


@bp.post('/<id>/remove-card')
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


@bp.post('/<id>/update-quantity')
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


def _validar_deck(deck) -> list[str]:
    """Valida composicao do deck segundo as regras.

    Regras por nivel de Renome:

    Nivel 20:
      - Renome total ≤ 20
      - Combat: minimo 20 cartas, max 2 copias por carta
      - Sept:   minimo 30 cartas, max 3 copias por carta

    Nivel 30:
      - Renome total ≤ 30
      - Combat: minimo 30 cartas, max 3 copias por carta
      - Sept:   minimo 40 cartas, max 3 copias por carta
    """
    erros = []

    cards = rep.deck_get_cards(deck)
    if not cards:
        return []  # Deck vazio na criacao, sem validacao ainda

    cap = deck.renown_cap or 20

    # Limites por nivel
    if cap <= 20:
        min_combat, max_combat_copia = 20, 2
        min_sept,   max_sept_copia   = 30, 3
    else:
        min_combat, max_combat_copia = 30, 3
        min_sept,   max_sept_copia   = 40, 3

    # Agrupa por categoria
    grupos = {'characters': [], 'combat': [], 'sept': []}
    for entry in cards:
        g = rep.grupo_carta(entry['card'].tipo or '')
        grupos.setdefault(g, []).append(entry)

    # 1. Renome total
    total_renown = 0
    for entry in grupos['characters']:
        card = entry['card']
        total_renown += (card.renown or 0) * entry['quantity']
    if total_renown > cap:
        erros.append(
            f'Renome total {total_renown} excede o limite de {cap}.')

    # 2. Combat
    total_combat = sum(e['quantity'] for e in grupos['combat'])
    if total_combat < min_combat:
        erros.append(
            f'Deck de combate tem {total_combat} cartas '
            f'(minimo {min_combat}).')
    for entry in grupos['combat']:
        if entry['quantity'] > max_combat_copia:
            card = entry['card']
            erros.append(
                f'{card.name}: {entry["quantity"]} copias no combat '
                f'(maximo {max_combat_copia}).')

    # 3. Sept
    total_sept = sum(e['quantity'] for e in grupos['sept'])
    if total_sept < min_sept:
        erros.append(
            f'Deck de septo tem {total_sept} cartas '
            f'(minimo {min_sept}).')
    for entry in grupos['sept']:
        if entry['quantity'] > max_sept_copia:
            card = entry['card']
            erros.append(
                f'{card.name}: {entry["quantity"]} copias no septo '
                f'(maximo {max_sept_copia}).')

    return erros


@bp.get('/<id>/export')
def export_deck(id):
    """Exporta deck em formato texto (TXT ou XML .dek)."""
    deck = rep.find_deck_by_id(id)
    if deck is None:
        abort(404)

    fmt = request.args.get('fmt', 'text')
    cards = rep.deck_get_cards(deck)

    # Agrupa por tipo real da carta (card.tipo)
    grupos_por_tipo: dict[str, list] = {}
    for entry in cards:
        tipo = entry['card'].tipo or 'Outro'
        grupos_por_tipo.setdefault(tipo, []).append(entry)

    if fmt == 'xml':
        return _export_xml(deck, grupos_por_tipo)
    elif fmt == 'discord':
        return _export_discord(deck, cards, grupos_por_tipo)
    else:
        return _export_text(deck, cards, grupos_por_tipo)


def _card_stats_short(card) -> str:
    """Retorna stats resumidos da carta para export."""
    partes = []
    if card.rage:
        partes.append(f'R{card.rage}')
    if card.gnosis:
        partes.append(f'G{card.gnosis}')
    if card.health:
        partes.append(f'H{card.health}')
    if hasattr(card, 'renown') and card.renown:
        partes.append(f'Ren{card.renown}')
    if partes:
        return ' '.join(partes)
    return ''


def _sanitize_filename(name: str) -> str:
    """Remove ou substitui caracteres nao-ASCII para filename seguro."""
    import unicodedata
    # Normaliza: e com acento → e + combinante; em-dash → hifen, etc.
    normalized = unicodedata.normalize('NFKD', name)
    # Substitui tracos especiais por hifen
    normalized = normalized.replace('\u2014', '-').replace('\u2013', '-')
    # Remove caracteres de controle e nao-ASCII
    safe = normalized.encode('ascii', 'ignore').decode('ascii')
    # Remove espacos extras, troca espacos por underscore
    safe = '_'.join(safe.split())
    return safe


def _export_text(deck, cards, grupos_por_tipo):
    """Exporta deck no formato TXT legivel e reimportavel."""
    ORDEM_TIPOS = [
        'Character', 'Ally', 'Enemy', 'Victim',
        'Gift', 'Equipment', 'Caern', 'Territory', 'Quest',
        'Event', 'Action', 'Rite', 'Moot',
        'Combat Action', 'Combat Event',
    ]

    lines = []
    lines.append(f'# {deck.name or "Deck sem nome"}')
    if deck.description:
        lines.append(f'# {deck.description}')
    lines.append('')

    for tipo in ORDEM_TIPOS:
        grupo = grupos_por_tipo.get(tipo, [])
        if not grupo:
            continue
        lines.append(f'{tipo}:')
        lines.append('')
        for entry in sorted(grupo, key=lambda x: x['card'].name):
            card = entry['card']
            qty = entry['quantity']
            stats = _card_stats_short(card)
            nome = f'  {qty} {card.name}'
            if stats:
                nome += f'  ({stats})'
            lines.append(nome)
        lines.append('')

    # Tipos remanescentes (nao listados em ORDEM_TIPOS)
    for tipo in grupos_por_tipo:
        if tipo not in ORDEM_TIPOS:
            lines.append(f'{tipo}:')
            lines.append('')
            for entry in sorted(grupos_por_tipo[tipo], key=lambda x: x['card'].name):
                card = entry['card']
                qty = entry['quantity']
                lines.append(f'  {qty} {card.name}')
            lines.append('')

    lines.append(f'# Total: {sum(e["quantity"] for e in cards)} cartas')

    text = '\n'.join(lines)
    nome_arquivo = f'{_sanitize_filename(deck.name) or "deck"}.txt'
    return current_app.response_class(
        text,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment; filename={nome_arquivo}'}
    )


def _export_discord(deck, cards, grupos_por_tipo):
    """Exporta deck em formato Markdown otimizado para Discord.

    Usa code blocks para formatação fixa, emojis para categorias,
    e layout compacto que funciona bem no Discord.
    """
    ORDEM_TIPOS = [
        ('Character', '👤', 'Characters'),
        ('Ally', '🤝', 'Allies'),
        ('Enemy', '👹', 'Enemies'),
        ('Victim', '🎯', 'Victims'),
        ('Gift', '✨', 'Gifts'),
        ('Equipment', '⚔️', 'Equipment'),
        ('Caern', '🏔️', 'Caerns'),
        ('Territory', '🗺️', 'Territories'),
        ('Quest', '📜', 'Quests'),
        ('Rite', '🔥', 'Rites'),
        ('Event', '🌟', 'Events'),
        ('Action', '⚡', 'Actions'),
        ('Moot', '🗳️', 'Moots'),
        ('Board Meeting', '🏛️', 'Board Meetings'),
        ('Combat Action', '🗡️', 'Combat Actions'),
        ('Combat Event', '💥', 'Combat Events'),
        ('Battlefield', '🏟️', 'Battlefields'),
        ('Past Life', '🔮', 'Past Lives'),
        ('Realm', '🌌', 'Realms'),
    ]

    lines = []

    # Cabeçalho
    lines.append(f'# {deck.name or "Untitled Deck"}')
    if deck.description:
        lines.append(f'*{deck.description}*')
    lines.append('')

    # Stats do deck
    total_chars = sum(e['quantity'] for e in cards if 'Character' in (e['card'].tipo or ''))
    total_combat = sum(e['quantity'] for e in cards if 'combat' in (e['card'].tipo or '').lower())
    total_sept = sum(e['quantity'] for e in cards if 'combat' not in (e['card'].tipo or '').lower() and 'Character' not in (e['card'].tipo or ''))
    total_cards = sum(e['quantity'] for e in cards)

    lines.append(f'**📊 Stats:** {total_cards} cards | 👤 {total_chars} characters | 🗡️ {total_combat} combat | 📦 {total_sept} sept')
    lines.append('')
    lines.append('---')
    lines.append('')

    # Cartas por tipo
    for tipo_raw, emoji, tipo_label in ORDEM_TIPOS:
        grupo = grupos_por_tipo.get(tipo_raw, [])
        if not grupo:
            continue

        lines.append(f'**{emoji} {tipo_label} ({len(grupo)} types, {sum(e["quantity"] for e in grupo)} cards)**')
        lines.append('')

        for entry in sorted(grupo, key=lambda x: x['card'].name):
            card = entry['card']
            qty = entry['quantity']
            stats = _card_stats_short(card)

            # Formatar nome com stats
            nome = card.name
            if stats:
                nome += f' *({stats})*'

            # Quantidade
            if qty > 1:
                lines.append(f'`{qty}x` {nome}')
            else:
                lines.append(f'• {nome}')

        lines.append('')

    # Tipos remanescentes
    tipos_cobertos = {t[0] for t in ORDEM_TIPOS}
    for tipo in sorted(grupos_por_tipo):
        if tipo not in tipos_cobertos:
            grupo = grupos_por_tipo[tipo]
            lines.append(f'**📦 {tipo} ({len(grupo)} types)**')
            lines.append('')
            for entry in sorted(grupo, key=lambda x: x['card'].name):
                card = entry['card']
                qty = entry['quantity']
                stats = _card_stats_short(card)
                nome = card.name
                if stats:
                    nome += f' *({stats})*'
                if qty > 1:
                    lines.append(f'`{qty}x` {nome}')
                else:
                    lines.append(f'• {nome}')
            lines.append('')

    lines.append('---')
    lines.append(f'*Exportado do Rage CCG Web*')

    text = '\n'.join(lines)
    nome_arquivo = f'{_sanitize_filename(deck.name) or "deck"}_discord.md'
    return current_app.response_class(
        text,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename={nome_arquivo}'}
    )


def _export_xml(deck, grupos_por_tipo):
    """Exporta deck como XML .dek (LackeyCCG)."""
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    root = ET.Element('deck')
    meta = ET.SubElement(root, 'meta')
    ET.SubElement(meta, 'title').text = deck.name or ''
    ET.SubElement(meta, 'format').text = 'Rage CCG'

    for tipo, grupo_cards in grupos_por_tipo.items():
        sz = ET.SubElement(root, 'superzone')
        ET.SubElement(sz, 'name').text = tipo
        for entry in grupo_cards:
            card = entry['card']
            qty = entry['quantity']
            for _ in range(qty):
                ce = ET.SubElement(sz, 'card')
                ET.SubElement(ce, 'name').text = card.name or ''
                if card.expansion:
                    ET.SubElement(ce, 'set').text = card.expansion

    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent='  ')
    nome_arquivo = f'{_sanitize_filename(deck.name) or "deck"}.dek'
    return current_app.response_class(
        xml_str,
        mimetype='application/xml',
        headers={'Content-Disposition': f'attachment; filename={nome_arquivo}'}
    )


@bp.get('/<id>/search-cards')
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
