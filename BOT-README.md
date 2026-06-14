# 🤖 Bot Telegram Rage CCG — @furia_ccg_bot

## 🚀 Iniciar o Bot

```bash
cd /workspace
source .venv/bin/activate
rage-bot
```

O bot lê o token do arquivo `.env` (variável `TELEGRAM_KEY_TOKEN`).

Para rodar em background:
```bash
make run-bot
```

Para ver logs:
```bash
tail -f /tmp/rage-bot.log
```

## 📱 Comandos

Envie `/start` no Telegram para ver as boas-vindas.

### Matchmaking (antes da partida)

| Comando | Exemplo | Descrição |
|---|---|---|
| `/decks` | `/decks` | Lista seus decks cadastrados |
| `/duel @user <deck>` | `/duel @joao 7` | Desafia alguém com seu deck 7 |
| `/accept @user <deck>` | `/accept @pedro 90` | Aceita desafio com seu deck 90 |
| `/decline @user` | `/decline @pedro` | Recusa desafio |

### Durante a partida

| Comando | Exemplo | Descrição |
|---|---|---|
| `/board` | `/board` | Tabuleiro completo |
| `/hand` | `/hand` | Sua mão |
| `/status` | `/status` | Status resumido |
| `/actions` | `/actions` | O que fazer agora |
| `/play <N>` | `/play 0` | Joga a carta de índice 0 da mão |
| `/use <N>` | `/use 2` | Usa carta de efeito (Gift, Rite...) |
| `/attack <id>` | `/attack 500` | Ataca Hunting Grounds |
| `/attack <a> <d>` | `/attack 500 601` | Ataca criatura específica |
| `/declare <id> <a>` | `/declare 500 strike` | Declara ação de combate |
| `/reveal` | `/reveal` | Revela ações |
| `/feint <id> <a>` | `/feint 500 dodge` | Troca ação (Último a Declarar) |
| `/resolve` | `/resolve` | Resolve combate |
| `/draw [deck] [n]` | `/draw combat 2` | Compra cartas |
| `/pass` | `/pass` | Passa a vez |
| `/concede` | `/concede` | Desistir |

## 🏗️ Arquitetura

```
Telegram ──► python-telegram-bot ──► handlers.py ──► GameManager ──► GameState
                                            │                        │
                                            ▼                        ▼
                                       Matchmaker              Game Engine
                                       (desafios)              (motor CCG)
```

## 📝 Notas

- O estado das partidas fica **em memória** (volátil)
- Se o bot reiniciar, partidas em andamento são perdidas
- Futuro: persistir partidas no SQLite
- Matchmaking usa @username do Telegram
- Desafios expiram em 2 minutos
