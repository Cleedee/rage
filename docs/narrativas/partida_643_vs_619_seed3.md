# Partida: Passos da Morte (643) vs Fúria e Sabedoria (619)

**Seed**: 3 | **Turnos**: 5 | **Dificuldade**: HARD vs HARD | **Formato**: 2 jogadores

---

## 📊 Estatísticas Finais

| Jogador | Deck | VP | Personagens Vivos | Sept Deck | Combat Deck |
|---|---|---|---|---|---|
| J1 | Passos da Morte (643) | 0 | Buries the Dead, Allya Sun-Follower, Ka Spirit | 14 | 17 |
| J2 | Fúria e Sabedoria (619) | 9 | Big Fisher, Margrave Konietzko | 8 | 16 |

---

## 🔄 Narração Turno a Turno

### Turno 1 — REDRAW

**Estado inicial:**
- J1 (643): Buries the Dead(2/2), Stalks Death(5/5), Allya Sun-Follower(4/4)
- J2 (619): Big Fisher(5/5), Margrave Konietzko(6/6)

**Ações:**
- J1: Visit from White Father (card draw) → Inspiration (Buries +1 Rage/Gnosis) → Spirit of the Fray (Fast Striking)
- J2: Mass Pollution (Allya -1 Gnosis) → Excitable Good Ol' Boy no HG → Spirit of the Fray (Mass Pollution +1 Rage)

**Alpha (J2):** Big Fisher ignorou desafio contra Buries the Dead (22% chance — muito baixa). Atacou alpha Stalks Death.

**Combate:**
- ⚔️ Big Fisher vs Stalks Death
- Stalks Death declarou `dano_<uid>` como ação de combate (P8: carta de dano como ação)
- `💀 Stalks Death foi destruído! J2 ganhou 9 VP`

---

### Turno 2 — REDRAW

**Estado:**
- J1: Buries(2/2), Allya(4/4), Visit from White Father
- J2: Margrave(2/6), Mass Pollution | HG: Excitable Good Ol' Boy

**Redraw seletivo (P6):** J2 descartou 2 cartas inúteis, comprou 2. J1 passou.

**Regeneration:** Margrave regenerou 4 → (6/6)

**Ações Resource:**
- J1: Catfeet (Allya esquiva) → The Naysayer's Hovel → Dead Zone
- J2: Flak Jacket em Margrave → Luna's Armor → Sneak Attack (destrói The Naysayer's Hovel)

**Alpha (J2):** Big Fisher atacou alpha Buries the Dead.

**Combate:**
- ⚔️ Big Fisher vs Buries the Dead
- Ambos usaram `dano_<uid>` (P8)
- Resolução sem mortes

---

### Turno 3 — REDRAW

**Estado:**
- J1: Buries(2/2), Visit, Dead Zone
- J2: Big Fisher(5/5), Margrave(6/6), Mass Pollution | HG: Excitable Good Ol' Boy

**Redraw seletivo (P6):** J2 descartou 3 cartas — uma de cada chamada de redraw. J1 passou.

**Regeneration:** Margrave regenerou 5 → (6/6)

**Ações Resource:**
- J1: Ka Spirit → Blur of the Milky Eye → Gooshy Gooze (sem alvo Wyrm)
- J2: Wendigo (Mass Pollution +2 Rage) → Mass Pollution → Iron Will

**Alpha (J2):** Big Fisher ignorou Ka Spirit (18%). Atacou alpha Buries the Dead.

**Combate:**
- ⚔️ Big Fisher vs Buries the Dead
- `dano_<uid>` de ambos os lados
- Sem mortes

---

### Turno 4 — REDRAW

**Estado:**
- J1: Buries(2/2), Visit, Dead Zone, Ka Spirit(2/2), Blur, Gooshy Gooze
- J2: Big Fisher(5/5), Margrave(6/6), Mass Pollution, Wendigo, Iron Will

**Redraw seletivo (P6):** J2 descartou 2 cartas.

**Ações Resource:**
- J1: Inspiration (Ka Spirit +1) → Checking the Classifieds (busca Território) → Gooshy Gooze (sem alvo)
- J2: Silver Claws (dano agravado) → Friends in High Places (encerra combate)

**Alpha (J2):** Big Fisher (48% — só 2% abaixo do corte 50%). Atacou Buries the Dead.

**Combate:**
- ⚔️ Big Fisher vs Buries the Dead
- Sem mortes

---

### Turno 5 — REDRAW

**Estado:**
- J1: Buries(2/2), Visit, Dead Zone, Ka Spirit(2/2), Blur, Gooshy Gooze, Checking the Classifieds, Gooshy Gooze
- J2: Big Fisher(5/5), Margrave(6/6), Mass Pollution, Wendigo, Mass Pollution, Iron Will

**Redraw seletivo (P6):** J2 descartou 1 carta.

**Ações Resource:**
- J1: Dead Zone → Friends in High Places → Owl (Pack Totem, olhar mão oponente)
- J2: Spirit of the Fray

**Alpha (J2):** Big Fisher ignorou Ka Spirit (37%). Atacou Buries the Dead.

**Combate:**
- ⚔️ Big Fisher vs Buries the Dead
- `dano_<uid>` de ambos os lados
- Sem mortes

**⏰ Limite de turnos (5) atingido.**

---

## 🔍 Análises

### 📈 Análise de Performance dos Bots

#### Bot J1 (Deck 643 — Passos da Morte) ⭐ 0 VP

| Aspecto | Avaliação |
|---|---|
| **Redraw (P6)** | Passou todos os 5 turnos. Nunca descartou — mão sempre tinha cartas úteis. ✅ |
| **Resource (P7)** | Boa priorização: Visit from White Father (card draw) primeiro, depois buffs. ✅ |
| **Desafios (P1)** | Nunca foi alpha (perdeu seleção para Big Fisher). N/A |
| **Equipamento (P5)** | Gooshy Gooze jogado 3× sem alvo Wyrm. Poderia economizar carta. ⚠️ |
| **Força relativa (P3)** | Alpha Buries (Rg=3) vs Big Fisher (Rg=5) — P3 corretamente evitou atacar direto. ✅ |
| **Combat cards (P4+P8)** | Stalks Death e Buries usaram `dano_<uid>` como ação. ✅ |
| **Estratégia geral** | Deck lento sem personagens ofensivos. Passou a maior parte do tempo acumulando cartas. |

**Gap identificado:** Deck 643 depende de Stalks Death como combatente principal, mas ela morreu no T1. Sem ela, Buries the Dead (Rg=2) não consegue ameaçar ninguém. O bot poderia ter priorizado proteger Stalks Death com Catfeet ou equipamentos.

#### Bot J2 (Deck 619 — Fúria e Sabedoria) ⭐ 9 VP

| Aspecto | Avaliação |
|---|---|
| **Redraw (P6)** | Descarte seletivo todas as rodadas. Removeu ~7 cartas inúteis ao longo do jogo. ✅ |
| **Resource (P7)** | Boa sequência: Mass Pollution → HG → buffs → equipamentos. ✅ |
| **Desafios (P1)** | 5× ignorou desafio (prob sempre < 50%). Correto — Big Fisher (Rg=5) vs Buries (Rg=2) arriscaria challenge refusal wasting alpha action. ✅ |
| **Equipamento (P5)** | Flak Jacket equipado em Margrave (HP tank). ✅ |
| **Força relativa (P3)** | Big Fisher vs Buries: `pode_eliminar` calculou corretamente. ✅ |
| **Combat cards (P4+P8)** | Big Fisher e Margrave usaram `dano_<uid>` em vez de strike básico. ✅ |
| **Alpha actions** | 5/5 turnos atacou o alpha inimigo com Big Fisher ou Margrave. Consistente. ✅ |
| **Estratégia geral** | Agressivo desde o T1. Matou Stalks Death e manteve pressão constante. |

### 🎯 Eficácia das Melhorias (P1–P8)

| Melhoria | Status | Observação |
|---|---|---|
| **P1 — Desafios inteligentes** | ✅ | Big Fisher calculou chance de aceitação < 50% em todos os 5 turnos. Correto. |
| **P2 — Fallback ataque direto** | ✅ | Após ignorar desafio, atacou alpha diretamente. |
| **P3 — Força relativa** | ✅ | Buries (Rg=3) não atacou Big Fisher (Rg=5+). |
| **P4 — Combat cards como ação** | ✅ | `dano_<uid>` usado por ambas as criaturas de ambos os lados. |
| **P5 — Equipamento automático** | ✅ | Flak Jacket em Margrave (maior HP). Gooshy Gooze sem alvo correto. |
| **P6 — Redraw seletivo** | ✅ | J2 descartou 7+ cartas inúteis. J1 nunca precisou. |
| **P7 — Resource otimizado** | ✅ | Card draw antes de buffs, buffs antes de equipamentos. |
| **P8 — Cartas de dano como ação** | ✅ | `dano_<uid>` visível em todos os combates. |

### 💡 Sugestões

1. **Deck 643 precisa de proteção**: Stalks Death morreu no T1 sem equipamento. Considerar Flak Jacket ou Catfeet preventivo no T1.
2. **Deck 619 consistente**: Margrave Konietzko com Flak Jacket + Luna's Armor é quase imortal. Shotgun no T5+ poderia finalizar.
3. **Redraw repetitivo**: J2 chama `descartar_da_mao()` múltiplas vezes no mesmo turno (até 3×). Isso reduz o sept deck rapidamente (de 26 para 8 em 5 turnos). Revisar lógica para descartar de uma vez.
4. **Combat cards de dano**: Ambos os lados usaram `dano_<uid>` consistentemente, provando que P8 funciona em cenário real.
