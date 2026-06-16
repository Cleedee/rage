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
│   ├── telegram_bot/               # 🤖 Bot Telegram (multiplayer)
│   │   ├── __init__.py
│   │   ├── bot.py                 # Entry point, build_application, run_polling/run_webhook
│   │   ├── handlers.py            # 16+ comandos, callbacks, turn_timeout_handler
│   │   ├── conversations.py       # ConversationHandlers: /duel guiado, /accept guiado
│   │   ├── game_manager.py        # GameSession, timer de turno, persistência
│   │   ├── matchmaker.py          # Challenge, aceite/recusa, criação de partidas
│   │   ├── user_registry.py       # Resolução @username → Telegram ID (SQLite)
│   │   ├── stats.py               # ELO, match_history, player_ratings
│   │   ├── persistence.py         # GamePersistence: pickle + SQLite
│   │   ├── render.py              # GameState → texto formatado para Telegram
│   │   ├── keyboards.py           # 8 funções de teclado inline
│   │   ├── i18n.py                # Internacionalização (pt_BR + en_US)
│   │   ├── locales/               # Traduções JSON
│   │   │   ├── pt_BR.json
│   │   │   └── en_US.json
│   │   ├── persistence.db         # 💾 Partidas salvas (pickle)
│   │   ├── user_registry.db       # 👤 Mapeamento @username → user_id
│   │   └── stats.db               # 📊 Histórico de partidas + ratings ELO
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
│   │   ├── card.py                 # Card (carta) — 18+ campos
│   │   ├── deck.py                 # Deck — com is_public, telegram_owner_id, usage_count
│   │   └── picture.py             # Picture (imagem)
│   │
│   ├── blueprints/                 # Blueprints (módulos)
│   │   ├── home/                   # Página inicial
│   │   ├── cards/                  # CRUD de cartas
│   │   ├── decks/                  # CRUD de decks
│   │   ├── game/                   # Interface web de partidas (HTMX)
│   │   ├── tournaments/            # Gerenciamento de torneios
│   │   ├── analysis/               # Análise de decks/cartas
│   │   ├── tutorial/               # Páginas de tutorial
│   │   ├── auth/                   # Login via Telegram Widget
│   │   └── games/                  # Lista de partidas ativas
│   │
│   ├── templates/
│   │   ├── base.html              # Template base (Bulma + HTMX)
│   │   ├── auth/login.html        # Página de login Telegram
│   │   └── games/list.html        # Meus Jogos
│   │
│   └── instance/
│       └── images/                # Imagens das cartas
│           └── hatii-the-thunderer.png
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
| **python-telegram-bot >=22.8** | Bot Telegram (polling/webhook) |
| **python-dotenv** | Config via `.env` (token do bot) |
| **SQLite** (4x) | Bancos: `database`, `persistence`, `user_registry`, `stats` |
| **ELO Rating** | Sistema de rating (K=32, default=1200) |
| **i18n JSON** | Traduções pt_BR + en_US com fallback |

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
| `is_public` | Boolean (default=False) | Deck público na galeria social |
| `telegram_owner_id` | Integer (nullable) | Dono do deck no Telegram |
| `usage_count` | Integer (default=0) | Nº de visualizações na galeria |
| `created_at` | DateTime | Data de criação |
| `updated_at` | DateTime | Data da última modificação |
| `cards` | Relationship | Muitos-para-muitos com Card (via `deck_cards`) |

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
| `/game/new` | GET | Criar nova partida |
| `/game/<id>` | GET | Acompanhar partida (HTMX) |
| `/game/<id>/board` | GET | Partial do board (HTMX polling) |
| `/game/<id>/action` | POST | Executar ação na partida |
| `/auth/login` | GET | Login via Telegram Widget |
| `/auth/telegram` | GET | Callback do Telegram Login |
| `/auth/logout` | GET | Logout |
| `/games/` | GET | Minhas partidas ativas |
| `/tutorial` | GET | Tutorial interativo |
| `/tournaments` | GET | Lista de torneios |
| `/analysis` | GET | Análise de decks/cartas |

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

**320 testes passando** (10 falhas pré-existentes) em 11 arquivos:

| Arquivo | Cobertura | Status |
|---|---|---|
| `test_endpoints.py` | Endpoints web (Cards, Decks) | ✅ 20 |
| `test_game_engine.py` | state, combat_queue, rules | ✅ 168 / 10 falhas pré-existentes |
| `test_game_engine_anunciador.py` | Anunciador, EfeitoAnunciado | ✅ |
| `test_game_engine_api.py` | Endpoints da API REST | ✅ |
| `test_game_engine_bot.py` | BoardEvaluator, PriorityBot | ✅ |
| `test_game_engine_cli.py` | CLI, comandos, save/load | ✅ |
| `test_game_engine_effects.py` | ModeloCarta, ResolvedorEfeitos | ✅ |
| `test_combat_declaration.py` | Declaração de combate (alpha, challenge, pass) | ✅ 6 |
| `test_damage_system.py` | Sistema de dano (damage cards, morte, VP) | ✅ 10 |
| `test_hand_size.py` | Tamanho de mão (sept/combat) | ✅ 5 |
| `test_restrict_play.py` | Restricted/Forced/Random Play (6.6.6) | ✅ 3 |

### Pontos de Atenção do Motor de Jogo

1. ~~**🎲 Bot usa `random.choice` para alvos**~~ — ✅ `GameState` tem `rng: random.Random` próprio; `ResolvedorEfeitos` usa `self.rng.choice()`. Partidas com mesma seed são totalmente determinísticas.
2. ~~**📢 Anunciador em `__post_init__`**~~ — ✅ Criado via `default_factory` no campo `anunciador`; `__post_init__` removido.
3. ~~**🔄 Verificação de Gauntlet incompleta**~~ — ✅ `_mesmo_lado_gauntlet` agora considera `hunting_grounds`, Caern/Territory/Spirit (ambos os lados) e a zona neutra de Hunting Grounds.
4. **🃏 Cartas sem `modelo_id` são "inúteis"** — O bot descarta cartas sem `modelo_id` no redraw, mas elas poderiam ter efeitos não estruturados.

---

---

# 🤖 Telegram Bot (Multiplayer)

## Visão Geral

O bot Telegram (`@furia_ccg_bot`) permite jogar Rage CCG online diretamente pelo Telegram.
Usa o mesmo motor de jogo (`game_engine/`) e banco de dados do site, rodando em **modo polling**
(sem precisar de URL pública).

### Arquitetura

```
Telegram User ──► python-telegram-bot ──► GameManager ──► GameState
                      │                          │
                      ▼                          ▼
                 Handlers / Render          Matchmaker
```

### Módulos

| Módulo | Responsabilidade |
|---|---|
| `bot.py` | Entry point (`rage-bot`), `build_application()`, `_restore_active_games()` |
| `handlers.py` | 16+ comandos, ~30 callbacks, `turn_timeout_handler` |
| `conversations.py` | Fluxos guiados: `/duel` passo-a-passo, `/accept` passo-a-passo |
| `game_manager.py` | `GameSession`, timer de turno, persistência, auto-concede |
| `matchmaker.py` | `Challenge`, aceite/recusa, criação de partidas, expiração 2min |
| `user_registry.py` | Resolução @username → Telegram ID (SQLite + fallback API) |
| `stats.py` | `StatsManager`, ELO (K=32), match_history, player_ratings |
| `persistence.py` | `GamePersistence`: GameSession picklizada em SQLite |
| `render.py` | GameState → texto formatado + emojis + HP bars |
| `keyboards.py` | 8 funções de teclado inline |
| `i18n.py` | Internacionalização: `t('chave', lang)` com fallback pt_BR |

### Comandos do Bot

| Comando | Descrição |
|---|---|
| `/start` | Boas-vindas + link do site |
| `/help` | Referência de comandos |
| `/decks` | Seus decks registrados |
| `/duel @user <deck_id>` | Desafiar jogador |
| `/accept @user <deck_id>` | Aceitar desafio |
| `/decline @user` | Recusar desafio |
| `/board` | Tabuleiro completo |
| `/hand` | Sua mão |
| `/status` | Resumo do jogo |
| `/actions` | Ações disponíveis |
| `/play N` | Jogar carta N da mão |
| `/use N` | Usar carta de efeito |
| `/attack <id> [alvo]` | Iniciar combate |
| `/declare <id> <ação>` | Declarar ação de combate |
| `/reveal` | Revelar ações |
| `/feint <id> <ação>` | Trocar ação (Último a Declarar) |
| `/resolve` | Resolver combate |
| `/pass` | Passar prioridade |
| `/next` | Avançar fase |
| `/concede` | Conceder partida |
| `/draw [deck] [qtd]` | Comprar cartas |
| `/endcombat` | Forçar fim do combate |
| `/timer <horas>` | Customizar timeout do turno (1h–48h) |
| `/stats` | Suas estatísticas (rating, winrate, deck favorito) |
| `/rank` | Top 15 jogadores (medalhas) |
| `/card N` | Detalhes visuais de uma carta |
| `/deck search <termo>` | Buscar decks públicos |
| `/deck view <id>` | Ver deck público |
| `/deck share <id>` | Compartilhar deck |
| `/deck top` | Decks mais populares |
| `/lang <código>` | Mudar idioma (pt_BR, en_US) |

### Feature Set

| Funcionalidade | Status |
|---|---|
| Partidas 1v1 com motor de jogo completo | ✅ |
| Matchmaking via @username (banco local + API) | ✅ |
| Timer de turno (default 2h, configurável) | ✅ |
| Auto-concede após 3 timeouts consecutivos | ✅ |
| Edição de mensagens (evita flood) | ✅ |
| Persistência SQLite (sobrevive a restart) | ✅ |
| Galeria social de decks (público/privado) | ✅ |
| Sistema ELO (K=32, rating default 1200) | ✅ |
| Estatísticas e rank (winrate, deck favorito) | ✅ |
| Efeitos visuais (HP bars, retrato de carta) | ✅ |
| Internacionalização (pt_BR + en_US) | ✅ |
| Login Telegram no site (Widget) | ✅ |
| Partidas visíveis no navegador (`/games/`) | ✅ |
| Modo polling (sem URL pública) | ✅ |

### Bancos de Dados

O bot usa **4 bancos SQLite independentes**:

| Banco | Localização | Conteúdo |
|---|---|---|
| `database.db` | `rage_web/` | Cartas, decks (compartilhado com Flask) |
| `persistence.db` | `rage_web/telegram_bot/` | GameSession picklizada |
| `user_registry.db` | `rage_web/telegram_bot/` | Mapeamento @username → user_id |
| `stats.db` | `rage_web/telegram_bot/` | Match history + ELO ratings |

### Fluxo de Partida

```
1. /duel @joao 7        → João recebe notificação + [🌐 Link web]
2. /accept @pedro 90    → Partida criada (decks 7 vs 90)
3. /board               → Ver tabuleiro (enviado ou editado)
4. /play 0              → Jogar carta da mão
5. /pass                → Passar a vez
6. (João é notificado)  → Vez de João + board editado
...
7. /concede             → Partida encerrada, ELO atualizado
```

---

## 🔍 Pontos de Atenção / Problemas Identificados

1. ~~**🏗️ `database.db` versionado**~~ — ✅ Incluído no `.gitignore`. Não está mais versionado.

2. ~~**🐍 Inconsistência no formulário de Character**~~ — ✅ `CharacterCardForm` já tem campo `tipo`; `save_new_character()` removida (era duplicada).

3. ~~**🔀 Rotas duplicadas / inconsistentes**~~ — ✅ Padronizadas em rotas RESTful (GET/POST/DELETE consistentes, URLs hierárquicas, sem duplicatas).

4. ~~**🧪 Testes quebrados**~~ — ✅ **320 testes passando** (10 falhas pré-existentes) em 11 arquivos de teste.

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
- **Motor de jogo completo** — 4 fases implementadas com 320 testes passando (10 falhas pré-existentes).
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

## 🤖 Automação: Checklist de Decks

Quando o usuário pedir para analisar um deck, verificar status de cartas, efeitos ou criar/atualizar checklist, execute:

```bash
cd /workspace && PYTHONPATH=. python3 scripts/gerar_checklist.py <deck_id>
```

O script:
- Consulta o banco SQLite (`Card`, `Deck`, `deck_cards`)
- Cruza com JSONs em `data/cards/` (detecta se a carta tem JSON novo, reaproveitado ou falta)
- Lista tipos de efeito usados vs implementados no motor (`effects.py`)
- Identifica gaps (passivas não registradas, efeitos sem resolvedor)
- Sugere testes
- Gera/salva `data/cards/deck<id>_checklist.md`

Exemplo: `PYTHONPATH=. python3 scripts/gerar_checklist.py 1050`

---

### ⚠️ Combat Phase: Closed Play vs Open Play (terminologia)

É importante distinguir dois conceitos diferentes no livro de regras:

1. **Seção 2.2.6 — Combat Phase (discard + redraw + alpha selection):**
   - Ao entrar na Combat Phase, jogadores *podem* descartar cartas de combate da
     mão e comprar até o máximo (*hand_size_combat*).
   - Selecionam alpha (personagem com maior Renome).
   - O motor implementa isso em `state.py:1027` (`redraw_combat()`) e na
     seleção automática de alfas.

2. **Seção 3.2 / 3.2.1 — Closed Play vs Open Play (regras de timing):**
   - **Closed Play:** períodos em que apenas cartas/abilidades específicas podem
     ser usadas (recursos, combat actions, passivas sempre ativas, etc.).
     Inclui: `declaration` + `pre_combat` + `play_card` → `targeting` → `reveal`
     (com sub-steps feinting 6.8.1, instinctive 6.8.2) → `bluff`).
   - **Open Play:** períodos em que cartas de sept/gifts/abilidades podem ser
     jogadas livremente. Inclui: `beginning_of_combat`, `between_rounds`.
   - Offensive Effects em Open Play exigem anúncio e atenção dos outros jogadores.

**Steps do combate e seu tipo de período (Cap. 6):**

| Step | Período | Descrição |
|---|---|---|
| `select_alpha` (2.2.6) | — | Escolha do alpha |
| `alpha_action` (6.5) | — | Alpha declara ataque/challenge/passa |
| `declaration` (6.1.1) | Closed Play | Declarar atacante+alvo; Hunting Party, Shieldmate |
| `pre_combat` (6.1.2) | Closed Play | Pack actions, redirect, step in, cancel |
| `beginning_of_combat` (6.1.3) | **Open Play** | Gifts pré-rodada, frenzy |
| `play_card` (6.2.1) | Closed Play | Jogar combat card face-down (+ weapons) |
| `targeting` (6.2.2) | Closed Play | Atribuir alvos (mesmo Gauntlet) |
| `reveal` (6.2.3) | Closed Play | Revelar cartas + sub-steps:
  feinting (6.8.1), instinctive (6.8.2), alternative (6.6.5) |
| `bluff` (6.2.4) | Closed Play | 6.9.1: ilegais → 6.9.2: bluffs (sucesso/falha) |
| `resolution` (6.2.5) | — | Fast → Normal → Slow, dano, morte → VP |
| `withdrawal` (6.2.6/6.3.1) | — | Atacante decide retirar (manual, não auto) |
| `between_rounds` (6.2.7) | **Open Play** | Gift entre rodadas; loop para play_card |
| `end` (6.3) | — | Cleanup, reabastecer mão, reverter Crinos |

O motor em `rules.py` define `COMBAT_STEPS` e `COMBAT_STEPS_AUTO` mapeando
cada step. O bot respeita esses períodos: em Open Play ele pode jogar gifts; em
Closed Play ele só pode jogar combat cards ou usar passivas. Não há restrição
adicional implementada — assume-se que o bot só toma ações válidas.

### ⚠️ Seleção de Alpha (2.2.6)

- Cada jogador seleciona um Character ou Ally do pack como alpha.
- *"A player may select a different alpha every combat phase, or use the same one
  repeatedly."* (seção 2.2.6) — **não** há restrição geral de alpha não poder
  ser escolhido 2 turnos seguidos.
- A restrição `nao_pode_alpha_2_turnos_seguidos` existe APENAS para cartas
  específicas (ex: Allonzo Montoya, card_id=29, por seu texto de carta).
- `nao_pode_ser_alpha` é usado para cartas que nunca podem ser alpha
  (ex: Caern Lua Crescente).
- Se o alpha morre durante o combate, o jogador não pode selecionar outro
  até a próxima Combat Phase.

---

### ⚠️ Nomenclatura dos JSONs

Os arquivos JSON em `data/cards/` usam o **slug** da carta (campo `Card.slug`) como nome de arquivo,
**não** o ID numérico. Exemplos:

| Carta | ID | Slug | Arquivo JSON |
|---|---|---|---|
| Stalks Death | 264 | `stalks-death_r9` | `stalks-death_r9.json` |
| Catfeet | 944 | `catfeet` | `catfeet.json` |
| Umbral Escape | 1324 | `umbral-escape_unlimited` | `umbral-escape_unlimited.json` |

O vínculo entre JSON e carta no banco é feito pelo campo `_metadata.card_id` dentro do JSON.

**IMPORTANTE:** Scripts que fazem busca de JSON por ID numérico NÃO devem usar glob patterns como
`data/cards/*_{cid}_*.json`, pois isso não funciona com a nomenclatura por slug. Em vez disso,
use o campo `_metadata.card_id` de cada JSON (carregue todos, indexe por card_id).

---

### ⚠️ Sincronia `EFEITOS_IMPLEMENTADOS` × `EfeitoTipo`

O script `gerar_checklist.py` mantém uma lista `EFEITOS_IMPLEMENTADOS` que deve refletir
exatamente o enum `EfeitoTipo` em `rage_web/game_engine/effects.py`.

**Sempre que um novo tipo de efeito for adicionado ao enum no motor, adicione-o também na lista
no script de checklist.** Caso contrário, o checklist reportará falsos gaps (❌) para efeitos
que já têm resolvedor.

---

### 📋 Decks Conhecidos (mapeados no script)

| ID | Nome | Estratégia |
|---|---|---|
| 7 | Kinfolk Resistance | Kinfolk + Firearms + Pack combat |
| 90 | Classic: Cliath Ahroun | Ahroun básico, Strike + Dodge |
| 160 | Mokole | Gaia com quests, morte e recrutamento |
| 416 | Questor | Vigilante que pontua matando menor Renome |
| 465 | Apocalypse: First Team 28 | Wyrm squad, ataque HG em massa |
| 484 | Ajaba Aggression | Hienas que fogem de dano alto |
| 524 | Classic: Wailer special | Aliados + pack attack |
| **1050** | **Assombração dos Passos da Morte** | **Pack Ragabash Silent Striders — Stalks Death + truques** |

---

## 🧩 Convenções de Código

### Registro de Passivas (register_card_passives)

Usar **slug** (não `card_id` numérico) para identificar cartas no
registro de passivas em `state.py`:

```python
# ✅ Correto (slug)
elif slug == 'frenar_r1':
    ...

# ❌ Evitar (card_id numérico)
elif card.card_id == 71:
    ...
```

**Motivo:** o slug é o identificador canônico da carta, imutável e
independente do banco de dados. Facilita correlação com JSONs e
evita confusão entre diferentes ambientes.

**Exceção:** triggers de morte (`DeathTrigger`) e cartas carregadas
de JSONs podem usar `card_id` quando o slug ainda não está
disponível no momento do registro.

### Tags de Cartas (Card.tags)

Tags são dados **curados manualmente** que **NÃO** foram importados
do LackeyCCG. São versionadas em:

- `data/card_tags.json` — dump de todas as tags (slug → tags)
- `scripts/apply_tags.py` — aplica tags do JSON ao banco

**Uso:**

```bash
# Aplicar todas as tags (após recriar banco)
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py

# Apenas uma carta específica
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py --slug war-council_r7

# Preview sem alterar
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py --dry-run
```

**Convenções de tags:**
- `gaia-only` — carta exclusiva para decks Gaia (ex: War Council)
- `gaia` — carta de alinhamento Gaia
- `wyrm` — carta de alinhamento Wyrm
- `moot` — carta do tipo Moot
- `character`, `equipment`, `gift`, `event`, `action` — tipo da carta
- `auspice-*` — aurépicio (ex: `auspice-ragabash`, `auspice-ahroun`)
- `tribo-*` — tribo (ex: `tribo-silver-fangs`, `tribo-shadow-lords`)
- `form-*` — forma (ex: `form-homid`, `form-lupus`)
- `class-*` — classe (ex: `class-garou`, `class-spirit`, `class-human`)

---

## 🔮 Sugestões de Melhorias (Pendentes)

1. ~~Remover `database.db` do versionamento~~ ✅ (`.gitignore`)
2. ~~Corrigir formulário de Character~~ ✅ (campo `tipo` adicionado)
3. ~~Padronizar as rotas~~ ✅
4. ~~Corrigir testes~~ ✅ (142+ testes passando)
5. ~~Implementar upload de imagens~~ ✅ Rotas + templates implementados
6. ~~Adicionar relacionamento Deck ↔ Card~~ ✅ (tabela `deck_cards`)
7. Implementar Redis se for realmente necessário, ou remover do docker-compose
8. ~~Adicionar autenticação (login Telegram)~~ ✅ Login via Telegram Widget implementado em `/auth/login`
9. Usar variáveis de ambiente para SECRET_KEY em produção
10. Adicionar validação e tratamento de erros mais robustos (páginas 404, flash messages consistentes)
11. ~~Registrar `api_bp` no `create_app()`~~ ✅ Já registrado
12. ~~Criar diretório `data/cards/`~~ ✅ Já existe com 550+ JSONs
13. ~~Adicionar seed determinística ao `ResolvedorEfeitos`~~ ✅ `GameState` tem `rng` próprio
14. ~~Integrar game engine ao frontend (HTMX)~~ ✅ Blueprint `game/` com board + ações + polling
15. ~~Sistema de matchmaking no Telegram~~ ✅ Matchmaker com desafios, aceite, notificação
16. ~~Timer de turno com auto-concede~~ ✅ Default 2h, configurável, 3 timeouts → concede
17. ~~Persistência de partidas~~ ✅ GameSession picklizada em SQLite
18. ~~Galeria social de decks~~ ✅ `/deck search`, `/deck view`, `/deck share`, `/deck top`
19. ~~Sistema ELO e estatísticas~~ ✅ `/stats`, `/rank`, ELO K=32
20. ~~Efeito Devilwhip (acao_extra_por_rodada)~~ ✅ JSON + resolver + combat Declaration + reaplicação por rodada
21. ~~Internacionalização~~ ✅ pt_BR + en_US com fallback
22. ~~Bugs corrigidos (5)~~ ✅ ConversationHandler, Matchmaker duplicado, Timeout 24h→2h, Edição de mensagens, Username case-sensitive
23. ~~Refatorar máquina de steps de combate (Cap. 6)~~ ✅ Alinhada com regras oficiais:
    - `feint` integrado como sub-step do `reveal` (6.8)
    - `between_rounds` loopa para `play_card` (6.2.7)
    - `withdrawal` não é mais auto-advance (6.3.1)
    - `bluff` processa ilegais (6.9.1) antes de bluffs (6.9.2)
    - 320 testes passando, partidas bot-vs-bot testadas com `rage-match`
24. ~~Bot iniciava múltiplos combates no mesmo turno (violava regra 6.3)~~ ✅ Corrigido:
    - Após `end_combat()`, bot passa a vez em vez de atacar novamente
    - Defensor pode selecionar alpha e contra-atacar (6.3)
    - Função `_agir_combat_fallback` duplicada removida
