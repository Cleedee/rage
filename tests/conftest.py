import pytest

from rage_web import create_app
from rage_web.ext.database import db as _db
from rage_web.models.card import Card
from rage_web.models.deck import Deck
from rage_web.models.picture import Picture


@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })

    with app.app_context():
        _db.create_all()

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def sample_card(app):
    with app.app_context():
        card = Card(name="Test Card", tipo="Character", rage=3, gnosis=2, health=5)
        _db.session.add(card)
        _db.session.flush()
        card_id = card.id
        _db.session.commit()
        return card_id


@pytest.fixture()
def sample_deck(app):
    with app.app_context():
        deck = Deck(name="Test Deck", description="A test deck")
        _db.session.add(deck)
        _db.session.flush()
        deck_id = deck.id
        _db.session.commit()
        return deck_id
