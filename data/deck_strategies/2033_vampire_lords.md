# Análise: Vampire Lords — Sangue Eterno (deck #2033)

## 📋 Visão Geral

| Campo | Valor |
|---|---|
| **ID** | 2033 |
| **Nome** | Vampire Lords — Sangue Eterno |
| **Estilo** | `wyrm_aggro` — Wyrm vampires |
| **Renome** | 20/20 (3 chars = 10+9+1) |
| **Cartas** | 55 |
| **Faccao** | **Wyrm** — mata Victims no HG = VP |

---

## 🃏 Personagens (Rn:20)

| Personagem | Rn | Hl | Rg | Gn | Função |
|---|---|---|---|---|---|
| **Harold Zettler** | **10** | **7** | **5** | **10** | Alpha. Vampire Pentex Executive. **Regenerates.** Cancela Board Meetings |
| **Allonzo Montoya** | **9** | **7** | **5** | **6** | Vampire Abomination. Usa gifts Shadow Lords/Metis/BSD |
| **Frenar** | 1 | 1 | 1 | 1 | Troca com alpha se atacado |

### Harold Zettler — O CEO Vampiro

```
Defiler. Vampire. Board of Directors. Once per turn he may cancel one Board Meeting before it is voted on.
He may use 7th Generation, Odyssey Fomori, and Fianna Gifts. Regenerates.
```

**Stats absurdos:** Hl:7, Rg:5, Gn:10. Regenera. Cancela juntas. Pode usar gifts Fianna.

### Allonzo Montoya — O Abomination

```
Allonzo is a werewolf who has been turned into a vampire. Thoroughly insane, he now serves the Wyrm.
Allonzo can use Shadow Lords, Metis and Black Spiral Dancer Gifts. He cannot be alpha 2 turns in a row.
```

**Hl:7, Rg:5.** Pode usar gifts BSD (Stench of Death, Roar of the Wyrm, etc.).

---

## 🦾 Mecânica Central

### Stench of Death — Proteção Vampírica

```
Only spirits, Banes, and Metis can attack the user of this Gift.
```

Com Stench of Death ativo:
- **✅ Harold** (Vampire, não é espírito/Bane/Metis) — imune a ataques da maioria dos oponentes
- **✅ Allonzo** (Vampire Abomination) — imune
- **❌ Frenar** (Bastet Metis? Não, Balam) — vulnerável

### Beast-of-War — +3 Rage

```
All pack members gain 3 Rage and lose 1 Gnosis.
```

Com Beast-of-War:
- **Harold:** Rg:5→**8**, Gn:10→9 — pode usar Massive Wound (Rg:7) e Maim (Rg:7)!
- **Allonzo:** Rg:5→**8**, Gn:6→5 — idem!

### Victims = VP (Wyrm)

```
Wyrm gains VP killing Victims.
```

8 Victims no HG. Harold/Allonzo matam Victims no HG = VP.

---

## ⚔️ Combo Principal

```
Beast-of-War (+3 Rg) → Stench of Death (proteção) → Victims no HG → Matar Victims = VP
→ Roar of the Wyrm / True Fear (nega Combat Actions do oponente)
→ Massive Wound / Maim (Rg:7) = dano massivo
→ Vampire Blood / Kiss of the Wyrm = cura
```

---

## 📦 Cartas-Chave

### Gifts (10)

| Gift | Gn | Efeito |
|---|---|---|
| **Stench of Death** ×2 | 2 | Só espíritos/Banes/Metis atacam o usuário |
| **Wyrm Hide** ×2 | 3 | +2 Health permanente |
| **Roar of the Wyrm** ×2 | 4 | Oponente não joga Combat Action |
| **True Fear** ×1 | 4 | Oponente não joga Combat Action (outro) |
| **Night terror** ×1 | 5 | Oponente skipa Redraw |
| **Laughter of the Soul** ×1 | 5 | Alvo não pode agir (fora de combate) |
| **Kiss of the Wyrm** ×1 | 6 | Cura dano até 7 |
| **Call of the Wyrm** ×1 | 4 | Força alphas Wyrm a atacar usuário |
| **Corrupting Presence** ×1 | 5 | +3 Gauntlet em caern |

### Events (4)

| Event | Função |
|---|---|
| **Beast-of-War** | Pack Totem. +3 Rg, -1 Gn para todos |
| **Eater-of-Souls** | Pack Totem. Habilita fetish equipment |
| **Knight Entropy** | VP por Territory/Caern destruídos |
| **Hyperion** | Regenera dano agravado |

### Equipamentos (5)

| Equipamento | Gn | Efeito |
|---|---|---|
| **Vampire Blood** | 2 | Bane Fetish. Cura lowest damage card |
| **Blood Dagger** | 3 | Bane Fetish. +1 Rg |
| **Blood Diamond** | 0 | +2 votos em Juntas |
| **Assegai** ×2 | 0 | Bloqueia 1 dano |

---

## 🔧 ThreatAnalyzer

| Ameaça | Severidade | Resposta |
|---|---|---|
| **Exorcism/Gift removal** | 0.75 | Matar quem tem o gift |
| **Gaia gift (dano alto)** | 0.65 | Stench of Death bloqueia |
| **Metis character** | 0.60 | Pode atacar via Stench of Death — prioridade |
| **Spirit ally** | 0.55 | Pode atacar via Stench — matar primeiro |
| **Moot proposal** | 0.50 | Harold cancela Board Meeting |

### Prioridade de Jogo
1. Stench of Death em Harold
2. Beast-of-War (+3 Rg) 
3. Victims no HG
4. Wyrm Hide (+2 Hl)
5. Atacar HG (matar Victims = VP)
6. Massive Wound/Maim em oponentes
