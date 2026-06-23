# Melhorias para Análise LLM + Engine — Deck #2005

## 📋 Problemas Identificados na Análise LLM

### 1. Interpretação Errada da Estratégia Central

**LLM diz:** "VP engine via Victims no HG"
**Humano diz:** "pack attack any target you think that Wailer can successfully flip on"

**Causa:** O LLM viu Victims no deck e assumiu que são para VP. Na realidade, Victims são **targets para Wailer flip**, não fontes de VP.

**Como prevenir:**
- Analisar o texto da carta Wailer antes de assumir estratégia
- Perguntar: "Qual é a habilidade central do deck?"
- Verificar se há cartas que interagem com a habilidade central

### 2. Superestimação de Infectious Touch

**LLM diz:** "Peça-chave do combo" (priority 85)
**Humano diz:** "rarely as useful as it seems it should be"

**Causa:** O LLM analisa a carta isoladamente (-1Rg/-1Gn é bom). O humano sabe que na prática é difícil de usar.

**Como prevenir:**
- Adicionar campo `practical_rating` (1-5) baseado em experiência humana
- Incluir notas como "rarely useful" no config
- Reduzir prioridade automaticamente para cartas com practical_rating baixo

### 3. Subestimação de Roar of the Wyrm

**LLM diz:** "Ferramenta de controle primária" (priority 80)
**Humano diz:** "backup option, but only Wailer can use it"

**Causa:** O LLM não entende que a carta tem restrição de uso (só Wailer).

**Como prevenir:**
- Adicionar campo `user_restriction` (quem pode usar)
- O bot deve verificar se o usuário está vivo antes de priorizar

### 4. Risco do Beast-of-War Ignorado

**LLM diz:** Não menciona risco
**Humano diz:** "careful with Beast-of-War that you don't undermine your Wailer"

**Causa:** O LLM não analisa interações negativas entre cartas.

**Como prevenir:**
- Adicionar seção `anti_synergies` no config
- O bot deve verificar interações antes de jogar cartas

### 5. Contagem Errada de Cartas

**LLM diz:** "18 cartas de combate"
**Realidade:** 21 cartas (17 CA + 4 CE)

**Causa:** O LLM confundiu CA com total de combat.

**Como prevenir:**
- Script de validação deve contar CA e CE separadamente
- Output deve mostrar: "X combat actions, Y combat events, Z total"

### 6. Papel do Shieldmate Não Entendido

**LLM diz:** Lista sem contexto
**Humano diz:** "shieldmate, so you can bring in Wailer whoever they attack"

**Causa:** O LLM não entende que Shieldmate permite que Wailer entre no combate.

**Como prevenir:**
- Adicionar campo `tactical_notes` para cada CE
- O bot deve entender: Shieldmate → Wailer entra → habilidade ativa

### 7. Beat Unmerciful para Fugas

**LLM diz:** "Anula Combat Action Rg:1"
**Humano diz:** "Beat Unmerciful, since Run Like Hell and Fox Frenzy may be the only two repeatable escapes"

**Causa:** O LLM não conecta Beat Unmerciful com cartas de fuga.

**Como prevenir:**
- Adicionar `counters` no config (Beat Unmerciful countera Run Like Hell)
- O bot deve usar Beat Unmerciful quando oponente tem cartas de fuga

### 8. Sneak Attack para Lynch Mob

**LLM diz:** "Ataque surpresa bypassando protocolo"
**Humano diz:** "Sneak Attacks, in this deck, might be best once you have an alpha so you can use Ass Whuppin' Lynch Mob"

**Causa:** O LLM não entende que Sneak Attack ativa Lynch Mob.

**Como prevenir:**
- Adicionar `combo_pairs` no config (Sneak Attack + Lynch Mob)
- O bot deve priorizar combo quando ambas as cartas estão na mão

---

## 🔧 Melhorias no Engine

### 1. Campo `practical_rating` (1-5)

```json
{
  "slug": "infectious-touch",
  "priority": 85,
  "practical_rating": 2,
  "desc": "Infectious Touch — -1Rg/-1Gn permanente. Raramente útil na prática."
}
```

**Implementação:**
- `StrategyEngine.sorted_gifts()` deve multiplicar prioridade por `practical_rating / 5`
- Ex: priority 85 × 2/5 = 34 (reduzido significativamente)

### 2. Campo `user_restriction`

```json
{
  "slug": "roar-of-the-wyrm",
  "priority": 80,
  "user_restriction": "wailer",
  "desc": "Roar of the Wyrm — só Wailer pode usar."
}
```

**Implementação:**
- `StrategyEngine.sorted_gifts()` deve verificar se o user está vivo
- Se user morto, reduzir prioridade em 100

### 3. Seção `anti_synergies`

```json
{
  "anti_synergies": [
    {
      "card": "beast-of-war",
      "conflicts_with": "wailer",
      "reason": "Beast-of-War -1 Gn pode undermine Wailer se oponente ganhar Gn > 3",
      "action": "check_before_play"
    }
  ]
}
```

**Implementação:**
- `PriorityBot._jogar_gift()` deve verificar anti-sinergias antes de jogar
- Se anti-sinergia detectada, reduzir prioridade ou pular

### 4. Campo `tactical_notes` para CE

```json
{
  "slug": "shieldmate",
  "priority": 88,
  "tactical_notes": "Permite que Wailer entre no combate como defensor. Ativa habilidade dele."
}
```

**Implementação:**
- `StrategyEngine.sorted_combat_events()` deve incluir tactical_notes
- Bot pode usar para decidir quando jogar

### 5. Seção `counters`

```json
{
  "counters": [
    {
      "card": "beat-unmerciful",
      "counters": ["run-like-hell", "fox-frenzy"],
      "desc": "Beat Unmerciful impede fugas Rg:1"
    }
  ]
}
```

**Implementação:**
- `PriorityBot._usar_beat_unmerciful()` deve verificar se oponente tem cartas counteradas
- Se sim, usar Beat Unmerciful; se não, guardar

### 6. Seção `combo_pairs`

```json
{
  "combo_pairs": [
    {
      "card1": "sneak-attack",
      "card2": "ass-whuppin-lynch-mob",
      "condition": "has_alpha",
      "desc": "Sneak Attack ativa Lynch Mob sem alpha"
    }
  ]
}
```

**Implementação:**
- `PriorityBot._agir_recurso()` deve verificar combo_pairs
- Se ambas as cartas na mão + condition ativa, priorizar ambas

### 7. Campo `deck_role`

```json
{
  "slug": "infectious-touch",
  "deck_role": "backup",
  "desc": "Raramente útil. Usar só se não houver better play."
}
```

**Implementação:**
- Bot deve ter hierarchy: core > important > backup > filler
- Backup cards só são jogadas se não houver core/important

### 8. Validação de Contagem

```python
# Script de validação
def validate_deck_counts(deck_id):
    """Conta CA, CE, total combat separadamente."""
    sept = count_sept_cards(deck_id)
    ca = count_combat_actions(deck_id)
    ce = count_combat_events(deck_id)
    total = sept + ca + ce
    
    print(f"Sept: {sept}")
    print(f"Combat Actions: {ca}")
    print(f"Combat Events: {ce}")
    print(f"Total Combat: {ca + ce}")
    print(f"Total Deck: {total}")
```

---

## 📊 Prioridade de Implementação

| Melhoria | Impacto | Esforço | Prioridade |
|---|---|---|---|
| `practical_rating` | Alto | Baixo | ⭐⭐⭐ |
| `user_restriction` | Médio | Baixo | ⭐⭐ |
| `anti_synergies` | Alto | Médio | ⭐⭐⭐ |
| `tactical_notes` | Médio | Baixo | ⭐⭐ |
| `counters` | Alto | Médio | ⭐⭐⭐ |
| `combo_pairs` | Alto | Médio | ⭐⭐⭐ |
| `deck_role` | Médio | Baixo | ⭐⭐ |
| Validação de contagem | Baixo | Baixo | ⭐ |

---

## 🎯 Resultado Esperado

Com essas melhorias, o bot deveria:

1. **Não priorizar Infectious Touch** (practical_rating = 2)
2. **Não jogar Roar of the Wyrm** se Wailer estiver morto (user_restriction)
3. **Verificar Beast-of-War** antes de jogar (anti_synergies)
4. **Usar Shieldmate** para trazer Wailer (tactical_notes)
5. **Usar Beat Unmerciful** quando oponente tem Run Like Hell (counters)
6. **Priorizar Sneak Attack + Lynch Mob** quando ambas na mão (combo_pairs)
7. **Não jogar cartas "backup"** se houver core/important disponível (deck_role)
