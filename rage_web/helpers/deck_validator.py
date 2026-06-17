"""
Validador de decks para Rage CCG.

Verifica a legalidade (regras de construção) e a viabilidade
(se as cartas podem ser efetivamente usadas pelos personagens).
"""

from __future__ import annotations
from typing import Any
from collections import Counter

from rage_web.ext.database import db
from rage_web.models.deck import Deck, deck_cards
from rage_web.models.card import Card


# ---------------------------------------------------------------------------
# Verificação de cobertura de JSON (engine de efeitos)
# ---------------------------------------------------------------------------

def _check_json_coverage(result: ValidationResult,
                         cards_data: list[tuple[Card, int]]) -> None:
    """Verifica se as cartas do deck têm JSON de efeitos estruturados.

    Cartas sem JSON são jogadas como 'vanilla' pelo bot — não usam
    efeitos especiais, apenas atributos básicos.
    """
    from rage_web.game_engine.effects import CARTAS_EXEMPLO

    missing: list[tuple[Card, int]] = []
    for card, qty in cards_data:
        modelo_key = card.slug or f'card_{card.id}'
        if modelo_key not in CARTAS_EXEMPLO:
            missing.append((card, qty))

    if not missing:
        result.ok("JSON_COVERAGE",
                  f"Todas as {sum(q for _, q in cards_data)} cartas têm JSON de efeitos")
        return

    total_missing = sum(q for _, q in missing)
    total_cards = sum(q for _, q in cards_data)
    pct = total_missing / total_cards * 100

    result.warn("JSON_COVERAGE",
                f"{total_missing}/{total_cards} cartas ({pct:.0f}%) sem JSON de efeitos")

    # Agrupar por tipo para diagnóstico
    from collections import Counter
    tipos_missing: Counter[str] = Counter()
    for card, qty in missing:
        tipo_norm = (card.tipo or 'Unknown').strip()
        tipos_missing[tipo_norm] += qty

    result.warn("JSON_COVERAGE_TIPOS",
                f"Distribuição por tipo:")
    for tipo, qty in tipos_missing.most_common():
        result.warn("JSON_COVERAGE_TIPOS_DET",
                    f"  {qty:2d}x {tipo}")

    result.warn("JSON_COVERAGE_CRAFT",
                "Execute `auto_craft_deck({deck_id})` para gerar JSONs automaticamente")

    # Listar cartas específicas
    for card, qty in sorted(missing, key=lambda x: x[0].name):
        result.warn("JSON_COVERAGE_CARD",
                    f"  '{card.name}' x{qty} (id={card.id}, {card.tipo})")


# ---------------------------------------------------------------------------
# Auto-craft de JSONs
# ---------------------------------------------------------------------------

def auto_craft_deck(deck_id: int, dry_run: bool = False) -> list[dict]:
    """Gera JSONs de efeitos para cartas do deck que ainda não têm.

    Args:
        deck_id: ID do deck.
        dry_run: Se True, só lista o que seria gerado sem salvar.

    Returns:
        Lista de modelos JSON gerados.
    """
    from rage_web.game_engine.effects import CARTAS_EXEMPLO

    deck = db.session.get(Deck, deck_id)
    if not deck:
        raise ValueError(f"Deck {deck_id} não encontrado")

    rows = db.session.execute(
        db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
    ).all()

    missing: list[Card] = []
    seen: set[int] = set()
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if not card or card.id in seen:
            continue
        seen.add(card.id)
        modelo_key = card.slug or f'card_{card.id}'
        if modelo_key not in CARTAS_EXEMPLO:
            missing.append(card)

    if not missing:
        return []

    if dry_run:
        print(f"📋 Dry-run: {len(missing)} carta(s) sem JSON")
        for c in sorted(missing, key=lambda x: x.name):
            print(f"   [{c.id}] {c.name} ({c.tipo})")
        return []

    # Importa e executa o crafter
    from rage_web.helpers.auto_json.crafter import craft_card

    gerados: list[dict] = []
    for card in missing:
        modelo = craft_card(card.id, deck_id)
        if modelo:
            gerados.append(modelo)
            print(f"  ✅ {modelo['nome']} (id={card.id})")
        else:
            print(f"  ⚠️  {card.name} (id={card.id}) — não foi possível gerar JSON")

    return gerados


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def validate_card_list(cards: list[tuple[int, int]],
                        deck_name: str = "(em construção)",
                        renown_cap: int = 20,
                        check_json: bool = False) -> ValidationResult:
    """Valida uma lista de cartas (card_id, qty) sem precisar de um deck no banco.

    Útil para scripts de IA que constroem decks programaticamente e querem
    validar ANTES de salvar.

    Args:
        cards: Lista de tuplas (card_id, quantity).
        deck_name: Nome do deck para o relatório.
        renown_cap: Cap de Renome do deck.
        check_json: Se True, verifica cobertura de JSON.

    Returns:
        ValidationResult com todos os checks.
    """
    # Mock um objeto Deck só para a validação
    class MockDeck:
        def __init__(self, name, cap):
            self.id = 0
            self.name = name
            self.renown_cap = cap

    deck = MockDeck(deck_name, renown_cap)

    cards_data: list[tuple[Card, int]] = []
    for cid, qty in cards:
        card = db.session.get(Card, cid)
        if card:
            cards_data.append((card, qty))
        else:
            print(f"  ⚠️  Carta ID {cid} não encontrada no banco")

    result = ValidationResult(0, deck_name)

    if not cards_data:
        result.fail("LEGAL_DECK_EMPTY", "Lista de cartas vazia")
        return result

    result.ok("LEGAL_DECK_EMPTY", f"Lista contém {sum(q for _, q in cards_data)} cartas")

    # 1. Legalidade
    _check_legal(result, cards_data, deck)

    # 2. Viabilidade
    _check_viability(result, cards_data, deck)

    # 3. Cobertura de JSON
    if check_json:
        _check_json_coverage(result, cards_data)

    return result


def validate_deck(deck_id: int, check_json: bool = True) -> ValidationResult:
    """
    Valida um deck pelo seu ID.

    Args:
        deck_id: ID do deck.
        check_json: Se True, verifica cobertura de JSON de efeitos.

    Retorna um objeto ValidationResult com todos os checks.
    """
    deck = db.session.get(Deck, deck_id)
    if not deck:
        raise ValueError(f"Deck {deck_id} não encontrado")

    result = ValidationResult(deck.id, deck.name)

    # Carregar cartas do deck
    rows = db.session.execute(
        db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
    ).all()

    cards_data: list[tuple[Card, int]] = []
    for row in rows:
        card = db.session.get(Card, row.card_id)
        if card:
            cards_data.append((card, row.quantity))

    if not cards_data:
        result.fail("LEGAL_DECK_EMPTY", "Deck não contém cartas")
        return result

    result.ok("LEGAL_DECK_EMPTY", f"Deck contém {sum(q for _, q in cards_data)} cartas")

    # 1. Legalidade
    _check_legal(result, cards_data, deck)

    # 2. Viabilidade
    _check_viability(result, cards_data, deck)

    # 3. Cobertura de JSON (engine de efeitos)
    if check_json:
        _check_json_coverage(result, cards_data)

    return result


def print_validation(deck_id: int, auto_craft: bool = False) -> str:
    """Valida e retorna o relatório formatado.

    Args:
        deck_id: ID do deck.
        auto_craft: Se True, gera automaticamente JSONs para cartas que faltam.
    """
    result = validate_deck(deck_id)
    report = result.report()

    # Verificar se há JSONs faltando
    has_missing = any(c['key'] == 'JSON_COVERAGE' and c['status'] == 'warning'
                      for c in result.checks)

    if has_missing:
        if auto_craft:
            report += f"\n\n🔧 Gerando JSONs automaticamente...\n"
            gerados = auto_craft_deck(deck_id)
            if gerados:
                report += f"\n✅ {len(gerados)} JSON(s) gerado(s) para deck {deck_id}\n"
            else:
                report += f"\nNenhum JSON novo necessário.\n"
        else:
            from rage_web.game_engine.effects import CARTAS_EXEMPLO
            rows = db.session.execute(
                db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
            ).all()
            missing_count = 0
            seen = set()
            for row in rows:
                if row.card_id in seen:
                    continue
                seen.add(row.card_id)
                if f'card_{row.card_id}' not in CARTAS_EXEMPLO:
                    missing_count += 1

            deck_ctx = deck_id
            report += f"\n💡 Dica: Execute `auto_craft_deck({deck_ctx})` para gerar "
            report += f"JSONs de efeitos para as {missing_count} carta(s) sem modelo.\n"
            report += f"   Ou passe auto_craft=True em print_validation().\n"

    return report


# ---------------------------------------------------------------------------
# Anti-sinergias conhecidas
# ---------------------------------------------------------------------------

def _check_known_antisynergies(result: ValidationResult,
                                cards_data: list[tuple[Card, int]],
                                chars: list[dict[str, Any]]) -> None:
    """Verifica anti-sinergias entre cartas do deck.

    Lista curada manualmente de interações problemáticas que um
    construtor de deck (humano ou IA) pode não perceber.
    """
    card_ids = {c.id for c, _ in cards_data}
    card_names = {c.name for c, _ in cards_data}

    # Anti-sinergia: Spirit Backlash (907) + Fetish Equipment G≥5
    if 907 in card_ids:
        for card, qty in cards_data:
            if card.tipo == 'Equipment':
                is_fetish = card.keyword and ('fetish' in card.keyword.lower() or 'klaive' in card.keyword.lower())
                if is_fetish and card.gnosis >= 5:
                    result.warn("VIAB_ANTISYNERGY",
                                f"'{card.name}' (G{card.gnosis}, fetish) será destruído por Spirit Backlash "
                                f"(descarta fetish Equipment com Gnosis ≥ 5)")

    # Anti-sinergia: Desert Klaive (1441) + Spirit Backlash (já capturado acima)

    # Verificar combat cards que exigem forma específica sem personagem compatível
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "combat" not in tipo:
            continue
        text = (card.text or "").lower()
        if 'not in homid form' in text or 'cannot be played in homid' in text:
            all_homid = all('homid' in ch['keyword_raw'].lower() and
                          'lupus' not in ch['keyword_raw'].lower()
                          for ch in chars)
            if all_homid and qty > 0:
                result.warn("VIAB_FORM_REQUIREMENT",
                            f"'{card.name}' requer forma não-Homid, mas todos os personagens "
                            f"são Homid")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_keyword_requirement(requires: str, chars: list[dict[str, Any]]) -> bool:
    """Verifica se algum personagem atende a um requisito de keyword simples.

    Suporta formato " - " (OR): qualquer uma das opções serve.
    """
    if not requires:
        return True
    opcoes = [p.strip() for p in requires.split(' - ')]
    for ch in chars:
        for opcao in opcoes:
            opcao_lower = opcao.lower()
            # Casos especiais
            if opcao_lower == 'any':
                return True
            # Verificação de keyword padrão
            kw = _parse_keywords(opcao)
            if kw & ch['keywords']:
                return True
    return False


def _verify_ally_requires(requires: str, chars: list[dict[str, Any]]) -> bool:
    """Verifica se algum personagem pode recrutar um Ally.

    Lida com formato " - " (OR). Cada opção pode ser:
    - 'Any': qualquer personagem recruta
    - '(Gnosis: N) + Keyword': personagem precisa Gnosis≥N + keyword
    - 'Keyword': personagem precisa ter a keyword
    """
    if not requires:
        return True
    opcoes = [p.strip() for p in requires.split(' - ')]
    for ch in chars:
        for opcao in opcoes:
            if opcao.lower() == 'any':
                return True
            # Verifica formato "(Gnosis: N) + Keyword"
            if '(gnosis:' in opcao.lower():
                import re
                m = re.match(r'\(Gnosis:\s*(\d+)\)\s*\+\s*(.+)', opcao, re.IGNORECASE)
                if m:
                    gn_req = int(m.group(1))
                    kw_req = m.group(2).strip()
                    if ch['gnosis'] >= gn_req:
                        kw_set = _parse_keywords(kw_req)
                        if not kw_set or kw_set & ch['keywords']:
                            return True
                    continue
            # Verificação padrão de keyword
            kw = _parse_keywords(opcao)
            if kw & ch['keywords']:
                return True
    return False


def _parse_keywords(raw: str) -> set[str]:
    """Separa uma string de keywords (hifenizada) num conjunto limpo."""
    if not raw:
        return set()
    return {k.strip().lower() for k in raw.replace('|', '-').split('-') if k.strip()}


# ---------------------------------------------------------------------------
# Resultado da validação
# ---------------------------------------------------------------------------

class ValidationResult:
    """Agrupa todos os checks de um deck."""

    def __init__(self, deck_id: int, deck_name: str):
        self.deck_id = deck_id
        self.deck_name = deck_name
        self.checks: list[dict[str, Any]] = []
        self.errors: int = 0
        self.warnings: int = 0

    def ok(self, key: str, msg: str) -> None:
        self.checks.append({"key": key, "status": "ok", "message": msg})

    def warn(self, key: str, msg: str) -> None:
        self.warnings += 1
        self.checks.append({"key": key, "status": "warning", "message": msg})

    def fail(self, key: str, msg: str) -> None:
        self.errors += 1
        self.checks.append({"key": key, "status": "error", "message": msg})

    @property
    def is_legal(self) -> bool:
        legal_errors = [c for c in self.checks
                        if c["status"] == "error" and c["key"].startswith("LEGAL_")]
        return len(legal_errors) == 0

    @property
    def summary(self) -> str:
        parts = [f"Deck «{self.deck_name}» (ID {self.deck_id})"]
        parts.append(f"  ✅ {len([c for c in self.checks if c['status']=='ok'])} checks OK")
        parts.append(f"  ⚠️  {self.warnings} avisos")
        parts.append(f"  ❌ {self.errors} erros")
        parts.append(f"  {'✅ LEGAL' if self.is_legal else '❌ ILEGAL'}")
        return "\n".join(parts)

    def report(self) -> str:
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f" VALIDAÇÃO DO DECK: {self.deck_name} (ID {self.deck_id})")
        lines.append(f"{'='*60}")
        lines.append("")

        for c in self.checks:
            icon = {"ok": "✅", "warning": "⚠️ ", "error": "❌"}[c["status"]]
            lines.append(f"  {icon} [{c['key']}] {c['message']}")

        lines.append("")
        lines.append(f"{'─'*60}")
        lines.append(self.summary)
        lines.append(f"{'─'*60}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validação de legalidade (deck construction rules)
# ---------------------------------------------------------------------------

def _check_legal(result: ValidationResult,
                 cards_data: list[tuple[Card, int]],
                 deck: Deck) -> None:
    """Verifica as regras obrigatórias de construção do deck."""

    chars: list[tuple[Card, int]] = []
    combat: list[tuple[Card, int]] = []
    sept: list[tuple[Card, int]] = []

    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "character" in tipo:
            chars.append((card, qty))
        elif "combat" in tipo:
            combat.append((card, qty))
        else:
            sept.append((card, qty))

    total_combat = sum(q for _, q in combat)
    total_sept = sum(q for _, q in sept)

    if total_combat >= 20:
        result.ok("LEGAL_COMBAT_MIN", f"Cartas de combate: {total_combat} ≥ 20")
    else:
        result.fail("LEGAL_COMBAT_MIN",
                     f"Cartas de combate: {total_combat} < 20 (mínimo 20)")

    if total_sept >= 30:
        result.ok("LEGAL_SEPT_MIN", f"Cartas de sept: {total_sept} ≥ 30")
    else:
        result.fail("LEGAL_SEPT_MIN",
                     f"Cartas de sept: {total_sept} < 30 (mínimo 30)")

    combat_names: Counter[str] = Counter()
    sept_names: Counter[str] = Counter()
    char_names: Counter[str] = Counter()

    for card, qty in combat:
        combat_names[card.name] += qty
    for card, qty in sept:
        sept_names[card.name] += qty
    for card, qty in chars:
        char_names[card.name] += qty

    combat_ok = True
    for name, qty in combat_names.items():
        if qty > 2:
            result.fail("LEGAL_COMBAT_COPIES",
                        f"'{name}': {qty}x em combate (máx. 2)")
            combat_ok = False
    if combat_ok:
        result.ok("LEGAL_COMBAT_COPIES",
                  "Limite de cópias em combate respeitado (máx. 2 por carta)")

    sept_ok = True
    for name, qty in sept_names.items():
        if qty > 3:
            result.fail("LEGAL_SEPT_COPIES",
                        f"'{name}': {qty}x em sept (máx. 3)")
            sept_ok = False
    if sept_ok:
        result.ok("LEGAL_SEPT_COPIES",
                  "Limite de cópias em sept respeitado (máx. 3 por carta)")

    char_copy_ok = True
    for card, qty in chars:
        if qty > 1:
            is_multiple = card.keyword and "multiple" in card.keyword.lower()
            if is_multiple and qty <= 5:
                continue
            result.fail("LEGAL_CHAR_COPIES",
                        f"'{card.name}': {qty}x (personagem único, máx. 1)")
            char_copy_ok = False
    if char_copy_ok:
        result.ok("LEGAL_CHAR_COPIES",
                  "Todos os personagens têm cópia única respeitada")

    total_renown = sum((card.renown or 0) * qty for card, qty in chars)
    cap = deck.renown_cap
    if total_renown <= cap:
        result.ok("LEGAL_RENOWN",
                  f"Renome total: {total_renown} ≤ {cap} (cap do deck)")
    else:
        result.fail("LEGAL_RENOWN",
                    f"Renome total: {total_renown} > {cap} (cap do deck)")

    gaia_count = 0
    wyrm_count = 0
    rogue_count = 0

    for card, qty in chars:
        tipo = card.tipo or ""
        if "rogue" in tipo.lower():
            rogue_count += qty
        elif "wyrm" in tipo.lower():
            wyrm_count += qty
        elif "gaia" in tipo.lower():
            gaia_count += qty

    if gaia_count > 0 and wyrm_count == 0:
        result.ok("LEGAL_ALLEGIANCE",
                  f"Alcunha: Gaia ({gaia_count} Gaia + {rogue_count} Rogue)")
        if gaia_count + rogue_count == rogue_count:
            result.fail("LEGAL_ALLEGIANCE_NONROGUE",
                        "Pack precisa de pelo menos 1 não-Rogue")
        else:
            result.ok("LEGAL_ALLEGIANCE_NONROGUE",
                      "Pelo menos 1 não-Rogue presente no pack")
    elif wyrm_count > 0 and gaia_count == 0:
        result.ok("LEGAL_ALLEGIANCE",
                  f"Alcunha: Wyrm ({wyrm_count} Wyrm + {rogue_count} Rogue)")
        if wyrm_count + rogue_count == rogue_count:
            result.fail("LEGAL_ALLEGIANCE_NONROGUE",
                        "Pack precisa de pelo menos 1 não-Rogue")
        else:
            result.ok("LEGAL_ALLEGIANCE_NONROGUE",
                      "Pelo menos 1 não-Rogue presente no pack")
    elif gaia_count > 0 and wyrm_count > 0:
        result.fail("LEGAL_ALLEGIANCE",
                    f"Alcunha mista! {gaia_count} Gaia + {wyrm_count} Wyrm + "
                    f"{rogue_count} Rogue — personagens Gaia e Wyrm no mesmo pack")
    else:
        if rogue_count > 0:
            result.fail("LEGAL_ALLEGIANCE",
                        "Apenas personagens Rogue — pack não pode ter só Rogues")
        else:
            result.fail("LEGAL_ALLEGIANCE",
                        "Nenhum personagem com alcunha definida")


# ---------------------------------------------------------------------------
# Validação de viabilidade (playability)
# ---------------------------------------------------------------------------

def _check_viability(result: ValidationResult,
                     cards_data: list[tuple[Card, int]],
                     deck: Deck) -> None:
    """Verifica se as cartas podem ser usadas pelos personagens do deck."""

    chars: list[dict[str, Any]] = []
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "character" in tipo:
            for _ in range(qty):
                chars.append({
                    "id": card.id,
                    "name": card.name,
                    "tipo": card.tipo,
                    "keywords": _parse_keywords(card.keyword),
                    "keyword_raw": card.keyword or "",
                    "rage": card.rage,
                    "gnosis": card.gnosis,
                    "health": card.health,
                })

    if not chars:
        result.warn("VIAB_CHARS", "Deck não tem personagens — nada a verificar")
        return

    unplayable: list[tuple[Card, int, str]] = []

    # ── Passo 1: Verificar combat actions por requisito de Rage ──
    # O campo `rage` da carta de combate indica o Rage mínimo do personagem
    # para poder jogá-la (regra 6.4 / 6.9.2). O campo `damage` é apenas
    # o dano causado, NÃO o requisito.
    max_char_rage = max(c["rage"] for c in chars) if chars else 0
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "combat" not in tipo:
            continue

        rage_req = card.rage  # <-- O campo `rage` da combat action é o requisito!
        if rage_req > 0 and rage_req > max_char_rage:
            unplayable.append(
                (card, qty,
                 f"Requer Rage {rage_req}, mas maior Rage do pack é {max_char_rage}"
                 f" — personagens: {', '.join(c['name'] for c in chars)}"))

    # ── Passo 2: Verificar equipamentos por requisito de Gnosis ──
    # Equipamentos (especialmente fetishes) têm custo de Gnosis para equipar.
    # O campo `gnosis` da carta indica a Gnosis mínima necessária.
    # Se o Requires field também tiver keywords, verifique ambos.
    max_char_gnosis = max(c["gnosis"] for c in chars) if chars else 0
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "equipment" not in tipo:
            continue

        gnosis_req = card.gnosis
        requires_raw = card.requires or ""
        requires = requires_raw.strip()

        # Verificar requisito de Gnosis
        if gnosis_req > max_char_gnosis:
            unplayable.append(
                (card, qty,
                 f"Requer Gnosis {gnosis_req}, mas maior Gnosis do pack é {max_char_gnosis}"))
            continue

        # Verificar requisito de keyword (quando houver)
        if requires and not _verify_keyword_requirement(requires, chars):
            unplayable.append(
                (card, qty,
                 f"Equipamento requer keyword '{requires}' — nenhum personagem atende"))
            continue

    # ── Passo 3: Verificar aliados (recruitment requirements) ──
    # A regra 4.4.1 diz que recrutar Ally requer um Character que atenda
    # ao campo `requires` do Ally. O formato pode ser:
    #   "Keyword" | "Keyword1 - Keyword2" (OR) | "(Gnosis: N) + Keyword"
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "ally" not in tipo:
            continue

        requires_raw = card.requires or ""
        if not requires_raw.strip():
            continue

        if not _verify_ally_requires(requires_raw, chars):
            unplayable.append(
                (card, qty,
                 f"Ally requer '{requires_raw}' — nenhum personagem atende ao requisito de recrutamento"))

    # ── Passo 4: Verificar gifts por keyword + Gnosis ──
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "gift" not in tipo:
            continue

        requires_raw = card.requires or ""
        requires = requires_raw.strip()
        gnosis_req = card.gnosis

        if not requires and gnosis_req <= 0:
            # Gift sem requisito especial — só precisa de Gnosis
            if gnosis_req > max_char_gnosis:
                unplayable.append(
                    (card, qty,
                     f"Requer Gnosis {gnosis_req}, mas maior Gnosis do pack é {max_char_gnosis}"))
            continue

        if requires:
            viable_chars = []
            for ch in chars:
                req_keywords = _parse_keywords(requires)
                matched = req_keywords & ch["keywords"]
                if not matched:
                    continue
                if ch["gnosis"] < gnosis_req:
                    continue
                viable_chars.append(f"{ch['name']} (Gn {ch['gnosis']}≥{gnosis_req}, kw={matched})")

            if not viable_chars:
                unplayable.append(
                    (card, qty,
                     f"Requer '{requires}' + Gnosis ≥ {gnosis_req}"
                     f" — nenhum personagem atende"))

    # ── Passo 5: Verificar outros tipos de carta com requires ──
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        # Já verificamos: character, combat, equipment, ally, gift
        if any(x in tipo for x in ['character', 'combat', 'equipment', 'ally', 'gift']):
            continue

        requires_raw = card.requires or ""
        if not requires_raw.strip():
            continue

        if not _verify_keyword_requirement(requires_raw, chars):
            unplayable.append(
                (card, qty,
                 f"Requer keyword '{requires_raw}' — nenhum personagem atende"))

    # ── Relatório ──
    if unplayable:
        total_unplayable = sum(qty for _, qty, _ in unplayable)
        result.warn("VIAB_UNPLAYABLE",
                    f"{total_unplayable} carta(s) injogável(is) por requisitos "
                    f"não atendidos:")
        for card, qty, reason in sorted(unplayable, key=lambda x: x[0].name):
            result.warn("VIAB_UNPLAYABLE_DETAIL",
                        f"  '{card.name}' x{qty} ({card.tipo}) — {reason}")
    else:
        result.ok("VIAB_UNPLAYABLE",
                  "Todas as cartas são jogáveis por pelo menos um personagem")

    # Caerns
    playable_caerns = []
    unplayable_caerns = []
    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if tipo != "caern":
            continue
        requires = (card.requires or "").strip()
        if not requires:
            playable_caerns.append((card, qty))
            continue
        req_keywords = _parse_keywords(requires)
        can_play = any(req_keywords & ch["keywords"] for ch in chars)
        if can_play:
            playable_caerns.append((card, qty))
        else:
            unplayable_caerns.append((card, qty))

    if unplayable_caerns:
        total_caern_unplayable = sum(q for _, q in unplayable_caerns)
        total_caern = total_caern_unplayable + sum(q for _, q in playable_caerns)
        result.warn("VIAB_CAERNS",
                    f"{total_caern_unplayable}/{total_caern} Caern(s) "
                    f"inacessível(is) — nenhum personagem atende ao keyword requirement")
    elif playable_caerns:
        result.ok("VIAB_CAERNS",
                  "Pelo menos um Caern jogável pelos personagens")

    # Pack Totems
    for card, qty in cards_data:
        if card.tipo == "Event" and card.keyword and "pack totem" in card.keyword.lower():
            requires = (card.requires or "").strip()
            if requires:
                if not _verify_keyword_requirement(requires, chars):
                    result.warn("VIAB_TOTEM",
                                f"Pack Totem '{card.name}' requer keyword "
                                f"'{requires}' — nenhum personagem atende")

    # ── Verificações de anti-sinergia conhecidas ──
    _check_known_antisynergies(result, cards_data, chars)

