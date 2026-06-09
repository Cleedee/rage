# Guia de Seleção de Presas (Victim / Enemy)

## Propósito

Este documento registra o conhecimento adquirido sobre como escolher
cartas de **Victim** e **Enemy** (coletivamente "presas") ao construir
decks para o Rage CCG. Serve como referência para o assistente de IA
e para humanos que usarem o `./scripts/gerar_checklist.py`.

---

## 1. Regra Básica: VP por Alinhamento

| Pack é... | Mata Victim | Mata Enemy |
|-----------|:-----------:|:----------:|
| **Gaia**  | 0 VP        | VP cheio   |
| **Wyrm**  | VP cheio    | 0 VP       |
| **Rogue** | ?           | ?          |

**Código relevante** (`combat_queue.py`):
```python
eh_gaia = _eh_pack_gaia(dono_origem)   # qualquer char com "Gaia" no tipo
eh_wyrm = _eh_pack_wyrm(dono_origem)    # qualquer char com "Wyrm" no tipo
if eh_gaia and 'victim' in ct_alvo: vp = 0
elif eh_wyrm and 'enemy' in ct_alvo: vp = 0
```

**Detecção de alinhamento:** 
- `_eh_pack_gaia()`: True se qualquer personagem do pack tem `"Gaia"` no `card.tipo`
- `_eh_pack_wyrm()`: True se qualquer personagem do pack tem `"Wyrm"` no `card.tipo`
- Um pack **misto** (Gaia + Wyrm) pode ter ambos True

---

## 2. Dilema: VP vs Habilidade Especial

Às vezes vale a pena sacrificar VP por uma habilidade especial.

### Decisão: Quando usar presa "errada"

| Situação | Exemplo real | Trocou VP por... |
|----------|-------------|------------------|
| **Acesso a Gifts** — presa pode usar Gifts que seus chars não têm | `Mage of the Celestial Chorus` em D605 (Wyrm) | **Qualquer Gift** — flexibilidade máxima |
| **Ally em potencial** — presa pode virar Ally | `Bitter Hatar` em D484 (Gaia) | **Ally Ananasi** — 1 criatura extra |
| **Efeito Umbra** — presa só existe na Umbra | `Dream Hunter` / `Elethoi` em D160 (Gaia) | **Presença Umbral** — deck Umbra-focused |
| **Negação de área** — presa bloqueia mecânica | `Pentex Refinery` em D705 (Gaia) | **Sem regeneração** pra oponente |
| **Combate forçado** — prende oponente | `Ootani Oil Bane` em D484 (Gaia) | **Sem retirada** do combate |
| **Remoção de carta** — limpa algo do jogo | `Glade Child` em D605 (Wyrm) | **Remove Mass Pollution** |

### Heurística de decisão

```
SE a presa tem habilidade especial:
    SE habilidade é CRÍTICA pra estratégia do deck:
        -> Use a presa (mesmo que VP = 0)
    SENÃO:
        -> Use presa alinhada (VP cheio)
SENÃO (presa simples, sem texto relevante):
    -> Use presa alinhada (VP cheio)
```

### Checklist para avaliar presas especiais

- [ ] **Presa usa Gift?** Qualquer Gift? Gifts de tribo específica?
- [ ] **Presa vira Ally?** Sob quais condições?
- [ ] **Presa existe na Umbra?** É imune a ataques normais?
- [ ] **Presa prende oponente?** Impede retirada/regeneração?
- [ ] **Presa remove cartas?** Mass Pollution, Caerns, etc.?
- [ ] **Presa ataca automaticamente?** Quem? Com que frequência?
- [ ] **Presa nega mecânica?** Regeneração, equipamentos, gifts?

---

## 3. Catálogo de Presas por Utilidade

### Presas comuns (sem habilidade especial → usar alinhamento correto)

| ID | Nome | Tipo | Health | Renown | Uso |
|----|------|:----:|:------:|:------:|-----|
| 535 | Renegade Werewolf Hunter | Victim | 7 | 4 | VP puro (Wyrm) |
| 565 | Vigilante | Victim | 5 | 3 | VP puro (Wyrm) |
| 568 | Wild Animals | Victim | 4 | 3 | VP puro (Wyrm) |
| 485 | Fomori Cop | Enemy | 4 | 5 | VP puro (Gaia) |
| 496 | Hogling | Enemy | 5 | 5 | VP puro (Gaia) |
| 479 | Excitable Good Ol' Boy | Enemy | 3 | 5 | VP puro (Gaia) |

### Presas com habilidade especial (podem valer o VP perdido)

| ID | Nome | Tipo | Habilidade | Vale pra... |
|----|------|:----:|------------|-------------|
| 503 | Mage of the Celestial Chorus | Victim | **Usa qualquer Gift** | Qualquer pack que queira acesso a gifts variados |
| 451 | Angus | Victim | Usa Gifts Galliard/Homid/Wendigo → vira Ally 3 turnos | Gaia packs que precisam de aliados |
| 569 | Wyldkin Kami | Victim | Usa Gifts de raça/auspício + 2 Combat Actions/round | Gaia packs combativos |
| 1335 | Bitter Hatar | Enemy | **Pode ser jogado como Ally** | Gaia packs com Ananasi |
| 1337 | Ootani Oil Bane | Enemy | Oponente não pode retirar do combate | Gaia packs agressivos |
| 573 | Dream Hunter | Enemy | Só existe na Umbra, usa Gifts Mokole/Get | Decks Umbra-focused |
| 1341 | Elethoi | Enemy | Só afetado por Gifts/Umbra, usa Combat Actions Umbrais | Decks Umbra-focused |
| 520 | Pentex Refinery | Enemy | **Previne regeneração** +2 Gauntlet | Gaia packs de negação |
| 517 | Pentex First Team 43 | Enemy | 2 Combat Actions/round | Gaia packs combativos |
| 488 | Glade Child | Victim | **Remove todos Mass Pollution** | Wyrm packs que sofrem com Mass Pollution |
| 1336 | Big Game Hunter | Enemy | Limita Combat Actions de Rage 6+ | Gaia packs defensivos |
| 1344 | Endron Security Team | Enemy | Protege outros Pentex | Gaia packs com múltiplos Pentex |
| 546 | Street Bum | Victim | **Contra-ataca 1 Mass Pollution** | Wyrm packs vs Mass Pollution |
| 547 | Suburban High School Kid | Victim | Pack defend com High School Athletes | Wyrm packs temáticos |
| 491 | Greenpeace Assault Team | Victim | Destrói 1 Caern Wyrm/fase | Wyrm packs que querem negar Caerns inimigos |

---

## 4. Exemplos de Decks Reais

### D605 — "Wyrm Deadzone" (Wyrm, usa Victims)

**Por que Victims em deck Wyrm?** Porque as habilidades especiais
valem mais que os VP perdidos:

| Carta | VP perdido | Habilidade ganha |
|-------|:----------:|------------------|
| Mage of the Celestial Chorus | 0 VP (Wyrm vs Victim) | **Qualquer Gift** do jogo |
| Angus | 0 VP | Gifts Galliard + vira Ally |
| Wyldkin Kami | 0 VP | Gifts + 2 ações/round |
| Glade Child | 0 VP | Remove Mass Pollution |

**Lições:** Se um deck Wyrm quer acesso a Gifts que seus personagens
não teriam (ex: Gifts de Gaia), usar Victims que concedem isso é
uma troca válida.

### D484 — "Ajaba Aggression" (Gaia, usa Enemies)

| Carta | VP perdido | Habilidade ganha |
|-------|:----------:|------------------|
| Bitter Hatar | 0 VP (Gaia vs Enemy) | **Ally Ananasi** em potencial |
| Ootani Oil Bane | 0 VP | Prende oponente no combate |

**Lições:** Enemy que pode virar Ally é como ganhar um personagem
extra — extremamente valioso.

---

## 5. Integração com o Script de Checklist

O script `scripts/gerar_checklist.py` deve:

1. Identificar o alinhamento do pack (Gaia/Wyrm/Misto)
2. Listar todas as presas no deck
3. Para cada presa:
   - Se alinhamento **correto** → VP cheio ✅
   - Se alinhamento **errado** → verificar se tem habilidade especial
   - Se tem habilidade especial → marcar como "troca válida?"
   - Se não tem habilidade especial → **ALERTA:** VP desperdiçado
4. Sugerir substituições (ex: Victim simples → Enemy simples para Gaia)

### Exemplo de saída:
```
=== Deck XYZ ===
Alinhamento: Gaia
Personagens: Big Fisher (Gaia), Margrave (Gaia)

Presas:
  #535 Renegade Werewolf Hunter  Victim x3  ⚠️ Gaia + Victim = 0 VP!
     Sem habilidade especial relevante
     Sugestão: substituir por Enemy (ex: #485 Fomori Cop)
  
  #503 Mage of the Celestial Chorus  Victim x1  🔄 Troca válida
     Habilidade: usa qualquer Gift (vale o VP perdido)
```

---

## 6. Regras para o Assistente de IA

Ao refinar decks no futuro, o assistente DEVE:

1. **Verificar alinhamento** de todos os personagens no deck
2. **Verificar VP** de cada presa baseado no alinhamento
3. **Ler o texto** de cada presa para identificar habilidades especiais
4. **Decidir** se a habilidade vale o VP perdido
5. **Documentar** a decisão na análise do deck

### Prioridade de substituição
```
1. Presa simples + alinhamento errado → substituir por alinhamento correto
2. Presa especial + alinhamento errado → manter (se habilidade > VP)
3. Presa especial + alinhamento correto → manter (melhor dos dois mundos)
```
