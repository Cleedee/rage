# Motor de Jogo - Rage CCG

## Arquitetura

```
rage_web/game_engine/
├── state.py           ← GameState, CardInstance, PlayerState
├── combat_queue.py    ← Fila de ações + "Último a Declarar"
├── actions.py         ← Ações válidas e validação
├── rules.py           ← Constantes, checagens de regra
├── cli.py             ← REPL de debug (PLAY, ATTACK, STATUS)
├── api.py             ← API REST thin (futuro)
└── bot/
    ├── base.py        ← Interface do bot
    ├── evaluator.py   ← Sistema de notas (ameaça, vantagem, etc.)
    └── priority_bot.py← Árvore de decisão por prioridades
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
