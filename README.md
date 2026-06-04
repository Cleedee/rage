# Rage CCG Web

A web application for managing **Rage CCG** cards and decks, built with Flask. Includes a complete game engine with AI bot opponents, a debug CLI, and a REST API.

> **Rage CCG** is a collectible card game based on the *World of Darkness* universe by White Wolf Entertainment. All card art, names, and game concepts are the property of their respective owners.

---

## Features

- **Card Catalog** — Browse, search, create, edit, and delete cards (Characters, Equipment, and generic cards)
- **Deck Builder** — Create and manage decks with a card database of 1,800+ imported cards
- **Game Engine** — Full turn-based CCG engine with 6 phases (redraw, regeneration, resource, umbra, moot, combat)
- **Combat System** — Simultaneous declaration, alpha order, reveal, feint, and resolution
- **Structured Effects** — JSON-defined card effects with 16 effect types and flexible targeting
- **AI Bot** — Priority-based decision tree with 3 difficulty levels (easy, medium, hard)
- **Match Simulator** — Run bot-vs-bot matches from the command line
- **Debug CLI** — Interactive REPL for testing game states
- **REST API** — Programmatic game access at `/api/game/`

---

## Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.12** | Language |
| **Flask 3.1** | Web framework |
| **SQLAlchemy** | ORM |
| **SQLite** | Database |
| **Alembic** | Migrations |
| **WTForms** | Form handling |
| **Bulma CSS** | UI framework |
| **HTMX** | AJAX interactivity |
| **pytest** | Testing |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/your-username/rage-web.git
cd rage-web

# Create a virtual environment (recommended)
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install uv
uv sync

# Set up the database
flask init-database

# (Optional) Import cards from LackeyCCG data
flask import-cards

# Run the development server
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Project Structure

```
├── app.py                          # Application entry point
├── pyproject.toml                  # Dependencies & project config
├── rage_web/
│   ├── __init__.py                 # Flask factory (create_app)
│   ├── config.py                   # App configuration
│   ├── blueprints/                 # Route modules
│   │   ├── cards/                  # Card CRUD
│   │   ├── decks/                  # Deck CRUD
│   │   └── home/                   # Landing page
│   ├── ext/                        # Extensions
│   │   ├── database.py             # SQLAlchemy setup
│   │   ├── repository.py           # Repository layer
│   │   └── cli.py                  # CLI commands
│   ├── game_engine/                # Card game engine
│   │   ├── state.py                # Game state, zones, combat
│   │   ├── combat_queue.py         # Combat cycle
│   │   ├── rules.py                # Game constants & rules
│   │   ├── effects.py              # Effects system
│   │   ├── anunciador.py           # Announce / respond / resolve
│   │   ├── match.py                # Bot match simulator
│   │   ├── cli.py                  # Debug REPL
│   │   ├── api.py                  # REST API blueprint
│   │   └── bot/                    # AI
│   │       ├── evaluator.py        # Board evaluation
│   │       └── priority_bot.py     # Decision tree bot
│   ├── helpers/
│   │   └── forms.py                # WTForms definitions
│   ├── models/
│   │   ├── card.py                 # Card model
│   │   ├── deck.py                 # Deck model
│   │   └── picture.py              # Card images
│   └── templates/
│       └── base.html               # Base layout (Bulma + HTMX)
├── data/cards/                     # Card effect JSONs
├── migrations/                     # Alembic migrations
└── tests/                          # pytest suite
```

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
4. **Resolve** — Apply damage, destroy creatures → Victory Pile
5. **End** — Remove dead creatures, check victory

### CLI Debug Commands

```
STATUS    — Show full board state
DRAW n    — Draw cards
PLAY n    — Play a card from hand
ATTACK    — Start combat
DECLARE   — Declare combat action
REVEAL    — Reveal declared actions
FEINT     — Change action (Last to Declare only)
RESOLVE   — Resolve combat
PASS      — Pass priority
NEXT      — Advance phase
```

```bash
# Launch the debug REPL
rage-cli

# Run a bot vs bot match
rage-match --deck1 "My Deck" --deck2 "Opponent Deck" --difficulty hard
```

---

## REST API

The game engine exposes a REST API at `/api/game/`:

| Endpoint | Action |
|---|---|
| `POST /api/game/new` | Create a new game |
| `GET /api/game/<id>` | Get game state |
| `GET /api/game/<id>/legal-actions` | Available actions |
| `POST /api/game/<id>/draw` | Draw cards |
| `POST /api/game/<id>/play` | Play a card |
| `POST /api/game/<id>/attack` | Declare attack |
| `POST /api/game/<id>/pass` | Pass priority |
| `POST /api/game/<id>/next` | Advance phase |

---

## Tests

```bash
pytest                # Run all tests
pytest -v             # Verbose mode
```

The test suite covers the game engine (state, combat, effects, bot, CLI, API) with **120+ passing tests**.

---

## Importing Cards

1,800+ cards were imported from the LackeyCCG community database:

```bash
flask import-cards                # Import all sources
flask import-cards --dry-run      # Preview only
flask import-cards --fonte oficial  # Official cards only
```

---

## License

This project is **for educational and non-commercial purposes only**.

All **Rage CCG** card data, names, artwork, and game concepts are the intellectual property of **White Wolf Entertainment AB** and/or **Paradox Interactive**. This project is not affiliated with, endorsed by, or sponsored by White Wolf Entertainment or Paradox Interactive.

The source code in this repository is provided under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

This is a fan project intended for personal use and study of game engine architecture, web development with Flask, and AI decision systems. No copyrighted card images or assets are distributed with this repository.
