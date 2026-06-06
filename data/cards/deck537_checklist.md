# Deck 537 — Deck 537

Gerado automaticamente em 06/06/2026 00:26

## Checklist de Cartas

| ID | Nome | Tipo | Qty | JSON | Deck fonte | Efeitos no JSON |
|---|---|---|---|---|---|---|
| **Action** | | | | | | |
| 790 | Friends in High Places | Action | 3 | ✅ | deck7 | 1 |
| 807 | Sneak Attack | Action | 3 | ✅ | deck90 | 1 |
| **Caern** | | | | | | |
| 579 | Caern of Rytthiku | Caern | 1 | ✅ | deck465 | 0 |
| **Character** | | | | | | |
| 18 | Count Vladimir Rustovitch | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| 29 | Allonzo Montoya | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| 161 | Juicy Johnes | Character - Wyrm | 1 | ✅ | deck537 | 0 |
| **Combat Action** | | | | | | |
| 312 | Dodge | Combat Action | 2 | ✅ | deck416 | 1 |
| 313 | Dry Gulch | Combat Action | 2 | ✅ | deck7 | 1 |
| 315 | Entrail Rend | Combat Action | 2 | ✅ | deck465 | 1 |
| 317 | Evasion | Combat Action | 1 | ✅ | deck416 | 1 |
| 321 | Feint | Combat Action | 2 | ✅ | deck537 | 1 |
| 1272 | Disarm | Combat Action | 1 | ✅ | deck537 | 1 |
| 1281 | Mangle | Combat Action | 2 | ✅ | deck484 | 2 |
| 1303 | Run Like Hell | Combat Action | 1 | ✅ | deck90 | 1 |
| 1324 | Umbral Escape | Combat Action | 1 | ✅ | deck537 | 1 |
| 1326 | Vital Blow | Combat Action | 2 | ✅ | deck7 | 1 |
| **Combat Event** | | | | | | |
| 112 | Frenzy | Combat Event | 2 | ✅ | deck416 | 1 |
| 1318 | Surprise Ally | Combat Event | 1 | ✅ | deck537 | 1 |
| 1322 | Taking the Death Blow | Combat Event | 1 | ✅ | deck7 | 1 |
| **Equipment** | | | | | | |
| 663 | Mage's Talisman | Equipment | 1 | ✅ | deck537 | 0 |
| 697 | Skin of the Hellbound | Equipment | 3 | ✅ | deck416 | 1 |
| 700 | Spiral Boomerang | Equipment | 1 | ✅ | deck416 | 2 |
| 720 | Whip of the Wicked | Equipment | 1 | ✅ | deck416 | 1 |
| **Event** | | | | | | |
| 880 | "Kirijama, 'The Hidden Foe' | Event | 1 | ✅ | deck537 | 0 |
| **Gift** | | | | | | |
| 100 | Consumption of Gaia | Gift | 3 | ✅ | deck465 | 1 |
| 954 | Eyes of Hate | Gift | 2 | ✅ | deck537 | 1 |
| 1016 | Patagia | Gift | 2 | ✅ | deck537 | 1 |
| 1063 | Subjugation of Gaia | Gift | 2 | ✅ | deck537 | 1 |
| 1079 | True Fear | Gift | 3 | ✅ | deck537 | 1 |
| 1090 | Wyrm Hide | Gift | 2 | ✅ | deck537 | 1 |

**Total:** 30 cartas unicas (14 novas + 16 reaproveitadas, 0 sem JSON)

## Efeitos Utilizados vs Motor

| Tipo de Efeito | Status no Motor |
|---|---|
| `anular` | ✅ Implementado |
| `combar_acao` | ✅ Implementado |
| `comprar` | ✅ Implementado |
| `curar` | ✅ Implementado |
| `dano` | ✅ Implementado |
| `fugir` | ✅ Implementado |
| `impedir_acoes` | ✅ Implementado |
| `modificar_atributo` | ✅ Implementado |
| `modificar_reducao_dano` | ✅ Implementado |
| `mover_para` | ✅ Implementado |
| `passiva:auto_regenerate_lowest` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:desafios_nao_recusados` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:nao_pode_ser_alpha_2_turnos` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:regenerates` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:usar_gifts_especiais` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:usar_qualquer_gift` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `remover_do_combate` | ✅ Implementado |
| `remover_do_jogo` | ✅ Implementado |
| `restricao:max_1_personal_totem` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `restringir` | ✅ Implementado |

### Gaps Identificados

- **passiva:auto_regenerate_lowest**: ⚠️ passiva
- **passiva:desafios_nao_recusados**: ⚠️ passiva
- **passiva:nao_pode_ser_alpha_2_turnos**: ⚠️ passiva
- **passiva:regenerates**: ⚠️ passiva
- **passiva:usar_gifts_especiais**: ⚠️ passiva
- **passiva:usar_qualquer_gift**: ⚠️ passiva
- **restricao:max_1_personal_totem**: ⚠️ passiva

## Sugestoes de Testes

- **Count Vladimir Rustovitch** (18): teste de Character - Wyrm
- **Allonzo Montoya** (29): teste de Character - Wyrm
- **Consumption of Gaia** (100): teste de Gift
- **Frenzy** (112): teste de Combat Event
- **Juicy Johnes** (161): teste de Character - Wyrm
- **Dodge** (312): teste de Combat Action
- **Dry Gulch** (313): teste de Combat Action
- **Entrail Rend** (315): teste de Combat Action
- **Evasion** (317): teste de Combat Action
- **Feint** (321): teste de Combat Action
- **Caern of Rytthiku** (579): teste de Caern
- **Mage's Talisman** (663): teste de Equipment
- **Skin of the Hellbound** (697): teste de Equipment
- **Spiral Boomerang** (700): teste de Equipment
- **Whip of the Wicked** (720): teste de Equipment
- **Friends in High Places** (790): teste de Action
- **Sneak Attack** (807): teste de Action
- **Kirijama, 'The Hidden Foe'** (880): teste de Event
- **Eyes of Hate** (954): teste de Gift
- **Patagia** (1016): teste de Gift
- **Subjugation of Gaia** (1063): teste de Gift
- **True Fear** (1079): teste de Gift
- **Wyrm Hide** (1090): teste de Gift
- **Disarm** (1272): teste de Combat Action
- **Mangle** (1281): teste de Combat Action
- **Run Like Hell** (1303): teste de Combat Action
- **Surprise Ally** (1318): teste de Combat Event
- **Taking the Death Blow** (1322): teste de Combat Event
- **Umbral Escape** (1324): teste de Combat Action
- **Vital Blow** (1326): teste de Combat Action