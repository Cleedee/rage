"""Motor de Estrategia — configura como o bot joga cada deck.

Um jogador experiente pode escrever um arquivo de configuracao JSON
por deck, instruindo o bot a usar melhor as cartas e estrategias.

O arquivo fica em:
    data/deck_strategies/deck<id>_config.json

Formato:
    {
        "deck_id": 1055,
        "name": "O Julgamento (Philodox)",

        "gift_priorities": [ ... ],
        "resource_play_order": [ ... ],
        "combat_action_preferences": { ... },
        "equipment_assignments": [ ... ],
        "caern_preferences": [ ... ],
        "target_priority": { ... },
        "umbra_strategy": { ... },
        "redraw_rules": { ... },
        "moot_strategy": { ... }
    }
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Optional

from rage_web.game_engine.state import CardInstance, GameState, PlayerState

logger = logging.getLogger(__name__)

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    'data', 'deck_strategies'
)


# ─── Utilitarios para condicoes ──────────────────────────────────────

def _eval_condition(cond: str, game: GameState,
                    player: PlayerState, bot) -> bool:
    """Avalia uma condicao textual.

    Condicoes suportadas:
        "umbra_available"            — fase Umbra ou pode step sideways
        "has_characters"             — pelo menos 1 Character no pack
        "has_strong_target"          — oponente tem criatura com Renown >= 2
        "has_injured_character"      — algum Character com HP < max
        "opponent_stronger"          — oponente tem mais chars ou rage total
        "has_character_named:<slug>" — personagem com slug=<slug> esta vivo
        "combat_likely"              — fase Combat ou tem oponentes no pack
        "combat_active"              — combate ativo no momento
        "has_good_target"            — ha Victim/Enemy no HG ou personagem fraco
        "in_combat_with_victim"      — esta em combate com Victim
        "about_to_attack"            — fase de declaracao de combate
        "character_under_attack"     — personagem esta sendo atacado
        "character_receives_mortal_wound" — personagem prestes a morrer
        "defensive_emergency"        — personagem com HP <= 2
        "ffa_mode"                   — 3+ jogadores ativos
        "card_in_hand:<nome>"        — carta com nome <nome> esta na mao
        "character_in_umbra"         — algum Character esta na Umbra
        "always"                     — sempre ativo
    """
    cond = cond.strip().lower()

    if cond == 'always':
        return True
    if cond == 'umbra_available':
        if game.phase == 'umbra':
            return True
        podem_ir, _ = player.personagens_que_podem_step()
        return len(podem_ir) > 0
    if cond == 'has_characters':
        return any('Character' in (c.card_type or '')
                   for c in player.pack_home)
    if cond == 'has_strong_target':
        from rage_web.game_engine.bot.evaluator import TargetPrioritizer
        tp = TargetPrioritizer(game, player.id)
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if c.health_current > 0 and tp.rate_threat(c) >= 5:
                    return True
        return False
    if cond == 'has_injured_character':
        return any(c.health > 0 and c.health_current < c.health
                   for c in player.pack_home
                   if 'Character' in (c.card_type or ''))
    if cond == 'opponent_stronger':
        my_rage = sum(c.effective_rage for c in player.pack_home
                      if 'Character' in (c.card_type or ''))
        max_opp_rage = 0
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Character' in (c.card_type or ''):
                    max_opp_rage = max(max_opp_rage, c.effective_rage)
        return max_opp_rage > my_rage
    if cond.startswith('has_character_named:'):
        slug = cond.split(':', 1)[1].strip()
        for c in player.pack_home:
            if 'Character' in (c.card_type or ''):
                # Compara por slug
                c_slug = getattr(c, 'slug', '') or ''
                if c_slug == slug:
                    return True
                # Fallback: nome
                nome = (c.name or '').lower().replace(' ', '-')
                if nome == slug:
                    return True
        return False
    if cond == 'combat_likely' or cond == 'is_combat_phase':
        if game.phase == 'combat':
            return True
        # Se ha oponentes com personagens, combate e provavel
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Character' in (c.card_type or '') for c in opp.pack_home):
                return True
        return False
    if cond == 'combat_active':
        return game.combat.is_active
    if cond == 'has_good_target':
        # Ha um alvo viavel para atacar (Victim/Enemy no HG ou personagem fraco)
        for c in player.hunting_grounds:
            if c.health_current > 0:
                ct = (c.card_type or '').lower()
                if 'victim' in ct or 'enemy' in ct:
                    return True
        # Ou personagem oponente com HP baixo
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if c.health_current > 0 and c.health_current <= 4:
                    return True
        return False
    if cond == 'in_combat_with_victim':
        # O jogador esta em combate com um Victim
        if not game.combat.is_active:
            return False
        for cid in game.combat.combatants:
            card = game.get_card(cid)
            if card and 'victim' in (card.card_type or '').lower():
                return True
        return False
    if cond == 'about_to_attack':
        # O jogador esta prestes a atacar (fase de declaracao)
        if not game.combat.is_active:
            return False
        step = game.combat.current_step
        return step in ('declaration', 'alpha_action', 'pre_combat')
    if cond == 'character_under_attack':
        # Algum personagem do jogador esta sendo atacado
        if not game.combat.is_active:
            return False
        return True  # Se esta em combate, ha ameaca
    if cond == 'character_receives_mortal_wound':
        # Um personagem do jogador esta prestes a morrer
        if not game.combat.is_active:
            return False
        for cid in game.combat.combatants:
            card = game.get_card(cid)
            if card and card.owner_id == player.id:
                if card.health_current <= 0:
                    return True
        return False
    if cond == 'defensive_emergency':
        # Situacao defensiva critica
        if not game.combat.is_active:
            return False
        for cid in game.combat.combatants:
            card = game.get_card(cid)
            if card and card.owner_id == player.id:
                if card.health_current <= 2:
                    return True
        return False
    if cond == 'ffa_mode':
        ativos = sum(1 for p in game.players if not p.eliminado)
        return ativos >= 3
    if cond.startswith('card_in_hand:'):
        nome = cond.split(':', 1)[1].strip().lower()
        return any(nome in (c.name or '').lower()
                   for c in player.hand)
    if cond == 'character_in_umbra':
        return any('Character' in (c.card_type or '')
                   for c in player.umbra)

    if cond == 'opponent_character_exists':
        # Oponente tem pelo menos 1 Character vivo
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Character' in (c.card_type or '') and c.health_current > 0
                   for c in opp.pack_home):
                return True
        return False

    if cond == 'in_combat_with_strong_opponent':
        # Em combate com oponente forte (Rage > 3 ou HP > 4)
        if not game.combat.is_active:
            return False
        for cid in game.combat.combatants:
            card = game.get_card(cid)
            if card and card.owner_id != player.id:
                if card.effective_rage > 3 or card.health_current > 4:
                    return True
        return False

    if cond == 'losing_board_position':
        # Jogador esta perdendo posicao no tabuleiro
        my_chars = sum(1 for c in player.pack_home
                       if 'Character' in (c.card_type or '') and c.health_current > 0)
        max_opp_chars = 0
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            opp_chars = sum(1 for c in opp.pack_home
                           if 'Character' in (c.card_type or '') and c.health_current > 0)
            max_opp_chars = max(max_opp_chars, opp_chars)
        return my_chars < max_opp_chars

    if cond == 'opponent_has_equipment':
        # Oponente tem algum equipamento
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Equipment' in (c.card_type or '') for c in opp.pack_home):
                return True
        return False

    if cond == 'no_lunar_phase':
        # Nao esta na fase lunar (nao ha Lua cheia)
        # Simplificacao: retorna True se nao esta em combate
        return not game.combat.is_active

    if cond == 'opponent_has_active_gift':
        # Oponente tem gift ativo
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Gift' in (c.card_type or '') for c in opp.pack_home):
                return True
        return False

    if cond == 'moot_phase':
        # Fase de moot (Junta)
        return game.phase == 'moot' or game.moot_atual is not None

    if cond == 'opponent_has_ally_or_prey':
        # Oponente tem ally ou presa (Victim/Enemy)
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                ct = (c.card_type or '').lower()
                if 'ally' in ct or 'victim' in ct or 'enemy' in ct:
                    return True
        return False

    if cond == 'enemy_spirit_in_play':
        # Ha espirito inimigo em jogo
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Spirit' in (c.card_type or ''):
                    return True
        return False

    if cond == 'opponent_can_frenzy':
        # Oponente pode frenzar (tem personagem com Rage > 0)
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Character' in (c.card_type or '') and c.effective_rage > 0:
                    return True
        return False

    if cond == 'threat_from_umbra':
        # Ha ameaca vindo da Umbra
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Character' in (c.card_type or '') for c in opp.umbra):
                return True
        return False

    if cond == 'opponent_has_banes':
        # Oponente tem Banes
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Bane' in (c.card_type or '') or 'bane' in (c.keywords or '').lower():
                    return True
        return False

    if cond == 'opponent_stepping_sideways':
        # Oponente esta entrando na Umbra
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if any('Character' in (c.card_type or '') for c in opp.umbra):
                return True
        return False

    if cond == 'opponent_has_fetish_equipment':
        # Oponente tem equipamento Fetish
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Equipment' in (c.card_type or '') and 'fetish' in (c.keywords or '').lower():
                    return True
        return False

    if cond == 'no_pack_totem':
        # Nao tem Pack Totem
        return not any('Pack Totem' in (c.card_type or '') for c in player.pack_home)

    if cond == 'opponent_has_spirit':
        # Oponente tem Spirit
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            for c in opp.pack_home:
                if 'Spirit' in (c.card_type or ''):
                    return True
        return False

    if cond == 'both_decks_nearly_empty':
        # Ambos os decks estao quase vazios
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            if len(player.deck_combat) <= 3 and len(opp.deck_combat) <= 3:
                return True
        return False

    if cond == 'entering_umbra':
        # Jogador esta entrando na Umbra
        return game.phase == 'umbra'

    if cond == 'opponent_dominates_umbra':
        # Oponente domina a Umbra (tem mais personagens la)
        my_umbra = sum(1 for c in player.umbra
                       if 'Character' in (c.card_type or ''))
        max_opp_umbra = 0
        for opp in game.players:
            if opp.id == player.id or opp.eliminado:
                continue
            opp_umbra = sum(1 for c in opp.umbra
                           if 'Character' in (c.card_type or ''))
            max_opp_umbra = max(max_opp_umbra, opp_umbra)
        return max_opp_umbra > my_umbra

    if cond == 'after_winning_moot':
        """Verifica se o jogador acabou de vencer uma junta que chamou."""
        if not game.moot_atual:
            return False
        if not game.moot_atual.resolvido:
            return False
        if not game.moot_atual.aprovado:
            return False
        if game.moot_atual.dono_id != player.id:
            return False
        return True

    logger.warning(f"Condicao desconhecida: '{cond}'")
    return False


# ─── Motor de Estrategia ─────────────────────────────────────────────

class StrategyEngine:
    """Motor de estrategia para o PriorityBot.

    Carrega um arquivo JSON de configuracao por deck e fornece
    metodos para guiar as decisoes do bot.
    """

    def __init__(self, deck_id: int | None = None,
                 config_path: str | None = None):
        self._config: dict[str, Any] = {}
        self.deck_id = deck_id
        self._loaded = False

        if config_path:
            self._load_file(config_path)
        elif deck_id:
            self._load_for_deck(deck_id)

    def _load_for_deck(self, deck_id: int):
        """Tenta carregar config de data/deck_strategies/deck<id>_config.json."""
        path = os.path.join(STRATEGY_DIR, f'deck{deck_id}_config.json')
        if os.path.exists(path):
            self._load_file(path)
        else:
            self._loaded = True  # Nao ha config, usa defaults
            logger.info(f'[StrategyEngine] Nenhum config para deck {deck_id}')

    def _load_file(self, path: str):
        """Carrega config de um arquivo JSON."""
        try:
            with open(path, 'r') as f:
                self._config = json.load(f)
            self._loaded = True
            logger.info(f'[StrategyEngine] Config carregado: {path}')
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f'[StrategyEngine] Erro ao ler {path}: {e}')
            self._loaded = True  # Continua sem config

    def is_loaded(self) -> bool:
        """Retorna True se ha config carregado."""
        return bool(self._config)

    def get(self, key: str, default=None) -> Any:
        """Acessa um campo da config."""
        return self._config.get(key, default)

    # ─── Gifts ───────────────────────────────────────────────────────

    @staticmethod
    def _card_by_slug(slug: str):
        """Busca carta no banco por slug, com fallback de app context."""
        from rage_web.models.card import Card as CardModel
        from rage_web import create_app
        from rage_web.ext.database import db
        try:
            return CardModel.query.filter(CardModel.slug == slug).first()
        except RuntimeError:
            flask_app = create_app()
            with flask_app.app_context():
                return db.session.query(CardModel).filter(
                    CardModel.slug == slug).first()

    def _resolve_card_ref(self, entry: dict, game: GameState | None = None) -> int | None:
        """Resolve uma referencia de carta (slug ou card_id) para card_id.

        Suporta:
          - slug: 'spirit-of-the-fray'
          - card_id: 1056
        """
        cid = entry.get('card_id') or entry.get('id')
        if cid:
            return int(cid)
        slug = entry.get('slug')
        if slug:
            card = self._card_by_slug(slug)
            if card:
                return card.id
        return None

    def sorted_gifts(self, hand_cards: list[CardInstance],
                     game: GameState, player: PlayerState,
                     bot) -> list[tuple[int, CardInstance]]:
        """Ordena gifts na mao por prioridade definida na config.

        Retorna lista de (priority, CardInstance) ordenada decrescente.
        Se nao ha config, retorna lista vazia (usa heuristica padrao do bot).
        """
        priorities = self.get('gift_priorities', [])
        if not priorities:
            return []

        # Indexa por card_id (slug resolve na hora)
        priority_map: dict[int, tuple[int, str]] = {}
        for entry in priorities:
            cid = self._resolve_card_ref(entry, game)
            if cid:
                condicao = entry.get('condition', 'always')
                priority_map[cid] = (entry.get('priority', 50), condicao)

        scored = []
        for card in hand_cards:
            if card.card_type != 'Gift':
                continue
            entry = priority_map.get(card.card_id)
            if entry is None:
                continue
            prio, cond = entry
            if not _eval_condition(cond, game, player, bot):
                prio -= 100  # Reduz drasticamente se condicao nao satisfeita
            scored.append((prio, card))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def get_gift_priority(self, card_id: int, game: GameState | None = None) -> int:
        """Retorna prioridade base de um gift (sem condicao)."""
        for entry in self.get('gift_priorities', []):
            if entry.get('card_id') == card_id or entry.get('id') == card_id:
                return entry.get('priority', 0)
            # Tambem resolve por slug
            slug = entry.get('slug')
            if slug:
                card = self._card_by_slug(slug)
                if card and card.id == card_id:
                    return entry.get('priority', 0)
        return 0

    # ─── Resource play order ─────────────────────────────────────────

    def resource_play_order(self) -> list[str]:
        """Retorna ordem de tipos para jogar na Resource phase.

        Returns:
            Lista de tipos na ordem desejada, ex:
            ['character', 'caern', 'card_draw', 'equipment', ...]
            Vazio se nao configurado.
        """
        return self.get('resource_play_order', [])

    def sorted_events(self, hand_cards: list[CardInstance],
                      game: GameState, player: PlayerState,
                      bot) -> list[tuple[int, CardInstance]]:
        """Ordena eventos na mao por prioridade definida na config.

        Similar a sorted_gifts() mas para Event cards.
        Retorna lista de (priority, CardInstance) ordenada decrescente.
        Se nao ha config, retorna lista vazia.
        """
        priorities = self.get('event_priorities', [])
        if not priorities:
            return []

        priority_map: dict[int, tuple[int, str]] = {}
        for entry in priorities:
            cid = self._resolve_card_ref(entry, game)
            if cid:
                condicao = entry.get('condition', 'always')
                priority_map[cid] = (entry.get('priority', 50), condicao)

        scored = []
        for card in hand_cards:
            if card.card_type != 'Event':
                continue
            entry = priority_map.get(card.card_id)
            if entry is None:
                continue
            prio, cond = entry
            if not _eval_condition(cond, game, player, bot):
                continue
            scored.append((prio, card))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    # ─── Action cards (Friends in High Places, Sneak Attack, etc.) ────

    def sorted_actions(self, hand_cards: list[CardInstance],
                       game: GameState, player: PlayerState,
                       bot) -> list[tuple[int, CardInstance]]:
        """Ordena Action cards na mao por prioridade definida na config.

        Usado pelo bot na Resource phase para jogar Action cards
        estrategicos (Friends in High Places, Sneak Attack, etc.)
        ANTES de tentar outros tipos de carta.

        Retorna lista de (priority, CardInstance) ordenada decrescente.
        Se nao ha config, retorna lista vazia (usa heuristica padrao).
        """
        priorities = self.get('action_priorities', [])
        if not priorities:
            return []

        priority_map: dict[int, tuple[int, str]] = {}
        for entry in priorities:
            cid = self._resolve_card_ref(entry, game)
            if cid:
                condicao = entry.get('condition', 'always')
                priority_map[cid] = (entry.get('priority', 50), condicao)

        scored = []
        for card in hand_cards:
            ct = (card.card_type or '')
            if ct != 'Action':
                continue
            entry = priority_map.get(card.card_id)
            if entry is None:
                continue
            prio, cond = entry
            if not _eval_condition(cond, game, player, bot):
                prio -= 100  # Reduz drasticamente se condicao nao satisfeita
            scored.append((prio, card))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    # ─── Combat Events (jogados face-down no play_card step) ─────────

    def sorted_combat_events(self, combat_hand_cards: list) -> list[tuple[int, object]]:
        """Ordena Combat Events na mao de combate por prioridade da config.

        Usado pelo bot no play_card step para jogar Combat Events
        estrategicos (Bum Rush, Pack Defense, etc.) ANTES de declarar
        acoes individuais.

        Suporta dois formatos de config:
        - `combat_event_priorities` (lista de dicts, igual gift_priorities)
        - `combat_event_priority` (dict slug -> prioridade, formato legado)

        Args:
            combat_hand_cards: Lista de CardInstance da mao de combate.

        Returns:
            Lista de (priority, CardInstance) ordenada decrescente.
            Vazia se nao ha config ou nenhum CE priorizado.
        """
        # Tenta formato novo (lista de dicts)
        priorities_list = self.get('combat_event_priorities', [])
        # Fallback para formato legado (dict slug -> priority)
        priorities_dict = self.get('combat_event_priority', {})

        if not priorities_list and not priorities_dict:
            return []

        priority_map: dict[int, int] = {}

        # Formato novo: lista de dicts
        for entry in priorities_list:
            cid = self._resolve_card_ref(entry)
            if cid:
                priority_map[cid] = entry.get('priority', 50)

        # Formato legado: dict slug -> priority
        for slug, prio in priorities_dict.items():
            card = self._card_by_slug(slug)
            if card:
                # So adiciona se nao foi definido pelo formato novo
                if card.id not in priority_map:
                    priority_map[card.id] = prio

        scored = []
        for card in combat_hand_cards:
            ct = (card.card_type or '').lower()
            if 'combat event' not in ct and ct != 'combat_event':
                continue
            prio = priority_map.get(card.card_id)
            if prio is None:
                continue
            scored.append((prio, card))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    # ─── Combat Actions ──────────────────────────────────────────────

    def preferred_actions(self, character_name: str) -> list[str]:
        """Retorna acoes de combate preferidas para um personagem.

        Args:
            character_name: Nome do personagem.

        Returns:
            Lista de slugs de acoes (ex: ['disembowelment', 'stunning_strike']).
        """
        prefs = self.get('combat_action_preferences', {})
        # Busca por nome exato ou contendo
        for key, actions in prefs.items():
            if key.lower() in character_name.lower():
                return actions
        return []

    def has_action_preference(self, character_name: str) -> bool:
        """Verifica se ha preferencia de acao para este personagem."""
        return bool(self.preferred_actions(character_name))

    # ─── Equipment ───────────────────────────────────────────────────

    def equipment_assignment(self, equip_name: str,
                              game: GameState,
                              player: PlayerState) -> Optional[str]:
        """Retorna o nome do personagem que deve receber um equipment.

        Args:
            equip_name: Nome do equipment.
            game: Estado do jogo.
            player: Jogador.

        Returns:
            Nome do personagem alvo, ou None se sem preferencia.
        """
        assignments = self.get('equipment_assignments', [])
        for entry in assignments:
            if entry.get('card_name', '').lower() in equip_name.lower():
                target = entry.get('target', '')
                # Verifica se o personagem esta no pack e vivo
                for c in player.pack_home:
                    if target.lower() in (c.name or '').lower():
                        if c.health_current > 0:
                            return target
                return None  # Personagem nao esta disponivel
        return None

    def caern_preference(self) -> Optional[str]:
        """Retorna nome do Caern preferido."""
        prefs = self.get('caern_preferences', [])
        if prefs:
            return prefs[0].get('card_name')
        return None

    # ─── Target Priority ─────────────────────────────────────────────

    def get_target_rules(self) -> dict:
        """Retorna regras de prioridade de alvo."""
        return self.get('target_priority', {})

    def prefers_low_hp_targets(self) -> bool:
        """Prefere matar alvos com HP baixo primeiro."""
        return self.get('target_priority', {}).get('prefer_low_health', True)

    def get_ffa_diplomacy(self) -> str:
        """Retorna estrategia FFA: 'weaken_largest', 'protect_strongest', etc."""
        return self.get('target_priority', {}).get('ffa_diplomacy', 'weaken_largest')

    # ─── Umbra ───────────────────────────────────────────────────────

    def get_umbra_strategy(self) -> dict:
        """Retorna config de estrategia da Umbra."""
        return self.get('umbra_strategy', {})

    def should_enter_umbra(self, char_name: str,
                           game: GameState, player: PlayerState) -> Optional[bool]:
        """Retorna se um personagem especifico deve entrar na Umbra.

        Returns:
            True/False se config instrui, None se sem preferencia.
        """
        strategy = self.get_umbra_strategy()
        enter = strategy.get('enter_characters', [])
        keep = strategy.get('keep_in_umbra', [])
        # Se esta na lista de 'enter', deve entrar
        for entry in enter:
            if entry.lower() in char_name.lower():
                return True
        # Se esta na lista de 'keep', fica
        for entry in keep:
            if entry.lower() in char_name.lower():
                return True
        return None

    def always_enter_if_opponent_cannot(self) -> bool:
        """Sempre entra na Umbra se oponente nao pode seguir."""
        return self.get('umbra_strategy', {}).get(
            'always_enter_if_opponent_cannot', True)

    # ─── Redraw ──────────────────────────────────────────────────────

    def never_discard_names(self) -> list[str]:
        """Retorna lista de nomes de cartas que nunca devem ser descartadas."""
        return self.get('redraw_rules', {}).get('never_discard', [])

    def always_discard_ids(self) -> list[int]:
        """Retorna lista de card_ids que devem ser descartados se duplicados.

        Suporta slugs e card_ids na config.
        """
        rules = self.get('redraw_rules', {})
        ids: list[int] = []
        for ref in rules.get('always_discard_if_duplicate', []):
            if isinstance(ref, int):
                ids.append(ref)
            elif isinstance(ref, str):
                card = self._card_by_slug(ref)
                if card:
                    ids.append(card.id)
        return ids

    def should_keep_in_redraw(self, card: CardInstance) -> Optional[bool]:
        """Retorna se uma carta deve ser mantida no redraw.

        Returns:
            True se deve manter, False se deve descartar, None se sem opiniao.
        """
        never = self.never_discard_names()
        nome = (card.name or '').lower()
        for n in never:
            if n.lower() in nome:
                return True

        discard_ids = self.always_discard_ids()
        if card.card_id in discard_ids:
            return False

        return None

    # ─── Moot ────────────────────────────────────────────────────────

    def get_moot_strategy(self) -> dict:
        """Retorna config de estrategia de Moot."""
        return self.get('moot_strategy', {})

    def should_call_moot(self, card_type: str) -> bool:
        """Verifica se deve chamar Junta de certo tipo."""
        strategy = self.get_moot_strategy()
        call_if = strategy.get('call_if_available', [])
        for entry in call_if:
            if entry.lower() in card_type.lower():
                return True
        return False

    def should_vote_yes(self, moot_name: str, owner_id: str,
                        game: GameState, player_id: str) -> Optional[bool]:
        """Retorna se deve votar sim em uma Junta.

        Returns:
            True/False/None (None = usa heuristica padrao).
        """
        strategy = self.get_moot_strategy()
        always_yes = strategy.get('always_vote_yes', [])
        for entry in always_yes:
            if entry.lower() == 'own' and owner_id == player_id:
                return True
            if entry.lower() in moot_name.lower():
                return True

        vote_no = strategy.get('vote_no_against', [])
        for entry in vote_no:
            if entry.lower() == 'leader':
                lider = max(game.players,
                            key=lambda p: p.victory_points / max(p.renown_level, 1))
                if owner_id == lider.id:
                    return False
            if entry.lower() in moot_name.lower():
                return False

        return None

    # ─── FFA Diplomacy ───────────────────────────────────────────────

    def get_ffa_target(self, game: GameState,
                       player: PlayerState) -> Optional[str]:
        """Retorna ID do jogador a atacar em FFA baseado na config.

        Estrategias:
            'weaken_largest' — ataca o lider em VP
            'attack_weakest' — ataca o mais fraco
            'balanced' — ataca quem tem mais personagens
        """
        diplomacy = self.get_ffa_diplomacy()
        active = [p for p in game.players if not p.eliminado and p.id != player.id]
        if not active:
            return None

        if diplomacy == 'weaken_largest':
            lider = max(active, key=lambda p: p.victory_points)
            return lider.id
        elif diplomacy == 'attack_weakest':
            mais_fracao = min(active, key=lambda p: len(p.pack_home))
            return mais_fracao.id
        elif diplomacy == 'balanced':
            # Ataca quem tem mais personagens (maior ameaca imediata)
            ameaca = max(active, key=lambda p: len(p.pack_home))
            return ameaca.id

        return None

    def should_save_umbra_actions(self) -> bool:
        """Se config instrui a preservar acoes de Umbra."""
        return self.get('umbra_strategy', {}).get('save_umbra_actions', False)
