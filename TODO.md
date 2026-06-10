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
- [ ] **Exportação de Deck para Discord** — Texto em inglês, Personagens antes dos demais tipos de cartas

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

- [x] **#2 Prey pode usar Gifts em combate (pagos por outros)** — `pode_usar_gift()` inclui Victims/Enemies do HG como personagens válidos
- [x] **#4 Bot: timing estratégico — quando atacar Prey vs Alpha inimigo** — `_deve_atacar_presa_estrategicamente()` avalia VP gap, força do alpha, eficiência da Presa

## ✅ Concluído (Sistema de Triggers de Presas)

- [x] **Wild Animals (#568) auto-ataque** — Ataca maior Rage Wyrm no fim do combate
- [x] **Vigilante (#565) auto-ataque** — Ataca quem matou a vítima de menor Renome
- [x] **Mage of the Celestial Chorus (#503) remoção** — Remove menor Renome victim no fim do turno
- [x] **Mage of the Celestial Chorus ANY Gifts** — Pode usar qualquer Gift (via `_info_char` text matching)
- [x] **Unlucky Lune (#558) Auspice Gifts** — pode usar Gifts com requisito 'Auspice'
- [x] **Unlucky Lune Full Moon Rage 6** — Rage aumenta para 6 com Full Moon ativa
- [x] **_coletar_todas_vitimas_hg()** — Coleta presas do HG global + HG de cada jogador
- [x] **_coletar_todos_personagens()** — Coleta personagens de pack_home + umbra
- [x] **_check_victim_attacks() expandido** — Verifica HG global + jogadores, todas as presas com auto-ataque
- [x] **_check_end_of_turn_effects()** — Efeitos de fim de turno (Mage removal)
- [x] **_check_lunar_phase_effects()** — Efeitos de Fase Lunar (Unlucky Lune)
- [x] **registrar_kill_vitima()** — Tracking de kills para Vigilante
- [x] **15 novos testes** — TestPreyTriggerSystem com cobertura completa
- [x] **291 testes passando** — 276 anteriores + 15 novos

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

## 🔄 Pendente (Eventos / Events)

- [x] **Event cards são jogados pelo bot** — Step 4.5 em `_agir_recurso()`, prioridade alta
- [x] **Events permanecem em jogo** — `aplicar_carta()` coloca em PACK_HOME (nao descarta)
- [x] **Events cruzam Gauntlet** — Já implementado via `zona_da_carta()`
- [x] **31 Event cards com modelo JSON** — Efeitos implementados (comprar, modificar_atributo, destruir, etc.)
- [x] **62/142 Event cards usados em decks** — Cobertura alta
- [ ] **"Playing Event is not an action"** — Eventos nao sao impedidos por restricoes de acao
- [x] **Lunar Phases restritos ao Redraw** — Bot joga na Redraw phase, validado por `validar_lunar_phase()`
- [x] **Lunar Phase substitui anterior** — `definir_lunar_phase()` descarta a anterior
- [x] **Lunar Eclipse bloqueia novas fases** — Remove fase atual e impede novas
- [x] **Display no CLI STATUS** — Mostra fase lunar ativa
- [x] **Pack Totems com keyword requirement** — `validar_totem_evento()` checa `requires` contra keywords dos personagens
- [x] **Limite de 1 Pack Totem por pack** — Personal Totems nao contam
- [x] **Integracao bot** — `_pode_pagar_custos()` valida Totems antes de jogar
- [x] **Integracao CLI** — `do_PLAY()` valida Totems
- [x] **Cannot be discarded voluntarily** — `carta_eh_evento_permanente()` + `impedir_descarte_voluntario()`
- [x] **Bot nao descarta Events/Totems** — Redraw phase protege cartas permanentes
- [ ] **Personal Totems** — Personagens com Personal Totem perdem bonus do Pack Totem

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

## 🔄 Pendente (Battlefields)

- [x] **Card type Battlefield reconhecido** — CARD_TYPES, zona_da_carta() para HG
- [x] **Vai para Hunting Grounds** —_play_card() em `priority_bot.py`
- [x] **Pode ser atacado como alpha action** — TIPOS_HG, start_combat()
- [x] **Auto-define block** — _eh_prey_no_hg() trata como presa
- [x] **Cannot be discarded voluntarily** — Protegido como Event
- [ ] **Engaging Renown limit** — Cada Battlefield limita renown dos combatentes
- [ ] **Defesa por outro alpha** — Qualquer alpha pode defender
- [ ] **Self-defending** — Battlefield tem stats proprios (Rage/Gnosis/Health)
- [ ] **Regras especiais por carta** — "Draw N cards", "No weapons", "1/2 Rage", "Umbral"
- [ ] **VP na derrota** — Battlefield derrotado vai pro Victory Pile
- [ ] **Unique restriction** — "Only 1 per game" em varios Battlefields
- [ ] **19/20 sem JSON model** — Apenas #1258 Grrash Tak'Hyrrr tem modelo
- [ ] **Apenas 1 Battlefield em decks** — Baixissimo impacto (1 em 20)

## 🔄 Pendente (Territories / Realms)

- [x] **Card type Territory/Realm reconhecido** — CARD_TYPES, zona_da_carta() para pack_home
- [x] **Vai para Pack Home** — Jogado na Resource phase
- [x] **Bot joga Territories** — Step 3 em `_agir_recurso()` e `_try_develop_board()`
- [x] **Keyword requirement** — `pode_jogar_territory()` valida `requires` contra personagens
- [x] **Realm Umbra requirement** — Precisa ter personagem na Umbra
- [x] **Limite 1 Realm por pack** — Validado em `pode_jogar_territory()`
- [x] **8/72 Territory cards com JSON model** — Todos os usados em decks
- [x] **Attack/destroy mechanic** — Alpha pode atacar Territory do oponente; se alpha defensor morre, Territory destruido
- [x] **Territory substituido por alpha defensor** — `start_combat()` troca defensor Territory pelo alpha do dono
- [ ] **Realms so podem ser atacados da Umbra** — Regra de targeting
- [ ] **Territory special abilities via JSON** — 64/72 sem modelo (baixo impacto)
- [ ] **"Using Territory ability is not an action"** — Pode ser usado a qualquer momento

## ✅ Combat Events

- [x] Card type reconhecido — CARD_TYPES, TIPOS_NAO_RECURSO, zona_da_carta()
- [x] 15 em decks, 15 com JSON models — 100% cobertura
- [x] Descartados apos uso — DISCARD_COMBAT em `aplicar_carta()`
- [x] Bot joga em combate — `_agir_combate()` step 2 via `_usar_carta_efeito()`
- [x] Keyword requirements — `_pode_pagar_custos()` valida `requires` (Ahroun, Firearm, etc.)
- [x] `_play_card()` fallback manda para DISCARD_COMBAT em vez de PACK_HOME
- [ ] Timing restrictions: "Play between rounds" — Complexo, baixo impacto (2 cards)
- [ ] Frenzy keyword mechanics — Frenzy cards tem regras especificas de berserk

## 🧪 Testes

- [x] **291 testes passando** — Endpoints, state, combat, bot, CLI, API, effects, anunciador, gauntlet, flip Crinos
- [ ] **Testes para Caern special abilities** — Verificar cada Caern implementado
- [ ] **Testes para Gift Rage FOO Rule** — Validação de requisitos
- [ ] **Testes para Ally recruitment** — `pode_recrutar_ally()` com diversos padrões
- [ ] **Testes para Quests** — `_check_quests()`, Past Life penalties, Unique enforcement

## 🔄 Pendente (Regras de Combate — Capítulo 6) — Análise Completa

### Status Geral

O sistema atual implementa um fluxo simplificado (`select_alpha → declare → reveal → resolve → end`) que resolve 1 rodada de combate sem pack actions, bluff, ou re-rodadas. O capítulo 6 (520 linhas) descreve um sistema muito mais completo.

**Cobertura estimada**: ~35% do Capítulo 6 implementado.

---

### 🏗️ 1. REFATORAR MÁQUINA DE STEPS (ALTA PRIORIDADE)

**Atual:** `select_alpha → declare → reveal → resolve → end` (5 steps)

**Regras (6.1, 6.2):**
```
Declaration Step       → Declarar ataque (Closed Play)
Pre-Combat Step        → Pack actions, redirect, cancel (Closed Play)
Beginning-of-Combat    → Open Play (gifts, frenzy pre-combate)
─── Rounds ───
  Play Card Step        → Jogar combat card face-down
  Targeting Step        → Atribuir alvos
  Reveal Step           → Revelar cartas, feinting, instinctive
  Bluff Step            → Verificar requisitos, descartar ilegais
  Resolution Step       → Fast → Normal → Slow, aplicar dano
  Withdrawal Step       → Atacante pode retirar
  Between-rounds Step   → Open Play (repetir rounds)
```

- [ ] **Fase extra: Declaration Step** — Declarar atacante + alvo; atacante (Hunting Party) e defensor (Shieldmate) jogam cards
- [ ] **Fase extra: Pre-Combat Step** — Pack actions, redirect attack, stepping in for Prey, defending Battlefield, combat cancelling
- [ ] **Fase extra: Beginning-of-Combat Step** — Open Play (gifts pre-combate, frenzy)
- [ ] **Rounds: Play Card Step** — Cada criatura joga uma combat card face-down; weapons declarados
- [ ] **Rounds: Targeting Step** — Alvos atribuídos às combat cards (devem mesmo mundo/Gauntlet)
- [ ] **Rounds: Bluff Step (Establish-Bluff)** — Verificar requisitos não-Rage; descartar ilegais; verificar bluff
- [ ] **Rounds: Withdrawal Step** — Atacante pode retirar (fim do combate)
- [ ] **Rounds: Between-rounds Step** — Open Play entre rodadas
- [ ] **Múltiplas rodadas** — Repetir Play Card → Between-rounds até condição de fim
- [ ] **Condições de fim (6.3)**: sem combat action, sem atacantes/defensores, atacante retirou, card forçou fim
- [ ] **Sem alvo válido por 1 round = removido** (6.3 último bullet)

### 🎴 2. COMBAT HAND / COMBAT DECK (ALTA PRIORIDADE)

**Atual:** Mão principal usada para Combat Actions. **Regras:** Combat Deck separado com Combat Hand.

- [ ] **Criar CombatDeck** — Deck separado com Combat Cards (Actions + Events)
- [ ] **Criar CombatHand** — Mão separada; tamanho baseado em Renome do alpha + participantes
- [ ] **Refill pós-combate** (6.3) — Reabastecer combat hand após cada combate
- [ ] **Embaralhar discard ao acabar** — Se combat deck acabar, reshuffle descartadas
- [ ] **Bot jogar da combat hand** — Bot precisa selecionar da combat hand, não da mão principal
- [ ] **Combat Events ficam em jogo** — (sidebar) Permanecem em jogo até efeito acabar

### 👊 3. COMBAT ACTIONS COM DANO PRÓPRIO (MÉDIA PRIORIDADE)

**Atual:** Dano = Rage do atacante (hardcoded em `resolve_combat`)

**Regras:** Combat Actions têm seu próprio valor de dano. A Rage do personagem é o **requirement**, não o dano.

- [ ] **Modelo JSON de Combat Action** — Cada CA precisa de: `damage`, `rage_requirement`, `speed` (fast/normal/slow), `keywords`
- [ ] **Resolver dano pelo card** — `resolve_combat()` usa damage do card, não `origem.rage`
- [ ] **Bluff check** — Se Rage do personagem < rage_requirement do card, é bluff (pode falhar)

### ⚡ 4. VELOCIDADES DE RESOLUÇÃO (MÉDIA PRIORIDADE)

**Atual:** Todas as ações resolvem simultaneamente

**Regras (6.10.1):** Fast Striking → Normal → Slow Striking

- [ ] **Fast Striking resolve primeiro** — Antes de ações normais
- [ ] **Slow Striking resolve depois** — Depois de ações normais
- [ ] **Criatura removida descarta ações não resolvidas** — Se morreu em Fast, não resolve Normal
- [ ] **Fast não pode ser dodged por Slow** — Fancy Footwork sem Spirit of the Fray falha
- [ ] **Múltiplos cards na mesma velocidade** — Oponente decide ordem do dano

### 📦 5. PACK COMBAT (MÉDIA PRIORIDADE)

**Atual:** 1v1 apenas. **Regras (6.5.8, 6.6.2):** Múltiplas criaturas por lado.

- [ ] **Estrutura PackAction/PackDefence** — Lista de criaturas atacando/defendendo juntas
- [ ] **Pack attack cards** — Hunting Party, Cub's Cry, Attacking the Wyrm, Ass Whuppin' Lynch Mob
- [ ] **Auto-pack creatures** — Dreams-of-Wonder (pack com Spirit Allies), etc.
- [ ] **Pack actions no Pre-Combat Step** — Anunciar pack actions
- [ ] **Draw adicional para pack** — Cada participante pode desenhar cards extras
- [ ] **Alpha pode recusar pack attack** — Para tomar alpha action diferente
- [ ] **Pack defence no HG** — Funciona igual (6.5.8)
- [ ] **Não pode pack attack com criatura de outro pack** — Exceto se card permite

### 🎯 6. TARGETING STEP (MÉDIA PRIORIDADE)

**Atual:** Alvo definido na declaração. **Regras (6.7):** Alvos declarados APÓS cartas face-down.

- [ ] **Alvos declarados após Play Card** — Primeiro jogam face-down, depois declaram alvos
- [ ] **Pack targeting alternado** — Atacante escolhe, depois defensor, repete
- [ ] **Dodge/Block não têm alvo** — Declarados sem alvo específico
- [ ] **Alvo no mesmo mundo** — Gauntlet check ao atribuir alvo

### 🃏 7. BLUFF E CARTAS ILEGAIS (MÉDIA PRIORIDADE)

**Regras (6.9):**

- [ ] **Illegal cards (6.9.1)** — Cartas sem requisitos não-Rage são descartadas no Bluff Step:
  - Gnosis requirements
  - Form restrictions ("crinos form only")
  - Keyword requirements
  - Combat Events face-down são ilegais
  - Restricted Play violations
- [ ] **Bluff (6.9.2)** — Jogar CA com Rage requirement maior que a Rage do personagem
  - **Succeed**: alvo também bluffou OU alvo não jogou carta legal
  - **Fail**: carta descartada
  - **Sem alvo**: succeed se ninguém targetou com non-bluffed card
- [ ] **Descartar ilegais ANTES de verificar bluff** — Ordem correta: 6.9.1 → 6.9.2
- [ ] **Legalidade é definitiva após Bluff Step** — Nada muda depois

### 🛡️ 8. FEINTING, INSTINCTIVE, ALTERNATIVE (MÉDIA PRIORIDADE)

**Regras (6.8):** Mini-step no fim do Reveal Step

**Ordem:** 1. Feinting → 2. Alternative → 3. Instinctive → 4. Escolher alvos

- [ ] **Feinting (6.8.1)** — Jogar card após ver oponente (parcial: só no reveal)
  - Pode jogar MÚLTIPLOS cards se tiver habilidades
  - Cards face-up (não pode feintar de novo)
  - Não OBRIGADO a jogar (diferente de Forced Play)
- [ ] **Instinctive (6.8.2)** — Se "stymied" (impedido de jogar)
  - Só se foi impedido, não se voluntariamente não jogou
  - Só se é alvo de um card
  - Alternative CAs são Instinctive (6.6.5)
- [ ] **Alternative Combat Actions (6.6.5)** — Sept cards jogadas como CA
  - Wasp Talons, Wanchese's Bow, etc.
  - Jogadas no fim do Reveal Step
  - Consideradas Instinctive; podem ser dodged/distracted
  - Bluff não funciona contra quem usa Alternative

### 🏃 9. CHALLENGE, STEP IN, ESCAPE (BAIXA PRIORIDADE)

- [ ] **Challenge (6.5.2)** — Alpha desafia não-Alpha; alvo pode recusar
  - Recusado = alpha action acaba sem combate
  - Só contra Characters (não Territory/Battlefield)
- [ ] **Stepping in (6.5.9)** — Alpha substitui Presa quando atacada
  - Gaia alpha step in for Victim; Wyrm alpha step in for Enemy
  - Maior Renome decide (sorteio se empate)
- [ ] **Escape** — Criatura sai do combate (Dodge como escape, Flee)
- [ ] **Nerve Agent** — Sai mas retorna (não é escape)
- [ ] **Escape não afeta outros** — Só a criatura escapa

### 🔄 10. COMBAT EVENTS COMO FACE-DOWN (BAIXA PRIORIDADE)

**Atual:** Combat Events são jogados como efeitos (anunciador). **Regras:** Podem ser face-down no Play Card Step.

- [ ] **CE jogáveis face-down** — No Play Card Step
- [ ] **CE face-down revelados = ilegais** — Descartados no Bluff Step
- [ ] **CE timing específico** — Alguns em momentos específicos

### 🔥 11. FRENZY (BAIXA PRIORIDADE — MUITO TRABALHO)

**Regras (6.11):**

- [ ] **Full Frenzy (6.11.3)**:
  - Flipa para Crinos
  - Draw cards = Rage em Crinos
  - Forced Play: deve jogar tudo
  - Attacker não pode withdraw
  - "Hacked apart" se dano >= Health + Rage (calculado no início)
  - Morre mas continua lutando até fim do combate/frenzy
- [ ] **Limited Frenzy** — Controle parcial
- [ ] **Fox Frenzy** — Foge do combate
- [ ] **Allies/Prey não frenzam** — Exceto se card especifica
- [ ] **Não double-frenzy** — Só um frenzy por vez
- [ ] **Frenzied não joga Gifts** — Pré-frenzy continuam
- [ ] **Ending frenzy (6.11.2)** — Cancelado, fim combate, sem actions
  - Descartar X cards aleatórios = cards draw para frenzy

### 🎲 12. RESTRICTED / FORCED / RANDOM PLAY (BAIXA PRIORIDADE)

**Regras (6.6.6):**

- [ ] **Restricted Play (6.6.6a)** — Só pode jogar CAs com certa restrição (e.g. Catfeet: Rage 1)
  - Não obriga a jogar; mas se jogar, deve atender
  - Sem cards legais ≠ impedido
- [ ] **Forced Play (6.6.6b)** — Obrigado a jogar se tiver cards
  - Não pode Alternative CAs
  - Pack: selecionar non-forced primeiro
  - Múltiplos effects: card deve atender TODOS
- [ ] **Random Play (6.6.6c)** — Card aleatório da combat hand
  - Alvo escolhido normalmente
  - Pode ser ilegal
  - Prey random: decidir aleatoriamente quem joga

### 🎯 13. MECÂNICAS ADICIONAIS (BAIXA PRIORIDADE)

- [ ] **Redirect (6.10.3)** — Redirecionar dano (depois dodge/block, antes outros effects)
  - Pode ser redirecionado múltiplas vezes
  - Novo alvo não estava em combate: original removido
- [ ] **Parting shots (6.10.4)** — Criatura que sai ainda leva dano na mesma velocidade
- [ ] **Forced Attacks (6.5.6)** — Força ataque contra alvo específico
  - Alpha pode passar em vez de forced attack
  - Alvo inválido = não forced
- [ ] **Attack Restrictions (6.5.7)** — Loyalty, etc.
  - Não pode atacar alvo específico
  - Não pode pack attack voluntário
- [ ] **Withdrawing (6.3.1)** — Atacante rompe combate no Withdrawal Step
  - Não é action
  - Maim impede withdraw
  - Frenzied não pode withdraw
- [ ] **Umbra-only CAs (6.6.4)** — Criatura E alvo na Umbra

### 📋 14. COMBAT DECLARATION OPTIONS

- [ ] **Territory attack (6.5.4)** — Alpha ataca Territory; alpha defensor defende
  - Defensor morto = Territory destruído
  - Attacker withdraw = Territory intacto
  - Existe em ambos mundos (Gauntlet check)
- [ ] **Battlefield attack (6.5.3)** — Alpha action; defendido por alpha ou self-defend
  - Self-defend: R/G/H = Renown, keywords do Defending Alpha + 1
  - Spirit keyword = ambos lados Gauntlet
  - Defeat = VP = Renown; Sweep = VP = Renown
- [ ] **Attacking to bind (6.5.5)** — Atacante na Umbra bind Spirit no HG
  - "Kill" = cura dano, vira Ally
  - Bound Spirit = 1/2 Renown VP
  - Wyrm bind Enemies, Gaia bind Victims
- [ ] **Multiple CAs (6.6.1)** — Criatura pode jogar múltiplos cards/round
  - Considerados separados
  - Podem mirar oponentes diferentes
  - Controlador decide ordem do dano

### 🎲 15. DAMAGE SYSTEM REWORK (MÉDIA PRIORIDADE)

**Atual:** Dano = inteiro (Rage do atacante). **Regras:** Damage cards são cards físicos.

- [ ] **Damage cards físicos** — Cada CA virada vira damage card
- [ ] **Aggravated damage (6.4.1)** — Marcado; não regenera
- [ ] **Healing** — Cura damage card de menor valor; efeitos do card terminam
- [ ] **Damage card effects** — Head Wound, Maim = efeitos do damage card, não do CA
- [ ] **Death blow tracking** — Quem deu o dano fatal = killer; apenas 1 killer (6.4.3)
- [ ] **VP complications (6.4.3)**:
  - Wyrm: 0 VP por Enemy; Gaia: 0 VP por Victim
  - Exceto se Presa iniciou ataque
  - Bonus VP AFTER VP base
  - 0 VP ainda vai pro VP (como 0)
- [ ] **Death outside combat (6.4.4)** — Character = removido; Non-character = discard

### 📊 Progresso Atualizado

- **291 testes passando**
- **~35% do Capítulo 6 implementado** (vs ~85% estimado anteriormente)
- **~70% das regras de Gauntlet implementadas**
- **~60% das regras de Moot/Juntas implementadas**
- **~50% das regras de Territories/Realms implementadas**

### Prioridade de Implementação

1. 🏗️ **Refatorar máquina de steps** — Fundação para todo o resto
2. 🎴 **Combat Hand/Deck** — Necessário para jogar combat cards adequadamente
3. 👊 **Combat Actions com dano próprio** — Muda completamente como dano é calculado
4. ⚡ **Velocidades de resolução** — Fast/Normal/Slow
5. 📦 **Pack Combat** — Múltiplas criaturas
6. 🎯 **Targeting Step** — Alvos após face-down
7. 🃏 **Bluff/Illegal** — Coração do sistema de combate
8. 🛡️ **Feinting/Instinctive/Alternative** — Complementos do Reveal Step
9. 🏃 **Challenge/Step In/Escape** — Ações de combate
10. 🔥 **Frenzy** — Complexo, requer base sólida
11. 🎲 **Restrict/Forced/Random Play** — Detalhes finos
12. 🎯 **Combat Declaration Options** — Battlefield, Territory, Bind
