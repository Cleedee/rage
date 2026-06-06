# Como Analisar e Montar Decks — Ferramentas Disponíveis

## 1. 📚 Regras do Jogo (`docs/game-rules/`)

Documentação completa do Rage CCG em português:

| Arquivo | Conteúdo |
|---|---|
| `00-indice.md` | Índice geral |
| `01-introducao.md` | Conceitos básicos |
| `02-jogo-basico.md` | Setup, turnos, zonas |
| `03-tipos-de-carta.md` | Personagens, Gift, Combat, Equipamento, etc. |
| `04-cartas-em-detalhe.md` | Atributos (Rage, Gnosis, Health, Renome) |
| `05-atributos-e-poderes.md` | Como funcionam os atributos |
| `06-combate.md` | Ciclo de combate completo |
| `07-umbra.md` | Regras de Umbra/Gauntlet |
| `08-moots.md` | Regras de Juntas/Votação |
| `09-deckbuilding.md` | Regras de construção de deck |
| `10-vencendo.md` | Condições de vitória |
| `11-personagens.md` | Personagens detalhados |
| `12-aliados.md` | Aliados |
| `13-equipamentos.md` | Equipamentos |
| `14-gifts.md` | Gifts (dons) |
| `15-acoes-e-eventos.md` | Ações e Eventos |
| `16-territorios.md` | Territórios |
| `17-caerns.md` | Caerns |
| `18-combate-avancado.md` | Regras avançadas de combate |
| `19-modos-de-jogo.md` | Modos alternativos |

Exemplo de regra que uso constantemente: uma Combat Action com `damage=3`
(custo de Rage 3) precisa de um personagem com Rage ≥ 3 para ser paga.
O validator checa isso automaticamente.

---

## 2. 🗄️ Banco SQLite (1800+ cartas)

Cada carta no banco tem:

```python
Card {
    id, name, expansion, tipo,              # Identificação
    rage, gnosis, health, renown,           # Atributos
    rage_morph, gnosis_morph, health_morph, # Forma alternativa
    requires, keyword,                      # Requisitos e keywords
    damage,                                 # Custo de Rage (Combat Actions)
    text, errata,                           # Texto da carta
}
```

Consigo consultar qualquer carta por tipo, keyword, atributo, nome. Exemplo:

```sql
-- Todas as Combat Actions com custo ≤ 3 que o deck pode usar
SELECT * FROM card 
WHERE tipo = 'Combat Action' 
  AND CAST(damage AS INTEGER) <= 3
  AND requires = ''
ORDER BY damage;
```

---

## 3. ✅ Deck Validator (`helpers/deck_validator.py`)


Faz duas análises completas:

### Legalidade (regras obrigatórias)
- Total de combate ≥ 20
- Total de septo ≥ 30
- Máx 2 cópias em combate, máx 3 em septo
- Personagens: 1 cópia cada (exceto Multiple, até 5)
- Renome total ≤ cap do deck
- Alcunha uniforme (só Gaia, só Wyrm, ou Rogue com não-Rogue)

### Viabilidade (cada carta é jogável?)
- Combat: custo (damage) precisa de personagem com Rage ≥ custo
- Gift: personagem precisa ter keyword que match + Gnosis ≥ custo
- Território/Evento/Aliado: personagem precisa atender `requires`
- Caern: precisa de personagem que atenda keywords
- Pack Totem: precisa atender requisitos

---

## 4. 🎮 Motor de Jogo Completo

```
match.py          → Simulador de partidas (bot vs bot)
    ├── seed determinística (mesma seed = mesmo resultado)
    ├── dificuldade do bot (easy/medium/hard)
    └── suporte a N jogadores

bot/
    ├── evaluator.py → BoardEvaluator (0-10: threat, advantage, pressure, victory)
    └── priority_bot.py → Árvore de decisão por fases

state.py          → GameState completo (turno, fases, zonas, pools)
combat_queue.py   → Ciclo de combate (declarar→revelar→resolver)
effects.py        → 12 resolvedores de efeitos + 278 modelos de carta JSON
anunciador.py     → Sistema anúncio→resposta→resolução
```

O match me diz: execução real do deck contra oponentes reais. Cada partida
mostra VP acumulados, quanto o deck comprou, quantas cartas jogou do septo.
Consigo ver padrões: deck explode cedo? Morre devagar? Nunca sai do lugar?

---

## 5. 📦 Modelos JSON de Efeitos (`data/cards/`)

278 cartas com efeitos estruturados que o bot consegue executar:

```json
{
  "id": "card_1095",
  "nome": "Sense of the Prey",
  "tipo": "Gift",
  "modos": [{
    "descricao": "Sentir a Presa",
    "efeitos": [{"tipo": "ataque_imediato", "condicao_alvo": "?"}]
  }]
}
```

Tipos de efeito implementados: `dano`, `curar`, `destruir`, `descartar`,
`comprar`, `tapar`, `fugir`, `anular`, `modificar_atributo`,
`redirecionar`, `restringir`, `impedir_retirada`, `olhar_topo_deck`,
`ganhar_vp`, `ataque_imediato`, etc.

**Se uma carta NÃO tem JSON, o bot a joga sem aplicar efeitos** — é uma
carta "vanilla" que só existe no campo.

---

## 6. 📊 Deck Database (600+ decks)

Deck IDs conhecidos: 7, 90, 160, 416, 465, 484, 524, 537, 563, 564, 605,
612, 613, 619, 629, 642, 643.

Cada deck tem nome, cap de renome, e lista de cartas com quantidades.

---

## 🔍 Como uso tudo junto para ANALISAR um deck

1. **Valido legalidade** — deck é construível?
2. **Valido viabilidade** — todas as cartas podem ser jogadas?
3. **Verifico quais cartas têm JSON** — o bot vai usar efeitos ou ignorá-los?
4. **Cruzo requisitos com personagens** — se um Gift requer "Ahroun" e só
   Stalks é Ragabash, não funciona
5. **Analiso o combat pool** — tem damage dealers suficientes? Os custos
   cabem nos Rages disponíveis?
6. **Rodo o match contra oponentes conhecidos** — performance real
7. **Padrões no log da partida** — quanto VP por turno? Com quantas cartas
   ficou preso?
8. **Itero** — troco cartas, rodo de novo, comparo resultados

---

## 🏗️ Como uso para MONTAR um deck

1. **Defino tema/tribo** — ex: Silent Striders
2. **Busco personagens disponíveis** — `Card.query.filter(Card.keyword.like('%Silent%'))`
3. **Calculo renome** — escolho combinação que some ≤ cap
4. **Busco gifts jogáveis** — cruzo keywords dos personagens com requires
   dos gifts
5. **Busco combat cards** — com custo ≤ Rage máximo do pack
6. **Busco territórios/aliados** — que os personagens podem usar
7. **Preencho septo** — com eventos, ações, equipamentos jogáveis
8. **Verifico se cartas escolhidas têm JSON** — se não, o bot ignora os
   efeitos
9. **Valido** → `validate_deck(id)`
10. **Testo** → `match --deck X --deck Y --seed N`
11. **Itero** — baseado nos resultados

---

## ⚠️ Limitações Atuais

1. **Modelos JSON incompletos** — ~278 de 1800 cartas têm efeitos
   estruturados
2. **Bot não entende sinergias textuais** — só executa efeitos JSON
3. **Sem Moots/Umbra implementados** — fases não-combate são simuladas
4. **Sem crafting de JSON automático** — preciso criar manualmente para
   cartas sem modelo
