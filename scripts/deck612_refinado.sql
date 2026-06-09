-- Ajuste do Deck 612 - Aliança de Prata Refinado (Ren30)
-- Data: 2026-06-08
-- 
-- Problemas corrigidos:
-- 1. Gifts sem cobertura: Silver Claws (x3→x2), Spirit of the Fray (x2→x1)
-- 2. Sem presas: adicionadas 4 Victims para VP farming
-- 3. Combat actions fracas: removidas Stinging Wound, Surprise Attack, Wild Flailing
-- 4. Equipment Wyrm: removidos Gooshy Gooze, Skin of Hellbound
-- 5. Territory sem sinergia: Dead Zone, Naysayer's Hovel mantidos (controle)
-- 6. Eventos não Gaia: removidos Beast-of-War (BSD), Mass Pollution (Wyrm)
--
-- Resultado: 74 cartas, Renome 30/30, Sept 30≥30, Combat 41≥20

-- Limpar deck existente
DELETE FROM deck_cards WHERE deck_id = 612;

-- Personagens (4 = 30 renome)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 167, 1);  -- King Albrecht (rn13)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 176, 1);  -- Lord Albrecht (rn7)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 31, 1);   -- Amanda Withers-in-Sun (rn5)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 15, 1);   -- Conrad Walks-the-Line (rn5)

-- Aliados (1) - boost
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 414, 1);  -- Angus MacRory (rn4)

-- Presas (4) - VP farming para Gaia pack
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 568, 2);  -- Wild Animals x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 565, 1);  -- Vigilante x1
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 558, 1);  -- Unlucky Lune x1

-- Ações (4)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 790, 2);  -- Friends in High Places x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 807, 2);  -- Sneak Attack x2

-- Combat Actions (41) - melhorado
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 286, 2);   -- Bite x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 289, 2);   -- Block and Strike x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 290, 2);   -- Body Blow x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 293, 2);   -- Brutal Kick x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1272, 2);  -- Disarm x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 312, 2);   -- Dodge x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 317, 2);   -- Evasion x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 321, 2);   -- Feint x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1283, 2);  -- Massive Wound x2 (NOVO!)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1328, 2);  -- Head Butt x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1274, 2);  -- Jaw Breaker x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1278, 2);  -- Low Blow x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1279, 2);  -- Lucky Blow x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1296, 2);  -- Reckless Swing x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1303, 2);  -- Run Like Hell x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1531, 2);  -- Strike x2 (NOVO!)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 283, 2);   -- Battle Fervor x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 112, 2);   -- Frenzy x2

-- Combat Events (2)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 114, 2);   -- Gang Beating x2

-- Equipment (6) - melhorado
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 630, 2);   -- Chronicle of the Black Labyrinth x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 720, 1);   -- Whip of the Wicked x1
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1722, 1);  -- Combat Reflexes x1
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1324, 2);  -- Umbral Escape x2

-- Eventos (6) - corrigidos
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 875, 2);   -- Iron Will x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 902, 2);   -- Red Alert x2
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 887, 2);   -- Fury of Gaia x2 (NOVO!)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 905, 3);   -- The Weaver's Gift x3 (NOVO!)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 818, 2);   -- Beast-of-War x2

-- Gifts (6) - cobertura 100%
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 927, 2);   -- Awe x2 (Amanda + King)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 988, 2);   -- Inspiration x2 (todos 4)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1052, 2);  -- Silver Claws x2 (todos 4)
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (612, 1056, 1);  -- Spirit of the Fray x1 (King+Lord+Conrad)

-- Atualizar descrição
UPDATE deck SET description = 'Aliança de Prata Refinado (Ren30): Silver Fang Leadership com gifts corretos, Victims para VP farming, combat actions otimizadas. 74 cartas.' WHERE id = 612;
