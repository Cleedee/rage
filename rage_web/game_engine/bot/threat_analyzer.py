"""Analisador de ameaças para o PriorityBot.

Detecta cartas permanentes do oponente que afetam negativamente
o deck do bot e sugere respostas (destroy, remove, flee, cancel, block).

Módulo integrado ao priority_bot.py via métodos de análise.
"""

from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass, field


if TYPE_CHECKING:
    from rage_web.game_engine.state import CardInstance, GameState, PlayerState


@dataclass
class Threat:
    """Representa uma ameaça detectada."""
    card: 'CardInstance'          # A carta ameaçadora
    card_name: str                # Nome legível
    card_slug: str                # Slug para matching
    threat_type: str              # 'equipment', 'gift', 'caern', 'ally', 'character', 'enemy', 'modifier'
    severity: float               # 0.0–1.0 (1.0 = crítica)
    reason: str                   # Por que é ameaça
    target_uid: Optional[int] = None   # UID do personagem que carrega (para equipment/gift)
    target_name: Optional[str] = None  # Nome do portador
    response: str = 'attack'      # Resposta sugerida: 'attack', 'remove', 'flee', 'cancel', 'block'
    response_detail: str = ''     # Detalhe da resposta


# ── Catálogo de ameaças conhecidas ──────────────────────────────────────────

# Cada entrada: slug → (severity, threat_type, reason_template, response)
# severity é a BASE; pode ser ajustada pelo contexto do deck

THREAT_CATALOG: dict[str, tuple[float, str, str, str]] = {
    # ── Equipment ──
    'flak-jacket':            (0.50, 'equipment',
                               'Flak Jacket nega dano no portador',
                               'attack'),
    'flak-jacket_r1':         (0.50, 'equipment',
                               'Flak Jacket nega dano no portador',
                               'attack'),
    'skin-of-the-hellbound':  (0.40, 'equipment',
                               'Skin of Hellbound: imune a Rage 6+',
                               'attack_low_rage'),
    'war-knife-of-benning-simon': (0.55, 'equipment',
                                   'War Knife causa dano agravado',
                                   'avoid'),
    'bivouac':                (0.30, 'equipment',
                               'Bivouac: +1 Health/regeneration',
                               'attack'),
    'bivouac_r5':             (0.30, 'equipment',
                               'Bivouac: +1 Health/regeneration',
                               'attack'),
    'vampire-blood':          (0.35, 'equipment',
                               'Vampire Blood: cura todo turno',
                               'attack'),
    'vampire-blood_r1':       (0.35, 'equipment',
                               'Vampire Blood: cura todo turno',
                               'attack'),
    'the-silver-crown':       (0.45, 'equipment',
                               'Silver Crown: +6 Renown moot, +6 Gnosis',
                               'attack_bearer'),
    'elder-stone':            (0.20, 'equipment',
                               'Elder Stone: +3 Gnosis',
                               'ignore'),

    # ── Gifts ──
    'luna-s-armor':           (0.60, 'gift',
                               "Luna's Armor: +2 Health no portador",
                               'attack'),
    'resist-pain':            (0.50, 'gift',
                               'Resist Pain: sem reducao de Rage',
                               'attack'),
    'heightened-senses':      (0.35, 'gift',
                               "Heightened Senses: recusa challenges",
                               'challenge_other'),
    'stench-of-death':        (0.70, 'gift',
                               'Stench of Death: so spirits/Banes/Metis atacam',
                               'use_spirit_attack'),
    'spirit-of-the-fray':     (0.30, 'gift',
                               'Spirit of the Fray: ataca primeiro',
                               'attack_with_evasion'),
    'shroud':                 (0.65, 'gift',
                               'Shroud: encerra combate instantaneamente',
                               'attack_from_umbra'),
    'aegis':                  (0.40, 'gift',
                               'Aegis: +2 Health +2 Renown moot',
                               'attack'),
    'spirit-drain':           (0.55, 'gift',
                               'Spirit Drain: elimina espirito + cura total',
                               'avoid_spirit_combat'),

    # ── Caerns ──
    'sky-river-caern':        (0.50, 'caern',
                               'Sky River: nao-alfa nao pode ser desafiado',
                               'attack_alpha'),
    'hollow-heart-caern':     (0.40, 'caern',
                               'Hollow Heart: Gnosis nao reduz forcadamente',
                               'attack_with_rage'),
    'caern-of-rytthiku':      (0.55, 'caern',
                               'Rytthiku: oponente ganha VP matando HG',
                               'clear_hg'),
    'court-of-five-chambers': (0.25, 'caern',
                               'Court of 5 Chambers: compra 2 combat cards',
                               'ignore'),

    # ── Pack Totems ──
    'falcon':                 (0.30, 'pack_totem',
                               'Falcon: +1 Renown por membro em moots',
                               'reduce_moot_power'),

    # ── Enemies ──
    'hogling':                (0.30, 'enemy',
                               'Hogling: enemy no HG, da VP c/ Caern Rytthiku',
                               'kill_hg'),
    'corrupt-kinfolk_r3':     (0.45, 'enemy',
                               'Corrupt Kinfolk: ataca maior Renome no fim do turno',
                               'kill_hg'),
    'fomori-cop_r5':          (0.40, 'enemy',
                               'Fomori Cop: descarta carta do deck de combate',
                               'kill_hg'),

    # ── Territories ──
    'ancestral-burial-mounds': (0.35, 'territory',
                                'Burial Mounds: fonte de Rage para Wendigo',
                                'attack_owner'),
    'backwoods-kinfolk-hideaway': (0.30, 'territory',
                                   'Hideaway: Kinfolk Allies +1 Health e regeneram',
                                   'attack_owner'),
    'toxic-waste-dump':       (0.50, 'territory',
                                'Toxic Waste: dano a personagens Gaia no inicio de cada turno',
                                'destroy_territory'),
    'shadow-lord-territory':  (0.40, 'territory',
                                'Shadow Lord Territory: +1 Rage para Shadow Lords',
                                'attack_owner'),
    'silver-fang-territory':  (0.35, 'territory',
                                'Silver Fang Territory: +1 Renown moot para Silver Fangs',
                                'attack_owner'),
    'glass-walker-territory': (0.30, 'territory',
                                'Glass Walker Territory: bonus tecnologia',
                                'attack_owner'),
    'stargazer-territory':    (0.35, 'territory',
                                'Stargazer Territory: bonus Gnosis',
                                'attack_owner'),
    'black-fury-territory':   (0.35, 'territory',
                                'Black Fury Territory: bonus para Black Furies',
                                'attack_owner'),
    'children-of-gaia-territory': (0.30, 'territory',
                                   'Children of Gaia Territory: bonus cura',
                                   'attack_owner'),
    'silent-strider-territory': (0.40, 'territory',
                                 'Silent Strider Territory: bonus Umbra',
                                 'attack_owner'),
    'red-talon-territory':    (0.35, 'territory',
                                'Red Talon Territory: bonus Lupus',
                                'attack_owner'),
    'wendigo-territory':      (0.40, 'territory',
                                'Wendigo Territory: bonus Rage para Wendigo',
                                'attack_owner'),
    'uktena-territory':       (0.35, 'territory',
                                'Uktena Territory: bonus magia',
                                'attack_owner'),
    'fianna-territory':       (0.30, 'territory',
                                'Fianna Territory: bonus gifts',
                                'attack_owner'),
    'get-of-fenris-territory': (0.35, 'territory',
                                 'Get of Fenris Territory: bonus combate',
                                 'attack_owner'),
    'bone-gnawer-territory':  (0.25, 'territory',
                                'Bone Gnawer Territory: bonus sobrevivencia',
                                'attack_owner'),

    # ── Battlefields ──
    'urban-clash':            (0.45, 'battlefield',
                                'Urban Clash: +2 combat cards para atacante/defensor',
                                'contest_battlefield'),
    'village-annexation':     (0.40, 'battlefield',
                                'Village Annexation: +2 combat cards',
                                'contest_battlefield'),
    'warehouse-brawl':        (0.35, 'battlefield',
                                'Warehouse Brawl: +1 combat card, sem armas',
                                'contest_battlefield'),
    'war-of-attrition':       (0.55, 'battlefield',
                                'War of Attrition: +4 combat cards, Ren20',
                                'contest_battlefield'),
    'battle-of-screaming-mud': (0.60, 'battlefield',
                                 'Battle of Screaming Mud: Rn:10, +4 cards, 1/2 Rage',
                                 'contest_battlefield'),
    'caern-siege':            (0.50, 'battlefield',
                                'Caern Siege: batalha por Caern',
                                'contest_battlefield'),

    # ── Combat Event ──
    'iron-will':              (0.50, 'event',
                               'Iron Will: protege contra gifts inimigos',
                               'use_combat_actions'),
    'taking-the-death-blow':  (0.40, 'combat_event',
                               'Taking the Death Blow: redireciona ferimento',
                               'attack_multiple'),
    'fox-frenzy':             (0.35, 'combat_event',
                               'Fox Frenzy: remove do combate',
                               'attack_from_umbra'),
    'frenzy':                 (0.30, 'combat_event',
                               'Frenzy: enlouquece personagem',
                               'avoid'),

    # ── Allies ──
    'dreamspeaker-mage':      (0.50, 'ally',
                               'Dreamspeaker Mage: pode cancelar qualquer Gift',
                               'attack_ally'),
    'flame-spirit':           (0.35, 'ally',
                               'Flame Spirit: ataque dano 3 agravado',
                               'attack_ally'),
}


class ThreatAnalyzer:
    """Analisa o tabuleiro do oponente e detecta ameaças."""

    def __init__(self, game: 'GameState', player_id: str):
        self.game = game
        self.player_id = player_id
        self._opponents: list['PlayerState'] = [
            p for p in game.players if p.id != player_id
        ]

    def _slugify(self, name: str) -> str:
        """Gera slug a partir de nome (lowercase, hífens)."""
        return name.lower().replace(' ', '-').replace('\'', '').replace(',', '')

    def _find_card_slug(self, card: 'CardInstance') -> str:
        """Retorna o slug de uma card instance."""
        modelo_id = getattr(card, 'modelo_id', None)
        if modelo_id:
            return modelo_id
        slug = self._slugify(card.name)
        if slug in THREAT_CATALOG:
            return slug
        # Tenta match parcial
        for key in THREAT_CATALOG:
            if key.startswith(slug) or slug.startswith(key):
                return key
        return slug

    def _scan_equipment_gifts(self, owner: 'PlayerState') -> list[Threat]:
        """Escaneia equipmentos e gifts anexados a personagens do oponente."""
        ameacas = []
        for char in owner.pack_home:
            ct = (char.card_type or '').lower()
            if 'character' not in ct and 'ally' not in ct:
                continue
            if char.health_current <= 0:
                continue
            # Verifica equipamentos anexados
            for eq in getattr(char, 'equipment', []):
                slug = self._find_card_slug(eq)
                if slug in THREAT_CATALOG:
                    base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                    ameacas.append(Threat(
                        card=eq,
                        card_name=eq.name,
                        card_slug=slug,
                        threat_type=ttype,
                        severity=base_sev,
                        reason=reason,
                        target_uid=id(char),
                        target_name=char.name,
                        response=resp,
                        response_detail=f'Equipamento {eq.name} em {char.name}',
                    ))
            # Verifica gifts ativos (via game_modifiers com card_uid)
            for m in self.game.game_modifiers:
                if m.ativo and m.card_uid == id(char):
                    mod_slug = m.modifier
                    if mod_slug in THREAT_CATALOG and mod_slug not in [t.card_slug for t in ameacas]:
                        base_sev, ttype, reason, resp = THREAT_CATALOG[mod_slug]
                        ameacas.append(Threat(
                            card=char,
                            card_name=char.name,
                            card_slug=mod_slug,
                            threat_type='gift',
                            severity=base_sev,
                            reason=reason,
                            target_uid=id(char),
                            target_name=char.name,
                            response=resp,
                            response_detail=f'Gift ativo em {char.name}',
                        ))
        return ameacas

    def _scan_caerns(self, owner: 'PlayerState') -> list[Threat]:
        """Escaneia caerns do oponente."""
        ameacas = []
        for c in owner.pack_home:
            ct = (c.card_type or '').lower()
            if 'caern' not in ct:
                continue
            slug = self._find_card_slug(c)
            if slug in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                ameacas.append(Threat(
                    card=c, card_name=c.name, card_slug=slug,
                    threat_type=ttype, severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'Caern {c.name} do oponente',
                ))
        return ameacas

    def _scan_modifiers(self) -> list[Threat]:
        """Escaneia modificadores globais ativos que afetam o bot."""
        ameacas = []
        for m in self.game.game_modifiers:
            if not m.ativo:
                continue
            mod = m.modifier
            if mod in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[mod]
                ameacas.append(Threat(
                    card=None, card_name=mod, card_slug=mod,
                    threat_type='modifier', severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'Modificador global: {mod}',
                ))
        return ameacas

    def _scan_opponent_chars(self, owner: 'PlayerState') -> list[Threat]:
        """Escaneia personagens do oponente que sao ameacas por si so."""
        ameacas = []
        for char in owner.pack_home:
            ct = (char.card_type or '').lower()
            if 'character' not in ct:
                continue
            if char.health_current <= 0:
                continue
            severity = 0.0
            razões = []
            # Alta Rage = ameaca ofensiva
            if char.rage >= 6:
                severity += 0.25
                razões.append(f'Rage {char.rage}')
            # Alta Gnosis = ameaca de gifts
            if char.gnosis >= 7:
                severity += 0.15
                razões.append(f'Gnosis {char.gnosis}')
            # Alta Health = dificil de matar
            if char.health_current >= 6:
                severity += 0.15
                razões.append(f'Health {char.health_current}')
            # Muitos equipamentos
            eq_list = getattr(char, 'equipment', [])
            if len(eq_list) >= 2:
                severity += 0.20
                razões.append(f'{len(eq_list)} equipamentos')
            if severity >= 0.30:
                ameacas.append(Threat(
                    card=char, card_name=char.name,
                    card_slug=self._slugify(char.name),
                    threat_type='character',
                    severity=min(severity, 1.0),
                    reason='; '.join(razões),
                    target_uid=id(char),
                    target_name=char.name,
                    response='attack',
                    response_detail=f'Personagem forte: {char.name}',
                ))
        return ameacas

    def _scan_enemies_hg(self) -> list[Threat]:
        """Escaneia inimigos/presas no HG (do oponente e global)."""
        ameacas = []
        # HG de cada oponente
        for p in self._opponents:
            for c in p.hunting_grounds:
                ct = (c.card_type or '').lower()
                if 'enemy' not in ct and 'victim' not in ct:
                    continue
                slug = self._find_card_slug(c)
                if slug in THREAT_CATALOG:
                    base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                    ameacas.append(Threat(
                        card=c, card_name=c.name, card_slug=slug,
                        threat_type=ttype, severity=base_sev,
                        reason=reason, response=resp,
                        response_detail=f'{c.name} no HG do oponente',
                    ))
        # HG global (cartas sem dono ou de todos)
        for c in self.game.hunting_grounds_cards:
            ct = (c.card_type or '').lower()
            if 'enemy' not in ct and 'victim' not in ct:
                continue
            slug = self._find_card_slug(c)
            if slug in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                dono_nome = ''
                if c.owner_id:
                    d = self._find_player(c.owner_id)
                    if d:
                        dono_nome = f' (dono: {d.name})'
                ameacas.append(Threat(
                    card=c, card_name=c.name, card_slug=slug,
                    threat_type=ttype, severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'{c.name} no HG global{dono_nome}',
                ))
        return ameacas

    def _scan_territories(self, owner: 'PlayerState') -> list[Threat]:
        """Escaneia Territories do oponente.

        Territories sao permanentes que concedem bonus ao dono
        ou penalidades ao oponente. Ex: Shadow Lord Territory
        da +1 Rage para Shadow Lords.
        """
        ameacas = []
        for c in owner.pack_home:
            ct = (c.card_type or '').lower()
            if 'territory' not in ct:
                continue
            slug = self._find_card_slug(c)
            if slug in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                ameacas.append(Threat(
                    card=c, card_name=c.name, card_slug=slug,
                    threat_type=ttype, severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'Territory {c.name} do oponente',
                ))
        return ameacas

    def _scan_battlefields(self) -> list[Threat]:
        """Escaneia Battlefields no HG.

        Battlefields sao cartas no HG que geram VP e concedem
        bonus de combate para atacantes/defensores.
        """
        ameacas = []
        fonte_cartas = list(self.game.hunting_grounds_cards)
        for p in self.game.players:
            fonte_cartas.extend(p.hunting_grounds)
        for c in fonte_cartas:
            ct = (c.card_type or '').lower()
            if 'battlefield' not in ct:
                continue
            slug = self._find_card_slug(c)
            if slug in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                ameacas.append(Threat(
                    card=c, card_name=c.name, card_slug=slug,
                    threat_type=ttype, severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'Battlefield {c.name} no HG',
                ))
        return ameacas

    def _scan_opponent_actives(self, owner: 'PlayerState') -> list[Threat]:
        """Escaneia Action/Event cards ativos do oponente.

        Alguns Events e Actions sao jogados e permanecem em jogo
        (Pack Totems como Wendigo/Falcon).
        """
        ameacas = []
        for c in owner.pack_home:
            ct = (c.card_type or '').lower()
            if ct not in ('action', 'event'):
                continue
            slug = self._find_card_slug(c)
            if slug in THREAT_CATALOG:
                base_sev, ttype, reason, resp = THREAT_CATALOG[slug]
                ameacas.append(Threat(
                    card=c, card_name=c.name, card_slug=slug,
                    threat_type=ttype, severity=base_sev,
                    reason=reason, response=resp,
                    response_detail=f'{ct.title()} ativo: {c.name}',
                ))
        return ameacas

    def _find_player(self, player_id: str) -> Optional['PlayerState']:
        """Busca jogador por ID."""
        for p in self.game.players:
            if p.id == player_id:
                return p
        return None

    def analyze(self) -> list[Threat]:
        """Analisa todas as ameaças no tabuleiro.

        Returns:
            Lista de Threat ordenada por severidade (maior primeiro).
        """
        todas: list[Threat] = []
        for opp in self._opponents:
            todas.extend(self._scan_equipment_gifts(opp))
            todas.extend(self._scan_caerns(opp))
            todas.extend(self._scan_territories(opp))
            todas.extend(self._scan_opponent_chars(opp))
            todas.extend(self._scan_opponent_actives(opp))
        todas.extend(self._scan_modifiers())
        todas.extend(self._scan_enemies_hg())
        todas.extend(self._scan_battlefields())

        # Ordena por severidade decrescente
        todas.sort(key=lambda t: (-t.severity, t.threat_type))
        return todas[:20]  # Limita a 20 ameaças

    def top_threat(self) -> Optional[Threat]:
        """Retorna a maior ameaça atual."""
        ameacas = self.analyze()
        return ameacas[0] if ameacas else None

    def threats_by_type(self, threat_type: str) -> list[Threat]:
        """Filtra ameaças por tipo."""
        return [t for t in self.analyze() if t.threat_type == threat_type]

    def threat_severity_for(self, slug: str) -> float:
        """Retorna a severidade de um slug específico no tabuleiro."""
        for t in self.analyze():
            if t.card_slug == slug:
                return t.severity
        return 0.0

    def get_threat_response(self, slug: str) -> Optional[str]:
        """Retorna a resposta recomendada para um slug."""
        for t in self.analyze():
            if t.card_slug == slug:
                return t.response
        return None

    def top_threat_target(self) -> Optional['CardInstance']:
        """Retorna a CardInstance da maior ameaça."""
        t = self.top_threat()
        if t:
            return t.card
        return None
