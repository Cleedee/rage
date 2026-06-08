# TODO - Rage CCG Web

## ✅ Concluído

- [x] **Importar cartas do LackeyCCG** — 1797 cartas importadas (3 TSVs)
- [x] **CRUD de cartas** — Character, Equipment, Card genérico
- [x] **CRUD de decks**
- [x] **Relacionamento Deck ↔ Card** — Tabela associativa `deck_cards`
- [x] **Adicionar/remover cartas nos decks** — Interface com HTMX
- [x] **Importar decks** — Formato texto e .dek (LackeyCCG) com CLI e web
- [x] **Busca visual de cartas** — Grid com filtros (nome, tipo, expansão), stats coloridos
- [x] **Dashboard (home)** — Estatísticas, barras por tipo/expansão, decks recentes
- [x] **Baixar imagens** — Script com rate limiting, backoff, 1650+ imagens baixadas
- [x] **Exibir imagens** — Na busca (thumb), no deck (tooltip 250px no hover)
- [x] **Agrupar cartas no deck** — Seções Characters / Sept / Combat
- [x] **Visualizar carta** — Página dedicada com imagem, texto completo, errata
- [x] **Upload de imagens** — Fan art com upload e prioridade sobre original
- [x] **Páginas de erro** — 404 e 500 customizadas
- [x] **Melhoria header/footer** — Navbar dark, footer 3 colunas
- [x] **Edição de cartas** — Formulário universal com todos os campos

## 🔄 Pendente

### Interface
- [ ] **Exportar deck** — Download em formato texto ou .dek
- [ ] **Filtros avançados** — Por renown, damage, atributos min/max

### Qualidade
- [ ] **Testes** — Aumentar cobertura (decks, importação, upload)
- [ ] **Validação** — Melhorar feedback nos formulários
- [ ] **Rotas RESTful** — Padronizar endpoints

### Infraestrutura
- [ ] **Autenticação** — Sign up / Log in
- [ ] **Redis** — Implementar cache ou remover docker-compose
- [ ] **Variáveis de ambiente** — SECRET_KEY, database URL
- [ ] **Docker** — Containerizar a aplicação

## 🎮 Área de Jogo (Motor / Partidas)

### Engine
- [ ] **Motor de jogo** — Implementar regras do Rage CCG (turnos, fases, combate)
- [ ] **Sistema de avaliação de estado** — Heurísticas para pontuar campo, mão, cemitério
- [ ] **Árvore de decisão** — Algoritmo Minimax / Monte Carlo para sugerir jogadas

### Partidas
- [ ] **Modo solo vs Bot** — Bot com perfis de dificuldade (fácil, médio, difícil)
- [ ] **Modo multiplayer** — Partidas PvP via WebSocket ou Server-Sent Events
- [ ] **Matchmaking** — Sala de espera, convites, ranking

### Interface
- [ ] **Tela de jogo** — Tabuleiro com campo, mão, deck, cemitério
- [ ] **Drag & drop** — Arrastar cartas do deck, mão para o campo
- [ ] **Histórico de ações** — Log da partida com replay
- [ ] **Timer / Relógio** — Controle de tempo por turno

### Infra Bot
- [ ] **Bot baseado em regras** — Estratégias simples (jogar carta mais forte, combinar tribo)
- [ ] **Perfis de dificuldade** — Fácil (escolhas aleatórias), Médio (heurística), Difícil (árvore profundidade 3+)
- [ ] **Treinamento** — Coletar dados de partidas para refinar heurísticas

## 🦴 Regras de Prey (Enemies & Victims)

### Implementado ✅
- [x] **Prey no Hunting Grounds** — `zona_da_carta()` → 'hunting_grounds'
- [x] **Não controlados por player específico** — `game.hunting_grounds_cards` (global)
- [x] **Alpha pode atacar Prey** — `_agir_alpha()` com `_melhor_alvo_hg()`
- [x] **Não-Alpha não ataca Prey** — `start_combat()` valida; `_pode_atacar()` restringe
- [x] **Prey se defende (Block)** — Auto-declara block via `declare_action()`
- [x] **Gaia→0VP por Victim, Wyrm→0VP por Enemy** — `_processar_morte()`
- [x] **Morte por Presa → sem VP** — `_processar_morte()` `morto_por_presa`
- [x] **Prey não frenzy/step sideways** — Regras de classe de criatura

### ❌ Pendente
- [x] **#3 Bot ignora alinhamento Gaia/Wyrm ao escolher presa** — `_melhor_alvo_hg()` não filtra presas que dão 0 VP
- [x] **#1 Outros jogadores podem jogar combat cards pela Presa** — `start_combat()` não auto-declara mais; qualquer não-atacante pode declarar pela Presa via `_decide_combat()`
- [ ] **#2 Prey pode usar Gifts em combate (pagos por outros)** — `Anyone but the player fighting the Prey can pay Gifts for them`
- [ ] **#4 Bot: timing estratégico — quando atacar Prey vs Alpha inimigo** — Priorizar VP rápido vs eliminar ameaça

## 🤝 Regras de Allies

### Implementado ✅
- [x] **Vai pro Pack Home** — `zona_da_carta('ally')` → `'pack_home'`
- [x] **Pode lutar em combates** — `TIPOS_COMBATENTES` inclui `'ally'`
- [x] **Pode equipar e usar Gifts** — Sem restrição por card type
- [x] **Pode ser alpha** — `selecionar_alfa` aceita Character ou Ally
- [x] **É membro do pack** — Afetado por Pack Totems e bônus de pack
- [x] **Não pode Frenzy / Step Sideways** — Regras de classe de criatura
- [x] **Regen conforme creature class** — `_pode_regenerar` checa keywords
- [x] **Morte fora de combate → removido do jogo** — `Zone.REMOVED`
- [x] **Morte em combate → VP do oponente** — `_processar_morte()`
- [x] **Recrutador morre → Ally fica** — Só removido se TODOS Characters morrerem
- [x] **Requisito de recrutamento validado** — `pode_recrutar_ally()` em `rules.py` parseia campo `requires` (Gnosis, keywords, zona)

### ❌ Pendente
- [ ] **Allies não jogam Actions/Past Lives/Rites/Totems/pack resources** — Engine não filtra por card type (baixo impacto)
- [ ] **Allies não podem ser descartados voluntariamente** — Sem mecânica de descarte voluntário

## ⚔️ Regras de Equipment (Equipamentos)

### Implementado ✅
- [x] **Fetish (Gaia only) vs Bane Fetish (Wyrm only) alignment** — `_validar_restricoes_equipamento()` em effects.py
- [x] **Gnosis requirement** — Criatura precisa Gnosis >= gnosis do Fetish/Bane Fetish
- [x] **Keyword requirements (Rage FOO Rule)** — `requires` validado contra keywords da criatura
- [x] **Form restrictions** — `(Homid Form)`, `(Crinos form)`, `(Not Animal form)`, `(Garou)`, etc.
- [x] **Weapon limit (1 per creature)** — Bloqueia segunda arma
- [x] **Armor limit (1 per creature)** — Bloqueia segunda armadura
- [x] **Equipment com equipar effect** — Bot usa `_usar_carta_efeito()` → `_resolver_equipar()`
- [x] **Equipment sem equipar effect** — Bot usa `_play_card()` → `_equip_card_to_pack()`
- [x] **Built-in equipment (Bannion etc.)** — `_resolver_equipar_inicial()`
- [x] **Equipment discarded on death** — `descartar_anexos()` em `_processar_morte()`

### ❌ Pendente
- [ ] **Trade entre pack members** — Trocar equipamentos durante Resource phase (baixo impacto)
- [ ] **Equipment em Prey** — Equipment não pode ser jogado/trocado para Presas (médio impacto)
- [ ] **JSON models para Equipment sem efeito** — Apenas 38/439 têm modelos JSON (alto impacto, muito trabalho)
- [ ] **Ativação de equipamentos com efeito** — Equipment como Animal Mummy (destruir sept card) não tem botão de ativação

## 🎁 Regras de Gifts

### Implementado ✅
- [x] **Gnosis requirement** — Criatura precisa Gnosis >= Gnosis do Gift (`_pode_pagar_custos`)
- [x] **Rage cost** — Alguns Gifts custam Rage via campo `damage` (`parse_custo_rage`)
- [x] **Keyword requirement (Rage FOO Rule)** — `pode_usar_gift()` em `rules.py` valida campo `requires` contra keywords da criatura
- [x] **Integração bot** — `_pode_pagar_custos()` bloqueia Gifts sem criatura qualificada
- [x] **Integração CLI** — `do_ANUNCIAR()` valida antes de anunciar
- [x] **Integração API** — `api_use_card()` retorna 400 para Gift inválido
- [x] **Efeitos temporários** — `modificar_atributo` com duração `end_of_combat`/`end_of_turn`/`permanente`
- [x] **Gifts de combate** — Usados durante Combat phase via `_agir_combate()`
- [x] **Gifts não-combate** — Usados durante Resource phase via `_agir_recurso()`
- [x] **Cancelamento** — `anunciador.anular()` com chain de cancelamento

### ❌ Pendente
- [ ] **Gift timing validation** — Gifts com "play at start of combat" só jogáveis nesse momento (médio impacto)
- [ ] **"Opponent" text = combat only** — Gifts mencionando "opponent" restritos ao combate (médio impacto)
- [ ] **Permanent Gifts permanecem em jogo** — Gifts com `duracao: permanente` não são descartados (baixo impacto)

## Extras
- [ ] **Deck builder** — Drag & drop, busca enquanto constrói
- [ ] **Compartilhar decks** — URL única para cada deck
