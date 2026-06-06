# Deck 550 — Deck 550

Gerado automaticamente em 06/06/2026 00:40

## Checklist de Cartas

| ID | Nome | Tipo | Qty | JSON | Deck fonte | Efeitos no JSON |
|---|---|---|---|---|---|---|
| **Action** | | | | | | |
| 790 | Friends in High Places | Action | 2 | ✅ | deck7 | 1 |
| 807 | Sneak Attack | Action | 2 | ✅ | deck90 | 1 |
| **Character** | | | | | | |
| 18 | Count Vladimir Rustovitch | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| 29 | Allonzo Montoya | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| 47 | Blossom | Character - Wyrm | 1 | ✅ | deck416 | 1 |
| 161 | Juicy Johnes | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| **Combat Action** | | | | | | |
| 312 | Dodge | Combat Action | 2 | ✅ | deck416 | 1 |
| 313 | Dry Gulch | Combat Action | 1 | ✅ | deck7 | 1 |
| 315 | Entrail Rend | Combat Action | 1 | ✅ | deck465 | 1 |
| 317 | Evasion | Combat Action | 1 | ✅ | deck416 | 1 |
| 1279 | Lucky Blow | Combat Action | 1 | ✅ | deck90 | 1 |
| 1281 | Mangle | Combat Action | 2 | ✅ | deck484 | 2 |
| 1296 | Reckless Swing | Combat Action | 2 | ✅ | deck524 | 2 |
| 1303 | Run Like Hell | Combat Action | 1 | ✅ | deck90 | 1 |
| 1312 | Stinging Wound | Combat Action | 2 | ✅ | deck90 | 2 |
| 1319 | Surprise Attack | Combat Action | 1 | ✅ | deck524 | 2 |
| 1326 | Vital Blow | Combat Action | 1 | ✅ | deck7 | 1 |
| **Equipment** | | | | | | |
| 305 | Gooshy Gooze | Equipment | 2 | ✅ | deck524 | 1 |
| 697 | Skin of the Hellbound | Equipment | 2 | ✅ | deck416 | 1 |
| **Event** | | | | | | |
| 818 | Beast-of-War | Event | 2 | ✅ | deck524 | 2 |
| 885 | Mass Pollution | Event | 2 | ✅ | deck524 | 2 |
| **Gift** | | | | | | |
| 986 | Infectious Touch | Gift | 3 | ✅ | deck524 | 1 |

**Total:** 22 cartas unicas (0 novas + 22 reaproveitadas, 0 sem JSON)

## Efeitos Utilizados vs Motor

| Tipo de Efeito | Status no Motor |
|---|---|
| `dano` | ✅ Implementado |
| `fugir` | ✅ Implementado |
| `impedir_acoes` | ✅ Implementado |
| `modificar_atributo` | ✅ Implementado |
| `modificar_rage` | ✅ Implementado |
| `modificar_reducao_dano` | ✅ Implementado |
| `passiva:auto_regenerate_lowest` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:nao_pode_ser_alpha_2_turnos` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:regenerates` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:usar_gifts_especiais` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `remover_do_jogo` | ✅ Implementado |
| `restricao:max_1_pack_totem` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `restringir` | ✅ Implementado |

### Gaps Identificados

- **passiva:auto_regenerate_lowest**: ⚠️ passiva
- **passiva:nao_pode_ser_alpha_2_turnos**: ⚠️ passiva
- **passiva:regenerates**: ⚠️ passiva
- **passiva:usar_gifts_especiais**: ⚠️ passiva
- **restricao:max_1_pack_totem**: ⚠️ passiva

## Sugestoes de Testes

- **Count Vladimir Rustovitch** (18): teste de Character - Wyrm
- **Allonzo Montoya** (29): teste de Character - Wyrm
- **Blossom** (47): teste de Character - Wyrm
- **Juicy Johnes** (161): teste de Character - Wyrm
- **Gooshy Gooze** (305): teste de Equipment
- **Dodge** (312): teste de Combat Action
- **Dry Gulch** (313): teste de Combat Action
- **Entrail Rend** (315): teste de Combat Action
- **Evasion** (317): teste de Combat Action
- **Skin of the Hellbound** (697): teste de Equipment
- **Friends in High Places** (790): teste de Action
- **Sneak Attack** (807): teste de Action
- **Beast-of-War** (818): teste de Event
- **Mass Pollution** (885): teste de Event
- **Infectious Touch** (986): teste de Gift
- **Lucky Blow** (1279): teste de Combat Action
- **Mangle** (1281): teste de Combat Action
- **Reckless Swing** (1296): teste de Combat Action
- **Run Like Hell** (1303): teste de Combat Action
- **Stinging Wound** (1312): teste de Combat Action
- **Surprise Attack** (1319): teste de Combat Action
- **Vital Blow** (1326): teste de Combat Action