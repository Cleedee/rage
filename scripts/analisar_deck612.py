#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from rage_web import create_app
from rage_web.ext.repository import find_deck_by_id, deck_get_cards

app = create_app()
with app.app_context():
    deck_id = 612
    deck = find_deck_by_id(deck_id)
    if not deck:
        print(f"Deck {deck_id} não encontrado")
        exit(1)

    print(f'=== Deck {deck_id}: {deck.name} ===')
    print(f'Desc: {deck.description}\n')

    # Obter cartas do deck
    deck_cards_data = deck_get_cards(deck)

    TIPOS_SEPT = {'Event', 'Action', 'Territory', 'Caern', 'Quest',
                  'Battlefield', 'Rite', 'Moot', 'Board Meeting',
                  'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
                  'Victim', 'Enemy', 'Equipment', 'Equipment - Fetish - Bane Fetish'}
    TIPOS_COMBAT = {'Combat Action', 'Combat Event'}
    TIPOS_CHAR = {'Character', 'Character - Gaia', 'Character - Wyrm', 'Character - Rogue',
                  'Character (Gaia)', 'Character (Wyrm)', 'Character-Gaia', 'Character-Wyrm', 'Character (Rogue)'}

    char_count = sept_count = combat_count = total = renown_total = 0
    chars_info = {}

    print('=== CARTAS DO DECK ===')
    for data in deck_cards_data:
        card = data['card']
        qty = data['quantity']
        total += qty
        if card.tipo in TIPOS_CHAR:
            char_count += qty
            renown_total += card.renown * qty
            chars_info[card.id] = (card.name, card.keyword)
        elif card.tipo in TIPOS_COMBAT:
            combat_count += qty
        elif card.tipo in TIPOS_SEPT:
            sept_count += qty
        
        stats = f'r={card.rage} g={card.gnosis} h={card.health} rn={card.renown}' if (card.rage or card.gnosis or card.health or card.renown) else ''
        costs = f' dmg={card.damage}' if card.damage else ''
        req = f' req={card.requires[:30]}' if card.requires else ''
        print(f'  x{qty} #{card.id} {card.name:<40} {stats}{costs}{req}')

    print(f'\n=== RESUMO ===')
    print(f'Total: {total} cartas')
    print(f'Characters: {char_count} (renome total: {renown_total})')
    print(f'Sept deck: {sept_count}')
    print(f'Combat deck: {combat_count}')
    print(f'\nRegras:')
    print(f'  Renome <= 30: {"✅" if renown_total <= 30 else "❌"} ({renown_total}/30)')
    print(f'  Sept >= 30: {"✅" if sept_count >= 30 else "❌"} ({sept_count}/30)')
    print(f'  Combat >= 20: {"✅" if combat_count >= 20 else "❌"} ({combat_count}/20)')

    # Analisar gifts
    gifts = [data for data in deck_cards_data if data['card'].tipo == 'Gift']
    print(f'\n=== GIFT COVERAGE ===')
    for data in gifts:
        card = data['card']
        qty = data['quantity']
        req_parts = [p.strip() for p in (card.requires or '').split(' - ')]
        users = []
        for cid, (cname, kw) in chars_info.items():
            if any(part in kw for part in req_parts):
                users.append(cname)
        print(f'  {card.name:<30} x{qty} | usuarios: {", ".join(users) if users else "🔴 NINGUEM!"}')

    # Identificar o tema
    print(f'\n=== ANÁLISE DE TEMA ===')
    print('🎯 Tema: Silver Fang Leadership - Gaia Elite Combat')
    print('👑 Personagens: King Albrecht (rn13), Lord Albrecht (rn7), Amanda (rn5)')
    print('🎭 Classes: Ahroun (King), Theurge (Amanda), Ragabash (Conrad)')
    print('🎁 Gifts: Silver Fangs, Ahroun, Silver Claws, Spirit of the Fray')
    print('⚔️ Focus: Combat actions físicas (Bite, Brutal Kick, Wild Flailing)')
    print('🏝️ Territory: Dead Zone, Naysayer\'s Hovel (controle + debuff)')

    # Problemas identificados
    print(f'\n=== PROBLEMAS IDENTIFICADOS ===')
    print('1. ❌ Gifts sem cobertura:')
    print('   - Silver Claws x3 (só King Albrecht usa)')
    print('   - Spirit of the Fray x2 (só King Albrecht usa)')
    print('   - Awe x2 (só Amanda usa)')
    
    print('\n2. ❌ Combat actions fracas:')
    print('   - Stinging Wound (dmg 2)')
    print('   - Surprise Attack (dmg 1)')
    print('   - Wild Flailing (dmg 3, mas sem estratégia)')
    
    print('\n3. ❌ Territory sem sinergia:')
    print('   - Dead Zone (Wyrm, deck é Gaia)')
    print('   - Naysayer\'s Hovel (controle, sem combo)')
    
    print('\n4. ❌ Falta de presas para VP farming')
    print('   - 0 Victims/Enemies deck é Gaia')
    
    print('\n5. ❌ Eventos sem sinergia')
    print('   - Beast-of-War (Black Spiral Dancer)')
    print('   - Mass Pollution (Wyrm deck)')
    print('   - Red Alert (sem estratégia de combo)')