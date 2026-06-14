# 📋 TODO — Rage CCG Telegram Bot

> Prioridade: 🔥 Alta | 🚀 Média | 💎 Baixa
> Status: ✅ Pronto | 🔄 Em andamento | ⏳ Pendente

---

## 🔥 Prioridade Alta (essencial para jogar)

### 1. ✅ Resolver @username → Telegram ID
**Arquivos:** `user_registry.py`, `conversations.py`, `matchmaker.py`
**Esforço:** 3h

**Implementado:**
- `user_registry.py` com banco SQLite (`user_registry.db`)
- `register_user()` chamado automaticamente via `@auto_register` nos handlers
- `resolve_username()` para lookup local
- `resolve_username_via_api()` fallback via `getChat` para usuários não registrados
- `/duel` e `/accept` notificam o oponente automaticamente
- `@auto_register` aplicado a: start, help, decks, decline, duel, accept

**Ainda falta:**
- [ ] Registrar usuários em TODOS os entry points (handlers de jogo)
- [ ] Notificação push: se o desafiado nunca falou com o bot, não recebe o desafio

### 2. ✅ Editar mensagens em vez de flood
**Arquivos:** `handlers.py`
**Esforço:** 1h

**Implementado:**
- `_update_board_message()` em `handlers.py` — edita mensagem existente, fallback para nova
- Armazena `board_msg_id` + `board_chat_id` em `context.user_data`
- Usado em: `/board`, `/play`, `/pass`, `/next` (texto e callbacks)
- Callbacks já usavam `_edit_with_keyboard()`

**Ainda falta:**
- [ ] Usar em `_notify_opponent()` para boards do oponente
- [ ] Limpar `board_msg_id` quando a partida termina

### 3. ✅ Timer customizável
**Arquivos:** `game_manager.py`, `handlers.py`, `bot.py`
**Esforço:** 30min

**Implementado:**
- Comando `/timer <horas>` — intervalo 1h~48h
- `game_manager.set_turn_timeout()` — altera o timeout da partida atual
- Cancela e reagenda timer automaticamente com novo valor
- Notifica o oponente da alteração
- Botão "⏱️" no teclado inline (pendente)

**Ainda falta:**
- [ ] Botão "⏱️" no teclado inline do board

---

## 🚀 Prioridade Média (expande o ecossistema)

### 4. ✅ Persistência SQLite (não perder partidas)
**Arquivos:** `persistence.py`, `game_manager.py`, `bot.py`
**Esforço:** 4h

**Implementado:**
- `persistence.py` — módulo completo (`GamePersistence`):
  - Tabela `active_games` com `game_id`, `game_session` (blob pickle),
    `player1_id`, `player2_id`, timestamps
  - `save_game()` / `load_game()` / `load_all_games()` / `delete_game()`
  - Índices por player_id para lookup rápido
- `game_manager.py`:
  - `_save_game()` chamado automaticamente em `create_game()`
  - `remove_game()` remove da persistência
  - `load_all_active_games()` — carrega + reconstrói `_players`
- `bot.py`:
  - `_restore_active_games()` como `post_init` do bot
  - Notifica jogadores: "🔄 Partida restaurada!"
  - Reagenda timers para o jogador atual

**Ainda falta:**
- [ ] Auto-save após ações (não apenas na criação)

### 5. ✅ Deck público — galeria social
**Arquivos:** `handlers.py`, `models/deck.py`, `bot.py`, migration
**Esforço:** 3h

**Implementado:**
- Modelo `Deck` com campos: `is_public`, `telegram_owner_id`, `usage_count`, `created_at`, `updated_at`
- Migration `5dfa67153220`
- `/deck search <termo>` — busca por nome (case-insensitive, top 20)
- `/deck view <id>` — lista cartas agrupadas por tipo com atributos
- `/deck share [id]` — alterna público/privado (verifica ownership)
- `/deck top` — top 10 mais usados com medalhas 🥇🥈🥉
- `/deck <termo>` — atalho para search
- Uso de `/deck view` incrementa contagem (⭐)

### 6. ✅ Histórico e estatísticas
**Arquivos:** `stats.py`, `handlers.py`, `bot.py`
**Esforço:** 4h

**Implementado:**
- `stats.py` — `StatsManager` com SQLite:
  - Tabela `match_history`: winner/loser, decks, método, timestamp
  - Tabela `player_ratings`: rating ELO (K=32, default=1200), wins/losses
  - `record_match()` — registra resultado + atualiza ELO automaticamente
  - `get_player_stats()` — winrate, deck favorito, últimas 5 partidas
  - `get_rankings()` — top N por rating
  - `get_deck_stats()` — winrate por deck
- `/concede` agora registra a partida (winner=oponente, loser=quem desistiu)
- `/stats` — mostra 📊 rating, W/L, winrate%, deck favorito
- `/rank` — ranking global top 15 com medalhas 🥇🥈🥉
- Timeout auto-concede também registra no histórico

### 7. ✅ Efeitos visuais no Telegram
**Arquivos:** `render.py`, `handlers.py`
**Esforço:** 2h

**Implementado:**
- `render_card_portrait()` — retrato visual de carta com moldura:
  ```
  ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
  ▎🐺 *Stalks Death            * ▎
  ▎ `CHARACTER               ` ▎
  ▎ 💚5 | 🩸4 | 🧠3 | 👑2          ▎
  ▎ ❤️ ` 3/5 ` █████░░░            ▎
  ▎ _Once per turn, you may..._ ▎
  ▎ `Garou, Ahroun             ` ▎
  ▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃▃
  ```
- `_send_card_image()` — envia foto da carta quando disponível
- `render_hand()` melhorada — mini-HP bars, separadores entre cartas, 
  atributos inline
- `render_board()` melhorada — HP bars visuais, oponente com resumo
  compacto (HP total, ataque, HG, Umbra, mão)
- `/card <N>` — comando novo: mostra retrato + detalhes de carta na mão
- Ao jogar carta (`/play`): mostra retrato + tenta enviar imagem

**Limitação:** Apenas 1 imagem de carta disponível no banco
(`hatii-the-thunderer.png`). O sistema está pronto para exibir
imagens assim que forem adicionadas.

---

## 💎 Prioridade Baixa (futuro)

### 8. Multijogador (3-6 jogadores)
**Arquivos:** `GameManager`, `matchmaker.py`, `handlers.py`
**Esforço:** 5h

O motor já suporta N jogadores (`build_game_from_decks_n`), o bot não.

**O que falta:**
- `/duel` aceitar múltiplos @: `/duel @joao @maria @pedro`
- Lobby com N jogadores
- Turn order: cada jogador age em sequência
- Detecção de eliminação

### 9. Torneios
**Arquivos:** Novo módulo `tournament.py`
**Esforço:** 6h

Competições com chaveamento.

**O que falta:**
- `/tournament create <nome>` — cria torneio
- `/tournament join` — inscreve jogador
- `/tournament start` — sorteia chaves
- `/tournament bracket` — mostra chaveamento
- Suporte a suíço ou eliminação simples

### 10. Sistema ELO
**Arquivos:** `stats.py` (ou novo `elo.py`)
**Esforço:** 4h

Rating para partidas ranqueadas.

**O que falta:**
- Implementar fórmula ELO (K=32)
- Partidas ranqueadas vs casuais
- `/elo` — ver rating
- Atualizar ao fim de cada partida

### 11. ✅ Integração com Web App Flask
**Arquivos:** `blueprints/auth/`, `blueprints/games/`, `blueprints/game/`, `telegram_bot/handlers.py`
**Esforço:** 8h

**Implementado:**
- **Login via Telegram Widget** (`/auth/login`):
  - Botão "Login with Telegram" na página
  - Verificação HMAC-SHA256 do payload
  - Sessão Flask com telegram_id, username, full_name, photo_url
- **Meus Jogos** (`/games/`):
  - Lista partidas ativas do jogador (do bot + da web)
  - Cards com ID, turno, fase, VP, indicador de quem está jogando
  - Links para acompanhar partida no navegador
- **Partidas do bot visíveis na web**:
  - `view_game`, `game_board_partial`, `game_action` buscam também
    no `GameManager` do bot
  - HTMX polling a cada 3s no board
- **Bot envia links web**:
  - Ao criar partida: `[🌐 Acompanhar no navegador]({{url}})`
- **Navbar atualizada**:
  - "Meus Jogos" no menu principal
  - Login/Logout com nome do usuário

**Para produção:** substituir `http://127.0.0.1:5000` pela URL real do site

### 12. Comandos de moderação
**Arquivos:** `handlers.py`
**Esforço:** 2h

Para administrar o bot quando houver múltiplos usuários.

**O que falta:**
- `/ban @user` — banir jogador
- `/unban @user` — desbanir
- `/warn @user` — advertir
- Lista de admins (configurável via .env)
- Log de ações de moderação

---

## 🐛 Bugs Corrigidos

- [x] **ConversationHandler vs CallbackQueryHandler**: `handle_callback` agora ignora callbacks com prefixo `duel_deck:` ou `accept_deck:` (deixando para o ConversationHandler). Também ignora silenciosamente se o usuário está em conversa.
- [x] **Matchmaking username→id**: `/duel` conversacional agora resolve @username via `resolve_username()` + `resolve_username_via_api()`, cria desafio no `Matchmaker` centralizado e notifica o desafiado.
- [x] **Timeout de 24h**: Reduzido para **2h** (7200s). Ainda configurável via `/timer <horas>`.
- [x] **Edição de mensagens**: `_notify_opponent()` agora usa `_update_board_message()`. Board é editado em vez de enviar novo.
- [x] **Instâncias separadas**: `Matchmaker` agora é importado de `handlers.py` no lugar de criar instância local.

---

## 📊 Legenda de Progresso

| Categoria | Total | ✅ Pronto | 🔄 Andamento | ⏳ Pendente |
|---|---|---|---|---|
| 🔥 Alta | 3 | 3 | 0 | 0 |
| 🚀 Média | 4 | 3 | 0 | 1 |
| 💎 Baixa | 5 | 1 | 0 | 4 |
| **Total** | **12** | **8** | **0** | **4** |
