# Motor de Jogo - Rage CCG

## Arquitetura

```
rage_web/game_engine/
├── state.py           ← GameState, CardInstance, PlayerState
├── combat_queue.py    ← Fila de ações + "Último a Declarar"
├── actions.py         ← Ações válidas e validação
├── rules.py           ← Constantes, checagens de regra
├── effects.py         ← Sistema de efeitos estruturados
├── anunciador.py      ← Sistema de anúncio → resposta → resolução
├── match.py           ← Simulador de partidas bot vs bot
├── cli.py             ← REPL de debug (PLAY, ATTACK, STATUS)
├── api.py             ← API REST thin (futuro)
├── tournament.py      ← Motor de torneio Suíço
└── bot/
    ├── base.py        ← Interface do bot
    ├── evaluator.py   ← Sistema de notas (ameaça, vantagem, etc.)
    ├── priority_bot.py← Árvore de decisão por prioridades
    └── strategy_engine.py ← Config de estratégia por deck (JSON)
```

## Plano de Implementação

### Fase 1 — State + Combat Queue
- `state.py`: `GameState`, `PlayerState`, `CardInstance`, `CombatState`
- `combat_queue.py`: Ciclo de combate com declaração, revelação, "Último a Declarar"
- Testes de unidade completos

### Fase 2 — CLI de Debug
- `cli.py`: REPL com comandos `PLAY`, `ATTACK`, `STATUS`, `DRAW`, `PASS`
- Jogar partidas completas no terminal

### Fase 3 — REST API
- `api.py`: Endpoints `/api/game/new`, `/api/game/<id>`, `/api/game/<id>/action`
- Tanto o front-end quanto o bot consomem a mesma API

### Fase 4 — Bot
- `bot/evaluator.py`: Sistema de notas (ameaça, vantagem, pressão de vida)
- `bot/priority_bot.py`: Árvore de decisão: sobreviver > eliminar ameaça > desenvolver mesa > atacar

## Mecânicas Implementadas

### Ciclo de Combate

O Rage CCG tem um sistema de combate único baseado em **ações simultâneas**:

1. **Declaração**: Cada criatura escolhe uma Combat Action (face-down)
2. **Revelação simultânea**: Todas as ações são reveladas ao mesmo tempo
3. **Reveal Step**: Quem declarou por último pode jogar **Feints** ou **Instinctive Actions**
4. **Resolução**: Aplica danos, curas, efeitos
5. **Fim**: Remove mortos, aplica mends

O "Último a Declarar" (Last to Declare) é a alma do combate: o jogador que declara por último vê as ações adversárias
e pode reagir com Feints, ganhando vantagem tática.

### Comandos CLI

| Comando | Exemplo | Descrição |
|---|---|---|
| `STATUS` | `STATUS` | Mostra tabuleiro, mão, VP |
| `DRAW` | `DRAW` | Compra uma carta |
| `PLAY <n>` | `PLAY 3` | Joga carta da mão (índice) |
| `ATTACK <criatura>` | `ATTACK 1` | Ataca criatura alvo |
| `PASS` | `PASS` | Passa a ação/vez |
| `HELP` | `HELP` | Lista comandos |
| `SAVE` | `SAVE partida1` | Salva estado |
| `LOAD` | `LOAD partida1` | Carrega estado |

### Sistema de Avaliação do Bot

O bot avalia o board com notas 0-10 para cada fator:

| Fator | Peso | Descrição |
|---|---|---|
| Ameaça | w1 | Dano potencial do inimigo |
| Vantagem de mesa | w2 | Diferença de criaturas/equipamentos |
| Pressão de vida | w3 | Vida restante dos meus personagens |
| Proximidade da vitória | w4 | VP atual vs necessário |

### Árvore de Decisão

```
1. SOBREVIVER
   → Curar, bloquear, fugir
2. ELIMINAR AMEAÇA
   → Atacar maior threat, usar gifts ofensivos
3. DESENVOLVER MESA
   → Jogar personagens, equipamentos, ritos
4. ATACAR
   → Buscar VP, atacar vulnerável
```

Estratégias suportadas via config JSON por deck:
- `midrange` (padrão): sobreviver > desenvolver > eliminar > atacar
- `aggro`: eliminar > atacar > desenvolver > sobreviver
- `control`: sobreviver > eliminar > desenvolver > atacar
- `vp_race`: desenvolver > sobreviver > eliminar > atacar
- `swarm` / `lento`: eliminar > atacar > sobreviver > desenvolver
- `defensive_pacing`: sobreviver > eliminar > desenvolver > atacar (novo)

---

## Strategy Engine (`strategy_engine.py`)

Motor de estratégia que permite guiar o PriorityBot com configurações JSON por deck.

### Arquivo de Configuração

```
data/deck_strategies/
├── deck<id>_config.json    ← Config do bot (motor lê)
└── deck<id>_<nome>.md      ← Documentação humana da estratégia
```

### Seções do Config

| Seção | O que faz |
|---|---|
| `gift_priorities` | Ordena gifts por prioridade + condições |
| `resource_play_order` | Ordem de tipos na Resource Phase |
| `combat_action_preferences` | Ações de combate preferidas por personagem |
| `combat_event_priorities` | Combat Events priorizados (Frenzy, Taking Death Blow, etc.) |
| `action_priorities` | Action cards priorizados (Friends in High Places, Sneak Attack) |
| `equipment_assignments` | Quem equipa o quê |
| `target_priority` | Quem atacar (inclui estratégia FFA) |
| `umbra_strategy` | Quem entra/sai da Umbra |
| `redraw_rules` | O que nunca descartar no redraw |
| `moot_strategy` | Como votar em Juntas |
| `combat_notes` | Notas táticas para o bot |

### Condições para `gift_priorities` e `combat_event_priorities`

| Condição | Descrição |
|---|---|
| `always` | Sempre ativo |
| `umbra_available` | Fase Umbra ou pode step sideways |
| `has_characters` | Pelo menos 1 Character no pack |
| `has_strong_target` | Oponente tem criatura com Renown >= 2 |
| `has_injured_character` | Algum Character com HP < max |
| `opponent_stronger` | Oponente tem mais chars ou rage total |
| `has_character_named:<slug>` | Personagem com slug=<slug> está vivo |
| `combat_likely` | Fase Combat ou tem oponentes no pack |
| `combat_active` | Combate ativo no momento |
| `has_good_target` | Há Victim/Enemy no HG ou personagem fraco |
| `in_combat_with_victim` | Está em combate com Victim |
| `about_to_attack` | Fase de declaração de combate |
| `character_under_attack` | Personagem está sendo atacado |
| `character_receives_mortal_wound` | Personagem prestes a morrer |
| `defensive_emergency` | Personagem com HP <= 2 |
| `ffa_mode` | 3+ jogadores ativos |
| `card_in_hand:<nome>` | Carta com nome <nome> está na mão |
| `character_in_umbra` | Algum Character está na Umbra |

### Métodos Principais

| Método | Descrição |
|---|---|
| `sorted_gifts()` | Ordena gifts na mão por prioridade |
| `sorted_events()` | Ordena eventos na mão por prioridade |
| `sorted_actions()` | Ordena Action cards (Friends in High Places, etc.) |
| `sorted_combat_events()` | Ordena Combat Events na mão de combate |
| `resource_play_order()` | Retorna ordem de tipos para Resource phase |
| `equipment_assignment()` | Retorna quem deve receber um equipment |
| `should_keep_in_redraw()` | Retorna se carta deve ser mantida no redraw |
| `get_ffa_target()` | Retorna ID do jogador a atacar em FFA |

---

## Limitador de Victim Attacks

### Problema

Victims no Hunting Grounds atacam automaticamente personagens ao final de cada Combat Phase. Se o combate da vítima cria um novo combate, que por sua vez cria outro combate, o jogo entra em loop infinito.

### Solução

Adicionado em `state.py`:

```python
_victim_attacks_this_phase: int = 0
_MAX_VICTIM_ATTACKS_PER_PHASE: int = 5
```

- Contador é incrementado quando um trigger de `victim_attack` é registrado
- Contador é resetado ao entrar na Combat Phase
- Quando atinge o limite, novos triggers não são registrados

### Exemplo de Loop Corrigido

```
1. Combat Phase termina
2. Vigilante (565) registra trigger para atacar Questor
3. Combate Vigilante vs Questor inicia
4. Combate termina → Vigilante ataca novamente
5. Limite atingido (5) → trigger não registrado
6. Jogo continua normalmente
```

---

## Torneio (`tournament.py`)

### Estrutura

```
Tournament
├── TournamentPlayer (inscritos)
└── TournamentMatch (empareamentos)
```

### Formatos

- `swiss`: Suíço (padrão) — rounds baseados em número de jogadores
- `single_elim`: Eliminação simples
- `double_elim`: Eliminação dupla

### Comandos

```python
from rage_web.game_engine.tournament import (
    criar_torneio,
    inscrever_jogador,
    executar_rodada,
    classificacao,
)

# Criar torneio
t = criar_torneio('Teste Deck 2004', formato='swiss')

# Inscrever jogadores (bots)
inscrever_jogador(t.id, 'Bot 2004', deck_id=2004, difficulty='hard')
inscrever_jogador(t.id, 'Bot 465', deck_id=465, difficulty='hard')

# Executar rodadas
executar_rodada(t.id)

# Ver classificação
ranking = classificacao(t.id)
```

### Script de Torneio

```bash
# Round-robin: 2004 vs todos os oponentes (3 partidas cada)
cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py --matches 3

# Partidas aleatórias
cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py --random --matches 20

# Com verbosidade
cd /workspace && PYTHONPATH=. python3 scripts/torneio_questor_2004.py --matches 1 -v 1
```

### Resultados do Torneio (Deck 2004)

| Métrica | Valor |
|---|---|
| Win Rate | 47.9% |
| vs Wyrm | 58% WR |
| vs Gaia | 33% WR |
| Erros stuck | 12.5% |

---

## Ações por Fase

### Combat Phase

O bot executa ações nesta ordem:

1. **Alpha Action**: Atacar, challenge, passar
2. **Play Card Step**: Jogar Combat Actions face-down
3. **Targeting Step**: Escolher alvos
4. **Reveal Step**: Revelar ações + Feints
5. **Bluff Step**: Processar ilegais + bluffs
6. **Resolution Step**: Aplicar danos (Fast → Normal → Slow)
7. **Withdrawal Step**: Atacante decide se retira
8. **Between Rounds**: Nova rodada ou fim do combate

### Resource Phase

Ordem de prioridade (configurável via `resource_play_order`):

1. Territory / Caern
2. Character / Ally
3. Equipment
4. Gift / Event / Action
5. Victim / Enemy / Battlefield

---

## ThreatAnalyzer (`bot/threat_analyzer.py`)

Analisador de ameaças que detecta cartas permanentes do oponente que afetam negativamente o deck do bot.

### Estrutura

```python
@dataclass
class Threat:
    card: CardInstance          # A carta ameaçadora
    card_name: str              # Nome legível
    card_slug: str              # Slug para matching
    threat_type: str            # 'equipment', 'gift', 'caern', etc.
    severity: float             # 0.0–1.0 (1.0 = crítica)
    reason: str                 # Por que é ameaça
    response: str               # Resposta sugerida
```

### Catálogo de Ameaças

O `THREAT_CATALOG` contém ameaças conhecidas:

| Tipo | Exemplos | Severidade |
|---|---|
| **Equipment** | Flak Jacket (0.50), Skin of Hellbound (0.40), Vampire Blood (0.35) |
| **Gift** | Luna's Armor (0.60), Stench of Death (0.70), Shroud (0.65) |
| **Caern** | Sky River (0.50), Rytthiku (0.55) |
| **Territory** | Toxic Waste (0.50), Shadow Lord Territory (0.40) |
| **Battlefield** | Battle of Screaming Mud (0.60), War of Attrition (0.55) |
| **Combat Event** | Iron Will (0.50), Taking the Death Blow (0.40) |
| **Ally** | Dreamspeaker Mage (0.50) |

### Métodos Principais

| Método | Descrição |
|---|---|
| `analyze()` | Escaneia tabuleiro, retorna Threats ordenados por severidade |
| `top_threat()` | Retorna maior ameaça |
| `threats_by_type(type)` | Filtra por tipo |
| `threat_severity_for(slug)` | Severidade de um slug |
| `get_threat_response(slug)` | Resposta recomendada |
| `top_threat_target()` | CardInstance da maior ameaça |

### Respostas Sugeridas

| Resposta | Descrição |
|---|---|
| `attack` | Atacar portador/origem |
| `attack_low_rage` | Atacar com Rage baixo |
| `attack_from_umbra` | Atacar da Umbra |
| `attack_multiple` | Atacar com múltiplos chars |
| `remove` | Remover装备/gift |
| `flee` | Fugir do combate |
| `cancel` | Cancelar efeito |
| `block` | Bloquear com CAs defensivos |
| `kill_hg` | Matar no HG |
| `ignore` | Ignorar (baixa prioridade) |

### Integração com Config JSON

```json
{
  "target_priority": {
    "threat_response": {
      "luna-s-armor": "ignore",
      "flak-jacket": "vital_blow",
      "stench-of-death": "use_spirit_attack"
    }
  }
}
```

---

## Notas Táticas

### Vital Blow Contingency

Se oponente usa **Vital Blow** (Rg:6) no seu personagem, ele fica com **Rage 1** no próximo round. Ter CAs Rage 1 na mão garante que você ainda pode agir:

- Off-balanced Attack (Rg:1)
- Stinging Wound (Rg:1)
- Dodge (Rg:1)

### Friends in High Places

Encerra **qualquer combate sem frenzy**. Usar para:
1. Encerrar combate desfavorável
2. Desacelerar oponentes em FFA
3. Proteger personagens frágeis

### Frenzy Timing

Frenzy dá +Rage cards e +hack-apart level. Usar **ANTES** de atacar para garantir kill com Gaia's Will Corrupted na Withdrawal step.

---

## Sistema de Efeitos Estruturados

O motor de jogo usa um sistema de efeitos estruturados para cartas com JSON em `data/cards/`. Cada carta tem modos com efeitos que são resolvidos automaticamente.

### Arquitetura

```
data/cards/<slug>.json  →  ModeloCarta  →  ResolvedorEfeitos  →  GameState
```

### ModeloCarta

```python
@dataclass
class ModeloCarta:
    id: str                          # ID da carta (slug)
    nome: str                        # Nome legível
    tipo: str                        # Tipo (Gift, Event, etc.)
    modos: list[Modo]                # Modos de uso
    descartar_apos_uso: bool = False # Descartar após usar (Clawstorm)
```

### Modo

```python
@dataclass
class Modo:
    descricao: str                   # Descrição do modo
    efeitos: list[Efeito]            # Lista de efeitos
    condicao_uso: Optional[str]      # Condição para usar (ex: between_rounds_only)
    restricoes: list[str]            # Restrições (ex: no_firearm)
```

### EfeitoTipo

| Tipo | Descrição |
|---|---|
| `dano` | Dano a uma criatura |
| `curar` | Cura uma criatura |
| `destruir` | Destrói uma criatura |
| `descarte` | Descarta cartas da mão |
| `comprar` | Compra cartas do deck |
| `equipar` | Equipa um item |
| `tocar` | Toca uma carta (ativa efeito) |
| `mover_umbra` | Move para/da Umbra |
| `ganhar_vp` | Ganha Victory Points |
| `perder_vp` | Perde Victory Points |
| `moot_*` | Efeitos de Moot (VP, restrições, etc.) |
| `impedir_acoes` | Impede ações por X rounds |
| `impedir_retirada` | Impede fugir do combate |
| `impedir_frenzy` | Impede frenzy (global) |
| `impedir_bluff` | Impede blufar por resto do combate |
| `acao_extra_por_rodada` | Ações extras de combate (Clawstorm, Devilwhip) |
| `imune_combate_rage` | Imune a CAs de certo Rage |
| `modificar_atributo_passivo` | Buff passivo persistente |
| `modificar_gauntlet` | Modifica o Gauntlet |
| `modificar_hand_size` | Modifica tamanho da mão |
| `descartar_apos_uso` | Descarta carta após uso |

### Condições de Uso (`condicao_uso`)

| Condição | Descrição |
|---|---|
| `between_rounds_only` | Só pode ser usado entre rodadas de combate |
| `personagem_na_umbra` | Precisa de personagem na Umbra |
| `nao_frenetico` | Não pode estar em frenzy |
| `fase_umbra_mokole` | Fase de Umbra do Mokole |
| `alpha_attack_hg` | Alpha atacando Hunting Grounds |
| `apos_vencer_junta` | Após vencer uma Junta |
| `tem_ratkin_character` | Tem personagem Ratkin no pack |

### Restrições do Modo (`restricoes`)

| Restrição | Descrição |
|---|---|
| `no_firearm` | Não pode ser usado com Firearm equipado |

### Exemplo: Clawstorm

```json
{
  "id": "clawstorm",
  "nome": "Clawstorm",
  "tipo": "Gift",
  "gnosis": 5,
  "requires": "Bastet",
  "modos": [
    {
      "descricao": "Play between rounds. Draw 2 combat cards. Play up to 3 CAs.",
      "condicao_uso": "between_rounds_only",
      "efeitos": [
        { "tipo": "comprar", "alvo": "self", "quantidade": 2 },
        { "tipo": "acao_extra_por_rodada", "alvo": "self", "quantidade": 3 },
        { "tipo": "impedir_bluff", "alvo": "self", "duracao": "end_of_combat" },
        { "tipo": "descartar_apos_uso", "alvo": "self" }
      ],
      "restricoes": ["no_firearm"]
    }
  ],
  "descartar_apos_uso": true
}
```

### Fluxo de Resolução

1. **Validação**: `aplicar_carta()` verifica `condicao_uso` e `restricoes`
2. **Pagamento**: Bot paga custos de Rage/Gnosis automaticamente
3. **Resolução**: Cada efeito é resolvido pelo `ResolvedorEfeitos`
4. **Descarte**: Se `descartar_apos_uso=true`, carta vai para discard_sept

### Adicionando Novos Efeitos

1. Adicione o tipo ao enum `EfeitoTipo` em `effects.py`
2. Implemente o resolver em `ResolvedorEfeitos`
3. Registre no dicionário `_RESOLVER_MAP`
4. Crie o JSON da carta em `data/cards/`
5. Adicione testes em `tests/test_game_engine_effects.py`
