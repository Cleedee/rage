# TODO - Rage CCG Web

## 🚨 Prioridade Alta

- [x] **Importar cartas do LackeyCCG** — 1797 cartas importadas
- [x] **CRUD de cartas** — Character, Equipment, Card genérico
- [x] **CRUD de decks**
- [x] **Relacionamento Deck ↔ Card** — Tabela associativa `deck_cards`
- [x] **Adicionar/remover cartas nos decks** — Interface com HTMX
- [x] **Importar decks** — Formato texto e .dek (LackeyCCG)
- [ ] **Busca visual de cartas** — Grid com filtros (tipo, expansão, atributos)

## 🔄 Pendente

### Interface
- [ ] **Melhorar home** — Dashboard com estatísticas (total cartas, decks, últimas adições)
- [ ] **Página de busca de cartas** — Layout em grid com preview do texto
- [ ] **Filtros avançados** — Por expansão, tipo, atributos (Rage, Gnosis, Renome)
- [ ] **Visualizar carta** — Página dedicada com imagem, texto completo, errata
- [ ] **Exportar deck** — Download em formato texto ou .dek

### Imagens
- [ ] **Baixar imagens das cartas** — Script para download das imagens do LackeyCCG
- [ ] **Upload de imagens** — Finalizar sistema de upload (rota `save_picture`)
- [ ] **Exibir imagens** — Nas páginas de carta e busca

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

### Extras
- [ ] **Deck builder** — Drag & drop, busca enquanto constrói
- [ ] **Compartilhar decks** — URL única para cada deck
- [ ] **Moots / Sept hand** — Simulador de jogo
