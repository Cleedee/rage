# Rage CCG Web

A web application for managing **Rage CCG** cards and decks, built with Flask. Includes a complete game engine with AI bot opponents, a debug CLI, and a REST API.

> **Rage CCG** is a collectible card game based on the *World of Darkness* universe by White Wolf Entertainment. All card art, names, and game concepts are the property of their respective owners.

---

> **Rage CCG** is a collectible card game based on the *World of Darkness* universe by White Wolf Entertainment. All card art, names, and game concepts are the property of their respective owners.

---

## Features

- **Card Catalog** — Browse, search, create, edit, and delete cards (Characters, Equipment, Events, Gifts, Allies, and more)
- **Deck Builder** — Create and manage decks with a card database of **1,800+ imported cards** from LackeyCCG
- **Card Import** — Import cards from LackeyCCG data files (`flask import-cards`)
- **Tag System** — Curated tags for cards (alignment, tribe, auspice, class, form, etc.)
- **Deck Checklist** — Analyze any deck against the game engine: detect structured effects, gaps, and suggest tests
- **Tournament Management** — Track tournaments and matches
- **Game Engine** — Full turn-based CCG engine with 6 phases (redraw, regeneration, resource, umbra, moot, combat)
- **Combat System** — Simultaneous declaration, alpha order, reveal, feint, and resolution
- **Structured Effects** — JSON-defined card effects with 16+ effect types and flexible targeting (550+ card JSONs)
- **Announcement System** — Announce → Respond → Resolve flow (not LIFO stack like Magic)
- **AI Bot** — Priority-based decision tree with 3 difficulty levels (easy, medium, hard) and board evaluation
- **Match Simulator** — Run bot-vs-bot matches from the command line with real decks
- **Debug CLI** — Interactive REPL for testing game states
- **REST API** — Programmatic game access at `/api/game/`
- **🤖 Telegram Bot** — Play Rage CCG online via `@furia_ccg_bot` in polling mode (no public URL needed)
- **Matchmaking** — Challenge players via `@username` with automatic user resolution (DB + API fallback)
- **Turn Timer** — Auto-pass after 2h (configurable via `/timer`), auto-concede after 3 timeouts
- **Message Editing** — Board messages are edited in-place (no flood)
- **Persistence** — Active games survive bot restart via pickle + SQLite
- **Social Deck Gallery** — Share, search, and star public decks (`/deck search`, `/deck top`)
- **ELO Rankings** — Competitive rating system (`/stats`, `/rank`)
- **i18n** — Portuguese (pt_BR) and English (en_US) with automatic fallback
- **Web Login** — Login via Telegram Widget (`/auth/login`) with partidas visíveis em `/games/`

---

## Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.12** | Language |
| **Flask 3.1.1** | Web framework |
| **Flask-SQLAlchemy 3.1.1** | ORM |
| **Flask-Migrate 4.1.0** | Migrations (Alembic) |
| **Flask-WTF 1.2.2** | Form handling + CSRF |
| **SQLite** | Database |
| **Bulma CSS 1.0.4** | UI framework (CDN) |
| **HTMX 1.9.10** | AJAX interactivity (CDN) |
| **Bootstrap Icons** | Icons (CDN) |
| **uv** | Package manager |
| **python-telegram-bot >=22.8** | Telegram Bot (polling/webhook) |
| **pytest** | Testing |
| **uv** | Package manager |
| **ELO Rating System** | Competitive match ratings (K=32) |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/rage-web.git
cd rage-web

# Install uv (if not available)
pip install uv

# Install dependencies
uv sync

# Set up the database
flask init-database

# (Optional) Import 1,800+ cards from LackeyCCG data
flask import-cards

# (Optional) Apply curated card tags
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py

# Run the development server
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Project Structure

```
├── app.py                          # Application entry point
├── pyproject.toml                  # Dependencies & project config
├── Makefile                        # Helper commands (flask run, docker)
├── rage_web/
│   ├── __init__.py                 # Flask factory (create_app)
│   ├── config.py                   # App configuration
│   ├── blueprints/                 # Route modules
│   │   ├── home/                   # Landing page
│   │   ├── cards/                  # Card CRUD
│   │   ├── decks/                  # Deck CRUD + gallery
│   │   ├── game/                   # Game web interface (HTMX)
│   │   ├── tournaments/            # Tournament management
│   │   ├── analysis/               # Deck/card analysis views
│   │   ├── tutorial/               # Tutorial pages
│   │   ├── auth/                   # Telegram Login Widget
│   │   └── games/                  # My active games list
│   ├── ext/                        # Extensions
│   │   ├── database.py             # SQLAlchemy initialization
│   │   ├── repository.py           # Repository layer (CRUD)
│   │   └── cli.py                  # CLI commands
│   ├── game_engine/                # Card game engine
│   │   ├── state.py                # Game state, zones, players
│   │   ├── combat_queue.py         # Combat cycle
│   │   ├── rules.py                # Game constants & rules
│   │   ├── effects.py              # Structured effects (16+ types)
│   │   ├── anunciador.py           # Announce / respond / resolve
│   │   ├── match.py                # Bot match simulator
│   │   ├── cli.py                  # Debug REPL (rage-cli)
│   │   ├── api.py                  # REST API blueprint
│   │   └── bot/                    # AI
│   │       ├── evaluator.py        # Board evaluation
│   │       └── priority_bot.py     # Decision tree bot
│   ├── telegram_bot/               # 🤖 Telegram Bot
│   │   ├── bot.py                  # Entry point (rage-bot)
│   │   ├── handlers.py             # All command & callback handlers
│   │   ├── conversations.py        # Guided /duel and /accept flows
│   │   ├── game_manager.py         # Game sessions, timers, persistence
│   │   ├── matchmaker.py           # Challenge / matchmaking
│   │   ├── user_registry.py        # @username → user_id resolution
│   │   ├── stats.py                # ELO, match history, rankings
│   │   ├── persistence.py          # GameSession pickle in SQLite
│   │   ├── render.py               # Game state → Telegram text
│   │   ├── keyboards.py            # Inline keyboards
│   │   ├── i18n.py                 # Translations (pt_BR + en_US)
│   │   └── locales/                # JSON locale files
│   ├── helpers/
│   │   └── forms.py                # WTForms definitions
│   ├── models/
│   │   ├── card.py                 # Card model (18+ fields)
│   │   ├── deck.py                 # Deck model (is_public, telegram_owner_id, etc.)
│   │   └── picture.py              # Card images
│   └── templates/
│       ├── base.html               # Base layout (Bulma + HTMX)
│       ├── auth/login.html         # Telegram login page
│       └── games/list.html         # Active games list
├── data/
│   ├── cards/                      # 550+ card effect JSONs (keyed by slug)
│   └── card_tags.json              # Curated card tags
├── scripts/                        # Utility scripts
│   ├── apply_tags.py               # Apply tags from JSON to database
│   ├── gerar_checklist.py          # Generate deck checklist
│   └── ...
├── migrations/                     # Alembic migrations
└── tests/                          # pytest suite (7 files, 142+ tests)
```

---

## 🤖 Telegram Bot (Multiplayer)

Play Rage CCG online via Telegram! The bot (`@furia_ccg_bot`) integrates directly with the
game engine, allowing async P2P matches with full combat, effects, and AI.

**No public URL needed** — runs in polling mode via `python-telegram-bot`.

### Quick Start

```bash
# 1. Set up token in .env
# 2. Start the bot
make run-bot

# Or manually:
# Set your bot token
source .env && export TELEGRAM_KEY_TOKEN

# Start in polling mode (no public URL needed)
rage-bot

# Or with explicit token
rage-bot --token "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

# Webhook mode (requires HTTPS URL)
rage-bot --webhook --url https://meusite.com --port 8443
```

### All Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome + site link |
| `/help` | Full command reference |
| `/board` | View game board (edits msg, no flood) |
| `/hand` | View your hand |
| `/status` | Game status summary |
| `/actions` | Available actions right now |
| `/decks` | List your decks |
| `/duel @user <deck_id>` | Challenge another player |
| `/accept @user <deck_id>` | Accept a pending challenge |
| `/decline @user` | Decline a challenge |
| `/play <N>` | Play card N from hand |
| `/use <N>` | Use a gift/rite/effect card |
| `/attack <id> [alvo]` | Start combat (alvo=hg para Hunting Grounds) |
| `/declare <id> <ação>` | Declare combat action (strike, dodge, etc.) |
| `/reveal` | Reveal all declared actions |
| `/feint <id> <ação>` | Change action (Last to Declare only) |
| `/resolve` | Resolve combat step |
| `/endcombat` | Force end combat phase |
| `/draw [deck] [qtd]` | Draw cards from combat/sept deck |
| `/pass` | Pass priority / turn |
| `/next` | Advance to next phase |
| `/concede` | Concede the game (updates ELO) |
| `/timer <horas>` | Set turn timeout (1h–48h) |
| `/stats` | Your ELO rating, winrate, favorite deck |
| `/rank` | Top 15 players with medals |
| `/card N` | Detailed card view with portrait |
| `/deck search <termo>` | Search public decks |
| `/deck view <id>` | View a public deck |
| `/deck share <id>` | Share your deck as public |
| `/deck top` | Most popular public decks |
| `/lang <código>` | Change language (pt_BR, en_US) |

### Feature Set

| Feature | Details |
|---|---|
| **Matchmaking** | `/duel @user <deck_id>` creates a Challenge; `/accept` starts the game |
| **@username resolution** | Local DB (`user_registry.db`) + fallback to Telegram API (`getChat`) |
| **Turn Timer** | Default **2 hours**, customisable via `/timer <horas>`. Auto-passes after timeout, auto-concedes after **3 consecutive** timeouts |
| **Message Editing** | Board messages are **edited in-place** (stored in `context.user_data`). Fallback to new message if edit fails |
| **Persistence** | `GameSession` is pickled to `persistence.db` via `GamePersistence`. Survives bot restart. Timer tasks are re-created on `post_init` |
| **Social Deck Gallery** | `/deck search`, `/deck view`, `/deck share`, `/deck top`. Decks have `is_public`, `telegram_owner_id`, `usage_count` |
| **ELO & Stats** | K-factor 32, default rating 1200. `/stats` shows winrate, rating history, favorite deck. `/rank` shows top 15 with 🥇🥈🥉 medals |
| **Card Visuals** | `/card N` renders a portrait (`▔▔`/`▃▃` frame), stats, HP bars. Board shows mini HP bars for each creature |
| **i18n** | pt_BR + en_US with JSON locale files. Fallback to pt_BR. Change with `/lang` |
| **Web Integration** | `/auth/login` for Telegram Login Widget. Bot sends `[🌐]()` links to web board. `/games/` lists active games |
| **Polling Mode** | No webhook needed. Uses `Application.run_polling(drop_pending_updates=True)` |

### Architecture

```
Telegram User ──► python-telegram-bot ──► GameManager ──► GameState
                      │                          │
                      ▼                          ▼
                 Handlers / Render          Matchmaker
```

| Module | Purpose |
|---|---|
| `bot.py` | Entry point (`rage-bot`), `build_application()`, game restoration on boot |
| `handlers.py` | 16+ command handlers, 30+ callback actions, turn timeout handler |
| `conversations.py` | Guided `/duel` and `/accept` flows (compatible with direct commands) |
| `game_manager.py` | `GameSession` with timer scheduling/cancellation, persistence hooks |
| `matchmaker.py` | `Challenge` dataclass, challenge lifecycle (create/accept/decline/expire) |
| `persistence.py` | `GamePersistence` — save/load/delete pickled `GameSession` in SQLite |
| `user_registry.py` | `register_user()`, `resolve_username()`, API fallback `resolve_username_via_api()` |
| `stats.py` | `StatsManager` — match history, ELO calculation, rating queries |
| `render.py` | Game state → Telegram-formatted text with Unicode emojis and HP bars |
| `keyboards.py` | 8 inline keyboard builders (board, hand, actions, combat, etc.) |
| `i18n.py` | Translation engine `t(key, lang, **kwargs)` with JSON locale files |

### Databases

The bot uses **4 SQLite databases** for different concerns:

| File | Location | Contents |
|---|---|---|
| `database.db` | `rage_web/` | Cards, decks, deck_cards (shared with Flask) |
| `persistence.db` | `rage_web/telegram_bot/` | Pickled `GameSession` for active games |
| `user_registry.db` | `rage_web/telegram_bot/` | `@username` → `user_id` mapping |
| `stats.db` | `rage_web/telegram_bot/` | Match history + player ELO ratings |

### Multiplayer Flow

```
1. /duel @joao 7        → João recebe notificação + [🌐 Link web]
2. /accept @pedro 90    → Partida criada (decks 7 vs 90)
3. /board               → Ver tabuleiro (editado, sem flood)
4. /play 0              → Jogar carta da mão
5. /pass                → Passar a vez
6. (João é notificado)  → Vez de João + board editado
7. /attack 500 hg       → Iniciar combate
8. /declare 500 strike  → Declarar ação
9. /reveal              → Revelar ações
10. /resolve            → Resolver dano
...
11. /concede            → Partida encerrada, ELO atualizado
```

### Running

```bash
# Development (auto-restart on file changes)
make run-bot

# Production (systemd / screen / tmux)
cd /workspace && source .venv/bin/activate
nohup rage-bot > /tmp/rage-bot.log 2>&1 &

# Check logs
tail -f /tmp/rage-bot.log
```

### Configuration

The bot reads configuration from environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_KEY_TOKEN` | — | Bot token from @BotFather (required) |
| `BOT_USERNAME` | `furia_ccg_bot` | Bot username for login widget |
| `BOT_DEFAULT_TIMEOUT` | `7200` | Default turn timeout in seconds |
| `BOT_MAX_TIMEOUT` | `86400` | Maximum allowed timeout (24h) |

---

## Game Engine

The engine simulates a full card game match with these turn phases:

```
redraw → regeneration → resource → umbra → moot → combat
```

### Combat Cycle

1. **Select Alpha** — Each player chooses an alpha (highest Renown acts first)
2. **Declare** — Each creature declares an action face-down
3. **Reveal** — All actions revealed; Last to Declare may feint
4. **Resolve** — Apply damage (Rage of attacker), destroy creatures → Victory Pile
5. **End** — Remove dead creatures, check victory

### Closed Play vs Open Play

| Period | Description |
|---|---|
| **Closed Play** | Combat cards, pack actions, passives. Includes: declaration, pre-combat, steps 1-6 |
| **Open Play** | Gifts, sept cards, abilities freely playable. Includes: beginning_of_combat, between_rounds |

### CLI Debug Commands

```
STATUS    — Show full board state
DRAW n    — Draw cards from combat/sept deck
PLAY n    — Play a card from hand
ANUNCIAR  — Announce a card effect
ESCOLHER  — Choose mode for modal card
ANULAR    — Cancel announced effect
ATTACK    — Start combat between creatures
DECLARE   — Declare combat action
REVEAL    — Reveal all declared actions
FEINT     — Change action (Last to Declare only)
RESOLVE   — Resolve combat
ENDCOMBAT — End combat phase
PASS      — Pass priority
NEXT      — Advance phase
SAVE      — Save game state
LOAD      — Load game state
```

### Installed Commands

The project installs three CLI entry points:

```bash
# Launch the debug REPL
rage-cli

# Run a bot vs bot match with real decks
rage-match --deck1 "My Deck" --deck2 "Opponent Deck" --difficulty hard

# Start the Telegram bot (polling mode)
rage-bot
```

### Makefile Commands

```bash
make run-web          # Start Flask dev server
make run-bot          # Start Telegram bot
make test             # Run all pytest tests
make shell            # Flask shell
make docker           # Docker compose up
```

---

## Web Routes

| Route | Method | Action |
|---|---|---|
| `/` | GET | Home |
| `/cards` | GET | Card catalog |
| `/cards/{id}` | GET/POST | View/edit card |
| `/cards/{id}/view` | GET | Card detail page |
| `/decks` | GET | Deck search |
| `/decks/new` | GET/POST | Create deck |
| `/decks/{id}` | GET | View/edit deck |
| `/decks/import` | GET/POST | Import deck |
| `/game/new` | GET | Create new game |
| `/game/{id}` | GET | Watch game (HTMX) |
| `/game/{id}/board` | GET | Board partial (HTMX polling) |
| `/game/{id}/action` | POST | Execute game action |
| `/auth/login` | GET | Telegram Login Widget |
| `/auth/telegram` | GET | Telegram login callback |
| `/auth/logout` | GET | Logout |
| `/games/` | GET | My active games |
| `/tutorial` | GET | Interactive tutorial |
| `/tournaments` | GET | Tournament list |
| `/analysis` | GET | Deck/card analysis |

## REST API (Game Engine)

The game engine exposes a REST API at `/api/game/`:

| Endpoint | Method | Action |
|---|---|---|
| `/api/game/new` | POST | Create a new game |
| `/api/game/<id>` | GET | Get game state |
| `/api/game/<id>/legal-actions` | GET | Available actions |
| `/api/game/<id>/draw` | POST | Draw cards |
| `/api/game/<id>/play` | POST | Play a card |
| `/api/game/<id>/use-card` | POST | Use a card effect |
| `/api/game/<id>/attack` | POST | Declare attack |
| `/api/game/<id>/declare` | POST | Declare combat action |
| `/api/game/<id>/reveal` | POST | Reveal declared actions |
| `/api/game/<id>/feint` | POST | Feint (Last to Declare) |
| `/api/game/<id>/resolve` | POST | Resolve combat |
| `/api/game/<id>/end-combat` | POST | End combat phase |
| `/api/game/<id>/pass` | POST | Pass priority |
| `/api/game/<id>/next` | POST | Advance phase |

---

## Deck Checklist Generator

Analyze any deck in the database against the game engine implementation:

```bash
cd /workspace && PYTHONPATH=. python3 scripts/gerar_checklist.py <deck_id>
```

The script:
- Queries the SQLite database for deck composition
- Cross-references with JSONs in `data/cards/` (new, reused, or missing)
- Lists effect types used vs. implemented in the engine
- Identifies gaps (unregistered passives, effects without resolvers)
- Suggests tests
- Generates `data/cards/deck<id>_checklist.md`

---

## Importing Cards

1,800+ cards were imported from the LackeyCCG community database:

| Source | Cards |
|---|---|
| `setinfo.txt` (official) | 1,627 |
| `conclavetest.txt` (test) | 44 |
| `hyplaytest.txt` (playtest) | 126 |
| **Total** | **1,797** |

```bash
flask import-cards                  # Import all sources
flask import-cards --dry-run        # Preview only
flask import-cards --fonte oficial  # Official cards only
```

---

## Card Tags

Curated tags (alignment, tribe, auspice, form, class, etc.) are stored in `data/card_tags.json` and applied to the database:

```bash
# Apply all tags
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py

# Single card preview
PYTHONPATH=. venv/bin/python3 scripts/apply_tags.py --slug war-council_r7 --dry-run
```

---

## Tests

```bash
pytest                          # Run all tests (142+ passing)
pytest -v                       # Verbose mode
PYTHONPATH=. pytest tests/      # Explicit path
```

Test coverage across 7 files:

| File | Coverage |
|---|---|
| `test_endpoints.py` | Web endpoints (Cards, Decks) |
| `test_game_engine.py` | State, combat queue, rules |
| `test_game_engine_anunciador.py` | Announcement system |
| `test_game_engine_api.py` | REST API endpoints |
| `test_game_engine_bot.py` | Board evaluator, priority bot |
| `test_game_engine_cli.py` | CLI commands, save/load |
| `test_game_engine_effects.py` | Card models, effect resolver |

---

## Architecture

### Game Engine Phases

| Phase | Module | Status |
|---|---|---|
| Phase 1 — State + Combat Queue | `state.py`, `combat_queue.py` | ✅ Complete |
| Phase 2 — Debug CLI | `cli.py` | ✅ Complete |
| Phase 3 — REST API | `api.py` | ✅ Complete |
| Phase 4 — AI Bot | `bot/evaluator.py`, `bot/priority_bot.py` | ✅ Complete |

### Key Data Models

**Card** — 18+ fields including `name`, `tipo`, `rage`, `gnosis`, `health`, `rage_morph`, `gnosis_morph`, `health_morph`, `requires`, `keyword`, `text`, `expansion`, `renown`, `damage`, `slug`

**Deck** — `name`, `description`, many-to-many relationship with Card via `deck_cards` (with `quantity`)

**Picture** — Card images with `name`, `side`, `version`, FK to Card

### Deterministic Simulation

The game engine uses a dedicated `random.Random` instance per game state, making matches fully deterministic when seeded — essential for reproducible testing and match analysis.

---

## Deck Model (Updated)

| Campo | Tipo | Descrição |
|---|---|---|
| `is_public` | Boolean | Deck visível na galeria social |
| `telegram_owner_id` | Integer (nullable) | Dono do deck no Telegram |
| `usage_count` | Integer | Contador de visualizações |
| `cards` | Relationship | Muitos-para-muitos com Card (tabela `deck_cards`) |

## Known Decks

Pre-built decks in the database for testing and match simulation:

| ID | Name | Strategy |
|---|---|---|
| 7 | Kinfolk Resistance | Kinfolk + Firearms + Pack combat |
| 90 | Classic: Cliath Ahroun | Basic Ahroun, Strike + Dodge |
| 160 | Mokole | Gaia with quests, death and recruitment |
| 416 | Questor | Vigilante scoring by killing lower Renown |
| 465 | Apocalypse: First Team 28 | Wyrm squad, mass HG attack |
| 484 | Ajaba Aggression | Hyenas fleeing high damage |
| 524 | Classic: Wailer special | Allies + pack attack |
| 1050 | Assombração dos Passos da Morte | Pack Ragabash Silent Striders — Stalks Death + tricks |

---

## Scripts

Utility scripts in `scripts/`:

| Script | Purpose |
|---|---|
| `gerar_checklist.py` | Generate deck checklist vs game engine |
| `apply_tags.py` | Apply curated tags to database |
| `gerar_tags.py` | Generate/edit card tags |
| `simular_torneio.py` | Simulate tournaments |
| `criar_deck_*.py` | Create specific decks |
| `analise_partidas.py` | Analyze recorded matches |

---

## License

This project is **for educational and non-commercial purposes only**.

All **Rage CCG** card data, names, artwork, and game concepts are the intellectual property of **White Wolf Entertainment AB** and/or **Paradox Interactive**. This project is not affiliated with, endorsed by, or sponsored by White Wolf Entertainment or Paradox Interactive.

The source code in this repository is provided under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

This is a fan project intended for personal use and study of game engine architecture, web development with Flask, and AI decision systems. No copyrighted card images or assets are distributed with this repository.
