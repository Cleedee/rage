"""
Gerador automático de tags para cartas do Rage CCG.

Estratégia híbrida:
1. Tags baseadas em tipo + keywords (automático, 100% das cartas)
2. Tags baseadas em regex no texto (semi-automático, habilidades especiais)
3. Overrides manuais (YAML) para correções e ajustes finos

Uso:
    python3 scripts/gerar_tags.py           # Gera tags para todas as cartas
    python3 scripts/gerar_tags.py --dry-run # Preview sem salvar
    python3 scripts/gerar_tags.py --stats   # Estatísticas de cobertura
"""

import os
import re
import sqlite3
import sys
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# MAPEAMENTO: Tipo + Keywords → Tags automáticas
# ═══════════════════════════════════════════════════════════════

TIPO_PARA_TAGS = {
    "character":          ["character"],
    "character - gaia":   ["character", "gaia"],
    "character - wyrm":   ["character", "wyrm"],
    "character - rogue":  ["character", "rogue"],
    "equipment":          ["equipment"],
    "gift":               ["gift"],
    "combat action":      ["combat-card", "combat-action"],
    "combat event":       ["combat-card", "combat-event"],
    "event":              ["event"],
    "ally":               ["ally"],
    "ally - victim":      ["ally", "victim"],
    "ally - enemy":       ["ally", "enemy"],
    "ally - caern":       ["ally", "caern"],
    "enemy":              ["prey", "enemy"],
    "victim":             ["prey", "victim"],
    "battlefield":        ["battlefield"],
    "rite":               ["rite"],
    "quest":              ["quest"],
    "past life":          ["quest", "past-life"],
    "caern":              ["caern"],
    "territory":          ["territory"],
    "realm":              ["territory", "realm"],
    "moot":               ["moot"],
    "board meeting":      ["board-meeting"],
    "action":             ["action"],
}

# Keywords que geram tags extras
KEYWORD_PARA_TAGS = {
    # Tribos (Characters)
    "silver fangs":       "tribo-silver-fangs",
    "fenrir":             "tribo-fenrir",
    "shadow lords":       "tribo-shadow-lords",
    "children of gaia":   "tribo-children-of-gaia",
    "wendigo":            "tribo-wendigo",
    "fianna":             "tribo-fianna",
    "bone gnawer":        "tribo-bone-gnawer",
    "black fury":         "tribo-black-fury",
    "uktena":             "tribo-uktena",
    "silent striders":    "tribo-silent-striders",
    "glass walkers":      "tribo-glass-walkers",
    "stargazers":         "tribo-stargazers",
    "red talons":         "tribo-red-talons",
    "black spiral dancer": "tribo-bsd",
    "rogue":              "tribo-rogue",

    # Auspício
    "ahroun":             "auspice-ahroun",
    "galliard":           "auspice-galliard",
    "theurge":            "auspice-theurge",
    "ragabash":           "auspice-ragabash",
    "philodox":           "auspice-philodox",

    # Formas
    "homid":              "form-homid",
    "glaber":             "form-glaber",
    "crinos":             "form-crinos",
    "lupus":              "form-lupus",
    "metis":              "class-metis",
    "breed":              "class-breed",

    # Wyrm
    "black spiral dancer": "bsd",
    "defiler":            "wyrm-defiler",
    "eater-of-souls":     "wyrm-eater-of-souls",
    "pentex":             "wyrm-pentex",
    "bane":               "wyrm-bane",

    # Classes criaturas (regeneração)
    "garou":              "class-garou",
    "bastet":             "class-bastet",
    "fera":               "class-fera",
    "fomori":             "class-fomori",
    "vampire":            "class-vampire",
    "nanashi":            "class-nanashi",
    "ajaba":              "class-ajaba",
    "mokole":             "class-mokole",
    "rokea":              "class-rokea",
    "corax":              "class-corax",
    "kitsune":            "class-kitsune",
    "gurahl":             "class-gurahl",
    "ratkin":             "class-ratkin",
    "nagah":              "class-nagah",
    "nuwisha":            "class-nuwisha",
    "shapeshifter":       "class-shapeshifter",
    "monster":            "class-monster",

    # Não regeneram
    "spirit":             "class-spirit",
    "faerie":             "class-faerie",
    "human":              "class-human",
    "animal":             "class-animal",
    "wraith":             "class-wraith",
    "chulorviah":         "class-chulorviah",

    # Equipment subtypes
    "weapon":             "equipment-weapon",
    "armor":              "equipment-armor",
    "fetish":             "equipment-fetish",
    "klaive":             "equipment-klaive",
    "firearm":            "equipment-firearm",
}

# ═══════════════════════════════════════════════════════════════
# MAPEAMENTO: Regex no texto → Tags de habilidades especiais
# ═══════════════════════════════════════════════════════════════

TEXTO_PARA_TAGS = [
    # Auto-ataque
    (r"(?i)attacks?\s+the\s+highest\s+Rage\s+Wyrm",     "auto-attack-wyrm"),
    (r"(?i)attacks?\s+the\s+highest\s+Renown\s+BSD",     "auto-attack-bsd"),
    (r"(?i)attacks?\s+whoever\s+killed\s+(the\s+)?lowest", "revenge-attack"),
    (r"(?i)attacks?\s+the\s+highest\s+Renown\s+Pentex",  "auto-attack-pentex"),
    (r"(?i)(?:at|during)\s+(the\s+)?end\s+of\s+(?:the\s+)?(?:each\s+)?combat\s+phase",
                                                            "combat-phase-trigger"),
    (r"(?i)at\s+the\s+end\s+of\s+(?:any|each)\s+turn",   "end-of-turn-trigger"),
    (r"(?i)automatically\s+(?:attack|strikes?|bites?)",  "auto-attack"),

    # Gift access
    (r"(?i)can\s+use\s+ANY\s+Gifts",                    "any-gift-user"),
    (r"(?i)can\s+use\s+any\s+Auspice\s+Gifts",           "auspice-gift-user"),
    (r"(?i)can\s+use\s+\w+\s+Gifts",                     "specific-gift-user"),

    # Remoção / destruição
    (r"(?i)removes?\s+(the\s+)?lowest\s+Renown\s+victim", "victim-remover"),
    (r"(?i)destroys?\s+\w+\s+Caern",                     "caern-destroyer"),
    (r"(?i)removes?\s+\w+\s+Mass\s+Pollution",           "pollution-remover"),
    (r"(?i)removes?\s+(the\s+)?lowest\s+Gnosis\s+Bane",  "bane-remover"),
    (r"(?i)auto-?(?:matically\s+)?exiles?\s+",           "auto-exile"),

    # Comprar / buscar cartas
    (r"(?i)(?:draw|buy)\s+\d+\s+card",                   "card-draw"),
    (r"(?i)search(?:es)?\s+(?:the|your|deck)",           "deck-search"),

    # Modificar atributos
    (r"(?i)\+\s*\d+\s+(?:Rage|Gnosis|Health|Renown)",    "stat-boost"),
    (r"(?i)[–\-]\s*\d+\s+(?:Rage|Gnosis|Health|Renown)",  "stat-debuff"),

    # Regeneração
    (r"(?i)regenerates?\s+(?:a\s+)?damage\s+card",       "regenerator"),
    (r"(?i)regenerates?\s+\w+\s+damage",                  "regenerator"),

    # Dano
    (r"(?i)aggravated\s+damage",                          "aggravated-damage"),
    (r"(?i)(?:causes?|deals?)\s+\d+\s+damage",           "damage-dealer"),

    # VP
    (r"(?i)\+\s*1\s+VP",                                "vp-bonus"),
    (r"(?i)gain\s+\d+\s+VP",                            "vp-gain"),

    # Restrictions / proteção
    (r"(?i)(?:cannot|can'?t)\s+(?:be\s+)?(?:attacked|targeted)", "immune-attack"),
    (r"(?i)immune\s+to\s+damage",                         "damage-immune"),
    (r"(?i)cannot\s+(?:be\s+)?(?:destroyed|killed)",      "indestructible"),
    (r"(?i)no\s+(?:character|opponent)\s+can\s+(?:withdraw|flee)", "no-withdraw"),

    # Lunar
    (r"(?i)(?:if|when)\s+(?:a\s+)?full\s+moon",          "lunar-synergy"),
    (r"(?i)lunar\s+phase",                                "lunar-synergy"),

    # Ressurreição
    (r"(?i)resurrects?\s+|returns?\s+from\s+(?:the\s+)?Umbra", "resurrection"),

    # Impedir gifts/effects
    (r"(?i)(?:ignore|negate|cancel)s?\s+\w+\s+Gift",     "gift-cancel"),
    (r"(?i)Gifts\s+(?:cannot|can'?t)\s+affect",          "gift-immune"),

    # Sneak attack / challenge
    (r"(?i)sneak\s+attack",                               "sneak-attack"),
    (r"(?i)challenge\s+cannot\s+be\s+refused",           "mandatory-challenge"),

    # Fast / slow striking
    (r"(?i)fast\s+striking",                              "fast-striking"),
    (r"(?i)slow\s+striking",                              "slow-striking"),

    # Frenzy
    (r"(?i)frenzy",                                       "frenzy"),

    # Transformação de forma
    (r"(?i)(?:step\s+sideways|shift\s+to\s+Breed)",       "form-shift"),
]


def tags_de_tipo(tipo: str) -> set:
    """Gera tags a partir do tipo da carta."""
    tags = set()
    t = (tipo or "").lower().strip()

    # Mapeamento direto
    if t in TIPO_PARA_TAGS:
        tags.update(TIPO_PARA_TAGS[t])

    # Mapeamento parcial (ex: "Character - Gaia" também é "character")
    for chave, valores in TIPO_PARA_TAGS.items():
        if chave in t:
            tags.update(valores)

    return tags


def tags_de_keywords(keywords: str) -> set:
    """Gera tags a partir das keywords da carta."""
    tags = set()
    kw = (keywords or "").lower()

    for keyword, tag in KEYWORD_PARA_TAGS.items():
        if keyword in kw:
            tags.add(tag)

    return tags


def tags_de_texto(text: str) -> set:
    """Gera tags a partir do texto (regras/habilidade) da carta."""
    tags = set()
    if not text:
        return tags

    for padrao, tag in TEXTO_PARA_TAGS:
        if re.search(padrao, text):
            tags.add(tag)

    return tags


def gerar_tags_carta(tipo: str, keywords: str, text: str) -> list:
    """Gera todas as tags para uma carta."""
    tags = set()
    tags.update(tags_de_tipo(tipo))
    tags.update(tags_de_keywords(keywords))
    tags.update(tags_de_texto(text))
    return sorted(tags)


def carregar_overrides(caminho: str = "data/card_tags_overrides.yaml") -> dict:
    """Carrega overrides manuais de tags (parse manual, sem dependência)."""
    overrides = {}
    if not os.path.exists(caminho):
        return overrides

    try:
        with open(caminho, 'r') as f:
            current_id = None
            current_tags = []
            for line in f:
                line = line.rstrip()
                if not line or line.lstrip().startswith('#'):
                    continue
                # Card ID (número seguido de dois pontos, com ou sem comentário)
                m = re.match(r'^(\d+):\s*(?:#.*)?$', line)
                if m:
                    if current_id is not None:
                        overrides[current_id] = current_tags
                    current_id = int(m.group(1))
                    current_tags = []
                    continue
                # Tags list: tags: ["tag1", "tag2"]
                m = re.match(r'\s+tags:\s*\[(.+)\]', line)
                if m:
                    tags_str = m.group(1)
                    current_tags = [t.strip().strip('"').strip("'")
                                    for t in tags_str.split(',')]
                    continue
                # Single tag: - tag_name
                m = re.match(r'\s+-\s+(.+)', line)
                if m:
                    tag = m.group(1).strip().strip('"').strip("'")
                    if tag:
                        current_tags.append(tag)
            if current_id is not None:
                overrides[current_id] = current_tags
        print(f"  Overrides carregados: {len(overrides)} cartas")
    except Exception as e:
        print(f"⚠️  Erro ao carregar overrides: {e}")

    return overrides


def gerar_todas_tags(dry_run=False, stats_only=False):
    """Gera tags para todas as cartas do banco."""
    conn = sqlite3.connect('rage_web/database.db')

    total = 0
    com_tags = 0
    tag_counts = defaultdict(int)
    tipo_sem_tags = defaultdict(int)

    cartas = conn.execute(
        'SELECT id, name, tipo, keyword, text FROM card ORDER BY tipo, name'
    ).fetchall()

    overrides = carregar_overrides()

    print(f"{'[DRY RUN] ' if dry_run else ''}Processando {len(cartas)} cartas...\n")

    for card_id, name, tipo, keyword, text in cartas:
        total += 1

        # Gerar tags automáticas
        tags = gerar_tags_carta(tipo, keyword or "", text or "")

        # Aplicar overrides (adicionar/remover tags manuais)
        if card_id in overrides:
            tags = sorted(set(tags) | set(overrides[card_id]))

        if tags:
            com_tags += 1
            for t in tags:
                tag_counts[t] += 1
        else:
            tipo_sem_tags[(tipo or "sem_tipo")] += 1

        if not dry_run and not stats_only:
            conn.execute(
                'UPDATE card SET tags = ? WHERE id = ?',
                (','.join(tags), card_id)
            )

    if not dry_run and not stats_only:
        conn.commit()
        conn.close()
        print(f"✅ Tags salvas para {com_tags}/{total} cartas\n")
    else:
        conn.close()

    # Estatísticas
    print("=== COBERTURA ===")
    print(f"  Cartas com tags: {com_tags}/{total} ({100*com_tags/total:.1f}%)")
    print(f"  Tags únicas: {len(tag_counts)}")

    print("\n=== TOP 30 TAGS ===")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:30]:
        print(f"  {tag:<35} {count:>4} cartas")

    print("\n=== TIPOS SEM TAGS ===")
    for tipo, count in sorted(tipo_sem_tags.items(), key=lambda x: -x[1]):
        print(f"  {tipo:<30} {count:>4} cartas")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    stats_only = '--stats' in sys.argv

    gerar_todas_tags(dry_run=dry_run, stats_only=stats_only)
