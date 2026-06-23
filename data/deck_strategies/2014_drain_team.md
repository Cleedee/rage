# Análise: Drain Team v1 — Wyrm Pentex Control (deck #2014)

## 📋 Visão Geral

| Campo | Valor |
|---|---|
| **ID** | 2014 |
| **Nome** | Drain Team v1 |
| **Estilo** | `control+midrange` — Wyrm Pentex, VP via Victims + Chronicle |
| **Renome** | 20/20 (3 chars = 10+9+1) |
| **Cartas** | 53 |
| **Torneios** | 🥇 **5-0 invicto** (último torneio) |
| **Força** | Skin of Hellbound + Chronicle + Beckons = VP engine |
| **Fraqueza** | Só 3 chars; dependente de equipamentos |

---

## 🃏 Personagens (Rn:20, 3 chars)

| Personagem | Rn | Hl | Rg | Gn | Função |
|---|---|---|---|---|---|
| **Count Vladimir Rustovitch** | 10 | 6 | 5 | 7 | Alpha (maior Rn), auto-regenera após kill, usa BSD Gifts |
| **Allonzo Montoya** | 9 | 7 | 5 | 6 | Tanque (Hl:7), usa Shadow Lords/Metis/BSD Gifts |
| **Juicy Johnes** | 1 | 1 | 1 | 1 | Lixeiro descartável |

### Count Vladimir — Habilidades Especiais
- **Auto-regeneração:** No fim de qualquer combate onde matou ≥1 oponente, regenera a carta de dano mais baixa
- **Black Spiral Dancer Gifts:** Pode usar gifts BSD (World of Human, Disquiet, Beckons, Arms of the Abyss, Consumption of Gaia)

### Allonzo Montoya
- **Versátil:** Pode usar Shadow Lords, Metis e BSD Gifts
- **Restrição:** *"Allonzo cannot be selected as alpha 2 turns in a row"* — se foi alpha no turno anterior, outro personagem deve ser alpha

---

## ⚙️ Mecânica Central — Chronicle + Beckons

### Fonte Primária de VP: Chronicle of the Black Labyrinth

```
Chronicle of the Black Labyrinth (Gn:1)
  Se um personagem Wyrm controla, Victims mortos valem o DOBRO de VP
  (Normal: 1 VP → Chronicle: 2 VP por Victim)
```

**Como funciona:**
1. Colocar Chronicle em jogo (Equipamento, Gn:1 — muito barato)
2. Oponentes (Gaia) jogam Victims no HG para quests/etc.
3. Matar esses Victims = **2 VP cada** com Chronicle
4. Cada Victim morto = 2 VP → 5 Victims = 10 VP

### Fonte Secundária: Beckons (Moot)

```
Beckons (Gn:5) — Uma vez por Moot
  Colocar o Human de menor Renome face-down no Victory Pile = 1 VP
```

**1 VP por turno de graça** na fase de Moot. Em 10 turnos = 10 VP.

### Fonte Terciária: Matar personagens
- Allonzo (Rg:5) + Arms of the Abyss (2 cartas de combate) = dano consistente
- Surprise Attack (x2) + Dry Gulch (Rg:5) = dano médio-alto

---

## 🛡️ Defesa em 3 Camadas

### Camada 1: Skin of the Hellbound (x3, Gn:4)

```
Imune a dano de Rage ≥ 6.
```

**Ambos os personagens principais têm Rg:5.** Com Skin:
- Ataques com Rg:6+ são anulados (maioria dos ataques fortes)
- Só ataques Rg:1-5 passam (dano baixo)
- Skin é o equipamento mais importante do deck

### Camada 2: Mass Pollution (x3)

```
Wyrm chars ganham +1 Gn. Não-Wyrm perdem 1 Gn.
```

- Wyrm chars sobem de Gn: Vladimir (8), Allonzo (7), Juicy (2)
- Oponentes Gaia perdem Gn — não conseguem jogar gifts caros
- Disruptivo contra decks com gifts de Gn alto (Luna's Armor Gn:4, Resist Pain Gn:3)

### Camada 3: Gooshy Gooze (x3, Gn:2)

```
Oponente perde 1 Rage e 1 Gnosis durante o combate.
```

Em combate, cada atacante com Gooshy Gooze reduz Rage e Gnosis do defensor em 1. Empilhável!

---

## 🎁 Gifts-Chave

| Gift | Gn | Função |
|---|---|---|
| **Arms of the Abyss** (x2) | 3 | **Permanente.** +1 combat card no 1º round de cada combate |
| **Consumption of Gaia** (x2) | 4 | Cancela qualquer gift de Gn ≤ 6. Descartável |
| **Disquiet** (x2) | 5 | Remove Ally/Prey Homid por 1 turno. Se Gn ≤ 3, manda pra Umbra permanente |
| **World of Human** (x1) | 6 | Aumenta Gauntlet de um caern em +1 (máx +4) |
| **Beckons** (x2) | 5 | 1 VP por Moot (ver acima) |

### Arms of the Abyss — Permanente!

```
O usuário pode jogar uma carta de combate extra no primeiro round de cada combate.
```

Com este gift ativo:
- Vladimir ou Allonzo jogam **2 combat cards no primeiro round**
- Dano médio por ataque: Dry Gulch (Rg:5) + Head Butt (Rg:3) = 8 de dano
- Com Lucky Blow (Rg:2) + Surprise Attack (Rg:2) = 4+4+2 = 10 de dano

### Consumption of Gaia — Proteção contra Gifts
- Cancela **qualquer gift de Gn ≤ 6**
- Útil contra: Luna's Armor (Gn:4), Resist Pain (Gn:3), Stench of Death (Gn:2), Heightened Senses (Gn:1)
- **Resposta direta a ameaças** — ThreatAnalyzer detecta e cancel

---

## ⚔️ Combat Actions (18 cartas)

| Carta | Qtd | Rg | Função |
|---|---|---|---|
| Dry Gulch | 2 | 5 | **Dano alto.** Ataque na garganta |
| Surprise Attack | 2 | 2 | Surpresa no 1º round (não precisa declarar) |
| Head Butt | 2 | 3 | Dano médio + stun |
| Kneecapper | 1 | 3 | Dano médio + immobilize |
| Lucky Blow | 2 | 2 | Sorte no dano |
| Reckless Swing | 2 | 2 | Ataque imprudente |
| Stinging Wound | 2 | 1 | Dano baixo mas consistente |
| Fancy Footwork | 1 | 2 | Esquiva + reposicionamento |
| Evasion | 2 | 2 | Esquiva |
| Dodge | 2 | 1 | Esquiva básica |
| Run Like Hell | 2 | 1 | Fuga |

### Com Arms of the Abyss ativo (1º round do combate):
1. **Dry Gulch** (Rg:5) — dano primário
2. **Head Butt** (Rg:3) — dano secundário
Total: 8 de dano no primeiro round

---

## 🃏 Ações

| Carta | Qtd | Função |
|---|---|---|
| **Friends in High Places** | 3 | Compra cartas OU encerra combate |
| **Sneak Attack** | 3 | Ataque surpresa bypassando protocolo |

### Friends in High Places — Prioridade Máxima
- **Compra:** Busca Chronicle, Skin, Arms of the Abyss
- **Fuga:** Encerra qualquer combate que não envolva frenesi
- Essencial para encontrar as peças-chave

---

## 📈 Fluxo de Jogo Ideal

### Turno 1-2 (Setup Defensivo)
1. **Redraw:** Manter Skin of Hellbound, Chronicle, Friends
2. **Resource:** Jogar Skin of Hellbound em Vladimir (prioridade). Mass Pollution.
3. **Moot:** Beckons → 1 VP
4. **Combat:** Defender com Dodge/Evasion. Não atacar até ter setup completo.

### Turno 3-4 (Ativação)
1. **Resource:** Chronicle of the Black Labyrinth. Arms of the Abyss (permanente). Gooshy Gooze.
2. **Moot:** Beckons → 2 VP total
3. **Combat:** Allonzo ou Vladimir atacam Victims no HG do oponente. 2 VP cada com Chronicle.

### Turno 5+ (Snowball)
- Chronicle + Beckons = 2-3 VP por turno
- Skin of Hellbound protege de ataques fortes
- Mass Pollution desabilita gifts inimigos
- Consumption of Gaia cancela ameaças

---

## ⚠️ Fraquezas

1. **Só 3 personagens** — Perdeu um → 50% da capacidade ofensiva. Juicy Johnes é lixo.
2. **Dependente de equipamentos** — Se Mass Pollution/Chronicle/Skin são destruídos, deck perde potência
3. **Sem cura** — Exceto regeneração padrão e auto-regeneração do Vladimir (só após kill)
4. **Sem Caerns** — Não joga Caerns, perde vantagem de território
5. **Chronicle precisa de Victims** — Se oponente não joga Victims, Chronicle não gera VP extra
6. **Beckons lento** — 1 VP por turno é pouco. Precisa de 20 turnos para vencer só com Beckons
7. **Allonzo não pode ser alpha 2x seguidas** — Precisa alternar com Vladimir

---

## 🔧 ThreatAnalyzer — Como Este Deck se Beneficia

| Ameaça | Severidade | Resposta |
|---|---|---|
| **Luna's Armor** | 0.60 | `consumption_of_gaia` — Cancela o gift! |
| **Stench of Death** | 0.70 | `consumption_of_gaia` — Cancela (Gn:2 <= 6) |
| **Resist Pain** | 0.40 | `consumption_of_gaia` — Cancela |
| **Flak Jacket** | 0.50 | Dry Gulch (Rg:5) — Flak anula 4, Dry Gulch faz 5 → 1 passa |
| **Heightened Senses** | 0.55 | `consumption_of_gaia` — Cancela challenge defense |
| **Spirit of the Fray** | 0.50 | `consumption_of_gaia` — Cancela |
| **Enemy no HG** | 0.30 | Ignorar (Wyrm não ganha VP por Enemy) |
| **Victim no HG** | **0.80** | **ATACAR! 2 VP com Chronicle!** |

O ThreatAnalyzer é perfeito para este deck porque:
1. **Consumption of Gaia** é a resposta certa para gifts — cancela Gn ≤ 6
2. **Chronicle** faz Victims valerem 2 VP — detectar Victims no HG = prioridade máxima
3. **Skin of Hellbound** já é passiva — o analyzer confirma que está ativo
4. **Disquiet** remove Allies problemáticos (Dreamspeaker Mage, Kinfolk Cop)

### Prioridade de Alvos
1. Personagens com gifts perigosos (cancelar com Consumption of Gaia primeiro)
2. **Victims no HG** (se existirem — 2 VP cada com Chronicle)
3. Personagens sem Skin protection (Rg < 6)
4. Personagens de baixo HP

> A config NÃO força ataque ao HG. O bot ataca personagens normalmente e usa o ThreatAnalyzer para detectar Victims no HG como oportunidade, nao como obrigacao.
