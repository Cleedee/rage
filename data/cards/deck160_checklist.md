# Deck 160 - Checklist de Revisão de Efeitos

Legenda:
- `[ ]` — Não revisado (apenas análise inicial)
- `[x]` — Revisado e completo
- `[~]` — Registrado em outro deck

## Personagens (Gaia)

- [x] 174 — Lone Wolf Circles
- [x] 269 — Sweet Luna's Smile
- [x] 374 — Sand's Last King

## Aliados

- [x] 391 — Carpet Snake
- [x] 408 — Haunter
- [x] 446 — Oracle of Sobek
- [~] 395 — Dreamspeaker Mage (deck7)

## Inimigos

- [x] 573 — Dream Hunter
- [x] 1341 — Elethoi

## Caern

- [x] 609 — Lake Nasser Wallow

## Equipamentos

- [x] 725 — Animal Mummy
- [x] 726 — Assegai

## Gift

- [x] 945 — Chant of Morpheus
- [x] 1071 — The Badger's Heart
- [x] 1099 — Primal Anger

## Rito

- [x] 1179 — Rite of the Opened Caern

## Quest

- [x] 1147 — Mnesis Dreams

## Evento

- [x] 1355 — Fog

## Ações de Combate

- [~] 123 — Instinctive Attack (deck90)
- [x] 280 — Anatomy Lesson
- [x] 288 — Block and Roll
- [x] 324 — Flicker
- [x] 1306 — Savage Beatdown
- [x] 1314 — Submission Hold
- [x] 1328 — Head Butt
- [x] 1330 — Searching for Weakness
- [x] 1331 — Tail Lash
- [~] 1332 — Duck and Cover (deck7)
- [x] 1359 — Aggressive Bite
- [x] 1470 — Desperate Struggles

---

---

## Sistemas Implementados

- [x] **Sistema de Quest** (`quest_check`) — Mnesis Dreams cria `QuestState`, conta turnos sem dano na Regeneration, completa com VP + shuffle
- [x] **Death Triggers** (`death_trigger`) — Dream Hunter registra trigger ao entrar em jogo; dispara se morto por Mokole: busca Quest/Rite/Moot no deck
- [x] **Recrutamento** (`recruitment`) — Sand's Last King adiciona tribos (`Ajaba`, `Bastet`, `Silent Striders`) ao `can_recruit` do dono
- [x] **Passivas Contínuas** (`continuous_passive`) — Lake Nasser Wallow adiciona `rites_gifts_cross_gauntlet` aos `game_modifiers`; verificado em `_validar_gauntlet_para_carta`
- [x] **Condição de Uso: `fase_umbra_mokole`** — Valida que a fase é Umbra e há um personagem Mokole no pack

**Total: 0 pendentes, 27 revisadas, 3 em outros decks, 4 sistemas implementados**
