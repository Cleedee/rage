# Partida: Ajaba Aggression (484) vs First Team 28 (465) — seed 20

**Resultado: ⏰ Limite de Turnos (25) — 8 × 0 VP**

---

## Resumo

As hienas de Gaia do deck 484 repetiram a blitz dos primeiros turnos, abatendo 4 dos 5 Pentex. Desta vez, porém, com a correção das regras de descarte, as cartas de combate usadas retornaram ao combat deck via reembaralhamento — mas o dano já estava feito: deck 484 não tinha mais gás para VP, e Carlotta Stearns sozinha segurou o impasse até o limite de turnos.

---

## Turno 1 — REDRAW

Ambos os packs completos em campo:

**Deck 484 (Ajaba):**
- Amber Eyes-Like-Knives (Mokole, R1 G3 H1)
- Ironjaw (Ajaba, R2 G6 H3)
- Njoki Scarface (Ajaba, R1 G1 H2)
- Thousand Cubs (Ajaba, R4 G6 H4)
- Clan of Hyenas (Ally, R6 G2 H8)

**Deck 465 (First Team 28):**
- Carlotta Stearns (Odyssey Fomori, R1 G6 H5)
- Charlene Brell (Iliad Fomori, R2 G5 H2)
- Elwood 'Slicer' Nedervitch (Iliad Fomori, R1 G2 H2)
- Leergo Cat Swallower (BSD Galliard, R2 G4 H2)
- Melvin Spivey (Pentex Executive, R3 G4 H4)

---

## Turnos 1–5: A Blitz

**Thousand Cubs** (Rage 4) declara alpha contra **Elwood** no HG. A corrente de combate é implacável:

1. `Ironjaw` acerta **Mangle** (6 dano) — Elwood ferido, impedido de agir.
2. `Amber Eyes` trava **Melvin Spivey** com Olhos de Âmbar — Melvin não pode agir no Resource.
3. `Bar the Way` + `impedir_retirada` prende **Carlotta** no combate.
4. `Clan of Hyenas` + `Leaping Rake` (5 dano) finalizam Elwood.

Turno 2: **Leergo** cai sob `Mangle` + `Savage Beatdown`.  
Turno 3: **Charlene Brell** alvejada por `Sniper Fire`, abatida.  
Turno 4: **Melvin Spivey**, ainda travado por Amber Eyes, é devorado pelo Clã das Hienas.  
Turno 5: Placar **8–0**. Sobra apenas **Carlotta Stearns**.

---

## Turnos 6–15: O Cerco

O deck 484 domina o Hunting Grounds. Desta vez, o reembaralhamento de combat deck (regra 04-cartas-em-detalhe:685) funciona — as cartas de combate usadas voltam ao deck, e o bot continua comprando. Mas o problema não é de munição: é de estratégia.

- **Carlotta** (Vitalidade 5, Block constante) se defende com `Duck and Cover` e `Block and Roll`.
- Cada ataque das hienas é bloqueado ou desviado.
- O deck 484 tem 19 cartas na mão (5 de combate + 14 de sept), mas suas gifts de alto impacto já foram gastas.
- O bot tenta repetidamente `eliminar_1437`, mas Carlotta nunca morre.

O reembaralhamento recicla as cartas de combate — o combat deck oscila entre C0 e C5 à medida que as cartas são jogadas, descartadas e recompradas — mas sem um meio de furar o bloqueio, o ciclo é infinito.

---

## Turnos 16–25: Estagnação

O jogo se arrasta num loop:

1. Redraw → o deck 484 compra suas 5 cartas de combate (recicladas do descarte).
2. Resource → nada útil na mão de sept; passa.
3. Combat → alpha ataca Carlotta, que bloqueia. Round após round.
4. Moot → sem alvos.

O deck 465 também não tem saída: Carlotta sozinha não consegue gerar VP sem packmates.

No turno 25, o limite é atingido.

---

## Análise

**O reembaralhamento funcionou?**
Sim. As cartas de combate voltaram ao deck. O combat deck passou de C0 a C5 repetidas vezes. Mas ter cartas na mão não adianta se o oponente bloqueia todo dano.

**O que faltou para o deck 484:**
- Um `Aggressive Bite` para impedir Carlotta de bloquear (`impede_escapar` não é `impede_bloquear`).
- `Laughter of the Soul` — mas foi gasta cedo e não reciclada (vai pro sept discard, não pro combat deck).
- Um segundo alpha com mais Rage para forçar dano através do Block.

---

## Status Final

```
Jogador 1 (Deck 484) 🃏19 📚C 0 S 8 🏆8
                   🏠 Ironjaw(3/3), Njoki Scarface(2/2), Clan of Hyenas(8/8)

Jogador 2 (Deck 465) 🃏12 📚C16 S 0 🏆0
                   🏠 Carlotta Stearns(5/5)
```

**Lições:** Reembaralhamento de combat deck consertado, mas o jogo ainda precisa de um tipo de efeito `impedir_bloqueio` para decks de agressão pura conseguirem furar defesas altas.
