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

| Arquivo | Deck |
|---|---|
| `data/deck_strategies/deck1055_config.json` | O Julgamento (Philodox) |
| `data/deck_strategies/deck1044_config.json` | Ajaba — Hienas da Savana |
| `data/deck_strategies/deck465_config.json` | Apocalypse — Primeiro Esquadrão #21 |

---

## Formato do JSON

```json
{
  "deck_id": 1055,
  "name": "O Julgamento (Philodox)",
  "style": "control | combo | aggro | midrange | ffa",

  "gift_priorities": [ ... ],
  "resource_play_order": [ ... ],
  "combat_action_preferences": { ... },
  "equipment_assignments": [ ... ],
  "caern_preferences": [ ... ],
  "target_priority": { ... },
  "umbra_strategy": { ... },
  "redraw_rules": { ... },
  "moot_strategy": { ... },
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
    "card_id": 1021,
    "priority": 100,
    "condition": "umbra_available",
    "desc": "Power of the Ways — cura na Umbra"
  },
  {
    "card_id": 1029,
    "priority": 90,
    "condition": "combat_likely",
    "desc": "Resist Pain — redução de dano"
  }
]
```

| Campo | Tipo | Descrição |
|---|---|---|
| `card_id` | int | ID da carta no banco SQLite |
| `priority` | int | Prioridade (0-100). Mais alto = jogado primeiro |
| `condition` | string | Condição para ativar (veja tabela abaixo) |
| `desc` | string | (opcional) Descrição humana |

**Regras:**
- Se múltiplos gifts estão na mão, o bot ordena por priority decrescente.
- Se a `condition` não é satisfeita, a prioridade é reduzida em 100
  (ou seja, o gift só é jogado se a condição estiver ativa).
- Uma mesma `card_id` pode aparecer múltiplas vezes com condições
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

### 3. `combat_action_preferences` — Preferências de Ação de Combate

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

### 4. `equipment_assignments` — Designação de Equipamentos

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

### 5. `caern_preferences` — Preferência de Caern

Define qual Caern jogar primeiro.

```json
"caern_preferences": [
  { "card_name": "Sky River Caern", "priority": 100 }
]
```

O bot tenta jogar o Caern da lista primeiro (comparação `in` no nome).

### 6. `target_priority` — Prioridade de Alvos

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
  }
}
```

| Campo | Tipo | Valores | Descrição |
|---|---|---|---|
| `prefer_low_health` | bool | true/false | Prefere alvos com menos HP |
| `character_kill_order` | string | `"lowest_health"`, `"highest_renown"`, `"lowest_rage"` | Ordem de eliminação |
| `ffa_diplomacy` | string | `"weaken_largest"`, `"attack_weakest"`, `"balanced"` | Estratégia FFA |
| `avoid_overextend` | bool | true/false | Evita ataques que deixariam o pack vulnerável |

**FFA Diplomacy:**
- `weaken_largest`: Ataca o líder em VP (default)
- `attack_weakest`: Ataca o jogador com menos personagens
- `balanced`: Ataca quem tem mais personagens (maior ameaça imediata)

### 7. `umbra_strategy` — Estratégia da Umbra

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

### 8. `redraw_rules` — Regras de Redraw

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
| `always_discard_if_duplicate` | int[] | card_ids que são descartados se há cópia duplicada |
| `prefer_discard_types` | string[] | Tipos preferenciais para descarte |

### 9. `moot_strategy` — Estratégia de Juntas

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

### 10. `notes` (documentação humana)

Comentários sobre a estratégia do deck, não usado pelo motor.

```json
"notes": {
  "combo_principal": "Song of Rage → Frenesi → Crinos → Fast Strike → Sense of the Prey → atacar novamente",
  "fraqueza_sem_caern": "Bivouac essencial para regeneração"
}
```

---

## Condições Suportadas

| Condição | Quando é verdadeira |
|---|---|
| `always` | Sempre |
| `umbra_available` | Fase Umbra OU algum personagem pode step sideways |
| `has_characters` | Pelo menos 1 Character no pack |
| `has_strong_target` | Oponente tem criatura com threat rating ≥ 5 |
| `has_injured_character` | Algum Character com HP atual < HP máximo |
| `opponent_stronger` | Oponente tem Rage total maior que o jogador |
| `has_character_named:<slug>` | Personagem com slug específico está vivo no pack |
| `combat_likely` | Fase é Combat OU há oponentes com personagens |
| `combat_active` | Combate ativo no momento |
| `is_combat_phase` | Fase atual é Combat |
| `ffa_mode` | 3+ jogadores ativos |
| `card_in_hand:<nome>` | Carta com nome contendo `<nome>` está na mão |
| `character_in_umbra` | Algum Character está na Umbra |

---

## Integração no PriorityBot

O `PriorityBot` verifica a estratégia nos seguintes métodos:

| Método do Bot | O que usa da estratégia |
|---|---|
| `_agir_recurso()` | `resource_play_order` para ordenar cartas |
| `_escolher_carta_combate_como_acao()` | `combat_action_preferences` (+20 bônus) |
| `_try_attack()` | `combat_action_preferences` |
| `_equip_card_to_pack()` | `equipment_assignments` |
| `_agir_umbra()` | `umbra_strategy` (\(enter/save/keep\)) |
| `_agir_redraw()` | `redraw_rules` (never_discard, prefer types) |
| `_agir_moot()` | `moot_strategy` (vote yes/no) |
| `_try_eliminate_threat()` | `target_priority` (ffa_diplomacy) |
| `_escolher_gift()` | `gift_priorities` (ordenar por prioridade) |

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
the Fray + Razor Claws são o combo principal (priority 90-100).

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
  "style": "midrange",

  "gift_priorities": [
    {"card_id": 1021, "priority": 100, "condition": "always", "desc": "Power of the Ways"}
  ],

  "redraw_rules": {
    "never_discard": ["Power of the Ways", "Caern"]
  }
}
```

### Config Completa

Veja `data/deck_strategies/deck1055_config.json` (Philodox) ou
`data/deck_strategies/deck1044_config.json` (Ajaba) para exemplos
de config completas com todas as seções.

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
