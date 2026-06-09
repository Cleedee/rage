# TODO - Rage CCG Web

## ✅ Concluído (Geral)

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

## ✅ Concluído (Motor de Jogo)

- [x] **Motor de jogo completo** — FSM com fases: redraw, regeneration, resource, umbra, moot, combat
- [x] **Sistema de combate** — Declaração simultânea, alpha, último a declarar, feint, resolução
- [x] **Sistema de efeitos** — 25+ tipos de efeito (DANO, CURAR, DESTRUIR, etc.)
- [x] **CLI de debug** — REPL com comandos STATUS, DRAW, PLAY, ATTACK, DECLARE, etc.
- [x] **API REST** — Blueprint `/api/game` para criar partidas e executar ações
- [x] **Simulador de partidas** — `match.py` bot vs bot com seeds determinísticas
- [x] **Bot com IA** — `PriorityBot` com árvore de decisão (3 dificuldades)
- [x] **Avaliador de tabuleiro** — `BoardEvaluator` com notas threat/advantage/pressure/victory
- [x] **Sistema de anúncio** — Anunciar → responder → resolver (cancelamento incluso)
- [x] **Mudança de forma Crinos** — Por dano (regra 14-ritos-moots)
- [x] **Processamento de morte unificado** — Regra 6.4.2 (combate vs não-combate, Presa, equipment discard)
- [x] **Block reduz dano pela Rage do defensor** — Regra 6.10 corrigida

## ✅ Concluído (Prey)

- [x] **Prey no Hunting Grounds** — `zona_da_carta()` → 'hunting_grounds'
- [x] **Não controlados por player específico** — `game.hunting_grounds_cards` (global)
- [x] **Alpha pode atacar Prey** — `_agir_alpha()` com `_melhor_alvo_hg()`
- [x] **Não-Alpha não ataca Prey** — `start_combat()` valida; `_pode_atacar()` restringe
- [x] **Prey se defende (Block)** — Auto-declara block via `declare_action()`
- [x] **Gaia→0VP por Victim, Wyrm→0VP por Enemy** — `_processar_morte()`
- [x] **Morte por Presa → sem VP** — `_processar_morte()` `morto_por_presa`
- [x] **Prey não frenzy/step sideways** — Regras de classe de criatura
- [x] **#3 Bot ignora alinhamento Gaia/Wyrm ao escolher presa** — `_melhor_alvo_hg()` filtra por `(vp > 0, efficiency, renown)`
- [x] **#1 Outros jogadores podem jogar combat cards pela Presa** — `start_combat()` não auto-declara mais; qualquer não-atacante pode declarar pela Presa via `_decide_combat()`

## ✅ Concluído (Allies)

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
- [x] **Requisito de recrutamento validado** — `pode_recrutar_ally()` parseia campo `requires` (Gnosis, keywords, zona)

## ✅ Concluído (Equipment)

- [x] **Fetish (Gaia only) vs Bane Fetish (Wyrm only) alignment** — `_validar_restricoes_equipamento()`
- [x] **Gnosis requirement** — Criatura precisa Gnosis >= gnosis do Fetish/Bane Fetish
- [x] **Keyword requirements (Rage FOO Rule)** — `requires` validado contra keywords da criatura
- [x] **Form restrictions** — `(Homid Form)`, `(Crinos form)`, `(Not Animal form)`, `(Garou)`, etc.
- [x] **Weapon limit (1 per creature)** — Bloqueia segunda arma
- [x] **Armor limit (1 per creature)** — Bloqueia segunda armadura
- [x] **Equipment com equipar effect** — Bot usa `_usar_carta_efeito()` → `_resolver_equipar()`
- [x] **Equipment sem equipar effect** — Bot usa `_play_card()` → `_equip_card_to_pack()`
- [x] **Built-in equipment (Bannion etc.)** — `_resolver_equipar_inicial()`
- [x] **Equipment discarded on death** — `descartar_anexos()` em `_processar_morte()`

## ✅ Concluído (Caerns — usados em decks)

- [x] **Caerns jogados na Resource phase** — Bot reconhece `ct == 'Caern'`
- [x] **Caerns vão para Pack Home** — `_play_card()` → `pack_home`
- [x] **Existência em ambos os lados do Gauntlet** — `_lado()` retorna 0 (ambos)
- [x] **Caern permite step sideways** — `encontrar_caern()` → `pode_step_sideways()`
- [x] **Umbra Phase** — FSM tem fase 'umbra' completa
- [x] **Bot Umbra actions** — `_agir_umbra()` com step in/out
- [x] **Zona Umbra** — `Zone.UMBRA`, `PlayerState.umbra`
- [x] **Gauntlet interaction** — `_mesmo_lado_gauntlet()` checa cross-Umbra
- [x] **Spirits são ambos os lados** — 'Spirit' em keywords = zona 0
- [x] **Step sideways/back** — `step_sideways()`, `step_back()` em PlayerState
- [x] **Limit 1 Caern per pack** — `pode_jogar_caern()` valida
- [x] **Caern requires validation** — `pode_jogar_caern()` usa `_simplificar_req_caern()`
- [x] **Caern em sept deck (bugfix)** — 'Caern' adicionado a `sept_types` no CLI
- [x] **Lake Nasser Wallow (#609)** — Rites/Gifts cruzam Gauntlet (modifier)
- [x] **Caern of Rytthiku (#579)** — Pode atacar Enemies no HG (modifier)
- [x] **Caern of the Unwashed Child (#586)** — -2 Rage/Gnosis em oponentes em combate
- [x] **Trinity Hive Caern (#599)** — BSD causam dano agravado, regeneram só na Umbra
- [x] **Sky River Caern (#597)** — Non-alphas imunes a challenge/sneak attack
- [x] **Caern of the Crescent Moon (#582)** — Dobra Renown no Moot, impede ser alpha
- [x] **Caern of the Snow Leopard (#584)** — Ressurreição da Umbra
- [x] **Council for Universal Trade (#590)** — Gauntlet nunca >6 ou <4 (modifier)
- [x] **The Wheel of Ptah (#600)** — Controla Moon Bridges (modifier)

## ✅ Concluído (Gifts)

- [x] **Gnosis requirement** — Criatura precisa Gnosis >= Gnosis do Gift (`_pode_pagar_custos`)
- [x] **Rage cost** — Alguns Gifts custam Rage via campo `damage` (`parse_custo_rage`)
- [x] **Keyword requirement (Rage FOO Rule)** — `pode_usar_gift()` valida campo `requires` contra keywords
- [x] **Integração bot** — `_pode_pagar_custos()` bloqueia Gifts sem criatura qualificada
- [x] **Integração CLI** — `do_ANUNCIAR()` valida antes de anunciar
- [x] **Integração API** — `api_use_card()` retorna 400 para Gift inválido
- [x] **Efeitos temporários** — `modificar_atributo` com duração `end_of_combat`/`end_of_turn`/`permanente`
- [x] **Gifts de combate** — Usados durante Combat phase via `_agir_combate()`
- [x] **Gifts não-combate** — Usados durante Resource phase via `_agir_recurso()`
- [x] **Cancelamento** — `anunciador.anular()` com chain de cancelamento

## ✅ Concluído (Quests)

- [x] **Sistema QuestState** — `QuestState` com progresso e recompensa
- [x] **_check_quests()** — Verifica na Regeneration phase
- [x] **_resolver_quest_check()** — Cria QuestState a partir de efeito
- [x] **Quest falha se alvo morre** — Marcado em `_processar_morte`, `_processar_ataque` e `_resolver_destruir`
- [x] **Gap #1 — Bot joga Quest cards** — `quest_check` removido de TIPOS_STUB, step dedicado
- [x] **Gap #2 — Um Quest por personagem** — Validação no resolvedor
- [x] **Gap #3 — Prey não faz Quests** — Victim/Enemy rejeitados
- [x] **Gap #4 — Só no próprio pack** — Alvo deve estar em pack_home ou umbra
- [x] **Gap #5 — Past Life: sept hand -1** — `_recalcular_past_life_hand_size()`
- [x] **Gap #6 — Past Life: -3 VP na morte** — `failed_due_to_death` flag
- [x] **Gap #7 — Past Life: Unique** — Segunda cópia do mesmo card_id rejeitada

## 🔄 Pendente (Interface)

- [ ] **Exportar deck** — Download em formato texto ou .dek
- [ ] **Filtros avançados** — Por renown, damage, atributos min/max

## 🔄 Pendente (Qualidade)

- [ ] **Testes** — Aumentar cobertura (decks, importação, upload)
- [ ] **Validação** — Melhorar feedback nos formulários
- [ ] **Rotas RESTful** — Padronizar endpoints

## 🔄 Pendente (Infraestrutura)

- [ ] **Autenticação** — Sign up / Log in
- [ ] **Redis** — Implementar cache ou remover docker-compose
- [ ] **Variáveis de ambiente** — SECRET_KEY, database URL
- [ ] **Docker** — Containerizar a aplicação

## 🔄 Pendente (Motor/Partidas)

- [ ] **Modo multiplayer** — Partidas PvP via WebSocket ou Server-Sent Events
- [ ] **Matchmaking** — Sala de espera, convites, ranking
- [ ] **Tela de jogo** — Tabuleiro com campo, mão, deck, cemitério (frontend HTML/HTMX)
- [ ] **Drag & drop** — Arrastar cartas do deck, mão para o campo
- [ ] **Histórico de ações** — Log da partida com replay
- [ ] **Timer / Relógio** — Controle de tempo por turno
- [ ] **Treinamento bot** — Coletar dados de partidas para refinar heurísticas

## 🔄 Pendente (Prey)

- [ ] **#2 Prey pode usar Gifts em combate (pagos por outros)** — `Anyone but the player fighting the Prey can pay Gifts for them`
- [x] **#4 Bot: timing estratégico — quando atacar Prey vs Alpha inimigo** — `_deve_atacar_presa_estrategicamente()` avalia VP gap, força do alpha, eficiência da Presa

## 🔄 Pendente (Allies)

- [ ] **Allies não jogam Actions/Past Lives/Rites/Totems/pack resources** — Engine não filtra por card type (baixo impacto)
- [ ] **Allies não podem ser descartados voluntariamente** — Sem mecânica de descarte voluntário (baixo impacto)

## 🔄 Pendente (Equipment)

- [ ] **Trade entre pack members** — Trocar equipamentos durante Resource phase (baixo impacto)
- [ ] **Equipment em Prey** — Equipment não pode ser jogado/trocado para Presas (médio impacto)
- [ ] **JSON models para Equipment sem efeito** — Apenas 38/439 têm modelos JSON (alto impacto, muito trabalho)
- [ ] **Ativação de equipamentos com efeito** — Equipment como Animal Mummy (destruir sept card) não tem botão de ativação (médio impacto)

## 🔄 Pendente (Caerns/Umbra)

- [ ] **Caern/Territory special abilities restantes** — 37/46 Caerns não implementados (não estão em decks cadastrados)
- [ ] **Discard Caern para trocar** — Regra permite descartar Caern existente e jogar outro (médio impacto)
- [ ] **Territory pode ser atacado/destruído** — Quickstart menciona "Attack a Territory" (médio impacto)
- [ ] **Realm requer Umbra** — Character precisa estar na Umbra para jogar Realm (baixo impacto)
- [ ] **Cross-Gauntlet combat details** — Regras de substituição de combatentes entre mundos (baixo impacto)
- [ ] **Umbra combat targeting** — Criaturas na Umbra só podem atacar outras na Umbra (parcial)
- [ ] **Territory effects cruzam Gauntlet** — Global effects vs action effects (parcial)

## 🔄 Pendente (Gifts)

- [x] **Gift timing validation** — `validar_timing_gift()` checa "play at start of combat", "Combat Restricted", "May not be used during combat"
- [x] **"Opponent" text = combat only** — `validar_opponent_gift()`: gifts mencionando "opponent" só em combate
- [x] **Permanent Gifts permanecem em jogo** — `gift_eh_permanente()` mantém card em pack_home ao invés de descarte
- [ ] **Prey Gift payment (#2)** — Outros jogadores pagam Gifts pela Presa em combate (médio impacto)

## 🔄 Pendente (Ritos / Rites)

- [x] **Bot joga Rites** — Adicionado `ct == 'Rite'` em `_agir_recurso()` e `_try_develop_board()`
- [x] **Renown requirement** — `pode_usar_rite()` valida Renown do personagem >= Renown listado
- [x] **Classe requirement (Garou/Fera/Cultist)** — `pode_usar_rite()` verifica keywords de classe
- [x] **Timing (fora de combate)** — `validar_timing_rite()` bloqueia Rites durante combat phase
- [x] **Integração CLI** — `do_ANUNCIAR()` valida timing + requisitos
- [x] **Integração API** — `api_use_card()` retorna 400 para Rite inválido
- [x] **Integração Bot** — `_pode_pagar_custos()` checa timing + requisitos de Rite
- [ ] **Apenas 1 Rite card (Rite of the Opened Caern) com modelo JSON** — 57/58 sem efeitos
- [ ] **Rites com timing específico** — Ex: "play after this character killed a Victim"
- [ ] **Rites que attach em criatura** — Permanecem na criatura até removidos por efeito

## 🔄 Pendente (Moot / Juntas)

- [x] **MootState** — Estrutura de votacao com sim/nao, aprovacao, resolucao
- [x] **Fase Moot na FSM** — Fase entre umbra e combat
- [x] **chamar_moot()** — Cria votacao com validacao Gaia/Wyrm + Renown minimo
- [x] **votar_moot()** — Vota com Renome total do jogador (inclui Thousand Cubs bonus)
- [x] **resolver_moot()** — Aplica efeitos se aprovado (modelo JSON)
- [x] **Bot _agir_moot()** — Vota estrategicamente ou chama Junta
- [x] **Bot _moot_voto_estrategico()** — Voto SIM se propria junta ou contra lider
- [x] **Bot reconhece Board Meeting** — Corrigido (`card_type == 'Board Meeting'`)
- [x] **Moot effect types (5)** — MOOT_REMOVER_PERSONAGEM, MOOT_GANHAR_VP, MOOT_RESTRICAO_GLOBAL, MOOT_REBAIXAR_FORMA, MOOT_CONSTRUIR_CAERN
- [ ] **Open Play durante Moot** — Bot so vota/passa sem jogar cartas
- [ ] **Votacao em ordem de Renome** — Todos votam simultaneamente
- [ ] **1 Junta por turno** — Sem flag de turno, so verifica se ja tem ativa
- [ ] **Moot cards sem modelo JSON** — 69/74 cartas sem efeitos implementados (baixo impacto, so 7 em decks)
- [ ] **Board Meeting sem modelo JSON** — Nenhum Board Meeting tem JSON model (baixo impacto)

## 🧪 Testes

- [x] **271 testes passando** — Endpoints, state, combat, bot, CLI, API, effects, anunciador
- [ ] **Testes para Caern special abilities** — Verificar cada Caern implementado
- [ ] **Testes para Gift Rage FOO Rule** — Validação de requisitos
- [ ] **Testes para Ally recruitment** — `pode_recrutar_ally()` com diversos padrões
- [ ] **Testes para Quests** — `_check_quests()`, Past Life penalties, Unique enforcement
