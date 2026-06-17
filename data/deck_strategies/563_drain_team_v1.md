# Estratégia: Drain Team v1 (Ren20) — ID 563

> **Arquétipo:** Controle de Gnosis  
> **Renown Cap:** 20  
> **Total de Cartas:** 53  
> **Personagens:** 3 (Allonzo, Vladimir, Juicy Johnes)

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Núcleo do Deck](#núcleo-do-deck)
3. [Mulligan](#mulligan)
4. [Fase a Fase](#fase-a-fase)
5. [Combos](#combos)
6. [Matchups](#matchups)
7. [Cartas Implementadas no Motor](#cartas-implementadas-no-motor)

---

## Visão Geral

Deck de **controle por dreno de Gnosis**. A ideia é reduzir a Gnosis dos personagens inimigos até que eles não consigam mais pagar por Gifts ou equipar Fetishes. Enquanto isso, seus personagens Wyrm ficam mais fortes.

### Progressão de Renown

1. **Beckons** — coloca o humano de menor Renown virado no Victory Pile (1 VP)
2. **Chronicle of the Black Labyrinth** — gera VP ao longo do tempo
3. **Matar personagens/Ally/Enemy inimigos** no combate

### Mecânica Central: Stack de -Gnosis

```
Mass Pollution (x3): cada cópia = -1 Gnosis em não-Wyrm, +1 em Wyrm
Juicy Johnes (morrer): -2 Gnosis no matador (permanente)
→ 3x Mass Pollution + Juicy morrer = -5 Gnosis no inimigo, +3 Gnosis em você
```

Com -5 Gnosis, a maioria dos personagens inimigos não consegue:
- Equipar klaives (G3+)
- Usar gifts de custo médio (G4+)
- Step Sideways (requer Gnosis ≥ Gauntlet)

---

## Núcleo do Deck

### Personagens

| Personagem | R/G/H | Papel |
|---|---|---|
| **Allonzo Montoya** ⚔️ | 5/6/7 (morph 10/6/10) | **Tanque principal.** Regenera. Pode usar gifts Shadow Lords, Metis, BSD. Não pode ser alpha 2 turnos seguidos. |
| **Count Vladimir** 🧛 | 5/7/6 (morph 9/7/10) | **Suporte de Gnosis.** Regenera dano mais baixo se matou alguém. Pode usar gifts BSD, 7th Gen, Homid, Shadow Lords. |
| **Juicy Johnes** 💣 | 1/1/1 | **Bomba suicida.** Quando morto, matador perde **2 Gnosis permanente**. |

### Allies

| Ally | Função |
|---|---|
| **Pentex Executive** (R3/H7) | 3 votos em Moot/Board Meeting. Pode destruir 1 Caern por jogo. Tanque de HP. |

### Core Cards

| Carta | Qtd | Função |
|---|---|---|
| **Mass Pollution** 🌍 | 3× | Evento permanente: Wyrm +1 Gnosis, não-Wyrm -1 Gnosis. **Stackável.** |
| **Juicy Johnes** 💣 | 1× | Bomba de -2 Gnosis ao morrer. |
| **Chronicle of the Black Labyrinth** 📖 | 3× | Gera VP + compra cartas. |
| **Gooshy Gooze** 🧪 | 3× | Modifica atributo do personagem (bônus flexível). |
| **Skin of the Hellbound** 🛡️ | 3× | Redução de dano. |
| **Beckons** 👻 | 2× | Gera 1 VP na Moot Phase (coloca humano no Victory Pile). |

### Gifts de Suporte

| Gift | Qtd | Função |
|---|---|---|
| **Arms of the Abyss** 🦑 | 2× | +1 combat card no primeiro round de cada combate (permanente). |
| **Consumption of Gaia** 🚫 | 2× | Cancela qualquer Gift de Gnosis ≤6. **Counter-mágico.** |
| **Disquiet** 😨 | 2× | Remove Ally/Prey em Homid do jogo por 1 turno (ou descarta se Gn ≤3). |
| **World of Human** 🌐 | 1× | Aumenta Gauntlet de um Caern em +1 (máx +4). |

### Ações de Combate (20)

Maioria de baixo custo — este deck **não** vence no combate, ele **sobrevive** até drenar o oponente:

| Carta | Qtd | Função |
|---|---|---|
| **Dodge** | 2× | Esquiva |
| **Evasion** | 2× | Esquiva |
| **Run Like Hell** | 2× | Fuga (Slow Striking) |
| **Stinging Wound** | 2× | Dano + modificar Rage do inimigo |
| **Surprise Attack** | 2× | Dano + restrição |
| **Lucky Blow** | 2× | Dano |
| **Reckless Swing** | 2× | Dano + impede ações |
| **Head Butt** | 2× | Dano |
| **Dry Gulch** | 2× | Dano |
| **Fancy Footwork** | 1× | Esquiva versátil (1 ataque ou 2 ataques) |
| **Kneecapper** 💀 | 1× | Dano 2 + oponente age a -1 Rage no próximo round |

### Ações de Fuga

| Carta | Qtd | Função |
|---|---|---|
| **Friends in High Places** | 3× | Encerra combate que não envolva frenesi. |
| **Sneak Attack** | 3× | Ataque surpresa. |

---

## Mulligan

### Segure SEMPRE

| Prioridade | Cartas |
|---|---|
| 🔴 **Crítico** | **Mass Pollution** — quanto mais cedo, melhor |
| 🟡 **Essencial** | **Allonzo** ou **Vladimir**, **Chronicle of the Black Labyrinth** |
| 🟢 **Bom** | **Skin of the Hellbound**, **Arms of the Abyss**, **Beckons** |

### Descarte na cara dura

| Carta | Motivo |
|---|---|
| ❌ Juicy Johnes | Só é útil quando morre — jogue depois que o oponente tiver board |
| ❌ Dry Gulch | Combat action de alto custo — seguram para combate |
| ❌ World of Human | G6, caro — situacional |

### Exemplo de mão ideal

> Mass Pollution + Allonzo + Chronicle + Skin of Hellbound

---

## Fase a Fase

### 1. Redraw Phase

Prioridade: encontrar **Mass Pollution** e um personagem. O deck tem 53 cartas, então você vai ver a maioria das cartas ao longo do jogo.

### 2. Resource Phase

Sem Resource cards — passe rápido.

### 3. Umbra Phase

Este deck **não** usa Umbra ativamente. Nenhum personagem tem Step Sideways ou Fast Shift. Se for forçado para a Umbra, use **Close Gauntlet** (se tiver) para voltar, ou lute lá.

**Dica:** Allonzo e Vladimir têm Gnosis alta (6-7) mesmo depois dos equipamentos, então podem Step Sideways se necessário.

### 4. Moot Phase

| Prioridade | Moot | Efeito |
|---|---|---|
| 🥇 | **Beckons** | Coloque o humano de menor Renown no Victory Pile = **1 VP direto**. |
| 🥈 | **Pentex Executive** | 3 votos — use para passar Beckons ou bloquear moots inimigos. |

### 5. Combat Phase — Sobrevivência

**Este deck NÃO busca combate.** A estratégia é:
1. **Evitar dano** → Dodge, Evasion, Run Like Hell
2. **Fugir** → Friends in High Places (3×)
3. **Só atacar quando necessário** → Surprise Attack, Kneecapper, Fancy Footwork

#### Escolha de Alpha

| Situação | Alpha ideal |
|---|---|
| Normal | **Allonzo** (não pode ser alpha 2× seguidas — alterne com Vladimir) |
| Precisa de Gnosis alta | **Vladimir** (G7) para pagar gifts |
| Juicy está em jogo | **Juicy** (deliberadamente — quer que ele morra) |

#### Tabela de Combate por Personagem

**ALLONZO (R5):**

| Situação | Carta | Por quê |
|---|---|---|
| Quer fugir | **Dodge** / **Evasion** / **Run Like Hell** | Não quer ser ferido |
| Quer dano leve | **Stinging Wound** | Dano + -Rage no inimigo |
| Quer debuff | **Kneecapper** | Dano 2 + oponente age a -1 Rage no próximo round |
| Quer esquivar | **Fancy Footwork** | Esquiva 1 ataque (mesmo os inevitáveis) ou 2 ataques |

**VLADIMIR (R5):**

| Situação | Carta | Por quê |
|---|---|---|
| Quer fugir | **Dodge** / **Evasion** | Esquiva |
| Quer dano | **Head Butt** / **Dry Gulch** | Dano |
| Quer restringir | **Surprise Attack** | Dano + restrição |

**JUICY JOHNES (R1):** Praticamente não pode jogar combat actions (só R1). Use **Run Like Hell** (R1) para fugir, ou coloque-o como alpha para ser morto deliberadamente.

---

## Combos

### Combo #1: Stack de Gnosis 🌍💀

```
Turno 1: Mass Pollution → inimigo -1 Gnosis, você +1
Turno 2: Mass Pollution → inimigo -2 Gnosis, você +2
Turno 3: Juicy Johnes morre → matador -2 Gnosis adicional
Resultado: inimigo com -4 a -5 Gnosis = não paga mais Gifts nem equipa
```

### Combo #2: Negação de Gifts 🚫

```
Consumption of Gaia (G4): cancela qualquer Gift de Gnosis ≤6
→ Com o oponente drenado, quase todos os gifts dele entram nessa faixa
```

### Combo #3: VP Passivo 📖👻

```
Beckons na Moot Phase → 1 VP
Chronicle of the Black Labyrinth → VP ao longo do tempo
→ Você ganha VP sem precisar de combate
```

### Combo #4: Pentex Executive 🏢

```
Executive em jogo:
- 3 votos em Moots (passe Beckons)
- Pode destruir 1 Caern por jogo (tira o Sept do oponente)
```

---

## Matchups

### vs. Decks de Gifts (qualquer deck Gaia)

**Vantagem:** Consumption of Gaia cancela gifts G≤6. Com Mass Pollution reduzindo Gnosis, a maioria dos gifts fica inacessível para o oponente.

**Tática:** Mass Pollution cedo. Consumption of Gaia para os gifts mais perigosos.

### vs. Decks de Combate (Crinos, Ahroun)

**Desvantagem:** Este deck foge de combate. Personagens têm Rage baixa (R5).

**Tática:** 
- Dodge/Evasion/Run Like Hell para sobreviver
- Friends in High Places para encerrar combates
- Use Kneecapper para reduzir Rage do atacante
- Deixe Juicy Johnes ser morto para drenar o matador

### vs. Decks de Umbra

**Neutro:** Nenhum dos lados tem vantagem clara.
- Allonzo e Vladimir têm Gnosis alta para Step Sideways se necessário
- Mass Pollution não afeta quem está na Umbra
- Foque em drenar quem está no physical

### vs. Decks de Equipamento (klaives, fetishes)

**Vantagem:** Skin of the Hellbound reduz dano. Stinging Wound debuffa o atacante. Drene a Gnosis deles e eles não conseguem mais equipar klaives (G3+).

### vs. Decks Wyrm

**Cuidado:** Mass Pollution também BUFFA Wyrm (+1 Gnosis). Se enfrentar outro Wyrm, você está dando Gnosis para ele também. Nesse caso, segure Mass Pollution e use só Juicy Johnes + Consumption of Gaia.

---

## Cartas Implementadas no Motor

| Carta | Status | Notas |
|---|---|---|
| **Allonzo Montoya** (29) | ✅ Completo | Passivas registradas em `register_card_passives`: regenera, alpha restriction, gifts SL/Metis/BSD |
| **Count Vladimir** (18) | ✅ Completo | Passiva `vladimir_auto_regenerate` registrada |
| **Juicy Johnes** (161) | ✅ Completo | Death trigger registrado: `buff_gnosis -= 2` no matador |
| **Mass Pollution** (885) | ✅ JSON pronto | Efeito `modificar_atributo` com `filtro_tipo` Wyrm/non-Wyrm |
| **Consumption of Gaia** (100) | ✅ JSON pronto | `anular` Gift de Gnosis ≤6 |
| **Disquiet** (109) | ✅ JSON atualizado | Agora usa `remover_do_jogo` (mais próximo do texto original). **Limitação:** condicional de Gnosis ≤3 ainda não implementada. |
| **World of Human** (1089) | ✅ JSON atualizado | Agora usa `gauntlet` como atributo. **Limitação:** engine não suporta completamente aumento de Gauntlet. |
| **Arms of the Abyss** (1488) | ✅ JSON pronto | `acao_extra_por_rodada` funciona |
| **Beckons** (1760) | ✅ JSON pronto | `ganhar_vp` com condição funciona |
| **Chronicle of the Black Labyrinth** (630) | ✅ Completo | Modifier `chronicle_active` registrado |
| **Gooshy Gooze** (305) | ✅ JSON pronto | `modificar_atributo` funciona |
| **Skin of the Hellbound** (697) | ✅ JSON pronto | `modificar_reducao_dano` funciona |
| **Eater-of-Souls** (840) | ✅ JSON pronto | `comprar` do sept deck. **Limitação:** efeito real (permitir fetishes) não implementado. |
| Todas as Combat Actions | ✅ JSONs prontos | Todas têm efeitos estruturados |
| Friends in High Places | ✅ JSON pronto | `fugir` do combate |

### Limitações Conhecidas

1. **Disquiet** — O efeito real condiciona em Gnosis ≤3 (descarta vs. remove temporariamente). A implementação atual sempre usa `remover_do_jogo`.
2. **World of Human** — A engine não tem suporte nativo a `gauntlet` como atributo de Caern. O JSON está semanticamente correto mas o efeito pode não resolver.
3. **Eater-of-Souls** — A carta deveria permitir equipar fetishes. Atualmente só compra do sept deck.

---

## ✅ Limitações Implementadas

Após análise, as seguintes correções foram aplicadas no motor:

### 1. Eater-of-Souls (840) — ✅ Implementado

**O quê:** Registra modificador `can_equip_fetish` quando entra em jogo. Sem ele, nenhum Fetish pode ser equipado.

**Onde:**
- `state.py`: `register_card_passives` para `card_id == 840`
- `effects.py`: `_validar_restricoes_equipamento` checa `game.has_modifier('can_equip_fetish')`

**Efeito:** Fetish Equipment (klaives, fetish armors, etc.) só pode ser equipado se Eater-of-Souls estiver em jogo.

### 2. World of Human (1089) — ✅ Implementado

**O quê:** Aumenta Gauntlet de um Caern em +1 (máx +4). Trata `gauntlet` como alias de `gnosis` quando alvo é um Caern.

**Onde:** `effects.py`: `_resolver_modificar_atributo` — novo handler para `attr == 'gauntlet'` com tracking em `game._gauntlet_increases`.

**Efeito:** World of Human agora aumenta o Gauntlet de um Caern alvo em +1, até o máximo de +4 (conforme card text original).

### 3. Disquiet (109) — ✅ Implementado

**O quê:** Se o alvo tem Gnosis ≤ 3, descarta em vez de remover temporariamente.

**Onde:** `effects.py`: `_resolver_remover_do_jogo` — novo parâmetro `gnosis_max_para_descarte` no JSON.

**Efeito:** Alvos com Gnosis ≤ 3 são descartados permanentemente. Alvos com Gnosis > 3 são removidos por 1 turno e retornam.

### 4. Juicy Johnes (161) — ✅ Implementado

**O quê:** Death trigger registrado em `register_card_passives`. Quando morto, matador perde `buff_gnosis -= 2` (permanente).

**Onde:** `state.py`: `register_card_passives` + `check_death_triggers` com action `reduce_gnosis:2`.

**Efeito:** Quem matar Juicy Johnes perde 2 Gnosis permanentemente.

### 5. Eater-of-Souls — JSON atualizado

O JSON mantém o efeito `comprar` (draw do sept deck) como utilitário. O efeito principal (permitir fetish) é gerenciado pelo modificador no motor.

---

## 🔍 Análise: Feedback do Jogador Experiente

Um jogador experiente apontou 3 problemas no deck original:

> *"Clan of Hyenas and Gunboat Pirates can't be recruited by anyone in the pack. Desert Klaive will be taken out by your own Spirit Backlash. Most of the high rage cards in the deck can't be played by any character in the deck and also can't be bluffed."*

### Problema 1: Aliados não recrutáveis

**Observação:** Clan of Hyenas (Requer: Ajaba) e Gunboat Pirates (Requer: Homid) não podem ser recrutados pelos personagens do pack.

| Carta | Requer | Personagens no Pack | Recrutável? |
|---|---|---|---|
| **Clan of Hyenas** (96) | Ajaba | Allonzo (Abom/Garou/Vamp), Vladimir (Vamp), Juicy (Fomori) — nenhum com Ajaba | ❌ Não |
| **Gunboat Pirates** (1570) | Homid | Allonzo tem Homid ✅ | ✅ Sim (Allonzo) |

**Conclusão:** Clan of Hyenas realmente não é recrutável. Gunboat Pirates até é (via Allonzo), mas nenhum dos dois está no deck. É uma limitação natural do arquétipo Wyrm/Vampiro — esses aliados simplesmente não encaixam.

### Problema 2: Anti-sinergia Desert Klaive + Spirit Backlash

**Observação:** Desert Klaive (G5, Gaia Fetish - Weapon - Klaive) seria destruído por Spirit Backlash, que descarta todo Fetish Equipment de G5+.

**Conclusão:** Estas cartas não estão no deck. É um alerta válido para quem considerar adicionar ambas — Spirit Backlash é um evento anti-fetish que não combina com klaives caros.

### Problema 3: Combat Actions de Rage alta (CORRIGIDO ✅)

**Observação:** Maim (Rg:7) e Vital Blow (Rg:6) não podem ser jogados por nenhum personagem (max Rg:5). Também não podem ser blefados (6.9.1 — cartas ilegais).

**Correção aplicada em 17/06/2026:**

| Card Antigo | Problema | Card Novo | Benefício |
|---|---|---|---|
| **Maim** (Rg:7, Dmg:4) | Nenhum personagem tem Rg≥7 | **Fancy Footwork** (Rg:2) | Esquiva versátil (1-2 ataques) — reforça a estratégia de sobrevivência |
| **Vital Blow** (Rg:6, Dmg:4) | Nenhum personagem tem Rg≥6 | **Kneecapper** (Rg:3, Dmg:2) | Dano + -1 Rage no oponente — reforça o tema de debuff/controle |

**Resultado:** 20 combat actions, todas com Rg ≤ 5, jogáveis por Allonzo e Vladimir (Rg:5). Juicy (Rg:1) ainda pode usar Dodge, Run Like Hell e Stinging Wound.

### Checklist pós-correção

- [x] Nenhuma combat action com Rg > 5 no deck
- [x] Todas as cartas de combate são jogáveis por Allonzo ou Vladimir
- [x] Nenhum aliado não-recrutável incluso
- [x] Nenhuma anti-sinergia de equipamentos
- [x] JSON do Kneecapper criado em `data/cards/kneecapper.json` (efeito `dano` + `modificar_rage`)
- [x] JSON do Fancy Footwork já existia em `data/cards/fancy-footwork.json`
