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
# Helpers
# ---------------------------------------------------------------------------

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
        self.checks: list[dict[str, Any]] = []  # cada check: dict com chave, status, mensagem
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
        """Erros de legalidade (não de viabilidade) indicam deck ilegal."""
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

    # -- Contagens mínimas ------------------------------------------------
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

    # -- Limites de cópia ------------------------------------------------
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

    # -- Personagens: cópia única (except Multiple) -----------------------
    char_copy_ok = True
    for card, qty in chars:
        if qty > 1:
            is_multiple = card.keyword and "multiple" in card.keyword.lower()
            if is_multiple and qty <= 5:
                continue  # Multiple permite até 5
            result.fail("LEGAL_CHAR_COPIES",
                        f"'{card.name}': {qty}x (personagem único, máx. 1)")
            char_copy_ok = False
    if char_copy_ok:
        result.ok("LEGAL_CHAR_COPIES",
                  "Todos os personagens têm cópia única respeitada")

    # -- Renome total ----------------------------------------------------
    total_renown = sum((card.renown or 0) * qty for card, qty in chars)
    cap = deck.renown_cap
    if total_renown <= cap:
        result.ok("LEGAL_RENOWN",
                  f"Renome total: {total_renown} ≤ {cap} (cap do deck)")
    else:
        result.fail("LEGAL_RENOWN",
                    f"Renome total: {total_renown} > {cap} (cap do deck)")

    # -- Alcunha (Allegiance) --------------------------------------------
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

    # Determinar alcunha do deck
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

    # Extrair personagens e suas keywords + atributos
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

    # Para cada carta não-personagem, verificar se pode ser jogada
    unplayable: list[tuple[Card, int, str]] = []

    for card, qty in cards_data:
        tipo = (card.tipo or "").lower()
        if "character" in tipo:
            continue

        requires_raw = card.requires or ""
        requires = requires_raw.strip()

        # --- Cartas de Combate: requires é condição (e.g. "Umbra") -------
        if "combat" in tipo:
            if requires:
                # verificar se tem personagem com Rage suficiente (damage = custo)
                cost_str = (card.damage or "").strip()
                cost = 0
                if cost_str:
                    try:
                        cost = int(cost_str)
                    except ValueError:
                        cost = 0

                has_user = any(c["rage"] >= cost for c in chars)
                if not has_user:
                    unplayable.append(
                        (card, qty,
                         f"Custo Rage {cost} — nenhum personagem tem Rage ≥ {cost}"))
                else:
                    # Mesmo que tenha condição (Umbra), é jogável com suporte
                    pass
            continue

        # --- Recursos / Sept cards: requires é keyword requirement --------
        if not requires:
            continue  # sem requisitos, sempre jogável

        req_keywords = _parse_keywords(requires)
        if not req_keywords:
            continue

        # Verificar se algum personagem atende ao keyword requirement
        viable_chars = []
        for ch in chars:
            matched = req_keywords & ch["keywords"]
            if not matched:
                continue

            # Gifts têm requisito adicional de Gnosis
            if "gift" in tipo:
                if ch["gnosis"] < card.gnosis:
                    continue
                viable_chars.append(f"{ch['name']} (Gn {ch['gnosis']}≥{card.gnosis}, {matched})")
            else:
                viable_chars.append(f"{ch['name']} ({matched})")

        if not viable_chars:
            unplayable.append(
                (card, qty,
                 f"requer keyword: {requires_raw}"
                 + (f" + Gnosis ≥ {card.gnosis}" if "gift" in tipo else "")))

    # Relatar cartas injogáveis
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

    # Verificar se há Caerns que podem ser jogados
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
        can_play = any(
            req_keywords & ch["keywords"]
            for ch in chars
        )
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

    # Verificar Pack Totems
    for card, qty in cards_data:
        if card.tipo == "Event" and card.keyword and "pack totem" in card.keyword.lower():
            requires = (card.requires or "").strip()
            if requires:
                req_keywords = _parse_keywords(requires)
                can_play = any(
                    req_keywords & ch["keywords"]
                    for ch in chars
                )
                if not can_play:
                    result.warn("VIAB_TOTEM",
                                f"Pack Totem '{card.name}' requer keyword "
                                f"'{requires}' — nenhum personagem atende")


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def validate_deck(deck_id: int) -> ValidationResult:
    """
    Valida um deck pelo seu ID.

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

    return result


def print_validation(deck_id: int) -> str:
    """Valida e retorna o relatório formatado."""
    result = validate_deck(deck_id)
    return result.report()
