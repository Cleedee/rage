.PHONY: run run-bot run-web install test shell backup db-health export-decks import-decks backup-full

# ── Ambiente ──────────────────────────────────────────────────────

.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/pip install -e .

install: .venv/bin/python

# ── Servidor Web ──────────────────────────────────────────────────

run-web: install
	.venv/bin/flask run --host 0.0.0.0 --port 5000

# ── Telegram Bot ──────────────────────────────────────────────────

# Inicia o bot em modo polling (lê TELEGRAM_KEY_TOKEN do .env)
run-bot: install
	.venv/bin/rage-bot

# Modo verbose (log detalhado)
run-bot-debug: install
	.venv/bin/rage-bot --verbose

# ── Utilitários ───────────────────────────────────────────────────

# Importar cartas do LackeyCCG
import-cards: install
	.venv/bin/flask import-cards

# Aplicar tags curadas
apply-tags: install
	PYTHONPATH=. .venv/bin/python3 scripts/apply_tags.py

# Gerar checklist de efeitos para um deck
checklist: install
	PYTHONPATH=. .venv/bin/python3 scripts/gerar_checklist.py $(DECK_ID)

# Rodar testes
test: install
	.venv/bin/python3 -m pytest -v

# ── Backup e Integridade ──────────────────────────────────────────

# Verificar integridade do banco
db-health: install
	.venv/bin/flask db-health

# Exportar todos os decks para JSON versionáveis
export-decks: install
	.venv/bin/flask export-decks

# Importar decks de JSON
import-decks: install
	.venv/bin/flask import-decks

# Fazer backup do banco de dados
backup: install
	.venv/bin/flask backup-db

# Backup completo: exporta decks + copia banco
backup-full: export-decks backup
	@echo '✅ Backup completo!'

# ── Docker ────────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# ── Shell ─────────────────────────────────────────────────────────

shell: install
	.venv/bin/flask shell
