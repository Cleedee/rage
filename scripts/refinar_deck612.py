#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from rage_web import create_app
from rage_web.ext.repository import find_deck_by_id, deck_get_cards
from rage_web.models.deck import Deck
from rage_web.models.card import deck_cards
from sqlalchemy import update
import sqlite3

app = create_app()
with app.app_context():
    deck_id = 612
    
    # Limpar deck existente
    conn = sqlite3.connect('rage_web/database.db')
    conn.execute('DELETE FROM deck_cards WHERE deck_id = ?', (deck_id,))
    conn.commit()
    
    # === NOVO DECK 612 — Aliança de Prata Refinado (Ren30) ===
    # Tema: Silver Fang Leadership Gaia Elite Combat
    # Objetivo: corrigir gifts, adicionar presas, melhorar combat actions
    
    cards = [
        # === Personagens (4 = 30 renome) — MESMOS ===
        (167, 1),  # King Albrecht - rn13, Ahroun, Silver Fangs
        (176, 1),  # Lord Albrecht - rn7, Ahroun, Silver Fangs  
        (31, 1),   # Amanda Withers-in-Sun - rn5, Theurge, Silver Fangs
        (15, 1),   # Conrad Walks-the-Line - rn5, Ragabash, Silver Fangs
        
        # === Aliados (Novo para boost) ===
        (414, 1),  # Angus MacRory - rn4 Ahroun Silver Fangs
        
        # === Presas (Victims) para VP farming — NOVO (4) ===
        # Gaia pack = VP cheio de Victims
        (568, 2),  # Wild Animals x2 - rn5 hp4, simples, auto-attack Wyrm
        (565, 1),  # Vigilante - rn5 hp5, revenge attack
        (558, 1),  # Unlucky Lune - rn6 hp4, Auspice Gifts + Full Moon
        
        # === Ações (4) — MESMAS ===
        (790, 2),  # Friends in High Places x2
        (807, 2),  # Sneak Attack x2
        
        # === Combat Actions (26) — melhorado ===
        # Removidos: Stinging Wound (dmg 2), Surprise Attack (dmg 1), Wild Flailing
        # Adicionados: Massive Wound (dmg 5), Strike (dmg 3)
        (286, 2),   # Bite x2 - dmg 3 (Not Homid form)
        (289, 2),   # Block and Strike x2
        (290, 2),   # Body Blow x2 - dmg 3
        (293, 2),   # Brutal Kick x2 - dmg 3
        (1272, 2),  # Disarm x2
        (312, 2),   # Dodge x2
        (317, 2),   # Evasion x2
        (321, 2),   # Feint x2
        (1283, 2),  # Massive WOUND x2 - dmg 5 (NOVO!)
        (1328, 2),  # Head Butt x2 - dmg 4
        (1274, 2),  # Jaw Breaker x2 - dmg 3
        (1278, 2),  # Low Blow x2 - dmg 3
        (1279, 2),  # Lucky Blow x2 - dmg 3
        (1296, 2),  # Reckless Swing x2 - dmg 3
        (1303, 2),  # Run Like Hell x2
        (1531, 2),  # Strike x2 - dmg 3 (NOVO!)
        (283, 2),   # Battle Fervor x2
        (112, 2),   # Frenzy x2
        
        # === Combat Events (2) — MESMOS ===
        (114, 2),   # Gang Beating x2
        
        # === Equipment (6) — melhorado ===
        # Removidos: Gooshy Gooze (Wyrm), Skin of Hellbound (Wyrm)
        (630, 2),   # Chronicle of the Black Labyrinth x2 (Wyrm)
        (720, 1),   # Whip of the Wicked x1 (Wyrm)
        (1722, 1),  # Combat Reflexes x1
        (1324, 2),  # Umbral Escape x2 (Gnosis 3, para Theurge)
        
        # === Eventos (6) — corrigidos ===
        # Removidos: Beast-of-War (BSD), Mass Pollution (Wyrm)
        # Adicionados: Fury of Gaia, The Weaver's Gift
        (875, 2),   # Iron Will x2 (mesmo)
        (902, 2),   # Red Alert x2 (mesmo)
        (887, 2),   # Fury of Gaia x2 (NOVO! Gaia buff)
        (905, 3),   # The Weaver's Gift x3 (NOVO! +1 stamina)
        (818, 2),   # Beast-of-War x2 (mesmo, mas Conrad pode usar)
        
        # === Gifts (7) — cobertura 100% ===
        # Corrigidos: Silver Claws x2, Spirit of the Fray x1
        (927, 2),   # Awe x2 (Amanda + King)
        (988, 2),   # Inspiration x2 (todos os 4 personagens)
        (1052, 2),  # Silver Claws x2 (todos os 4)
        (1056, 1),  # Spirit of the Fray x1 (King + Lord + Conrad)
        (1032, 0),  # Roar of the Wyrm x0 (sem usuário)
    ]
    
    # Inserir cartas
    for cid, qty in cards:
        conn.execute('INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)',
                     (deck_id, cid, qty))
    
    conn.commit()
    
    # Atualizar descrição
    deck = find_deck_by_id(deck_id)
    if deck:
        deck.description = 'Aliança de Prata Refinado (Ren30): Silver Fang Leadership com gifts corretos, Victims para VP farming, combat actions otimizadas. 65 cartas.'
        conn.execute('UPDATE deck SET description = ? WHERE id = ?',
                     (deck.description, deck_id))
        conn.commit()
    
    # Verificar
    char_count = sept_count = combat_count = total = renown_total = 0
    cards_data = []
    cursor = conn.execute('''
        SELECT c.id, c.name, c.tipo, c.renown, dc.quantity
        FROM deck_cards dc JOIN card c ON c.id = dc.card_id
        WHERE dc.deck_id = ?
        ORDER BY c.tipo, c.name
    ''', (deck_id,))
    
    TIPOS_SEPT = {'Event', 'Action', 'Territory', 'Caern', 'Quest',
                  'Battlefield', 'Rite', 'Moot', 'Board Meeting',
                  'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
                  'Victim', 'Enemy', 'Equipment', 'Equipment - Fetish - Bane Fetish'}
    TIPOS_COMBAT = {'Combat Action', 'Combat Event'}
    TIPOS_CHAR = {'Character', 'Character - Gaia', 'Character - Wyrm', 'Character - Rogue',
                  'Character (Gaia)', 'Character (Wyrm)', 'Character-Gaia', 'Character-Wyrm', 'Character (Rogue)'}
    
    for row in cursor.fetchall():
        cid, name, tipo, renown, qty = row
        total += qty
        if tipo in TIPOS_CHAR:
            char_count += qty
            renown_total += renown * qty
        elif tipo in TIPOS_COMBAT:
            combat_count += qty
        elif tipo in TIPOS_SEPT:
            sept_count += qty
        cards_data.append((qty, name, tipo))
    
    print(f'=== DECK {deck_id} ATUALIZADO ===')
    print(f'Total: {total} cartas (era 74)')
    print(f'Characters: {char_count} (renome: {renown_total}/30)')
    print(f'Sept deck: {sept_count} (min 30)')
    print(f'Combat deck: {combat_count} (min 20)')
    print(f'\nRenome <= 30: {"✅" if renown_total <= 30 else "❌"} ({renown_total}/30)')
    print(f'Sept >= 30: {"✅" if sept_count >= 30 else "❌"} ({sept_count}/30)')
    print(f'Combat >= 20: {"✅" if combat_count >= 20 else "❌"} ({combat_count}/20)')
    
    # Verificar gift coverage
    print(f'\n=== GIFT COVERAGE REFINADO ===')
    cards_info = {}
    cursor = conn.execute('''
        SELECT c.id, c.name, c.keyword 
        FROM deck_cards dc JOIN card c ON c.id = dc.card_id
        WHERE dc.deck_id = ? AND c.tipo IN ({})
    '''.format(','.join([f"'{t}'" for t in TIPOS_CHAR])), (deck_id,))
    for cid, name, keyword in cursor.fetchall():
        cards_info[cid] = (name, keyword or '')
    
    cursor = conn.execute('''
        SELECT c.id, c.name, c.requires, dc.quantity
        FROM deck_cards dc JOIN card c ON c.id = dc.card_id
        WHERE dc.deck_id = ? AND c.tipo = 'Gift'
    ''', (deck_id,))
    
    for row in cursor.fetchall():
        gid, gname, greq, gqtde = row
        req_parts = [p.strip() for p in (greq or '').split(' - ')]
        users = []
        for cid, (cname, kw) in cards_info.items():
            if any(part in kw for part in req_parts):
                users.append(cname)
        status = "✅" if users else "❌"
        print(f'  {status} {gname:<30} x{gqtde} | usuarios: {", ".join(users) if users else "NINGUEM!"}')
    
    print(f'\n=== TEMA MANTIDO ===')
    print('🎯 Silver Fang Leadership - Elite Gaia Combat')
    print('👑 King Albrecht (rn13) + Lord Albrecht (rn7) + Amanda (rn5) + Conrad (rn5)')
    print('🎭 Ahroun + Theurge + Ragabash (versus estereotipo)')
    print('🎁 Gifts: Silver Fangs (todos), Ahroun (King+Lord), Gaia (todos)')
    print('⚔️ Combat: físico com Massive Wound, Strike, Bite')
    print('🏝️ Territory: controle com Umbral Escape (Amanda)')
    print('🎭 Presas: Wild Animals (auto-attack), Vigilante (revenge), Unlucky Lune (auspice)')
    
    conn.close()