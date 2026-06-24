# Sistema de Estratégia por Config JSON

## Visão Geral

O **StrategyEngine** (`rage_web/game_engine/bot/strategy_engine.py`) permite que
um jogador experiente escreva um arquivo de configuração JSON por deck,
instruindo o PriorityBot a tomar decisões melhores — quais gifts priorizar,
quem equipar com o quê, que ações de combate preferir, etc.

**Arquitetura:** O config é lido no início da partida pelo `StrategyEngine`,
consultado pelo `PriorityBot` via hooks específicos. Sem config, o bot usa
heurística original (100% retrocompatível).

## Localização dos Arquivos

```
data/deck_strategies/
├── README.md                  ← este arquivo
├── deck<id>_config.json       ← config do bot (motor lê)
└── deck<id>_<nome>.md         ← documentação humana da estratégia
```

Exemplos existentes:

| Arquivo | Deck | Estilo |
|---|---|---|
| `data/deck_strategies/deck1055_config.json` | O Julgamento (Philodox) | moot_control |
| `data/deck_strategies/deck1044_config.json` | Ajaba — Hienas da Savana | engine |
| `data/deck_strategies/deck465_config.json` | Apocalypse — Primeiro Esquadrão #21 | pack_combat |
| `data/deck_strategies/deck2004_config.json` | Classic: Questor Defence | victim_hunt |
| `data/deck_strategies/deck2008_config.json` | Classic: Grimfang Moot | moot_control |

---

## Formato do JSON

```json
{
  "deck_id": 1055,
  "name": "O Julgamento (Philodox)",
  "style": "pack_combat | moot_control | hg_control | victim_hunt | engine | balanced | ffa",

  "gift_priorities": [ ... ],
  "resource_play_order": [ ... ],
  "combat_action_preferences": { ... },
  "combat_event_priorities": [ ... ],
  "action_priorities": [ ... ],
  "equipment_assignments": [ ... ],
  "caern_preferences": [ ... ],
  "target_priority": { ... },
  "umbra_strategy": { ... },
  "redraw_rules": { ... },
  "moot_strategy": { ... },
  "combat_notes": { ... },
  "notes": { ... }
}
```

### Seções Obrigatórias
Apenas `deck_id` é obrigatório. Todas as demais seções podem ser omitidas
— o bot usa heurística padrão para o que não estiver configurado.

---

## Seções Detalhadas

### 1. `gift_priorities` — Prioridade de Gifts

Controla **qual gift jogar** na Resource Phase e na Umbra.

```json
"gift_priorities": [
  {
    "slug": "power-of-the-ways",
    "priority": 100,
    "condition": "umbra_available",
    "desc": "Power of the Ways — cura na Umbra"
  },
  {
    "slug": "resist-pain",
    "priority": 90,
    "condition": "combat_likely",
    "desc": "Resist Pain — redução de dano"
  }
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `slug` | string | Slug da carta no banco (ex: `power-of-the-ways`, `razor-claws`) |
| `priority` | int | Prioridade (0-100). Mais alto = jogado primeiro |
| `condition` | string | Condição para ativar (veja tabela abaixo) |
| `desc` | string | (opcional) Descrição humana |

**Regras:**
- Se múltiplos gifts estão na mão, o bot ordena por priority decrescente.
- Se a `condition` não é satisfeita, a prioridade é reduzida em 100
  (ou seja, o gift só é jogado se a condição estiver ativa).
- Uma mesma `slug` pode aparecer múltiplas vezes com condições
  diferentes (ex: Power of the Ways com `umbra_available` priority 100,
  e com `has_injured_character` priority 80).

### 2. `resource_play_order` — Ordem de Jogar na Resource Phase

Controla a **ordem dos tipos de carta** a jogar na Resource Phase.

```json
"resource_play_order": [
  "character",
  "caern",
  "equipment",
  "gift",
  "event",
  "ally",
  "action",
  "rite",
  "territory",
  "victim",
  "enemy",
  "quest",
  "moot"
]
```

O bot percorre a lista na ordem definida. Tipos não listados são jogados
por último (ordem original do bot). Isso permite, por exemplo, jogar
`character` antes de `equipment` (para equipar o personagem recém-chegado).

### 3. `event_priorities` — Prioridade de Eventos

Funciona de forma idêntica a `gift_priorities` mas para cartas do tipo Event.

```json
"event_priorities": [
  {"priority": 85, "condition": "always", "slug": "fenris", "desc": "Fenris — buff"},
  {"priority": 80, "condition": "always", "slug": "grandfather-thunder", "desc": "Grandfather Thunder — ataque"}
]
```

Mesmo formato, mesmas condições.

### 4. `action_priorities` — Prioridade de Action Cards

Controla **quais Action cards** (Friends in High Places, Sneak Attack, etc.)
o bot tenta jogar na Resource Phase, ANTES de outros tipos.

```json
"action_priorities": [
  {
    "slug": "friends-in-high-places",
    "priority": 92,
    "condition": "combat_active",
    "desc": "Friends in High Places — encerra combate sem frenzy"
  },
  {
    "slug": "sneak-attack",
    "priority": 65,
    "condition": "has_good_target",
    "desc": "Sneak Attack — bypass alpha cycle"
  }
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `slug` | string | Slug da carta no banco |
| `priority` | int | Prioridade (0-100). Mais alto = jogado primeiro |
| `condition` | string | Condição para ativar |
| `desc` | string | (opcional) Descrição humana |

**Como funciona:**
1. Durante a Resource Phase, o bot verifica `action_priorities`.
2. Para cada Action card na mão, verifica se o slug está na lista.
3. Se a `condition` não é satisfeita, prioridade é reduzida em 100.
4. O bot usa `sorted_actions()` para ordenar e jogar o mais prioritário.

### 5. `combat_event_priorities` — Prioridade de Combat Events (Pack Actions)

Controla **quais Combat Events** o bot tenta jogar face-down no `play_card`
step durante o combate, ANTES de declarar ações individuais.

Isso é essencial para decks de **pack combat** (Bum Rush, Pack Defense,
Attacking the Wyrm) que precisam trazer múltiplos personagens para o
combate antes que cada um declare sua Combat Action.

```json
"combat_event_priorities": [
  {"priority": 95, "slug": "bum-rush", "desc": "Bum Rush — traz todo o pack para combate"},
  {"priority": 90, "slug": "hunting-party", "desc": "Hunting Party — allies entram no combate"},
  {"priority": 85, "slug": "pack-defense", "desc": "Pack Defense — pack defende junto"},
  {"priority": 75, "slug": "reinforcements", "desc": "Reinforcements — substituto de combate"}
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `slug` | string | Slug da carta no banco (ex: `bum-rush`, `pack-defense`) |
| `priority` | int | Prioridade (0-100). Mais alto = jogado primeiro |
| `desc` | string | (opcional) Descrição humana |

**Como funciona no motor:**
1. Durante o `play_card` step, o bot verifica se a config tem
   `combat_event_priorities`.
2. Se sim, varre a `combat_hand` em busca de Combat Events com slug
   na lista, ordenados por prioridade.
3. Para o CE de maior prioridade, chama `_jogar_ce_face_down()` que
   coloca o CE face-down como ação de combate (`ce_<id>`).
4. No Bluff Step (6.2.4), CEs com propriedades `pack_attack` ou
   `puxa_pack` (Bum Rush, Pack Defense, Attacking the Wyrm) são
   reconhecidos como **legítimos** (não marcados como ilegais).
5. `_process_pack_combat()` expande os combatentes, adicionando
   todos os personagens vivos do pack do dono.
6. Novo round: os personagens recém-chegados podem declarar suas
   próprias Combat Actions.

**Formato legado** (`combat_event_priority` como dict) também é
suportado para retrocompatibilidade:

```json
"combat_event_priority": {
  "bum-rush": 95,
  "pack-defense": 80
}
```

**Dica:** Coloque `bum-rush` com priority 95 para que o bot sempre
tente trazer o pack inteiro antes de declarar ataques individuais.

### 6. `combat_action_preferences` — Preferências de Ação de Combate

Define **quais Combat Actions** cada personagem prefere usar.

```json
"combat_action_preferences": {
  "Carla Grimsson": [
    "disembowelment",
    "stunning_strike",
    "head_butt",
    "block",
    "dodge"
  ],
  "Grek Twice-Tongue": [
    "block",
    "careful_strike",
    "lucky_blow",
    "dodge"
  ]
}
```

**Como funciona:**
- A chave é o **nome do personagem** (comparação `in`, então
  `"Carla"` casa com `"Carla Grimsson"`).
- O valor é uma lista de **slugs de Combat Action** (nome em
  minúsculo com underscores, ex: `disembowelment`, `block`, `dodge`).
- O bot recebe um **bônus de +20** na pontuação de dano para ações
  na lista de preferências (elas sobem no ranking vs ações não preferidas).
- Ações sem carta na mão são ignoradas.

**Slugs comuns:**
`block`, `dodge`, `head_butt`, `body_blow`, `disembowelment`,
`stunning_strike`, `fast_strike`, `planned_strike`, `careful_strike`,
`lucky_blow`, `low_blow`, `overextended_attack`, `rapid_reload`,
`fancy_footwork`, `block_and_strike`, `beat_unmerciful`,
`aggressive_bite`, `lobotomy`, `dismember`, `whirlwind_defense`,
`iron_skin`.

### 7. `equipment_assignments` — Designação de Equipamentos

Define **quem deve receber** cada equipamento.

```json
"equipment_assignments": [
  {
    "card_name": "Assegai",
    "target": "Carla Grimsson",
    "priority": 80
  },
  {
    "card_name": "Shotgun",
    "target": "Charlene Brell",
    "priority": 90
  }
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `card_name` | string | Nome do equipamento (comparação `in` — `"Shotgun"` casa com `"Shotgun"`) |
| `target` | string | Nome do personagem alvo (vazio `""` = não equipa em ninguém) |
| `priority` | int | (opcional) Prioridade — maior = equipa primeiro |

**Regras:**
- Se o personagem alvo não está no pack (morto/nunca entrou), o
  equipamento não é designado.
- Múltiplas entradas para o mesmo `card_name` com targets diferentes
  funcionam como fallback (tenta o primeiro, depois o segundo).
- `target: ""` com priority alta pode ser usado para equipamentos
  que *não* devem ser equipados em personagens (ex: Concertina Wire).

### 8. `caern_preferences` — Preferência de Caern

Define qual Caern jogar primeiro.

```json
"caern_preferences": [
  { "card_name": "Sky River Caern", "priority": 100 }
]
```

O bot tenta jogar o Caern da lista primeiro (comparação `in` no nome).

### 9. `target_priority` — Prioridade de Alvos

Controla **quem atacar** no combate.

```json
"target_priority": {
  "prefer_low_health": true,
  "character_kill_order": "lowest_health",
  "ffa_diplomacy": "weaken_largest",
  "avoid_overextend": true,
  "hunting_grounds": {
    "prefer_prey_over_enemy": true,
    "priority_types": ["Victim", "Enemy"]
  },
  "threat_response": {
    "luna-s-armor": "ignore",
    "flak-jacket": "vital_blow",
    "stench-of-death": "use_spirit_attack"
  }
}
```

| Campo | Tipo | Valores | Descrição |
|---|---|---|---|
| `prefer_low_health` | bool | true/false | Prefere alvos com menos HP |
| `character_kill_order` | string | `"lowest_health"`, `"highest_renown"`, `"lowest_rage"` | Ordem de eliminação |
| `ffa_diplomacy` | string | `"weaken_largest"`, `"attack_weakest"`, `"balanced"` | Estratégia FFA |
| `avoid_overextend` | bool | true/false | Evita ataques que deixariam o pack vulnerável |
| `threat_response` | dict | slug → resposta | Respostas customizadas para ameaças do ThreatAnalyzer |

**FFA Diplomacy:**
- `weaken_largest`: Ataca o líder em VP (default)
- `attack_weakest`: Ataca o jogador com menos personagens
- `balanced`: Ataca quem tem mais personagens (maior ameaça imediata)

**Threat Response:**
- Sobrescreve respostas padrão do ThreatAnalyzer por slug
- Respostas válidas: `attack`, `flee`, `cancel`, `ignore`, `vital_blow`, etc.

### 10. `umbra_strategy` — Estratégia da Umbra

Controla **quem entra na Umbra** e quando.

```json
"umbra_strategy": {
  "enter_characters": ["Morgan the Unworthy", "Shari"],
  "keep_in_umbra": [],
  "save_for_combat": ["Grek Twice-Tongue", "Lone Wolf Circles"],
  "always_enter_if_opponent_cannot": true,
  "approach": "defensive",
  "enter_with_high_gnosis": true,
  "save_umbra_actions": false
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `enter_characters` | string[] | Personagens que entram na Umbra (lista de nomes) |
| `keep_in_umbra` | string[] | Personagens que ficam na Umbra mesmo em combate |
| `save_for_combat` | string[] | Personagens que NÃO entram (ficam para combate) |
| `always_enter_if_opponent_cannot` | bool | Se oponente não pode step sideways, sempre entra |
| `approach` | string | `"defensive"`, `"aggressive"`, `"balanced"` |
| `enter_with_high_gnosis` | bool | Prefere entrar com quem tem Gnosis alto |
| `save_umbra_actions` | bool | Preserva ações de Umbra (não gasta desnecessariamente) |

### 11. `redraw_rules` — Regras de Redraw

Controla **o que descartar** na fase de redraw.

```json
"redraw_rules": {
  "never_discard": [
    "Power of the Ways",
    "Resist Pain",
    "Sky River Caern",
    "Shari"
  ],
  "always_discard_if_duplicate": [962, 1077],
  "prefer_discard_types": ["Combat Event", "Event", "Moot", "Board Meeting"]
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `never_discard` | string[] | Nomes de cartas que nunca são descartadas |
| `always_discard_if_duplicate` | string[] | **Slugs** de cartas que são descartados se há cópia duplicada |
| `prefer_discard_types` | string[] | Tipos preferenciais para descarte |

### 12. `moot_strategy` — Estratégia de Juntas

Controla **como votar** nas Juntas (Board Meetings).

```json
"moot_strategy": {
  "call_if_available": ["Moot", "Board Meeting"],
  "always_vote_yes": ["Own"],
  "vote_no_against": ["Leader"],
  "strategic_vote": true
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `call_if_available` | string[] | Tipos de carta que o bot chama Junta |
| `always_vote_yes` | string[] | `"Own"` = vota sim nas próprias; ou nomes de cartas |
| `vote_no_against` | string[] | `"Leader"` = vota não contra o líder; ou nomes de cartas |
| `strategic_vote` | bool | Vota com base na situação do jogo (não aleatório) |

### 13. `combat_notes` (notas táticas)

Notas táticas para o bot, usadas como referência.

```json
"combat_notes": {
  "vital_blow_contingency": "Se oponente usa Vital Blow, ter CAs Rage 1 na mão",
  "friends_in_high_places": "Usar para encerrar combates desfavoráveis",
  "frenzy_timing": "Usar ANTES de atacar para garantir kill"
}
```

### 14. `notes` (documentação humana)

Comentários sobre a estratégia do deck, não usado pelo motor.

```json
"notes": {
  "combo_principal": "Song of Rage → Frenesi → Crinos → Fast Strike → Sense of the Prey → atacar novamente",
  "fraqueza_sem_caern": "Bivouac essencial para regeneração"
}
```

---

## Condições Suportadas

### Condições Básicas

| Condição | Quando é verdadeira |
|---|---|
| `always` | Sempre |
| `umbra_available` | Fase Umbra OU algum personagem pode step sideways |
| `has_characters` | Pelo menos 1 Character no pack |
| `has_strong_target` | Oponente tem criatura com threat rating ≥ 5 |
| `has_injured_character` | Algum Character com HP atual < HP máximo |
| `opponent_stronger` | Oponente tem Rage total maior que o jogador |
| `has_character_named:<slug>` | Personagem com slug específico está vivo no pack |
| `ffa_mode` | 3+ jogadores ativos |
| `card_in_hand:<nome>` | Carta com nome contendo `<nome>` está na mão |
| `character_in_umbra` | Algum Character está na Umbra |

### Condições de Combate

| Condição | Quando é verdadeira |
|---|---|
| `combat_likely` | Fase é Combat OU há oponentes com personagens |
| `combat_active` | Combate ativo no momento |
| `is_combat_phase` | Fase atual é Combat |
| `has_good_target` | Há Victim/Enemy no HG ou personagem fraco (HP ≤ 4) |
| `in_combat_with_victim` | Jogador está em combate com um Victim |
| `in_combat_with_strong_opponent` | Em combate com oponente forte (Rage > 3 ou HP > 4) |
| `about_to_attack` | Fase de declaração de combate (declaration/alpha_action) |
| `character_under_attack` | Personagem do jogador está sendo atacado |
| `character_receives_mortal_wound` | Personagem do jogador prestes a morrer (HP ≤ 0) |
| `defensive_emergency` | Personagem do jogador com HP ≤ 2 |

### Condições de Oponente

| Condição | Quando é verdadeira |
|---|---|
| `opponent_character_exists` | Oponente tem pelo menos 1 Character vivo |
| `opponent_has_equipment` | Oponente tem algum equipamento |
| `opponent_has_active_gift` | Oponente tem gift ativo |
| `opponent_has_ally_or_prey` | Oponente tem ally ou presa (Victim/Enemy) |
| `opponent_has_banes` | Oponente tem Banes |
| `opponent_has_spirit` | Oponente tem Spirit |
| `opponent_has_fetish_equipment` | Oponente tem equipamento Fetish |
| `opponent_can_frenzy` | Oponente pode frenzar (tem personagem com Rage > 0) |
| `opponent_stepping_sideways` | Oponente está entrando na Umbra |
| `enemy_spirit_in_play` | Espírito inimigo está em jogo |
| `opponent_dominates_umbra` | Oponente controla a Umbra (mais Gnosis ou personagens na Umbra) |
| `threat_from_umbra` | Há ameaça vindo da Umbra |

### Condições de Tabuleiro

| Condição | Quando é verdadeira |
|---|---|
| `losing_board_position` | Jogador tem menos personagens que o oponente |
| `no_pack_totem` | Não tem Pack Totem no pack |
| `no_pack_totem` | Não tem Pack Totem no pack |
| `no_lunar_phase` | Não está na fase lunar (simplificação: fora de combate) |
| `both_decks_nearly_empty` | Ambos os decks têm ≤ 3 cartas |

### Condições de Fase

| Condição | Quando é verdadeira |
|---|---|
| `moot_phase` | Fase de moot (Junta) ou Junta ativa |
| `entering_umbra` | Jogador está entrando na Umbra |
| `after_winning_moot` | Jogador acabou de vencer uma Junta que chamou |

---

## Integração no PriorityBot

O `PriorityBot` verifica a estratégia nos seguintes métodos:

| Método do Bot | O que usa da estratégia |
|---|---|
| `_agir_recurso()` | `resource_play_order` para ordenar cartas |
| `_agir_recurso()` | `action_priorities` para Action cards (Friends in High Places) |
| `_escolher_carta_combate_como_acao()` | `combat_action_preferences` (+20 bônus) |
| `_try_attack()` | `combat_action_preferences` |
| `_equip_card_to_pack()` | `equipment_assignments` |
| `_agir_umbra()` | `umbra_strategy` (enter/save/keep) |
| `_agir_redraw()` | `redraw_rules` (never_discard, prefer types) |
| `_agir_moot()` | `moot_strategy` (vote yes/no) |
| `_try_eliminate_threat()` | `target_priority` (ffa_diplomacy, threat_response) |
| `_escolher_gift()` | `gift_priorities` (ordenar por prioridade) |
| `_decide_combat()` / `play_card` step | `combat_event_priorities` (jogar CE face-down estratégico) |
| `strategy.sorted_actions()` | `action_priorities` (ordenar Action cards por prioridade) |

**Fallback:** Se o `deck_id` do jogador não tem config (`deck<id>_config.json`
não existe), o bot usa a heurística original — nenhuma modificação no
comportamento. 100% retrocompatível.

---

## Como Criar uma Config

### Passo 1: Diagnosticar o deck

Use o validador e as queries de deck para entender o que o deck precisa:

```bash
# Validar
PYTHONPATH=. .venv/bin/python3 -c "
from rage_web.helpers.deck_validator import validate_deck
r = validate_deck(1055)
print(r)
"

# Ver gifts, equipamentos, CAs, etc
PYTHONPATH=. .venv/bin/python3 -c "
from rage_web.helpers.deck_queries import resumo_pack
r = resumo_pack(1055)
print(r)
"
```

### Passo 2: Identificar gifts-chave

Quais gifts são o motor do deck? Ex: para Ajaba, Song of Rage + Spirit of
the Fray + Razor Claws são o engine principal (priority 90-100).

Quais gifts são situacionais? Power of the Ways (só útil na Umbra),
Geas (só se há alvo forte).

### Passo 3: Definir equipamentos

Quem recebe o quê? Um personagem com Rage baixo é bom candidato para
Shotgun. Um tanque deve receber o Bivouac (cura extra).

### Passo 4: Definir ações de combate

Para cada personagem, liste as CAs que funcionam melhor:
- Personagem frágil com Rage baixo: prefere block/dodge/defensive.
- Personagem agressor: prefere ações de alto dano.

### Passo 5: Testar

```bash
# Partida 1v1
.venv/bin/rage-match --deck 1055 --deck 629 --seed 42

# FFA 4 jogadores
.venv/bin/rage-match --deck 1055 --deck 1054 --deck 629 --deck 465 --seed 42

# Testar múltiplas seeds
for seed in 7 13 21 42 99; do
    result=$(.venv/bin/rage-match --deck 1055 --deck 629 --seed $seed --quiet 2>&1)
    echo "Seed $seed: $(echo '$result' | grep VENCEU | sed 's/.*🏆 //;s/ VENCEU.*//')"
done
```

---

## Exemplos Completos

### Config Mínima (apenas gifts + redraw)

```json
{
  "deck_id": 9001,
  "name": "Meu Deck",
  "style": "balanced",

  "gift_priorities": [
    {"slug": "power-of-the-ways", "priority": 100, "condition": "always", "desc": "Power of the Ways"}
  ],

  "redraw_rules": {
    "never_discard": ["Power of the Ways", "Caern"]
  }
}
```

### Config Completa (Defensive)

Veja `data/deck_strategies/deck2004_config.json` (Questor Defence) para
exemplo de config com `defensive_pacing`, `action_priorities` e `combat_notes`.

### Outros Exemplos

Veja `data/deck_strategies/deck1055_config.json` (Philodox) ou
`data/deck_strategies/deck1044_config.json` (Ajaba) para exemplos
de config com outras estratégias.

### Config Moot — Grimfang (deck 2008)

Exemplo de deck de **controle via Moot** com insights de jogador
humano. Resultado: 64.3% → 82.6% WR após aplicar insights.

```json
{
  "deck_id": 2008,
  "style": "control",
  "combat_notes": {
    "philosophy": "ESCAPE ONLY. Combat deck = end combats, not win them.",
    "who_fights": "Flame Spirits are good alphas. Never use voting chars.",
    "run_like_hell": "Voting chars should NOT use Run Like Hell."
  },
  "combat_action_preferences": {
    "_default": {
      "escape_priority": "ALWAYS escape. Never attack unless forced."
    },
    "grimfang": {
      "special": "NEVER fight. Voting lynchpin.",
      "run_like_hell": "FORBIDDEN on Grimfang"
    }
  },
  "target_priority": {
    "never_initiate_alpha_combat": true,
    "use_flame_spirit_for_alpha": true
  }
}
```

**Chave:** `never_initiate_alpha_combat: true` + escape priority.
O bot para de atacar desnecessariamente e foca em Moots.

---

## Boas Práticas

1. **Prioridades realistas:** 100 = essencial, 80-90 = importante,
   50-70 = útil, <50 = filler. Gifts com priority 0-10 só são jogados
   se não há mais nada.

2. **Condições específicas:** Use `has_character_named:<slug>` para gifts
   que só um personagem específico pode usar. Use `combat_likely` para
   gifts de combate que são inúteis fora de combate.

3. **FFA:** Em configs para Free-for-All, considere `ffa_mode` como
   condição para gifts defensivos (cura, redução de dano). Use
   `ffa_diplomacy: "weaken_largest"` para atacar o líder.

4. **Evite duplicação:** Se o deck tem 3 cópias de um gift, uma entrada
   no config cobre todas.

5. **Documente os combos:** Use o campo `notes` para explicar a estratégia
   — ajuda outros jogadores a entenderem o deck.

6. **Teste antes de comitar:** Sempre rode uma partida de teste após
   criar/modificar um config para garantir que o bot não quebra.
