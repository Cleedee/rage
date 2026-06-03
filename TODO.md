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
- [x] **Exibir imagens** — Na busca (thumb), no deck (tooltip 390px no hover)
- [x] **Agrupar cartas no deck** — Seções Characters / Sept / Combat

## 🔄 Pendente

### Interface
- [ ] **Visualizar carta** — Página dedicada com imagem, texto completo, errata
- [ ] **Exportar deck** — Download em formato texto ou .dek
- [ ] **Filtros avançados** — Por renown, damage, atributos min/max

### Imagens
- [ ] **Upload de imagens** — Finalizar sistema de upload (rota `save_picture`)

### Infraestrutura
- [ ] **Autenticação** — Sign up / Log in
- [ ] **Redis** — Implementar cache ou remover docker-compose
- [ ] **Variáveis de ambiente** — SECRET_KEY, database URL
- [ ] **Docker** — Containerizar a aplicação

### Qualidade
- [ ] **Rotas RESTful** — Padronizar endpoints
- [ ] **Tratamento de erros** — Páginas 404, 500 customizadas
- [ ] **Testes** — Aumentar cobertura (decks, importação)
- [ ] **Validação** — Melhorar feedback nos formulários
- [ ] **Atualizar TODO.md** — Manter sincronizado com o progresso

### Extras
- [ ] **Deck builder** — Drag & drop, busca enquanto constrói
- [ ] **Compartilhar decks** — URL única para cada deck
- [ ] **Moots / Sept hand** — Simulador de jogo
