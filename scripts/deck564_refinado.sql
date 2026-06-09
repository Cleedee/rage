-- Ajuste do Deck 564 - Drain Team Refinado (Ren30)
-- Data: 2026-06-08
-- 
-- Problemas corrigidos:
-- 1. Gifts sem cobertura: Consumption of Gaia (x3→x1), Roar of the Wyrm (x3→x1)
-- 2. Sem presas: adicionadas 6 Victims para VP farming
-- 3. Combat actions fracas: removidas Stinging Wound, Surprise Attack, Head Wound
-- 4. Equipment excessivo: Chronicle (x3→x1), Gooshy Gooze (x3→x1)
--
-- Resultado: 62 cartas, Renome 30/30, Sept 32≥30, Combat 25≥20

-- Limpar deck existente
DELETE FROM deck_cards WHERE deck_id = 564;

-- Personagens (5 = 30 renome)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 18, 1);   -- Count Vladimir Rustovitch (rn10)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 29, 1);   -- Allonzo Montoya (rn9)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 67, 1);   -- Fek (rn6)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 47, 1);   -- Blossom (rn4)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 161, 1);  -- Juicy Johnes (rn1)

-- Aliados (3)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 400, 1);  -- Experimental Fomori
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 430, 2);  -- Pentex Executive x2

-- Presas (6) - NOVO: VP farming para Wyrm pack
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 568, 2);  -- Wild Animals x2 (auto-attack Wyrm)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 565, 2);  -- Vigilante x2 (revenge attack)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 558, 1);  -- Unlucky Lune (Auspice Gifts + Full Moon)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 503, 1);  -- Mage of Celestial Chorus (ANY Gifts + removal)

-- Ações (4)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 790, 2);  -- Friends in High Places x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 807, 2);  -- Sneak Attack x2

-- Combat Actions (22) - melhorado
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1722, 1); -- Combat Reflexes
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 312, 2);  -- Dodge x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 313, 2);  -- Dry Gulch x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 317, 2);  -- Evasion x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1328, 2); -- Head Butt x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1280, 2); -- Maim x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1283, 2); -- Massive Wound x2 (NOVO)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1289, 2); -- Overextended Attack x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1296, 2); -- Reckless Swing x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1303, 2); -- Run Like Hell x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1308, 2); -- Septum Crushed x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1326, 2); -- Vital Blow x2

-- Combat Events (2)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 114, 2);  -- Gang Beating x2

-- Equipment (7) - reduzido
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 697, 3);  -- Skin of the Hellbound x3
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 720, 1);  -- Whip of the Wicked x1
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 630, 1);  -- Chronicle x1 (era x3)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 305, 1);  -- Gooshy Gooze x1 (era x3)

-- Eventos (4) - reduzido
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 885, 2);  -- Mass Pollution x2 (era x3)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 840, 1);  -- Eater-of-Souls x1 (era x2)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 913, 1);  -- The Dark Fungus x1

-- Gifts (9) - cobertura 100%
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 100, 1);  -- Consumption of Gaia x1 (era x3, só Vladimir)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1032, 1); -- Roar of the Wyrm x1 (era x3, só Fek)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 986, 2);  -- Infectious Touch x2 (era x3, Fek+Blossom)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 1488, 2); -- Arms of the Abyss x2 (Vladimir+Allonzo)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 935, 1);  -- Benefactor's Boon x1 (era x2)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (564, 109, 2);  -- Disquiet x2 (4 personagens)

-- Atualizar descrição
UPDATE deck SET description = 'Drain Team Refinado (Ren30): gifts com cobertura 100%, Victims para VP farming, combat actions otimizadas. 62 cartas.' WHERE id = 564;
