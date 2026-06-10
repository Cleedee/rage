# 🎮 Partida Seed 3 — Sem Umbra (Ninguém Tem Caern)

**643 (Passos da Morte) vs 619 (Fúria e Sabedoria) vs 629 (Umbral Wardens)**
*Teste da regra 2.2.4: stepping sideways exige Caern no pack.*

---

## 📋 Observação Principal

Nenhum dos três decks **comprou Caern na mão inicial** nesta seed.
Com a correção da regra 2.2.4 (`pode_step_sideways` retorna `False` se
`caern is None`), **ninguém entrou na Umbra** — comportamento correto.

Para ver a estratégia de Umbra em ação: rode seed 2 (J3 começa com
Sky River Caern na mão e o joga prioritariamente).

---

## ⚔️ Turno 1 — Big Fisher vs Fomori Cop

### 🔄 Redraw
- Margrave Konietzko (J2): Wyrm ganha +1 VP por vítima
- Fade-To-Black (J3): +2 Gnosis para step sideways/combat

### 🎴 Resource
- **J2**: Excitable Good Ol' Boy no HG; Iron Will; Mass Pollution (-1 Gnosis em Cernonous)
- **J3**: Fomori Cop no HG; Iron Will; Umbral Wave
- **J1**: The Naysayer's Hovel; Visit from White Father; Inspiration (+1 Rage/Gnosis)

### ⚔️ Combate Alpha: Big Fisher (J2) → Fomori Cop (J3)
```
🛡️ Fomori Cop bloqueia! Redução 5 ≥ dano 5 → 0 de dano
🐟 Big Fisher sobrevive
```

**Margrave Konietzko ataca Cernonous** — mas Cernonous revida e:
```
💀 [T1 COMBAT] Big Fisher destruído! J3 +10 VP (total: 10)
```

---

## 🔥 Turno 2 — O Massacre

### 💚 Regeneração
- Margrave e Cernonous regeneram dano do turno anterior

### 🎴 Resource
- **J2**: Flak Jacket em Margrave; **Sneak Attack** em Buries the Dead (💀)
- **J3**: Skin of the Hellbound; Flak Jacket em Modi Votishal; Chimera
- **J1**: Dead Zone; Catfeet (Allya esquiva); Blur of the Milky Eye

### ⚔️ Múltiplos Combates

**Margrave (J2) → Fomori Cop (J3)**
```
💀 Fomori Cop destruído! J2 +5 VP (total: 5)
```

**Fade-To-Black (J3) → Stalks Death (J1)** + **Stalks Death → Fade**
```
💀 Stalks Death destruído! J3 +9 VP (total: 19)
```

**Allya Sun-Follower (J1) → Margrave (J2)**
```
💀 Margrave destruído! J1 +10 VP (total: 10)
💀 Allya destruída! J2 +5 VP (total: 10)
```

---

## 🏆 Resultado

```
💀 Jogador 1 eliminado! (sem Characters)
💀 Jogador 2 eliminado! (sem Characters)
🏆 Jogador 3 (Deck 629) VENCEU!
```

| Jogador | Deck | VP |
|---|---|---|
| 🟪 J3 | Umbral Wardens | 19+ |
| 🟨 J2 | Fúria e Sabedoria | 10 |
| 🟦 J1 | Passos da Morte | 10 |

### Mecânicas Verificadas

| Mecânica | Status |
|---|---|
| ✅ Combates resolvem no COMBATE (não sangram pro REDRAW) | OK |
| ✅ Passar a vez durante combate não avança a fase | OK |
| ✅ Sem Caern → ninguém step (regra 2.2.4) | OK |
| ✅ Block funciona (Fomori Cop) | OK |
| ✅ Sneak Attack (mata durante Resource) | OK |
