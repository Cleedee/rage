# Análise: Classic: Questor Defence — Defensive Pacing (deck #2004)

## 📋 Visão Geral

| Campo | Valor |
|---|---|
| **ID** | 2004 |
| **Nome** | Classic: Questor Defence |
| **Estilo** | `defensive_pacing` — Wyrm, sobrevivência e controle de ritmo |
| **Renome** | 20/20 (3 chars = 8+8+4) |
| **Cartas** | 53 |
| **Torneios** | Consistentemente top 8 |
| **Força** | **Tanque defensivo** — Longtooth (Hl:8) suporta ataques, equipment defensivo dissuade oponentes |
| **Fraqueza** | Questor (Hl:3) e Blossom (Hl:2) frágeis; Victims atacam SEUS chars todo turno |

---

## 🧠 Estratégia Central — Defesa e Ritmo

**Este é um deck defensivo.** O objetivo NÃO é caçar Victims para VP — é **sobreviver ao máximo de ataques possível** por turno, usando equipment defensivo para se proteger e controlar o ritmo do jogo.

> "This is about pacing yourself so you can be attacked as many times as you can cope with each round." — Humano

### O ponto do deck:
1. **Receber ataques** — Victims no HG atacam SEUS personagens todo Combat Phase
2. **Sobreviver** — Skin of Hellbound (imune Rg≥6), Vampire Blood (cura), Tambertail's Heart (escape)
3. **Controlar ritmo** — Friends in High Places encerra combates desfavoráveis, Spiral Boomerang remove ameaças
4. **VP incidental** — Gaia's Will Corrupted mata Victims na Withdrawal step (+VP de Questor/Chronicle/Pit se disponível)

---

## 🃏 Personagens (Rn:20, 3 chars)

| Personagem | Rn | Hl | Rg | Gn | Função |
|---|---|---|---|---|---|
| **Longtooth Soulkiller** | 8 | **8** | **8** | 7 | **Tanque principal.** Hl:8 suporta ataques de Victims. Rage 8 usa CAs de alto custo. Gn:7 usa Gaia's Will Corrupted. |
| **Questor** | 8 | 3 | 3 | 7 | **VP engine.** +1 VP por Victim morto no HG. MAS Hl:3 é frágil — precisa de Skin + Vampire Blood. |
| **Blossom** | 4 | 2 | 1 | 6 | **Utility.** Remove self + 1 char antes do alpha (emergência). Hl:2 é muito frágil. |

### Sinergia entre Champions

Longtooth e Questor são **complementares** ("double for each other"):
- Longtooth: tanque que sobrevive aos ataques e mata Victims
- Questor: ganha VP quando Victims morrem
- Blossom: completa o pack com exatamente o espaço certo (3 chars = Ren20)

> "This counts as a double champion deck... even though the champions are not the biggest. They are, however, right for this deck and double for each other." — Humano

---

## 🦾 Equipamentos — Defensivos Primeiro

**Equipamentos servem para PROTEÇÃO, não para matar.**

| Equipamento | Qtd | Gn | Função | Prioridade |
|---|---|---|---|---|
| **Skin of the Hellbound** | 3 | 4 | Imune a dano Rg≥6. ESSENCIAL para Longtooth e Questor. | 🔴 Máxima |
| **Vampire Blood** | 2 | 2 | Cura a qualquer momento. Longtooth e Questor precisam. | 🔴 Alta |
| **Tambertail's heart** | 1 | 4 | Escape apos round 2. **Dissuade oponentes de atacar.** | 🟠 Alta |
| **Spiral Boomerang** | 2 | 3 | Manda char inimigo para Umbra por 2 turnos. Remove ameaças. | 🟠 Alta |
| **Whip of the Wicked** | 1 | 5 | Oponente joga block/dodge antes de outras ações. Controle. | 🟡 Média |
| **War Knife of Benning Simon** | 1 | 4 | Dano agravado Rg≤4. Util contra chars com Skin. | 🟡 Média |
| **Chronicle of the Black Labyrinth** | 1 | 1 | +1 VP por Victim. **Nice-to-have, não essencial.** | 🟢 Baixa |

### Dissuasão

> "The Spiral Boomerangs and Tambertail's heart really dissuade opponents from attacking you." — Humano

- **Tambertail's Heart**: Oponentes sabem que você pode escapar após round 2 → menos incentivo para atacar
- **Spiral Boomerang**: Remove personagens do combate por 2 turnos → controla ameaças
- **Skin of Hellbound**: Imunidade a Rg≥6 → muitos CAs inimigos são inúteis

### Distribuição (config)

```
Longtooth: Skin + Tambertail's Heart + Vampire Blood + Spiral Boomerang + Whip + War Knife
Questor:    Skin + Vampire Blood (+ Chronicle se sobrar)
Blossom:    Skin (se sobrar)
```

---

## 🎁 Gifts

| Gift | Qtd | Gn | Função |
|---|---|---|---|
| **Gaia's Will Corrupted** | 3 | 7 | **5 dano a Victim na Withdrawal step.** Mata Victims Hl:4 em 1 golpe. |

### Gaia's Will Corrupted — A Ferramenta de Execução

```
Combat Restricted. Play during the Withdrawal step of combat.
Gaia's Will Corrupted does 5 damage to a Victim that the Gift user is facing in combat.
```

- 5 de dano na Withdrawal step → mata Victims de Hl:4 (Werewolf Hunter, Wild Animals) em 1 golpe
- Victims de Hl:5 (Vigilante) precisam de dano adicional
- **Só usar em combate com Victim** (condition: `in_combat_with_victim`)

---

## ⚔️ Combat Events — Defesa e Sobrevivência

| Carta | Qtd | Função | Prioridade |
|---|---|---|---|
| **Frenzy** | 1 | +Rage cards e hack-apart level. Usar em Longtooth ANTES de atacar Victim. | 🔴 Máxima |
| **Taking the Death Blow** | 1 | Redireciona ferimento mortal para packmate. **Salva Questor/Blossom.** | 🔴 Máxima |
| **Fox Frenzy** | 1 | Remove personagem do combate (fuga). Emergência quando personagem vai morrer. | 🟠 Alta |
| **Shieldmate** | 1 | Packmate junta-se à defesa. Divide dano. | 🟡 Média |

### Por que essas cartas são "fairly obvious"

> "The Frenzy, Taking the Death Blow and Fox Frenzy are fairly obvious." — Humano

- **Frenzy**: +Rage = mais cards = mais chance de matar Victim com Gaia's Will Corrupted
- **Taking the Death Blow**: Questor (Hl:3) e Blossom (Hl) morrem fácil → redireciona para Longtooth (Hl:8)
- **Fox Frenzy**: Escape de emergência quando não tem dodge/block

---

## ⚔️ Combat Actions — Cobertura Completa

### Distribuição por Rage

| Rage | Cartas | Função |
|---|---|---|
| **Rg:6** | Vital Blow (2x) | Dano 4 + oponente fica Rg:1 no próximo round |
| **Rg:5** | Dry Gulch (2x), Septum Crushed (1x) | Dano 4 — mata Victims Hl:4 |
| **Rg:4** | Block and Strike (2x), Curb Stomp (1x) | Dano + defesa/controle |
| **Rg:2** | Evasion (2x), Fancy Footwork (1x), Lucky Blow (1x) | Esquiva — defesa pura |
| **Rg:1** | Off-balanced Attack (2x), Stinging Wound (1x), Dodge (1x) | **Contingência para Vital Blow** |

### Rage 1 — Contingência para Vital Blow

> "some Rage 1 cards in case of Vital Blow" — Humano

Se o oponente usa **Vital Blow** no seu personagem, ele fica com **Rage 1** no próximo round → só pode jogar CAs Rage 1. Ter Off-balanced Attack, Stinging Wound e Dodge garante que você ainda pode agir.

### Dodges — Mind Games

> "a good selection of dodges so you can outguess your opponent" — Humano

- **Evasion** (Rg:2): Dodge ALL attacks — forte mas caro
- **Fancy Footwork** (Rg:2): Dodge 1 ou 2 attacks — flexível, escolhe APÓS ver oponente
- **Dodge** (Rg:1): Dodge 1 attack — barato e sempre útil

---

## 🏞️ Territórios e Actions

| Carta | Qtd | Função | Nota |
|---|---|---|---|
| **The Pit** | 1 | +1 VP por Victim morto | "never did too much for me, but are definitely flavourful" — Humano |
| **Friends in High Places** | 3 | **Encerra qualquer combate sem frenzy** | 🔴 ESSENCIAL — controle de ritmo |
| **Sneak Attack** | 3 | Bypass alpha cycle, engaja qualquer personagem | 🟡 Util para atacar targets específicos |

### Friends in High Places — Controle de Ritmo

> "allowing you to end combats you aren't involved in to slow down your opponents" — Humano

Friends in High Places é uma das cartas mais importantes do deck:
1. **Encerra combate desfavorável** — quando seu personagem vai morrer
2. **Desacelera oponentes em FFA** — encerra combates entre outros jogadores
3. **Protege Questor/Blossom** — salva chars frágeis de morte

**3 cópias** — alta chance de ter uma na mão.

### The Pit e Chronicle — Flavor, Não Essencial

> "The latter two never did too much for me, but are definitely flavourful." — Humano

- The Pit e Chronicle dão +1 VP cada, mas são **nice-to-have**
- O VP real vem de: 1 VP base + Questor (+1) + equipment (+1) = 3-4 VP por Victim
- **NÃO priorizar** essas cartas sobre equipamento defensivo

---

## 📊 Fluxo de Jogo

### Turno 1 (Setup Defensivo)
1. **Redraw:** Skin of Hellbound, Vampire Blood, Frenzy, Friends in High Places
2. **Resource:** The Pit (se tiver). Skin em Longtooth. Skin em Questor. Vampire Blood em Longtooth.
3. **Combat:** Defender. NÃO atacar ainda.

### Turno 2 (Primeiras Vitimas)
1. **Resource:** Tambertail's Heart em Longtooth. Vampire Blood em Questor.
2. **Combat:** Longtooth ataca Victim no HG. Frenzy ANTES → +Rage cards. Dry Gulch (4 dano) + Gaia's Will Corrupted na Withdrawal (5 dano) = Victim Hl:4 morto.
3. **VP:** 1 base + 1 Questor = 2 VP (ou 3-4 com Chronicle/Pit)

### Turno 3+ (Sobrevivência)
1. Receber ataques de Victims restantes
2. Usar Taking the Death Blow para salvar Questor
3. Usar Fox Frenzy para fugir se necessário
4. Usar Friends in High Places para encerrar combates desfavoráveis
5. Matar mais Victims quando seguro

---

## ⚠️ Fraquezas

1. **Victims revidam** — Werewolf Hunter (agravado!) ataca Longtooth, Wild Animals ataca Longtooth, Vigilante ataca Questor todo Combat Phase
2. **Questor (Hl:3) morre fácil** — Precisa de Skin + Vampire Blood constantemente
3. **Blossom (Hl:2) é frágil** — Um ataque bom mata
4. **The Pit pode ser destruído** — Território vulnerável (mas é flavor, não essencial)
5. **Gaia's Will Corrupted é Combat Restricted** — Só na Withdrawal step, 1 por combate
6. **Depende de equipment** — Sem Skin, os chars morrem rápido

---

## 🔧 ThreatAnalyzer — Defensivo

| Ameaça | Severidade | Resposta |
|---|---|---|
| **Victim no HG** | 0.70 | Matar com Gaia's Will Corrupted na Withdrawal. NÃO é prioridade — Victims atacam, mas Longtooth suporta. |
| **Personagem com alto Rage** | 0.80 | Spiral Boomerang → Umbra por 2 turnos. Ou Evasion/Dodge. |
| **Vital Blow** | 0.75 | Ter Rage 1 CAs na mão (Off-balanced Attack, Stinging Wound, Dodge). |
| **Ataque em pack** | 0.85 | Friends in High Places → encerra combate. Ou Taking the Death Blow → redireciona. |
| **Flak Jacket** | 0.40 | Vital Blow (Rg:6) — Flak anula 4, Vital faz 4. |
| **Luna's Armor** | 0.50 | Gaia's Will Corrupted ignora armadura (5 dano na Withdrawal). |
| **Stench of Death** | 0.30 | `ignore` — seus chars não são espíritos/Banes. |

### Prioridade de Respostas
1. **🟢 Proteger personagens** — Skin, Vampire Blood, Taking the Death Blow, Fox Frenzy
2. **🟢 Controlar ritmo** — Friends in High Places, Tambertail's Heart, Spiral Boomerang
3. **🟡 Matar Victims quando seguro** — Gaia's Will Corrupted na Withdrawal
4. **🔴 The Pit / Chronicle** — Nice-to-have, não essencial

---

## 📝 Notas do Humano

> "I'm not sure you need the Fox Frenzy but you can normally discard it if you don't need it."

Fox Frenzy é discartável no redraw se não precisa. Mas é útil como seguro de vida.

> "The equipment and The Pit largely serve to back up the strategy by making it harder for the victims or other attackers to deal lasting harm."

Equipamento = proteção, não ofensiva.

> "The Spiral Boomerangs and Tambertail's heart really dissuade opponents from attacking you"

Dissuasão é a palavra-chave. O deck funciona porque oponentes hesitam em atacar.

---

## 🏆 Resultados do Torneio (Bot vs Bot)

### Estatísticas Gerais

| Métrica | Valor |
|---|---|
| **Total de partidas** | 48 |
| **Vitórias** | 23 (47.9%) |
| **Derrotas** | 17 (35.4%) |
| **Empates** | 2 (4.2%) |
| **Erros (stuck/timeout)** | 6 (12.5%) |

### Por Alinhamento do Oponente

| Alinhamento | Vitórias | Derrotas | Win Rate |
|---|---|---|---|
| **vs Wyrm** | 11 | 8 | **58%** |
| **vs Gaia** | 3 | 9 | **25%** |

### Matchups Detalhados

| Oponente | V | D | E | WR% | Nota |
|---|---|---|---|---|---|
| Passos da Morte (Ren20) | 3 | 0 | 0 | 100% | ✅ Favorável |
| Virtual: Gaia Umbra | 3 | 0 | 0 | 100% | ✅ Favorável |
| Apocalypse: First Team #21 | 2 | 0 | 0 | 100% | ✅ Favorável |
| Classic: Grimfang Moot | 2 | 0 | 0 | 100% | ✅ Favorável |
| Classic: Wyrm Frenzy | 2 | 0 | 0 | 100% | ✅ Favorável |
| Ajaba: Hienas da Savana | 2 | 0 | 1 | 67% | ✅ Favorável |
| Virtual: Ajaba Aggression | 2 | 0 | 1 | 67% | ✅ Favorável |
| Drain Team v1 (Ren20) | 2 | 1 | 0 | 67% | ✅ Levemente favorável |
| Morgans Bully Quest | 2 | 1 | 0 | 67% | ✅ Levemente favorável |
| Furia e Sabedoria | 1 | 1 | 0 | 50% | ⚖️ Neutro |
| Classic: Wailer special | 1 | 2 | 0 | 33% | ⚠️ Desfavorável |
| Classic: Gaia Weenie | 1 | 2 | 0 | 33% | ⚠️ Desfavorável |
| Apocalypse: First Team 28 | 0 | 3 | 0 | 0% | ❌ Desfavorável |
| Kitsune: Raposas da Fortuna | 0 | 3 | 0 | 0% | ❌ Desfavorável |
| Trovao dos Metis v2 | 0 | 2 | 0 | 0% | ❌ Desfavorável |
| Umbral Wardens | 0 | 2 | 0 | 0% | ❌ Desfavorável |

### Análise dos Matchups

**Pontos Fortes (vs Wyrm - 58% WR):**
- Deck defende bem contra agressão direta
- Skin of Hellbound bloqueia muitos CAs de dano alto
- Longtooth (Hl:8) sobrevive a muitos ataques
- Gaia's Will Corrupted mata Victims eficientemente

**Pontos Fracos (vs Gaia - 33% WR):**
- Gaia decks frequentemente têm mais personagens
- Mais personagens = mais ataques por turno
- Questor (Hl:3) e Blossom (Hl:2) morrem fácil
- Deck não tem resposta para múltiplos ataques simultâneos

**Matchups específicos:**
- ✅ **Passos da Morte, Virtual: Gaia Umbra, Grimfang Moot, Wyrm Frenzy** — 100% WR
- ⚠️ **Gaia Weenie, Wailer special** — 33% WR (desfavorável)
- ❌ **Apocalypse: First Team 28, Kitsune** — 0% WR (muito desfavorável)

**Problemas Técnicos (reduzidos):**
- Apenas 12.5% dos jogos ficaram stuck/timeout (antes era 25%)
- Corrigido: loop infinito de Victim attacks via limitador
- Ainda há casos extremos que precisam de investigação

### Recomendações para Melhoria

1. **Anti-Gaia:** Adicionar cartas que lidem com múltiplos personagens (board wipes)
2. **Victim Management:** Melhorar lógica para lidar com Victim attacks automáticas
3. **Stuck Prevention:** Detectar loops de combate e forçar fim (já parcialmente implementado)
4. **Alternative Win Con:** Considerar estratégias que não dependem apenas de sobrevivência
5. **Matchup Analysis:** Estudar por que perde vs Kitsune e Apocalypse: First Team 28
