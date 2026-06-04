# Análise do Projeto: Rage CCG Web

## 📋 Visão Geral

**rage-web** é uma aplicação web Flask para gerenciar cartas de um **Collectible Card Game (CCG)** chamado **Rage CCG**. A aplicação permite criar, listar, editar e excluir cartas (personagens, equipamentos e genéricas), além de gerenciar decks. O projeto inclui um **motor de jogo completo** (`game_engine/`) com simulação de partidas, bot com IA e API REST.

---

## 🏗️ Estrutura do Projeto

```
/workspace
├── app.py                          # Ponto de entrada da aplicação
├── pyproject.toml                  # Configuração do projeto Python (dependências)
├── docker-compose.yml              # Infraestrutura: Redis (desejado, mas não usado)
├── Makefile                        # Comandos auxiliares (flask run, docker)
├── NOTAS.txt                       # Links de referência (Flask, HTMX, Bulma, Redis OM)
├── README.md                       # Vazio
├── uv.lock                         # Lock file do gerenciador de pacotes uv
├── .python-version                 # Python 3.12
├── .gitignore
│
├── rage_web/                       # 📦 Pacote principal da aplicação
│   ├── __init__.py                 # Factory: create_app()
│   ├── config.py                   # Configurações (SQLite, SECRET_KEY)
│   ├── database.db                 # 🗄️ Banco SQLite
│   │
│   ├── game_engine/                # 🎮 Motor de jogo (4 fases implementadas)
│   │   ├── __init__.py
│   │   ├── state.py               # GameState, CardInstance, PlayerState, CombatState, MootState
│   │   ├── combat_queue.py        # Ciclo de combate: declarar → revelar → resolver
│   │   ├── rules.py               # Constantes, validações, pagadores de custo Rage/Gnosis
│   │   ├── effects.py             # Sistema de efeitos estruturados (ModeloCarta, ResolvedorEfeitos)
│   │   ├── anunciador.py          # Sistema de anúncio → resposta → resolução
│   │   ├── match.py               # Simulador de partida entre dois bots
│   │   ├── cli.py                 # REPL de debug (STATUS, DRAW, PLAY, ATTACK, etc.)
│   │   ├── api.py                 # API REST (Blueprint Flask)
│   │   └── bot/                    # IA do bot
│   │       ├── __init__.py
│   │       ├── evaluator.py       # BoardEvaluator (threat, advantage, pressure, victory)
│   │       └── priority_bot.py    # PriorityBot (árvore de decisão por prioridades)
│   │
│   ├── ext/                        # Extensões
│   │   ├── base.py                 # Base declarativa do SQLAlchemy
│   │   ├── database.py             # Inicialização do SQLAlchemy
│   │   ├── cli.py                  # Comando CLI: flask init-database
│   │   └── repository.py          # Camada de repositório (CRUD)
│   │
│   ├── helpers/
│   │   └── forms.py                # Formulários WTForms
│   │
│   ├── models/                     # Modelos do banco
│   │   ├── card.py                 # Card (carta)
│   │   ├── deck.py                 # Deck
│   │   └── picture.py             # Picture (imagem)
│   │
│   ├── blueprints/                 # Blueprints (módulos)
│   │   ├── home/                   # Página inicial
│   │   ├── cards/                  # CRUD de cartas
│   │   └── decks/                  # CRUD de decks
│   │
│   ├── templates/
│   │   └── base.html              # Template base com Bulma + HTMX
│   │
│   └── instance/images/           # Imagens das cartas
│       └── hatii-the-thunderer.png
│
├── migrations/                     # Migrations Alembic
│   ├── alembic.ini
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 6bda8104262a_tabelas_iniciais.py
│
├── data/
│   └── cards/                     # JSONs de cartas com efeitos estruturados
│
└── tests/
    ├── conftest.py                 # Fixtures pytest
    ├── test_endpoints.py           # Testes dos endpoints web
    ├── test_game_engine.py         # Testes do motor de jogo (state, combat_queue, rules)
    ├── test_game_engine_anunciador.py  # Testes do sistema de anúncio
    ├── test_game_engine_api.py     # Testes da API REST
    ├── test_game_engine_bot.py     # Testes do bot (evaluator + priority)
    ├── test_game_engine_cli.py     # Testes do CLI/REPL
    └── test_game_engine_effects.py # Testes do sistema de efeitos
```

---

## ⚙️ Stack Tecnológica

| Tecnologia | Uso |
|---|---|
| **Python 3.12** | Linguagem |
| **Flask 3.1.1** | Framework web |
| **Flask-SQLAlchemy 3.1.1** | ORM + banco de dados |
| **Flask-Migrate 4.1.0** | Migrations (Alembic) |
| **Flask-WTF 1.2.2** | Formulários + CSRF |
| **WTForms** | Definição de formulários |
| **SQLite** | Banco de dados |
| **Bulma CSS 1.0.4** | Framework CSS (via CDN) |
| **HTMX 1.9.10** | Interatividade AJAX (via CDN) |
| **Bootstrap Icons** | Ícones (via CDN) |
| **python-slugify** | Slug para nomes de arquivos |
| **pytest** | Testes |
| **uv** | Gerenciador de pacotes |

---

## 🗄️ Modelos de Dados

### Card (Carta) — `rage_web/models/card.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome da carta |
| `tipo` | String | Tipo: "Character", "Equipment" ou genérico |
| `rage` | Integer (default=0) | Atributo Fúria |
| `gnosis` | Integer (default=0) | Atributo Gnose |
| `health` | Integer (default=0) | Atributo Vitalidade |
| `rage_morph` | Integer (default=0) | Fúria em forma alternada |
| `gnosis_morph` | Integer (default=0) | Gnose em forma alternada |
| `health_morph` | Integer (default=0) | Vitalidade em forma alternada |
| `requires` | String (default='') | Requisitos (para equipamentos) |
| `keyword` | String (default='') | Palavras-chave |
| `text` | String (default='') | Texto/descrição/efeito |

### Deck — `rage_web/models/deck.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome do deck |
| `description` | String (nullable) | Descrição opcional |

### Picture (Imagem) — `rage_web/models/picture.py`

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | Integer (PK) | Identificador único |
| `name` | String | Nome do arquivo salvo |
| `side` | Integer (default=0) | 0 = frente, 1 = verso |
| `version` | String (nullable) | Versão da imagem |
| `card_id` | Integer (FK → card.id) | Relacionamento com Card |
| `card` | Relationship | Objeto Card relacionado |

---

## 🧭 Rotas / Endpoints

| Rota | Método | Funcionalidade |
|---|---|---|
| `/` | GET | Home |
| `/cards` | GET | Listar cartas |
| `/cards/new` | GET | Menu de criação |
| `/cards/new/character` | GET | Formulário de nova carta Character |
| `/cards/new/equipment` | GET | Formulário de nova carta Equipment |
| `/cards/new/generic` | GET | Formulário de nova carta genérica |
| `/cards/character` | POST | Salvar/atualizar Character |
| `/cards/equipment` | POST | Salvar Equipment |
| `/cards/generic` | POST | Salvar carta genérica |
| `/cards/{id}` | GET | Visualizar/editar carta |
| `/cards/{id}` | POST | Salvar edição da carta |
| `/cards/{id}/view` | GET | Página de detalhes |
| `/cards/{id}/delete` | POST | Excluir carta |
| `/cards/{id}/upload-fan` | POST | Upload de imagem |
| `/cards/{id}/remove-fan` | POST | Remover imagem |
| `/decks` | GET | Listar decks |
| `/decks/new` | GET | Formulário de novo deck |
| `/decks` | POST | Salvar/atualizar deck |
| `/decks/{id}` | GET | Visualizar/editar deck |
| `/decks/{id}/delete` | POST | Excluir deck |
| `/decks/{id}/add-card` | POST | Adicionar carta |
| `/decks/{id}/remove-card` | POST | Remover carta |
| `/decks/{id}/update-quantity` | POST | Atualizar quantidade |
| `/decks/import` | GET/POST | Importar deck |

---

## 🎮 Motor de Jogo (`game_engine/`)

### Arquitetura — 4 Fases Implementadas

| Fase | Módulo | Status |
|---|---|---|
| Fase 1 — State + Combat Queue | `state.py`, `combat_queue.py` | ✅ Completo |
| Fase 2 — CLI de Debug | `cli.py` | ✅ Completo |
| Fase 3 — REST API | `api.py` | ✅ Completo |
| Fase 4 — Bot | `bot/evaluator.py`, `bot/priority_bot.py` | ✅ Completo |

### Módulos

#### `state.py` — Estado do Jogo
- **`Zone`**: Enum com 11 zonas (DECK_COMBAT, DECK_SEPT, HAND, PACK_HOME, HUNTING_GROUNDS, UMBRA, DISCARD_COMBAT, DISCARD_SEPT, VICTORY_PILE, OUT_OF_PLAY, REMOVED)
- **`CardInstance`**: Instância de carta em jogo (ID único, atributos, estado tapped/face-down, dano agravado)
- **`PlayerState`**: Estado do jogador (zonas, pools, redraw, regeneração, pagamento de custos Rage/Gnosis, step sideways)
- **`CombatState`**: Estado do combate (declarações, ordem de alpha, último a declarar)
- **`MootState`**: Estado de Juntas/Board Meetings (votação por Renome)
- **`GameState`**: Estado completo (turno, fase, jogadores, log, anúncios, vitória)

#### `combat_queue.py` — Ciclo de Combate
- Sistema de combate com **declaração simultânea** e **"Último a Declarar"**
- Funções: `start_combat`, `selecionar_alfa`, `calcular_ordem_alfa`, `declare_action`, `reveal_all`, `feint_action`, `resolve_combat`, `end_combat`, `verificar_vitoria`
- Verificação de Gauntlet (mesmo lado para combate)
- Resolução: ataques por índice + contra-ataques, destruição → Victory Pile

#### `rules.py` — Constantes e Regras
- Constantes: limites de atributos, tamanhos de mão, fases do turno, tipos de carta, zonas
- `parse_custo_rage()`: Converte campo damage para custo numérico
- `encontrar_pagador_rage/gnosis()`: Encontra personagem destapped com atributo suficiente
- `zona_da_carta()`: Determina zona por tipo (Pack Home vs Hunting Grounds)
- `encontrar_caern()`: Encontra Caern no pack
- `pode_step_sideways()`: Verifica Gnosis >= Gauntlet e Creature Class

#### `effects.py` — Sistema de Efeitos
- **`EfeitoTipo`**: Enum com 16 tipos (DANO, CURAR, DESTRUIR, DESCARTE, COMPRAR, TAPAR, etc.)
- **`AlvoTipo`**: Enum com condições de alvo (criatura inimiga/aliada, jogador, mão, etc.)
- **`ModeloCarta`**: Modelo de carta com modos e efeitos estruturados
- **`ResolvedorEfeitos`**: Aplica efeitos no estado do jogo (12 resolvedores)
- Carregamento automático de JSONs de `data/cards/`

#### `anunciador.py` — Sistema de Anúncio
- Fluxo: **anunciar → responder → resolver** (diferente de pilha LIFO estilo Magic)
- Suporte a **cartas modais** (escolha de modo)
- **Cancelamento**: anular efeito (pode cancelar cancelamento)
- `anunciar_e_resolver()`: Atalho de alto nível

#### `match.py` — Simulador de Partidas
- `run_match()`: Partida entre dois bots com dificuldades configuráveis
- Suporte a decks do banco de dados (`--deck1`, `--deck2`)
- Detecção de travamento (stale steps)
- Saída colorida no terminal com ícones Unicode

#### `cli.py` — REPL de Debug
- Comandos: `STATUS`, `DRAW`, `PLAY`, `ANUNCIAR`, `ESCOLHER`, `ANULAR`, `ATTACK`, `DECLARE`, `REVEAL`, `FEINT`, `RESOLVE`, `ENDCOMBAT`, `PASS`, `NEXT`, `CARDS`, `SAVE`, `LOAD`, `HELP`, `QUIT`
- `create_sample_game()`: Cria partida de exemplo com personagens e decks
- `build_game_from_decks()`: Cria partida a partir de decks do banco SQLite

#### `api.py` — API REST
- Blueprint Flask (`/api/game`) com endpoints:
  - `POST /new` — Nova partida
  - `GET /<id>` — Estado da partida
  - `GET /<id>/legal-actions` — Ações válidas no momento
  - `POST /<id>/draw`, `/play`, `/use-card`, `/attack`, `/declare`, `/reveal`, `/feint`, `/resolve`, `/end-combat`, `/pass`, `/next`
- Armazenamento em memória (dicionário `_games`)

#### `bot/evaluator.py` — Avaliador de Tabuleiro
- **`BoardEvaluator`**: Notas 0-10 para threat, advantage, pressure, victory
- **Pesos**: threat=0.35, advantage=0.25, pressure=0.25, victory=0.15
- `composite_score()`: Nota composta para decisão

#### `bot/priority_bot.py` — Bot com Árvore de Decisão
- **`PriorityBot`**: 3 dificuldades (easy/medium/hard)
- **Árvore**: Sobreviver → Eliminar Ameaça → Desenvolver Mesa → Atacar
- Ações por fase: redraw, resource, umbra, moot, combate
- **Alpha actions**: Atacar Hunting Grounds como ação alpha
- Pagamento automático de custos Rage/Gnosis
- Escolha de modo para cartas modais (heurísticas por ID de carta)

### Ciclo de Combate

```
1. SELECT_ALPHA → Cada jogador escolhe alpha (maior Renome age primeiro)
2. DECLARAR     → Cada criatura declara ação face-down
3. REVELAR      → Todas reveladas; Último a Declarar pode Feint
4. RESOLVER     → Aplica dano (Rage do atacante), destrói mortos → VP
5. FIM          → Remove mortos, verifica vitória
```

### Fases do Turno

```
redraw → regeneration → resource → umbra → moot → combat → (próximo turno)
```

### Comandos CLI do Game Engine

| Comando | Exemplo | Descrição |
|---|---|---|
| `STATUS` | `STATUS` | Mostra tabuleiro completo |
| `DRAW` | `DRAW combat 2` | Compra cartas |
| `PLAY <n>` | `PLAY 3` | Joga carta da mão |
| `ANUNCIAR <n>` | `ANUNCIAR 0` | Anuncia carta de efeito |
| `ESCOLHER <n>` | `ESCOLHER 1` | Escolhe modo de carta modal |
| `ANULAR` | `ANULAR` | Anula efeito anunciado |
| `ATTACK <a> [d]` | `ATTACK 500 501` | Inicia combate |
| `DECLARE <id> <acao>` | `DECLARE 500 strike` | Declara ação de combate |
| `REVEAL` | `REVEAL` | Revela ações |
| `FEINT <id> <acao>` | `FEINT 502 strike` | Troca ação (Último a Declarar) |
| `RESOLVE` | `RESOLVE` | Resolve combate |
| `ENDCOMBAT` | `ENDCOMBAT` | Encerra combate |
| `PASS` | `PASS` | Passa a vez |
| `NEXT` | `NEXT` | Avança fase |

### Testes do Motor de Jogo

**142 testes passando** em 6 arquivos:

| Arquivo | Cobertura |
|---|---|---|
| `test_endpoints.py` | Endpoints web (Cards, Decks) |
| `test_game_engine.py` | state, combat_queue, rules |
| `test_game_engine_anunciador.py` | Anunciador, EfeitoAnunciado |
| `test_game_engine_api.py` | Endpoints da API REST |
| `test_game_engine_bot.py` | BoardEvaluator, PriorityBot |
| `test_game_engine_cli.py` | CLI, comandos, save/load |
| `test_game_engine_effects.py` | ModeloCarta, ResolvedorEfeitos |

### Pontos de Atenção do Motor de Jogo

1. ~~**🎲 Bot usa `random.choice` para alvos**~~ — ✅ `GameState` tem `rng: random.Random` próprio; `ResolvedorEfeitos` usa `self.rng.choice()`. Partidas com mesma seed são totalmente determinísticas.
2. **📢 Anunciador em `__post_init__`** — O `Anunciador` é criado no `__post_init__` do `GameState`, dificultando serialização e mocking em testes.
3. **🔄 Verificação de Gauntlet incompleta** — O `_mesmo_lado_gauntlet` em `combat_queue.py` não considera personagens no mundo físico (pack_home) vs Umbra para o atacante.
4. **🃏 Cartas sem `modelo_id` são "inúteis"** — O bot descarta cartas sem `modelo_id` no redraw, mas elas poderiam ter efeitos não estruturados.

---

## 🔍 Pontos de Atenção / Problemas Identificados

1. ~~**🏗️ `database.db` versionado**~~ — ✅ Incluído no `.gitignore`. Não está mais versionado.

2. ~~**🐍 Inconsistência no formulário de Character**~~ — ✅ `CharacterCardForm` já tem campo `tipo`; `save_new_character()` removida (era duplicada).

3. ~~**🔀 Rotas duplicadas / inconsistentes**~~ — ✅ Padronizadas em rotas RESTful (GET/POST/DELETE consistentes, URLs hierárquicas, sem duplicatas).

4. ~~**🧪 Testes quebrados**~~ — ✅ **142 testes passando** (20 endpoint + 122 game engine).

5. **📦 Redis configurado mas não implementado** — O `docker-compose.yml` sobe Redis, o `NOTAS.txt` menciona `redis-om-python`, mas Redis não é usado em lugar nenhum.

6. **🔒 `SECRET_KEY` hardcoded** — `"mysecretkey1234567890"` como fallback na configuração.

7. **📝 Imports não utilizados** — Em `blueprints/cards/__init__.py`, `PictureForm` e `secure_filename` são importados mas usados de forma incompleta ou não usados.

8. **🖼️ Upload de imagens incompleto** — O método `save_card()` (POST `/card`) tenta salvar imagem acessando `form.image.data`, mas o formulário `CardForm` não tem campo `image`. O template `picture.html` existe mas está sem rota vinculada (`save_picture` não existe como rota registrada).

9. **⚠️ `snippet_cards.html` obsoleto** — Usa `card.pk` em vez de `card.id`, indicando ser resquício de versão anterior (talvez Redis OM).

10. **🔄 Migrations vs Modelos** — A migration inicial está consistente com os modelos atuais.

11. **📝 Tratamento de erros inconsistente** — Mistura de `current_app.logger.error()` e `logging.error()`. `assert card is not None` pode gerar erros 500 em vez de 404.

12. **🔗 Relacionamento Card ↔ Picture** — O modelo `Picture` tem FK para `Card`, mas o blueprint de cards não implementa o upload de imagens nas rotas existentes.

---

## ✅ Pontos Positivos

- **Organização em Blueprints** — Separação clara de responsabilidades (home, cards, decks).
- **Uso de factory pattern** (`create_app()`) — Boa prática Flask.
- **Camada de repositório** — Abstração do banco em `ext/repository.py`.
- **Migrations com Alembic** — Controle de versão do schema.
- **Formulários WTForms com validação** — `DataRequired` nos campos obrigatórios.
- **Template base com Bulma + HTMX** — UI moderna sem muito JS customizado.
- **Extensões separadas** (`ext/`) — Código modular.
- **CLI command** `init-database` para setup inicial.
- **Motor de jogo completo** — 4 fases implementadas com 142 testes passando.
- **Bot com IA** — Árvore de decisão com 3 níveis de dificuldade e avaliador de tabuleiro.
- **Sistema de efeitos estruturado** — Cartas com modos, condições de alvo e efeitos encadeados.
- **API REST do game engine** — Endpoints para criar partidas, executar ações e consultar estado.
- **Simulador de partidas** — `match.py` permite rodar partidas bot vs bot com decks reais.

---

## 📦 Importação de Cartas (Concluído)

### Dados importados do LackeyCCG

**Fonte:** http://www.werepenguin.com/rage/lackey/

| Base | Cartas |
|---|---|
| `setinfo.txt` (oficiais) | 1.627 |
| `conclavetest.txt` (teste) | 44 |
| `hyplaytest.txt` (playtest) | 126 |
| **Total** | **1.797** |

**Comando de importação:**
```bash
flask import-cards          # Importa todas as fontes
flask import-cards --dry-run # Preview sem inserir
flask import-cards --fonte oficial  # Apenas oficiais
```

### Principais tipos de carta
Character (Gaia/Wyrm/Rogue), Gift, Equipment, Combat Action, Event, Ally, Enemy, Victim, Territory, Quest, Caern, Rite, Moot, Action

### Modelos atualizados
- **Card** — Novos campos: `expansion`, `image_file`, `sealed`, `notes`, `renown`, `damage`, `errata`
- **Deck** — Agora com relacionamento `cards` (muitos-para-muitos)
- **deck_cards** — Tabela associativa com `quantity`

---

## 🔮 Sugestões de Melhorias (Pendentes)

1. ~~Remover `database.db` do versionamento~~ ✅ (`.gitignore`)
2. ~~Corrigir formulário de Character~~ ✅ (campo `tipo` adicionado)
3. ~~Padronizar as rotas~~ ✅
4. ~~Corrigir testes~~ ✅ (142 testes passando)
5. Implementar upload de imagens completo com rotas e templates
6. ~~Adicionar relacionamento Deck ↔ Card~~ ✅ (tabela `deck_cards`)
7. Implementar Redis se for realmente necessário, ou remover do docker-compose
8. Adicionar autenticação (sign up / log in estão no template mas não implementados)
9. Usar variáveis de ambiente para SECRET_KEY em produção
10. Adicionar validação e tratamento de erros mais robustos (páginas 404, flash messages consistentes)
11. ~~Registrar `api_bp` no `create_app()`~~ ✅ Já registrado
12. ~~Criar diretório `data/cards/`~~ ✅ Já existe com 67 exemplos
13. Adicionar seed determinística ao `ResolvedorEfeitos` para reprodutibilidade
14. Integrar o game engine ao frontend (HTMX) para partidas web
