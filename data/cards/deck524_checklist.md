# Deck 524 — Classic: Wailer special

**Estratégia:** Aliados + pack attack. Wailer flipa e trava Combat Actions.

Gerado automaticamente em 06/06/2026 00:25

## Checklist de Cartas

| ID | Nome | Tipo | Qty | JSON | Deck fonte | Efeitos no JSON |
|---|---|---|---|---|---|---|
| **Action** | | | | | | |
| 806 | Shapeshift | Action | 3 | ✅ | deck524 | 1 |
| 807 | Sneak Attack | Action | 3 | ✅ | deck90 | 1 |
| **Ally** | | | | | | |
| 90 | Unseelie Troll | Ally | 2 | ✅ | deck465 | 0 |
| 398 | Enticer | Ally | 3 | ✅ | deck524 | 0 |
| 418 | Kinfolk Small Town Cop | Ally | 2 | ✅ | deck7 | 1 |
| 430 | Pentex Executive and Limousine | Ally | 3 | ✅ | deck524 | 0 |
| **Caern** | | | | | | |
| 586 | Caern of the Unwashed Child | Caern | 3 | ✅ | deck524 | 1 |
| **Character** | | | | | | |
| 42 | Barnaby Shadrack | Character - Wyrm | 1 | ✅ | deck524 | 1 |
| 47 | Blossom | Character - Wyrm | 1 | ✅ | deck416 | 1 |
| 64 | Fangs-Through-Eye | Character - Wyrm | 1 | ✅ | deck524 | 0 |
| 347 | Wailer | Character - Wyrm | 1 | ✅ | deck524 | 1 |
| **Combat Action** | | | | | | |
| 119 | Head or Gut ? | Combat Action | 1 | ✅ | deck524 | 2 |
| 284 | Beat Unmerciful | Combat Action | 1 | ✅ | deck90 | 2 |
| 312 | Dodge | Combat Action | 1 | ✅ | deck416 | 1 |
| 319 | Fancy Footwork | Combat Action | 1 | ✅ | deck7 | 2 |
| 1279 | Lucky Blow | Combat Action | 2 | ✅ | deck90 | 1 |
| 1286 | Off-balanced Attack | Combat Action | 2 | ✅ | deck90 | 2 |
| 1289 | Overextended Attack | Combat Action | 2 | ✅ | deck7 | 1 |
| 1296 | Reckless Swing | Combat Action | 2 | ✅ | deck524 | 2 |
| 1303 | Run Like Hell | Combat Action | 2 | ✅ | deck90 | 1 |
| 1312 | Stinging Wound | Combat Action | 2 | ✅ | deck90 | 2 |
| 1319 | Surprise Attack | Combat Action | 1 | ✅ | deck524 | 2 |
| **Combat Event** | | | | | | |
| 122 | Hunting Party | Combat Event | 1 | ✅ | deck7 | 1 |
| 281 | Ass Whuppin' Lynch Mob | Combat Event | 1 | ✅ | deck524 | 1 |
| 1309 | Shieldmate | Combat Event | 1 | ✅ | deck416 | 2 |
| 1322 | Taking the Death Blow | Combat Event | 1 | ✅ | deck7 | 1 |
| **Equipment** | | | | | | |
| 305 | Gooshy Gooze | Equipment | 3 | ✅ | deck524 | 1 |
| **Event** | | | | | | |
| 818 | Beast-of-War | Event | 2 | ✅ | deck524 | 2 |
| 885 | Mass Pollution | Event | 3 | ✅ | deck524 | 2 |
| **Gift** | | | | | | |
| 986 | Infectious Touch | Gift | 3 | ✅ | deck524 | 1 |
| 1032 | Roar of the Wyrm | Gift | 3 | ✅ | deck524 | 1 |
| 1060 | Stench of Death | Gift | 2 | ✅ | deck524 | 1 |
| **Victim** | | | | | | |
| 448 | A Bus Full of People | Victim | 1 | ✅ | deck524 | 0 |
| 491 | Greenpeace Assault Team | Victim | 2 | ✅ | deck524 | 0 |

**Total:** 34 cartas unicas (19 novas + 15 reaproveitadas, 0 sem JSON)

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
| `modificar_rage` | ✅ Implementado |
| `passiva:bloquear_combat_action_round1` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:destroi_caern_wyrm` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:destruir_caern` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:ignorar_gifts` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:nao_pode_bluff_rage6` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:start_equip` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `passiva:votos_moot` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `remover_do_jogo` | ✅ Implementado |
| `restricao:max_1_pack_totem` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `restricao:nao_defende_fomori` | ⚠️ Passiva (registro manual em `register_card_passives`) |
| `restringir` | ✅ Implementado |
| `tapar` | ✅ Implementado |

### Gaps Identificados

- **passiva:bloquear_combat_action_round1**: ⚠️ passiva
- **passiva:destroi_caern_wyrm**: ⚠️ passiva
- **passiva:destruir_caern**: ⚠️ passiva
- **passiva:ignorar_gifts**: ⚠️ passiva
- **passiva:nao_pode_bluff_rage6**: ⚠️ passiva
- **passiva:start_equip**: ⚠️ passiva
- **passiva:votos_moot**: ⚠️ passiva
- **restricao:max_1_pack_totem**: ⚠️ passiva
- **restricao:nao_defende_fomori**: ⚠️ passiva

## Sugestoes de Testes

- **Barnaby Shadrack** (42): teste de Character - Wyrm
- **Blossom** (47): teste de Character - Wyrm
- **Fangs-Through-Eye** (64): teste de Character - Wyrm
- **Unseelie Troll** (90): teste de Ally
- **Head or Gut?** (119): teste de Combat Action
- **Hunting Party** (122): teste de Combat Event
- **Ass Whuppin' Lynch Mob** (281): teste de Combat Event
- **Beat Unmerciful** (284): teste de Combat Action
- **Gooshy Gooze** (305): teste de Equipment
- **Dodge** (312): teste de Combat Action
- **Fancy Footwork** (319): teste de Combat Action
- **Wailer** (347): teste de Character - Wyrm
- **Enticer** (398): teste de Ally
- **Kinfolk Small Town Cop** (418): teste de Ally
- **Pentex Executive and Limousine** (430): teste de Ally
- **A Bus Full of People** (448): teste de Victim
- **Greenpeace Assault Team** (491): teste de Victim
- **Caern of the Unwashed Child** (586): teste de Caern
- **Shapeshift** (806): teste de Action
- **Sneak Attack** (807): teste de Action
- **Beast-of-War** (818): teste de Event
- **Mass Pollution** (885): teste de Event
- **Infectious Touch** (986): teste de Gift
- **Roar of the Wyrm** (1032): teste de Gift
- **Stench of Death** (1060): teste de Gift
- **Lucky Blow** (1279): teste de Combat Action
- **Off-balanced Attack** (1286): teste de Combat Action
- **Overextended Attack** (1289): teste de Combat Action
- **Reckless Swing** (1296): teste de Combat Action
- **Run Like Hell** (1303): teste de Combat Action
- **Shieldmate** (1309): teste de Combat Event
- **Stinging Wound** (1312): teste de Combat Action
- **Surprise Attack** (1319): teste de Combat Action
- **Taking the Death Blow** (1322): teste de Combat Event