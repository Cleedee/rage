# Deck 550 — Drain Team: Gnosis Siphon

**Estratégia:** Drenar Gnosis dos oponentes até eles não conseguirem mais pagar custos de gifts/umbra, enquanto acumula VP com Renome alto.

## Mecânica Central

1. **Mass Pollution** + **Beast-of-War** reduzem Gnosis dos oponentes no início
2. **Infectious Touch** drena -1 Rage e -1 Gnosis por alvo (até 2x por alvo)
3. **Gooshy Gooze** reduz Rage e Gnosis em combate
4. **Juicy Johnes** morre → -2 Gnosis permanente pro matador
5. **Count Vladimir** (R10) + **Allonzo Montoya** (R9) atacam HG repetidamente

## Decklist

| ID | Nome | Tipo | Qty |
|---|---|---|---|
| **Characters** | | | |
| 18 | Count Vladimir Rustovitch | Character - Wyrm | 1 |
| 29 | Allonzo Montoya | Character - Wyrm | 1 |
| 161 | Juicy Johnes | Character - Wyrm | 1 |
| 47 | Blossom | Character - Wyrm | 1 |
| **Equipment** | | | |
| 305 | Gooshy Gooze | Equipment | 2 |
| 697 | Skin of the Hellbound | Equipment | 2 |
| **Gifts** | | | |
| 986 | Infectious Touch | Gift | 3 |
| **Events** | | | |
| 885 | Mass Pollution | Event | 2 |
| 818 | Beast-of-War | Event | 2 |
| **Actions** | | | |
| 790 | Friends in High Places | Action | 2 |
| 807 | Sneak Attack | Action | 2 |
| **Combat Actions** | | | |
| 1296 | Reckless Swing | Combat Action | 2 |
| 1281 | Mangle | Combat Action | 2 |
| 1312 | Stinging Wound | Combat Action | 2 |
| 1319 | Surprise Attack | Combat Action | 1 |
| 312 | Dodge | Combat Action | 2 |
| 1279 | Lucky Blow | Combat Action | 1 |
| 1326 | Vital Blow | Combat Action | 1 |
| 1303 | Run Like Hell | Combat Action | 1 |
| 313 | Dry Gulch | Combat Action | 1 |
| 317 | Evasion | Combat Action | 1 |
| 315 | Entrail Rend | Combat Action | 1 |

**Total:** 22 cartas únicas, 34 cartas no total

## Como vencer

1. **Turno 1-2**: Mass Pollution + Beast-of-War reduzem atributos dos oponentes
2. **Turno 1-3**: Jogue Vladimir e Allonzo. Eles são tanques com Renome alto
3. **Turno 2+**: Infectious Touch nos personagens mais perigosos
4. **Combate**: Juicy Johnes morre → -2 Gnosis pro matador
5. **VP**: Ataques HG com Vladimir e Allonzo (Skin of Hellbound = imunes a Rage 6+)
6. **Final**: Oponentes sem Gnosis não cruzam Umbra, não usam gifts

## Resultados de Testes

| Oponente | 1v1 | 3-player |
|---|---|---|
| Questor (416) | ✅ Venceu 20-19 (seed 42) | ❌ Perdeu em 5 seeds |
| Kinfolk (7) | — | ❌ Perdeu em 5 seeds |
| Bloodsucking (537) | — | ❌ Perdeu em 5 seeds |

## Gap: Bot não usa Infectious Touch

O bot não tem prioridade explícita para jogar Gifts como Infectious Touch durante a fase de Resource. Isso reduz a efetividade da estratégia de dreno de Gnosis. Para corrigir, o bot precisaria de lógica para:

1. Detectar Gifts na mão com efeito `modificar_atributo` adverso
2. Priorizar alvos com Gnosis mais alto
3. Jogar o Gift antes de equipamentos

**Status:** 🟡 Funcional, mas sub-otimizado pelo bot
