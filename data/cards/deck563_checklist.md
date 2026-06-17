# Deck 563 — Deck 563

Gerado automaticamente em 17/06/2026 21:52

## Checklist de Cartas

| ID | Nome | Tipo | Qty | JSON | Deck fonte | Efeitos no JSON |
|---|---|---|---|---|---|---|
| **Action** | | | | | | |
| 790 | Friends in High Places | Action | 3 | ✅ | friends-in-high-places_thewyrm.json | 1 |
| 807 | Sneak Attack | Action | 3 | ✅ | sneak-attack.json | 1 |
| **Ally** | | | | | | |
| 430 | Pentex Executive and Limousine | Ally | 1 | ✅ | pentex-executive-and-limousine_r8.json | 0 |
| **Character** | | | | | | |
| 18 | Count Vladimir Rustovitch | Character - Wyrm | 1 | ✅ | count-vladimir-rustovitch_r10.json | 0 |
| 29 | Allonzo Montoya | Character - Wyrm | 1 | ✅ | allonzo-montoya_r9.json | 0 |
| 161 | Juicy Johnes | Character - Wyrm | 1 | ✅ | juicy-johnes_r1.json | 0 |
| **Combat Action** | | | | | | |
| 312 | Dodge | Combat Action | 2 | ✅ | dodge.json | 1 |
| 313 | Dry Gulch | Combat Action | 2 | ✅ | dry-gulch.json | 1 |
| 317 | Evasion | Combat Action | 2 | ✅ | evasion.json | 1 |
| 319 | Fancy Footwork | Combat Action | 1 | ✅ | fancy-footwork.json | 2 |
| 1276 | Kneecapper | Combat Action | 1 | ✅ | kneecapper.json | 2 |
| 1279 | Lucky Blow | Combat Action | 2 | ✅ | lucky-blow.json | 1 |
| 1296 | Reckless Swing | Combat Action | 2 | ✅ | reckless-swing.json | 2 |
| 1303 | Run Like Hell | Combat Action | 2 | ✅ | run-like-hell.json | 1 |
| 1312 | Stinging Wound | Combat Action | 2 | ✅ | stinging-wound.json | 2 |
| 1319 | Surprise Attack | Combat Action | 2 | ✅ | surprise-attack.json | 2 |
| 1328 | Head Butt | Combat Action | 2 | ✅ | head-butt.json | 1 |
| **Equipment** | | | | | | |
| 305 | Gooshy Gooze | Equipment | 3 | ✅ | gooshy-gooze.json | 1 |
| 630 | Chronicle of the Black Labyrinth | Equipment | 3 | ✅ | chronicle-of-the-black-labyrinth.json | 2 |
| 697 | Skin of the Hellbound | Equipment | 3 | ✅ | skin-of-the-hellbound.json | 1 |
| **Event** | | | | | | |
| 840 | Eater-of-Souls | Event | 2 | ✅ | eater-of-souls.json | 1 |
| 885 | Mass Pollution | Event | 3 | ✅ | mass-pollution.json | 2 |
| **Gift** | | | | | | |
| 100 | Consumption of Gaia | Gift | 2 | ✅ | consumption-of-gaia.json | 1 |
| 109 | Disquiet | Gift | 2 | ✅ | disquiet.json | 1 |
| 1089 | World of Human | Gift | 1 | ✅ | world-of-human.json | 1 |
| 1488 | Arms of the Abyss | Gift | 2 | ✅ | arms-of-the-abyss.json | 1 |
| 1760 | Beckons | Gift | 2 | ✅ | beckons.json | 1 |

**Total:** 27 cartas unicas (0 novas + 27 reaproveitadas, 0 sem JSON)

## Efeitos Utilizados vs Motor

| Tipo de Efeito | Status no Motor |
|---|---|
| `acao_extra_por_rodada` | ✅ Implementado |
| `adicionar_modifier` | ✅ Implementado |
| `anular` | ✅ Implementado |
| `comprar` | ✅ Implementado |
| `dano` | ✅ Implementado |
| `fugir` | ✅ Implementado |
| `ganhar_vp` | ✅ Implementado |
| `impedir_acoes` | ✅ Implementado |
| `modificar_atributo` | ✅ Implementado |
| `modificar_rage` | ✅ Implementado |
| `modificar_reducao_dano` | ✅ Implementado |
| `passiva:auto_regenerate_lowest` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:destruir_caern` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:nao_pode_ser_alpha_2_turnos` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:regenerates` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:usar_gifts_especiais` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:votos_moot` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `remover_do_jogo` | ✅ Implementado |
| `restringir` | ✅ Implementado |

### Gaps Identificados

- **passiva:auto_regenerate_lowest**: ⚠️ passiva
- **passiva:destruir_caern**: ⚠️ passiva
- **passiva:nao_pode_ser_alpha_2_turnos**: ⚠️ passiva
- **passiva:regenerates**: ⚠️ passiva
- **passiva:usar_gifts_especiais**: ⚠️ passiva
- **passiva:votos_moot**: ⚠️ passiva

## Validacao de Equipamentos vs Personagens

Verifica se os equipamentos do deck sao compativeis com as formas
e alinhamento dos personagens.

✅ Todos os equipamentos sao compativeis com os personagens do deck.


## Sugestoes de Testes

- **Count Vladimir Rustovitch** (18): teste de Character - Wyrm
- **Allonzo Montoya** (29): teste de Character - Wyrm
- **Consumption of Gaia** (100): teste de Gift
- **Disquiet** (109): teste de Gift
- **Juicy Johnes** (161): teste de Character - Wyrm
- **Gooshy Gooze** (305): teste de Equipment
- **Dodge** (312): teste de Combat Action
- **Dry Gulch** (313): teste de Combat Action
- **Evasion** (317): teste de Combat Action
- **Fancy Footwork** (319): teste de Combat Action
- **Pentex Executive and Limousine** (430): teste de Ally
- **Chronicle of the Black Labyrinth** (630): teste de Equipment
- **Skin of the Hellbound** (697): teste de Equipment
- **Friends in High Places** (790): teste de Action
- **Sneak Attack** (807): teste de Action
- **Eater-of-Souls** (840): teste de Event
- **Mass Pollution** (885): teste de Event
- **World of Human** (1089): teste de Gift
- **Kneecapper** (1276): teste de Combat Action
- **Lucky Blow** (1279): teste de Combat Action
- **Reckless Swing** (1296): teste de Combat Action
- **Run Like Hell** (1303): teste de Combat Action
- **Stinging Wound** (1312): teste de Combat Action
- **Surprise Attack** (1319): teste de Combat Action
- **Head Butt** (1328): teste de Combat Action
- **Arms of the Abyss** (1488): teste de Gift
- **Beckons** (1760): teste de Gift