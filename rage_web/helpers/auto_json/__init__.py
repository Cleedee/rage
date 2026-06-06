"""Sistema de crafting automatizado de JSON de efeitos.

Gera modelos JSON para cartas do banco de dados que ainda não têm
efeitos estruturados no motor de jogo.

Uso:
    from rage_web.helpers.auto_json import craft_card, craft_deck_cards
    modelo = craft_card(card_id=1234)
    modelos = craft_deck_cards(deck_id=643)
"""
from rage_web.helpers.auto_json.crafter import craft_card, craft_deck_cards, craft_all_missing
