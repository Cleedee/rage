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

## Extras
- [ ] **Deck builder** — Drag & drop, busca enquanto constrói
- [ ] **Compartilhar decks** — URL única para cada deck
