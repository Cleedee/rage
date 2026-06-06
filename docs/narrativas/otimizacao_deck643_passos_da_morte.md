# Otimização do Deck 643 — Passos da Morte (Ren20)

## Histórico

O deck foi criado originalmente em `criar_deck_stalks_ren20.py` como versão Ren20 do
conceito "Passos da Morte" (Silent Striders liderados por Stalks Death).

### Deck Original (antes da otimização)

**Personagens (20 renome):**
- Stalks Death (Ren9, Rg3, Gn8, H5) — Ragabash, Lupus
- Allya Sun-Follower (Ren5, Rg3, Gn3, H4) — Ahroun, Lupus
- Buries the Dead (Ren6, Rg2, Gn5, H2) — Ahroun, Homid

**Total:** 54 cartas (20 combate + 31 septo + 3 personagens)

---

## Problemas Identificados

### 1. Cartas sem modelo JSON no motor de jogo

O motor de jogo (`effects.py`) carrega efeitos estruturados de arquivos JSON em
`data/cards/`. Cartas sem JSON são tratadas como "vanilla" — o bot pode jogá-las,
mas **seus efeitos especiais não são aplicados**.

O deck original tinha **13 das 27 cartas únicas sem JSON**:

| Carta | Tipo | Impacto |
|---|---|---|
| Ghost Lance x2 | Gift | Principal arma do deck — sem efeito |
| Messenger's Fortitude x2 | Gift | Buff principal — sem efeito |
| Critical Blow x2 | Combat | Dano inbloqueável — sem efeito |
| Swift Reconnaissance | Gift | Escotismo — sem efeito |
| Gaia's Favored Messenger | Gift | Tutor — sem efeito |
| Owl x2 | Pack Totem | Totem — sem efeito |
| Grand Klaive | Equipment | Arma — sem efeito |
| Bell Trees x2 | Territory | Território — sem efeito |
| Tribal Road x2 | Territory | Território — sem efeito |
| Ka Spirit x2 | Ally | Aliado — sem efeito |
| Twice-Born x2 | Ally | Aliado — sem efeito |
| Kinfolk Packleader | Ally | Aliado — sem efeito |
| Kinfolk Shaman | Ally | Aliado — sem efeito |

### 2. Cartas injogáveis

- **Run Like Hell x2** — requer keyword "Slow Striking", nenhum personagem tem

### 3. Fragilidade estrutural

- **Apenas 3 personagens** → pack sangra rápido quando um cai
- **Rage máxima 3** → sem acesso a combat cards de custo 4+ (ex: Maim, Overextended Attack)
- **Sem motor de VP** → cada kill vale só 1 VP (sem Chronicle of the Black Labyrinth)
- **Sem vantagem de carta** → só Visit from White Father x2 para comprar
- **Perfil "all or nothing"** → ou explode no turno 1 (7-10 VP) ou fica preso em 0-2 VP

---

## Otimização Round 1

Substituiu 12 cartas sem JSON ou injogáveis por equivalentes com JSON.

### Combat (4 trocas)

| Removeu | Motivo | Adicionou | Efeito (JSON) |
|---|---|---|---|
| Run Like Hell x2 | Injogável (Slow Striking) | Telling Blow x2 📦 | Dano 1 (custo 1, Rg3) |
| Critical Blow x2 | Sem JSON | Off-balanced Attack x2 📦 | Dano 2 ou reduz custo de Rage |

### Septo (8 trocas)

| Removeu | Motivo | Adicionou | Efeito (JSON) |
|---|---|---|---|
| Ghost Lance x2 | Sem JSON | Sense of the Prey x2 📦 | Ataque imediato (Gn6, Ragabash) |
| Messenger's Fortitude x2 | Sem JSON | Inspiration x2 📦 | +1 Rage/+1 Gnosis (Gn2, Ahroun) |
| Bell Trees x2 | Sem JSON | Dead Zone x2 📦 | Proteger de Gifts |
| Tribal Road x2 | Sem JSON | The Naysayer's Hovel x2 📦 | Neutraliza território |

### Resultado Round 1

- ✅ 0 cartas injogáveis
- ✅ 0 avisos de viabilidade
- ✅ Legal mantido (20 combate + 31 septo + 3 chars, 20 renome)
- 📦 Cartas com JSON: 22 de 27 tipos únicos (antes: 14)

---

## Otimização Round 2

Substituiu mais 2 cartas sem JSON.

| Removeu | Adicionou |
|---|---|
| Swift Reconnaissance ❌ | Checking the Classifieds 📦 (buscar território) |
| Gaia's Favored Messenger ❌ | Checking the Classifieds 📦 (2ª cópia) |

---

## Testes 1v1 (Hard/Hard)

### vs Deck 90 — Lobos Solitários

| Seed | Antes | Depois |
|---|---|---|
| 1 | ❌ 2-20 | ❌ perdeu |
| 5 | — | ❌ perdeu |
| 7 | — | ❌ perdeu |
| 11 | — | ❌ perdeu |
| 42 | ✅ 20-14 | ❌ perdeu |
| 50 | ✅ 20-9 | ❌ perdeu |
| 77 | ✅ 20-18 | ✅ venceu |
| 100 | ❌ 12-20 | ❌ perdeu |
| **Total** | **2/3 (66%)** | **1/8 (12%)** |

### vs Deck 7 — Questor

| Seed | Antes | Depois |
|---|---|---|
| 1 | ❌ 2-20 | ❌ perdeu |
| 5 | — | ❌ perdeu (24-20) |
| 7 | — | ❌ perdeu |
| 11 | — | ❌ perdeu |
| 42 | ❌ 0-20 | ❌ perdeu |
| 50 | — | ❌ perdeu |
| 77 | ❌ 3-20 | ❌ perdeu |
| 100 | — | ❌ perdeu |
| **Total** | **0/3 (0%)** | **0/8 (0%)** |

### vs Deck 619 — Fúria e Sabedoria

| Seed | Antes | Depois |
|---|---|---|
| 1 | ⏱ timeout | ⏱ timeout |
| 5 | — | ✅ venceu |
| 7 | — | ❌ perdeu |
| 11 | — | ✅ venceu |
| 42 | ✅ 20-12 | ✅ venceu |
| 50 | — | ✅ venceu |
| 77 | ✅ 20-5 | ❌ perdeu |
| 100 | — | ✅ venceu |
| **Total** | **2/2+ (66%+)** | **5/7 (71%)** |

---

## Conclusão

A otimização melhorou o aproveitamento contra Deck 619 (gifts com JSON finalmente
funcionam) mas não resolveu os problemas estruturais profundos:

1. **3 personagens ainda é frágil** — qualquer morte reduz o pack a 2
2. **Rage máxima 3 limita o combate** — sem acesso a cartas de custo 4+
3. **Sem motor de VP** — cada kill rende 1 VP, sem acelerador
4. **Sem draw engine** — deck não se recupera de mão ruim

### Próxima etapa possível

Restruturação de personagens para usar **Walks-with-Might (Ren9, Rg5, H5)** no
lugar de Allya + Buries, adicionando **Passer (Ren1)** como 4º personagem:

- Stalks Death (Ren9) + Walks-with-Might (Ren9) + Passer (Ren1) = **19 renome**
- Walks tem Rg5 → acesso a combat cards de custo 4-5 (Overextended Attack,
  Head Butt, Septum Crushed, Maim)
- Passer adiciona 4º corpo para resiliência
- Walks tem Fast Striking nativo → Spirit of the Fray vira redundante
