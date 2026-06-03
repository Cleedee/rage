def test_home_page(client):
    """A página inicial deve carregar e conter elementos do layout base."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Rage CCG" in response.data
    assert b"Home" in response.data
    assert b"Gerenciador de cartas" in response.data


def test_cards_search(client, sample_card):
    """A listagem de cartas deve mostrar as cartas cadastradas."""
    # Busca especificamente pela carta de teste
    response = client.get(f'/cards/search?q=Test+Card')
    assert response.status_code == 200
    assert b"Test Card" in response.data
    assert b"Character" in response.data


def test_cards_search_empty(client):
    """A listagem de cartas sem cartas deve funcionar."""
    response = client.get('/cards/search')
    assert response.status_code == 200


def test_cards_new_menu(client):
    """O menu de nova carta deve mostrar as opções disponíveis."""
    response = client.get('/cards/new')
    assert response.status_code == 200
    assert b"New Card" in response.data
    assert b"Character" in response.data
    assert b"Equipment" in response.data
    assert b"Card" in response.data


def test_cards_new_character_form(client):
    """O formulário de nova carta Character deve carregar."""
    response = client.get('/cards/new-character')
    assert response.status_code == 200
    assert b"Register Character Card" in response.data
    assert b"Name" in response.data
    assert b"Rage" in response.data
    assert b"Gnosis" in response.data
    assert b"Health" in response.data
    assert b"Text" in response.data


def test_cards_new_equipment_form(client):
    """O formulário de nova carta Equipment deve carregar."""
    response = client.get('/cards/new-equipment')
    assert response.status_code == 200
    assert b"Register Equipment Card" in response.data
    assert b"Name" in response.data
    assert b"Gnosis" in response.data
    assert b"Requires" in response.data
    assert b"Text" in response.data


def test_cards_new_card_form(client):
    """O formulário de nova carta genérica deve carregar."""
    response = client.get('/cards/new-card')
    assert response.status_code == 200
    assert b"Register Card" in response.data
    assert b"Name" in response.data
    assert b"Type" in response.data
    assert b"Text" in response.data


def test_cards_create_character(client):
    """Criar uma carta Character via POST deve funcionar."""
    response = client.post('/cards/new-character', data={
        'name': 'New Character',
        'tipo': 'Character',
        'rage': 5,
        'gnosis': 3,
        'health': 7,
        'text': 'A powerful character',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Personagem salvo" in response.data or b"salvo" in response.data


def test_cards_create_equipment(client):
    """Criar uma carta Equipment via POST deve funcionar."""
    response = client.post('/cards/new-equipment', data={
        'name': 'Sword of Power',
        'tipo': 'Equipment',
        'gnosis': 4,
        'requires': 'Gnosis 2',
        'text': 'A mighty weapon',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Equipamento salvo" in response.data or b"salvo" in response.data


def test_cards_view_card(client, sample_card):
    """A página de visualização da carta deve carregar."""
    response = client.get(f'/cards/{sample_card}/view')
    assert response.status_code == 200
    assert b"Test Card" in response.data
    assert b"Character" in response.data
    assert b"Rage" in response.data
    assert b"Editar" in response.data
    assert b"Excluir" in response.data


def test_cards_view_card_not_found(client):
    """Carta inexistente na view deve retornar 404."""
    response = client.get('/cards/99999/view')
    assert response.status_code == 404


def test_cards_read_card(client, sample_card):
    """Visualizar uma carta existente deve mostrar seus dados."""
    response = client.get(f'/cards/card/{sample_card}')
    assert response.status_code == 200
    assert b"Test Card" in response.data


def test_cards_read_card_not_found(client):
    """Visualizar uma carta inexistente deve retornar 404."""
    response = client.get('/cards/card/9999')
    assert response.status_code == 404


def test_cards_delete_card(client, sample_card):
    """Excluir uma carta deve funcionar e redirecionar."""
    response = client.get(f'/cards/delete-card/{sample_card}', follow_redirects=True)
    assert response.status_code == 200
    assert b"Card exclu" in response.data


def test_decks_search(client, sample_deck):
    """A listagem de decks deve mostrar os decks cadastrados."""
    response = client.get('/decks/search')
    assert response.status_code == 200
    assert b"Test Deck" in response.data


def test_decks_search_empty(client):
    """A listagem de decks sem decks deve funcionar."""
    response = client.get('/decks/search')
    assert response.status_code == 200


def test_decks_new_form(client):
    """O formulário de novo deck deve carregar."""
    response = client.get('/decks/new')
    assert response.status_code == 200
    assert b"Deck" in response.data
    assert b"Name" in response.data
    assert b"Description" in response.data


def test_decks_create(client):
    """Criar um deck via POST deve funcionar."""
    response = client.post('/decks/deck', data={
        'name': 'My New Deck',
        'description': 'A brand new deck',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Deck salvo" in response.data or b"salvo" in response.data


def test_decks_read_deck(client, sample_deck):
    """Visualizar um deck existente deve mostrar seus dados."""
    response = client.get(f'/decks/deck/{sample_deck}')
    assert response.status_code == 200
    assert b"Test Deck" in response.data


def test_decks_delete_deck(client, sample_deck):
    """Excluir um deck deve funcionar e redirecionar."""
    response = client.get(f'/decks/delete_deck/{sample_deck}', follow_redirects=True)
    assert response.status_code == 200
    assert b"Deck removido" in response.data
