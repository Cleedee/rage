"""Testes do content_hash (identificação de decks por conteúdo)."""

import pytest

from rage_web.ext.repository import (deck_add_card, deck_content_hash,
                                     deck_get_cards, deck_remove_card,
                                     deck_update_quantity, hash_conteudo)
from rage_web.ext.database import db
from rage_web.models.card import Card
from rage_web.models.deck import Deck


@pytest.fixture
def cartas(app):
    """Cria 2 cartas de teste e devolve seus ids."""
    with app.app_context():
        c1 = Card(name="Carta A", tipo="Character", rage=3, health=5)
        c2 = Card(name="Carta B", tipo="Gift", gnosis=2)
        db.session.add_all([c1, c2])
        db.session.flush()
        ids = (c1.id, c2.id)
        db.session.commit()
        return ids


# ── Função pura ──────────────────────────────────────────────────────

def test_hash_conteudo_ignora_ordem():
    a = hash_conteudo([(10, 2), (5, 1)])
    b = hash_conteudo([(5, 1), (10, 2)])
    assert a == b


def test_hash_conteudo_depende_de_quantidade():
    assert hash_conteudo([(10, 2)]) != hash_conteudo([(10, 3)])
    assert hash_conteudo([(10, 2), (5, 1)]) != hash_conteudo([(10, 2)])


def test_hash_conteudo_deterministico_e_hex():
    h = hash_conteudo([(1, 1), (2, 3)])
    assert h == hash_conteudo([(1, 1), (2, 3)])
    assert len(h) == 64
    assert all(c in '0123456789abcdef' for c in h)


# ── Repositório: recomputação nas mutações ──────────────────────────

def test_deck_add_card_calcula_hash(app, cartas):
    with app.app_context():
        deck = Deck(name="Deck Hash")
        db.session.add(deck)
        db.session.flush()
        deck_id = deck.id
        db.session.commit()

        deck = db.session.get(Deck, deck_id)
        deck_add_card(deck, db.session.get(Card, cartas[0]), 2)
        h1 = db.session.get(Deck, deck_id).content_hash
        assert len(h1) == 64

        deck_add_card(deck, db.session.get(Card, cartas[1]), 1)
        h2 = db.session.get(Deck, deck_id).content_hash
        assert h2 != h1
        assert h2 == hash_conteudo([(cartas[0], 2), (cartas[1], 1)])


def test_deck_update_quantity_recalcula(app, cartas):
    with app.app_context():
        deck = Deck(name="Deck Qtd")
        db.session.add(deck)
        db.session.flush()
        deck_id = deck.id
        db.session.commit()

        deck = db.session.get(Deck, deck_id)
        deck_add_card(deck, db.session.get(Card, cartas[0]), 1)
        h1 = db.session.get(Deck, deck_id).content_hash

        deck_update_quantity(deck, db.session.get(Card, cartas[0]), 4)
        h2 = db.session.get(Deck, deck_id).content_hash
        assert h2 != h1
        assert h2 == hash_conteudo([(cartas[0], 4)])


def test_deck_remove_card_recalcula(app, cartas):
    with app.app_context():
        deck = Deck(name="Deck Remove")
        db.session.add(deck)
        db.session.flush()
        deck_id = deck.id
        db.session.commit()

        deck = db.session.get(Deck, deck_id)
        deck_add_card(deck, db.session.get(Card, cartas[0]), 1)
        deck_add_card(deck, db.session.get(Card, cartas[1]), 1)

        deck_remove_card(deck, db.session.get(Card, cartas[1]))
        h = db.session.get(Deck, deck_id).content_hash
        assert h == hash_conteudo([(cartas[0], 1)])


def test_decks_identicos_tem_mesmo_hash(app, cartas):
    """Dois decks com as mesmas cartas/quantidades têm o mesmo hash."""
    with app.app_context():
        d1 = Deck(name="Deck X")
        d2 = Deck(name="Deck Y")
        db.session.add_all([d1, d2])
        db.session.flush()
        ids = (d1.id, d2.id)
        db.session.commit()

        for did in ids:
            deck = db.session.get(Deck, did)
            deck_add_card(deck, db.session.get(Card, cartas[0]), 3)
            deck_add_card(deck, db.session.get(Card, cartas[1]), 2)

        h1 = db.session.get(Deck, ids[0]).content_hash
        h2 = db.session.get(Deck, ids[1]).content_hash
        assert h1 == h2


def test_decks_diferentes_tem_hash_diferente(app, cartas):
    with app.app_context():
        d1 = Deck(name="Deck P")
        d2 = Deck(name="Deck Q")
        db.session.add_all([d1, d2])
        db.session.flush()
        ids = (d1.id, d2.id)
        db.session.commit()

        deck1 = db.session.get(Deck, ids[0])
        deck_add_card(deck1, db.session.get(Card, cartas[0]), 2)
        deck_add_card(deck1, db.session.get(Card, cartas[1]), 1)
        deck2 = db.session.get(Deck, ids[1])
        deck_add_card(deck2, db.session.get(Card, cartas[0]), 2)

        h1 = db.session.get(Deck, ids[0]).content_hash
        h2 = db.session.get(Deck, ids[1]).content_hash
        assert h1 != h2


def test_deck_content_hash_casamento_com_pure(app, cartas):
    """deck_content_hash == hash_conteudo sobre o mesmo conteúdo."""
    with app.app_context():
        deck = Deck(name="Deck Match")
        db.session.add(deck)
        db.session.flush()
        deck_id = deck.id
        db.session.commit()

        deck = db.session.get(Deck, deck_id)
        deck_add_card(deck, db.session.get(Card, cartas[1]), 5)
        deck_add_card(deck, db.session.get(Card, cartas[0]), 1)

        got = deck_content_hash(deck_id)
        assert got == hash_conteudo([(cartas[0], 1), (cartas[1], 5)])
        assert got == db.session.get(Deck, deck_id).content_hash
