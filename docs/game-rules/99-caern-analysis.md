# Análise de Habilidades Especiais de Caerns

## Visão Geral

Dos 46 Caerns no banco, apenas 1 (`#579 Caern of Rytthiku`) tem habilidade
implementada via `register_card_passives()` no engine. Os demais precisam
ser analisados para implementação.

## Caerns em Decks Populares

### 1. Lake Nasser Wallow (#609) — Deck 160 (Gaia)

**Texto original:**
> Rites and Gifts played by your pack may cross the Gauntlet.

**Efeito necessário:**
- Modificador global: Gifts e Rites do jogador funcionam através do Gauntlet
- Isso significa que um personagem no mundo físico pode usar um Gift que
  afeta criaturas na Umbra, e vice-versa
- Também significa que o alvo de um Gift pode estar em qualquer lado

**Onde implementar:**
- `combat_queue.py: _mesmo_lado_gauntlet()` — atualmente só verifica
  Caern/Territory/Spirit como "ambos os lados"
- `state.py: register_card_passives()` — adicionar `GameModifier`
  tipo `rites_gifts_cross_gauntlet`
- `effects.py: _buscar_alvo()` — quando filtrar alvos, ignorar restrição
  de Gauntlet se este modificador estiver ativo

**Complexidade:** Média (afeta targeting em effects.py)

---

### 2. Caern of the Unwashed Child (#586) — Deck 524 (Wyrm)

**Texto original:**
> Opponents facing your pack lose either 2 Gnosis or 2 Rage for the
> duration of the combat (caern holder chooses which). This caern can
> never reduce an opponent's Rage or Gnosis below 1.

**Efeito necessário:**
- Quando um oponente está em combate contra o pack, ele perde -2 Gnosis
  OU -2 Rage (escolha do dono do Caern)
- Mínimo de 1 em cada atributo
- Duração: durante o combate (até o fim)

**Onde implementar:**
- `combat_queue.py: start_combat()` — se o defensor tem este Caern,
  aplicar modificador ao atacante
- Ou em `_processar_ataque()` — aplicar debuff no início de cada round
- Usar `modificar_atributo` do sistema de efeitos com `duracao: end_of_combat`

**Complexidade:** Média (nova mecânica de debuff em combate)

---

### 3. Trinity Hive Caern (#599) — Deck 605 (Wyrm)

**Texto original:**
> Any Black Spiral Dancers in your pack now do aggravated damage.
> However, these Black Spiral Dancers can only regenerate in the Umbra.
> Only 1 Trinity Hive Caern can be in play at any time.

**Efeitos necessários:**

1. **Dano agravado para BSD:**
   - Personagens com keyword "Black Spiral Dancer" causam `is_aggravated = True`
   - Atualmente, `is_aggravated` é verificado em `_processar_ataque()` e
     `_processar_morte()` (dano agravado não regenera)

2. **Regeneração só na Umbra para BSD:**
   - Modificador: BSD no pack só podem regenerar se estiverem na Umbra
   - `_pode_regenerar()` em rules.py precisa checar este modificador

**Onde implementar:**
- `state.py: register_card_passives()` — adicionar `GameModifier`
  tipo `bsd_aggravated_damage`
- `combat_queue.py: _processar_ataque()` — quando calcular dano, se
  atacante tem modificador `bsd_aggravated_damage` e keyword BSD,
  marcar dano como agravado
- `rules.py: _pode_regenerar()` — se modificador ativo e BSD,
  só regenera na Umbra

**Complexidade:** Média-Alta (afeta dano e regeneração)

---

### 4. Sky River Caern (#597) — Deck 705 (Gaia) e Deck 629 (Gaia)

**Texto original:**
> Non-alpha members of your pack cannot be challenged or sneak attacked.
> Only one Sky River Caern can be in play at any time.

**Efeito necessário:**
- Imunidade a "challenge" e "sneak attack" para não-alfas
- "Challenge" = provavelmente ações de combate específicas
- "Sneak attack" = ataque surpresa (mecânica de combate)

**Onde implementar:**
- `state.py: register_card_passives()` — `GameModifier` tipo
  `sky_river_protection`
- `combat_queue.py: declare_action()` — bloquear declarações de
  challenge/sneak attack contra não-alfas

**Complexidade:** Baixa (só precisa do modifier + validação)

---

## Outros Caerns Notáveis

| ID | Nome | Deck | Efeito | Complexidade |
|----|------|------|--------|-------------|
| 576 | Caern of Awakening | — | Redraw: descartar sept hand, comprar 5 | Média |
| 577 | Caern of Bygone Visions | — | Moot: procurar Fetish no sept deck | Alta |
| 578 | Caern of Ichiyo Modoribashi | — | Não pode ser removido/destruído | Baixa |
| 579 | Caern of Rytthiku | — | Pack pode atacar Enemies no HG | ✅ Já implementado |
| 580 | Caern of the Bloodfist | — | +2 Health na Umbra | Baixa |
| 581 | Caern of the Blood God | — | Discar kill do VP para frenzy | Alta |
| 582 | Caern of the Crescent Moon | — | Dobrar Renown no Moot | Média |
| 583 | Caern of the Painted Sands | — | Pack Totem sem requisitos | Média |
| 584 | Caern of the Snow Leopard | 629 | Descartar caern para salvar char | Média |
| 585 | Caern of the Tri-Spiral | — | +2 Gnosis para Gifts | Baixa |
| 587 | Caern of the Waking Dream | — | VP total por spirits bindados | Média |
| 588 | Caern of the Weeping Daughter | — | Atacantes não frenzy, -1 Rage | Média |
| 589 | Caern of the Western Eye | — | Kinfolk votam em Moots | Média |
| 590 | Council for Universal Trade | 629 | Gauntlet entre 4-6, imune Pattern Spiders | Baixa |
| 591 | Fist of the Comet | — | +1 VP por Enemy morto na Umbra | Baixa |
| 592 | Hell's Hand Hive | — | BSD auto pack defend | Média |
| 593 | Hollow Heart Caern | — | Pack nunca perde Gnosis | Baixa |
| 594 | Operation Blight | — | Quem não pode step, agora pode | Média |
| 595 | Sept of Gold | — | Nunca perde Redraw/Regen | Baixa |
| 596 | Sept of the Five Winds | — | Auto pack attack/defend 15 renown | Alta |
| 598 | The Under Barrows | — | Buscar Faerie Ally no sept deck | Alta |
| 600 | The Wheel of Ptah | 629 | Controla Moon Bridges | Média |
| 601 | Caern of White Water | — | +1 Gnosis na Umbra, Umbra actions | Média |
| 602 | Caern of the Sentinel | — | Draw 3 combat cards ao atacar Victim | Média |
| 603 | Dank Well Hive | — | Bind Faerie como spirits | Alta |
| 604 | Hive of the Jagged Maw | — | Forçar descarte de sept card | Alta |
| 608 | Hive of the Dark Mother | — | Spirit Allies regeneram | Média |
| 1382 | Caern of the Bloodied Rock | — | Não perde Redraw phase | Baixa |
| 1383 | Sept of the Last Stone | — | +1 Rage por tribo (max +3) | Baixa |
| 1384 | Den Realm | — | Qualquer um pode step usando este Caern | Média |
| 1445 | Sept of the Etesian Wind | — | Step sideways fora da Umbra phase | Média |
| 1446 | The Descending Aerie | — | Atacantes frenzy sem combat cards | Alta |
| 1493 | Deepwater Complex | — | Considerado ambos mundos | Média |
| 1542 | Great Barrier Reef | — | +1 Health, regenera agravado na Umbra | Média |
| 1563 | Bermuda Triangle | — | Ships/Aquatic step sideways | Baixa |
| 1647 | Sept of Night Sky | — | Shadow Lord bonus renown por tribo | Média |
| 1674 | Court of Five Chambers | — | Draw 2 combat cards início combate | Média |
| 1675 | Korean caves | — | +X Renown (X=num chars) | Baixa |

## Próximos Passos Sugeridos

1. **Prioridade baixa (fácil de implementar):**
   - Lake Nasser Wallow (#609) — só precisa de modifier + ignorar Gauntlet
   - Sky River Caern (#597) — modifier + bloquear challenge/sneak
   - Caern of the Tri-Spiral (#585) — +2 Gnosis para Gifts
   - Caern of the Bloodfist (#580) — +2 Health na Umbra

2. **Prioridade média (impacto em jogabilidade):**
   - Caern of the Unwashed Child (#586) — debuff em combate
   - Trinity Hive Caern (#599) — dano agravado + regen condicional
   - Hell's Hand Hive (#592) — auto pack defend para BSD

3. **Prioridade baixa (complexo ou raro):**
   - Caern of the Snow Leopard (#584) — ressurreição
   - Caern of the Painted Sands (#583) — totem sem requisitos
   - The Under Barrows (#598) — busca no sept deck
