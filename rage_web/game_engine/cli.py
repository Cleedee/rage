"""CLI de debug para testar partidas do Rage CCG via terminal.

Uso:
    from rage_web.game_engine.cli import RageCLI
    cli = RageCLI()
    cli.cmdloop()
"""

from __future__ import annotations

import cmd
import json
import os
import random
import shutil
import sys
import textwrap
from typing import Optional

from rage_web.game_engine.combat_queue import (
    start_combat, declare_action, reveal_all, feint_action,
    can_feint, resolve_combat, end_combat, get_declaration_summary,
    get_combatants, COMBAT_ACTIONS,
)
from rage_web.game_engine.state import (
    GameState, PlayerState, CardInstance, Zone,
)
from rage_web.game_engine.rules import PHASES


def _make_sample_card(card_id: int, name: str, card_type: str,
                      owner_id: str, rng: random.Random) -> CardInstance:
    """Cria uma carta de exemplo para testes."""
    health = rng.randint(3, 7)
    return CardInstance(
        card_id=card_id,
        name=name,
        card_type=card_type,
        zone=Zone.DECK_COMBAT,
        owner_id=owner_id,
        controller_id=owner_id,
        rage=rng.randint(1, 5),
        gnosis=rng.randint(1, 4),
        health=health,
        health_current=health,
    )


def create_sample_game(seed: int = 42) -> GameState:
    """Cria uma partida de exemplo com personagens e decks predefinidos.

    Args:
        seed: Semente aleatoria para geracao dos atributos.
    """
    g_rng = random.Random(seed)

    # Nomes de cartas de combate
    combat_names = [
        'Strike', 'Block', 'Dodge', 'Claw Swipe', 'Bite',
        'Tackle', 'Howl', 'Pounce', 'Rip', 'Tear',
        'Feint', 'Frenzy', 'Overpower', 'Side Step', 'Head Butt',
    ]
    sept_names = [
        'Moon Bridge', 'Rite of Passage', 'Pack Hunt', 'Territory Claim',
        'Spirit Gift', 'Tribal Unity', 'Caern Access', 'Moot Call',
        'Past Life', 'Quest for Glory', 'Battlefield', 'Event: Full Moon',
    ]
    character_names = [
        'Shadow Fang', 'Iron Claw', 'Storm Howler', 'Moon Chaser',
        'Red Talon', 'Silver Eye', 'Crinos Beast', 'Alpha Wolf',
    ]

    p1 = PlayerState(id='p1', name='Jogador 1')
    p2 = PlayerState(id='p2', name='Jogador 2')

    # Deck de combate do P1
    for i, name in enumerate(combat_names):
        card = _make_sample_card(100 + i, name, 'Combat Action', 'p1', g_rng)
        card.zone = Zone.DECK_COMBAT
        p1.deck_combat.append(card)

    # Deck de combate do P2
    for i, name in enumerate(combat_names):
        card = _make_sample_card(200 + i, name, 'Combat Action', 'p2', g_rng)
        card.zone = Zone.DECK_COMBAT
        p2.deck_combat.append(card)

    # Deck de sept
    for i, name in enumerate(sept_names):
        card = _make_sample_card(300 + i, name, 'Event', 'p1', g_rng)
        card.zone = Zone.DECK_SEPT
        p1.deck_sept.append(card)
        card = _make_sample_card(400 + i, name, 'Event', 'p2', g_rng)
        card.zone = Zone.DECK_SEPT
        p2.deck_sept.append(card)

    # Personagens iniciais no Pack Home Ground
    for i, name in enumerate(character_names[:4]):
        owner = 'p1' if i < 2 else 'p2'
        player = p1 if i < 2 else p2
        char = CardInstance(
            card_id=500 + i, name=name, card_type='Character',
            zone=Zone.PACK_HOME, owner_id=owner, controller_id=owner,
            rage=g_rng.randint(2, 5),
            gnosis=g_rng.randint(1, 4),
            health=g_rng.randint(4, 8),
            health_current=0,
        )
        char.health_current = char.health
        player.pack_home.append(char)

    g = GameState(players=[p1, p2], rng=g_rng)

    # Adiciona cartas com efeitos (modelo_id) no deck de combate
    from rage_web.game_engine.effects import CARTAS_EXEMPLO
    efeito_ids = list(CARTAS_EXEMPLO.keys())
    for i, mid in enumerate(efeito_ids):
        modelo = CARTAS_EXEMPLO[mid]
        # P1 recebe metade, P2 recebe a outra
        owner = 'p1' if i % 2 == 0 else 'p2'
        player = p1 if i % 2 == 0 else p2
        card = CardInstance(
            card_id=600 + i, name=modelo.nome, card_type=modelo.tipo,
            zone=Zone.DECK_COMBAT, owner_id=owner, controller_id=owner,
            modelo_id=mid,
            rage=0, gnosis=0, health=0, health_current=0,
        )
        # Insere no topo do deck para ser comprada primeiro
        player.deck_combat.insert(0, card)

    # Redraw inicial: mao cheia de sept + combat
    for p in g.players:
        p.draw_combat(p.hand_size_combat)
        p.draw_sept(p.hand_size_sept)

    return g


def _barra(valor: int, maximo: int, largura: int = 20) -> str:
    """Barra de progresso tipo [████░░░░] VP."""
    if maximo == 0:
        return f'│   VP: 0/{maximo}'
    preenchido = int((valor / maximo) * largura)
    bar = '█' * min(preenchido, largura) + '░' * (largura - min(preenchido, largura))
    return f'│ 🏆 VP [{bar}] {valor}/{maximo}'


def _sigla_tipo(tipo: str) -> str:
    """Sigla curta para tipo de carta."""
    mapa = {
        'Combat Action': '⚔️A',
        'Combat Event': '⚡E',
        'Action': '📋A',
        'Event': '📋E',
        'Gift': '🎁',
        'Equipment': '🛡️',
        'Ally': '🤝',
        'Enemy': '👹',
        'Victim': '🎯',
        'Territory': '🏞️',
        'Quest': '📜',
        'Battlefield': '🏴',
        'Rite': '🔮',
        'Moot': '🗣️',
    }
    if 'Character' in tipo:
        return '🧑'
    return mapa.get(tipo, '📄')


def _card_ref(c: CardInstance) -> str:
    """Retorna referencia curta de uma carta."""
    return f'#{c.card_id} {c.name}'


def _fmt_zone(zone: Zone) -> str:
    return zone.value.replace('_', ' ').title()


class RageCLI(cmd.Cmd):
    """REPL para debug do motor de jogo."""

    intro = textwrap.dedent("""\
        ╔══════════════════════════════════════╗
        ║   RAGE CCG - Terminal Debug          ║
        ║   Digite HELP para comandos          ║
        ╚══════════════════════════════════════╝
    """)
    prompt = 'rage> '

    def __init__(self, game: Optional[GameState] = None):
        super().__init__()
        self.game = game or create_sample_game()
        self.save_dir = '/tmp/rage_saves'
        os.makedirs(self.save_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------

    def do_STATUS(self, arg):
        """STATUS - Mostra o estado completo da partida."""
        g = self.game
        cp = g.current_player

        # ── Cabecalho ──
        fase_icone = {
            'redraw': '🔄', 'regeneration': '💚', 'resource': '🛠️',
            'umbra': '🌙', 'moot': '🗳️', 'combat': '⚔️',
        }
        icone = fase_icone.get(g.phase, '?')
        print()
        print(f'╔══ RAGE CCG — Turno {g.turn_number} {icone} {g.phase.upper()} ══╗')
        print(f'║ Vez de: {cp.name:40s}║')
        print(f'╚═══════════════════════════════════════════════════╝')

        if g.combat.alphas:
            print('┌─ 👑 Alphas ───────────────────────────────────┐')
            for pid, cid in g.combat.alphas.items():
                nome_p = next((p.name for p in g.players if p.id == pid), pid)
                # Encontra o nome da criatura
                nome_c = cid
                for p in g.players:
                    for c in p.pack_home + p.umbra:
                        if str(c.card_id) == cid:
                            nome_c = c.name
                            break
                is_atual = ' ⚡' if cid == g.combat.current_alpha else ''
                pos = ''
                if g.combat.alpha_order:
                    try:
                        idx = g.combat.alpha_order.index(cid)
                        pos = f' (#{idx+1}/{len(g.combat.alpha_order)})'
                    except ValueError:
                        pass
                print(f'│   {nome_p}: {nome_c}{pos}{is_atual}')
            print()

        if g.combat.is_active:
            self._show_combat_status()

        for p in g.players:
            eh_cp = ' 👈' if p.id == cp.id else ''
            print()
            print(f'┌─ {p.name}{eh_cp} ─────────────────────────────────┐')

            # Stats: VP, decks, discards
            print(f'│ {_barra(p.victory_points, p.renown_level, 20)}')
            print(f'│   VP {p.victory_points}/{p.renown_level}  '
                  f'Rage Pool: {p.rage_pool}  Gnosis Pool: {p.gnosis_pool}')
            print(f'│   📚 Combat: {len(p.deck_combat)} rest.  '
                  f'Sept: {len(p.deck_sept)} rest.')
            print(f'│   🗑️ D/C:{len(p.discard_combat)}  D/S:{len(p.discard_sept)}')

            # Pack Home (criaturas em jogo)
            if p.pack_home:
                print(f'│ 🏠 Pack Home ({len(p.pack_home)}):')
                for c in p.pack_home:
                    hp = f'{c.health_current}/{c.health}'
                    mods = ''
                    if c.modelo_id:
                        mods += ' ✨'
                    if c.rage or c.gnosis:
                        mods += f' R:{c.rage} G:{c.gnosis}'
                    print(f'│   [{c.card_id:4d}] {c.name:28s} '
                          f'❤️{hp:5s}{mods}')
            else:
                print(f'│ 🏠 Pack Home: (vazio)')

            # Umbra
            if p.umbra:
                print(f'│ 🌙 Umbra ({len(p.umbra)}):')
                for c in p.umbra:
                    print(f'│     [{c.card_id}] {c.name}')

            # Hunting Grounds
            hg_local = p.hunting_grounds
            if hg_local:
                print(f'│ 🎯 HG ({len(hg_local)}):')
                for c in hg_local:
                    s = f'│     [{c.card_id}] {c.name}'
                    if hasattr(c, 'health') and c.health:
                        s += f' ❤️{c.health_current}/{c.health}'
                    print(s)

            # Victory Pile
            if p.victory_pile:
                print(f'│ 🏆 VPs: {" | ".join(c.name for c in p.victory_pile)}')

            # Mao
            if p.hand:
                print(f'│ 🃏 Mao ({len(p.hand)}):')
                for i, c in enumerate(p.hand):
                    tipo_sigla = _sigla_tipo(c.card_type)
                    efeito = ' 🎴' if c.modelo_id else ''
                    rage_info = f' D:{c.damage}' if c.damage else ''
                    print(f'│   [{i:2d}] {c.name:30s} {tipo_sigla}{efeito}{rage_info}')

            # Discards recentes
            for disc_name, disc_list in [('⚔️ Combat disc.', p.discard_combat),
                                          ('🛡️ Sept disc.', p.discard_sept)]:
                if disc_list:
                    ultimos = disc_list[-3:]
                    print(f'│   {disc_name} ({len(disc_list)}): '
                          + ', '.join(c.name for c in ultimos))

        # ── Moot ──
        if g.moot_atual and not g.moot_atual.resolvido:
            print()
            print('┌─ 🗳️ Moot ───────────────────────────────────┐')
            print(f'│   {g.moot_atual.nome} '
                  f'({"Board" if g.moot_atual.is_board_meeting else "Moot"})')
            print(f'│   SIM: {g.moot_atual.votos_sim}  NAO: {g.moot_atual.votos_nao}')

        # ── Fase Lunar ──
        if g.lunar_phase:
            print()
            print('┌─ 🌙 Fase Lunar ──────────────────────────────┐')
            print(f'│   {g.lunar_phase.nome} (por {g.lunar_phase.dono_id})')
            print(f'├────────────────────────────────────────────────┤')

        # ── Hunting Grounds global ──
        print()
        print('┌─ Hunting Grounds (Global) ─────────────────────┐')
        if g.hunting_grounds_cards:
            for c in g.hunting_grounds_cards:
                hp = f' ❤️{c.health_current}/{c.health}' if hasattr(c, 'health') and c.health else ''
                print(f'│   [{c.card_id}] {c.name}{hp}')
        else:
            print(f'│   (vazio)')

        # ── Anunciador ──
        an = g.anunciador
        if an.tem_anuncio_ativo:
            print()
            print('┌─ 📢 Anuncio ──────────────────────────────────┐')
            e = an.anuncio_atual
            status_an = 'ANULADO' if e.anulado else an.estado.value.upper()
            print(f'│   {e.descricao} [{status_an}]')
            if an.estado.value == 'aguardando_modo':
                print(f'│   ⏳ Aguardando escolha de modo')
                if an.prompt_atual and 'modos' in an.prompt_atual:
                    for m in an.prompt_atual['modos']:
                        efs = ', '.join(m['efeitos'])
                        print(f'│     [{m["indice"]}] {m["descricao"]}  ({efs})')

        # ── Log ──
        print()
        print('┌─ Log (ultimas 8) ──────────────────────────────┐')
        if g.log:
            for entry in g.log[-8:]:
                print(f'│ {entry}')
        else:
            print(f'│ (vazio)')
        print()

    def _show_combat_status(self):
        g = self.game
        c = g.combat
        print(f'\n⚔️  COMBATE [{c.step.upper()}] ⚔️')
        print(f'   Atacantes: {", ".join(c.attackers)}')
        print(f'   Defensores: {", ".join(c.defenders)}')
        if c.last_to_declare:
            print(f'   Último a Declarar: {c.last_to_declare}')
        summary = get_declaration_summary(g)
        if 'declarations' in summary and summary['declarations']:
            for cid, action in summary['declarations'].items():
                print(f'   {cid}: {action}')
        elif 'declared_count' in summary:
            print(f'   Declaracoes: {summary["declared_count"]}')
        print()

        # Sistema de anuncio
        an = g.anunciador
        if an.tem_anuncio_ativo:
            e = an.anuncio_atual
            status_an = 'ANULADO' if e.anulado else an.estado.value.upper()
            print(f'  📢 Anuncio: {e.descricao} [{status_an}]')
            if an.estado.value == 'aguardando_modo':
                print(f'     ⏳ Aguardando escolha de modo')
        print()

    def do_DRAW(self, arg):
        """DRAW [combat|sept] [n] - Compra n cartas do deck.

        Padrao: DRAW combat 1
        Exemplos:
          DRAW              - compra 1 do deck de combate
          DRAW sept 2       - compra 2 do deck de sept
          DRAW combat 3     - compra 3 do deck de combate
        """
        g = self.game
        cp = g.current_player
        args = arg.split()
        deck_type = 'combat'
        count = 1

        if args:
            if args[0] in ('combat', 'sept'):
                deck_type = args[0]
                if len(args) > 1:
                    try:
                        count = max(1, int(args[1]))
                    except ValueError:
                        print('Uso: DRAW [combat|sept] [n]')
                        return
            else:
                try:
                    count = max(1, int(args[0]))
                except ValueError:
                    print('Uso: DRAW [combat|sept] [n]')
                    return

        if deck_type == 'combat':
            drawn = cp.draw_combat(count)
        else:
            drawn = cp.draw_sept(count)

        for c in drawn:
            g.add_log(f'{cp.name} comprou {c.name}')
            print(f'  Comprou: {c.name} ({c.card_type})')
        print(f'  Mao agora: {len(cp.hand)} cartas')

    def do_PLAY(self, arg):
        """PLAY <indice> - Joga uma carta da mao para o Pack Home.

        Exemplos:
          PLAY 0           - joga a carta no indice 0 da mao
        """
        g = self.game
        cp = g.current_player

        if not arg.strip():
            print('Uso: PLAY <indice>')
            return

        try:
            idx = int(arg.strip())
        except ValueError:
            print('Uso: PLAY <indice>')
            return

        if idx < 0 or idx >= len(cp.hand):
            print(f'Indice invalido. Mao tem {len(cp.hand)} cartas (0-{len(cp.hand)-1}).')
            return

        card = cp.hand[idx]

        # Verifica requisito de recrutamento para Allies (4.4.1)
        if 'Ally' in (card.card_type or ''):
            from rage_web.game_engine.rules import pode_recrutar_ally
            if not pode_recrutar_ally(cp, card):
                print(f'  Nao pode recrutar {card.name}: '
                      f'nenhum personagem atende o requisito'
                      f' ("{card.requires}")')
                return

        # Verifica requisitos para Totem Event
        if card.card_type == 'Event':
            from rage_web.game_engine.rules import (validar_totem_evento,
                                                      TOTEM_IDS)
            if card.card_id in TOTEM_IDS:
                if not validar_totem_evento(cp, card):
                    print(f'  Nao pode jogar Totem {card.name}: '
                          f'requisito de keyword nao atendido'
                          f' ("{card.requires}")')
                    return

        cp.hand.pop(idx)
        card.zone = Zone.PACK_HOME
        card.health_current = card.health
        cp.pack_home.append(card)
        g.add_log(f'{cp.name} jogou {card.name}')

        print(f'  Jogou: {card.name} ({card.card_type}) no Pack Home')

    def do_ANUNCIAR(self, arg):
        """ANUNCIAR <indice> - Anuncia uma carta de efeito da mao.

        A carta vai para o sistema de anuncio. Se tiver modos > 1,
        o motor pausa ate ESCOLHER o modo. O oponente pode
        RESPONDER ou ANULAR.

        Exemplos:
          ANUNCIAR 0       - anuncia carta no indice 0
        """
        g = self.game
        cp = g.current_player

        if g.anunciador.tem_anuncio_ativo:
            print('Ja ha um efeito anunciado. Resolva ou anule primeiro.')
            return

        if not arg.strip():
            print('Uso: ANUNCIAR <indice>')
            return

        try:
            idx = int(arg.strip())
        except ValueError:
            print('Uso: ANUNCIAR <indice>')
            return

        if idx < 0 or idx >= len(cp.hand):
            print(f'Indice invalido. Mao tem {len(cp.hand)} cartas.')
            return

        card = cp.hand[idx]
        if not card.modelo_id:
            print(f'Carta {card.name} nao tem modelo de efeitos.')
            return

        # Verifica requisitos de Rite
        if card.card_type == 'Rite':
            from rage_web.game_engine.rules import (pode_usar_rite,
                                                      validar_timing_rite)
            if not validar_timing_rite(card, g.phase):
                print(f'  {card.name}: Rito nao pode ser usado durante combate')
                return
            if not pode_usar_rite(cp, card):
                print(f'  {card.name}: nenhum personagem atende os requisitos'
                      f' (Renown {card.renown})')
                return

        # Verifica requisitos de Gift (Rage FOO Rule + timing)
        if card.card_type == 'Gift':
            from rage_web.game_engine.rules import (pode_usar_gift,
                                                      pode_usar_gift_para_presa,
                                                      validar_timing_gift,
                                                      validar_opponent_gift)
            # Valida timing
            if not validar_timing_gift(card, g.phase):
                print(f'  {card.name}: nao pode ser usado na fase "{g.phase}" '
                      f'(restricao de timing)')
                return
            # Valida 'opponent' = combat only
            if not validar_opponent_gift(card, g.phase):
                print(f'  {card.name}: usa "opponent" e so pode ser usado '
                      f'durante combate')
                return
            pode_normal = pode_usar_gift(cp, card)
            pode_presa = False
            # Durante combate, verifica se ha Presa que pode usar o Gift
            if g.combat and g.combat.is_active:
                for c in g.hunting_grounds_cards:
                    if c.health_current > 0:
                        ct = (c.card_type or '').lower()
                        if 'victim' in ct or 'enemy' in ct:
                            if str(c.card_id) in g.combat.defenders:
                                eh_atacante = g.combat.prey_attackers.get(cp.id, False)
                                if not eh_atacante:
                                    if pode_usar_gift_para_presa(c, card):
                                        pode_presa = True
                                        break
            if not pode_normal and not pode_presa:
                print(f'  Nao pode usar {card.name}: '
                      f'nenhum personagem/presa atende os requisitos'
                      f' ("{card.requires}")')
                return

        from rage_web.game_engine.anunciador import anunciar_e_resolver

        # Remove da mao e anuncia
        cp.hand.pop(idx)
        logs = anunciar_e_resolver(
            g, cp.id, str(card.card_id), card.modelo_id,
            modo_idx=None,  # Modo nao escolhido ainda
        )

        for log in logs:
            print(f'  {log}')

        # Se modo > 1 e nao foi escolhido, mostra prompt
        if g.anunciador.estado.value == 'aguardando_modo':
            prompt = g.anunciador.prompt_atual
            if prompt and 'modos' in prompt:
                print(f'\n  Escolha um modo para {card.name}:')
                for m in prompt['modos']:
                    efs = ', '.join(m['efeitos'])
                    print(f'    [{m["indice"]}] {m["descricao"]}  ({efs})')
                print(f'  Use: ESCOLHER <indice>')

    def do_ESCOLHER(self, arg):
        """ESCOLHER <indice> - Escolhe o modo de uma carta modal.

        Usado apos ANUNCIAR uma carta com modos > 1.
        """
        g = self.game

        if g.anunciador.estado.value != 'aguardando_modo':
            print('Nenhuma carta aguardando escolha de modo.')
            return

        if not arg.strip():
            print('Uso: ESCOLHER <indice>')
            return

        try:
            modo_idx = int(arg.strip())
        except ValueError:
            print('Uso: ESCOLHER <indice>')
            return

        erro = g.anunciador.escolher_modo(modo_idx)
        if erro:
            print(f'  Erro: {erro}')
            return

        # Resolve apos escolher o modo
        logs = g.anunciador.resolver(g)
        for log in logs:
            print(f'  {log}')

    def do_ANULAR(self, arg):
        """ANULAR - Anula o efeito anunciado atual.

        So funciona se houver um efeito pendente.
        """
        g = self.game
        cp = g.current_player

        if not g.anunciador.tem_anuncio_ativo:
            print('Nenhum efeito para anular.')
            return

        if g.anunciador.anular(g, cp.id):
            print(f'  Efeito anulado por {cp.name}.')
        else:
            print('  Nao foi possivel anular.')

    def do_ATTACK(self, arg):
        """ATTACK <id_atacante> [id_defensor] - Inicia combate entre criaturas.

        Os IDs sao mostrados no STATUS (ex: [500] Shadow Fang).
        Se id_defensor nao for informado, ataca o Hunting Grounds.

        Exemplos:
          ATTACK 500 501   - [500] ataca [501]
          ATTACK 500       - [500] ataca hunting grounds
        """
        g = self.game
        cp = g.current_player

        args = arg.split()
        if not args:
            print('Uso: ATTACK <id_atacante> [id_defensor]')
            return

        try:
            atk_id = args[0]
            def_id = args[1] if len(args) > 1 else 'hg'
        except (ValueError, IndexError):
            print('Uso: ATTACK <id_atacante> [id_defensor]')
            return

        # Verifica se o atacante existe e pertence ao jogador atual
        atacante = self._find_card(atk_id, cp)
        if not atacante:
            print(f'Criatura {atk_id} nao encontrada no seu Pack Home.')
            return

        defensores = []
        if def_id != 'hg':
            # Encontra defensor entre todos os jogadores
            defensor = None
            for p in g.players:
                defensor = self._find_card(def_id, p)
                if defensor:
                    break
            if not defensor:
                print(f'Criatura {def_id} nao encontrada.')
                return
            defensores = [def_id]
        else:
            # Resolve 'hg' para a melhor presa no Hunting Grounds
            alvo_hg = self._melhor_alvo_hg()
            if alvo_hg:
                defensores = [str(alvo_hg.card_id)]
                def_id = str(alvo_hg.card_id)
                print(f'  Atacando {alvo_hg.name} no Hunting Grounds...')
            else:
                print('  Nenhum alvo no Hunting Grounds.')
                return

        if start_combat(g, [atk_id], defensores):
            print(f'  Combate iniciado: {atacante.name} ataca {def_id}!')
        else:
            print('  Ja existe um combate ativo.')

    def do_DECLARE(self, arg):
        """DECLARE <card_id> <acao> - Declara acao de combate.

        Acoes validas: strike, block, dodge, claw, bite, feint,
                       ranged_strike, weapon_strike, use_gift,
                       use_equipment, flee

        Exemplos:
          DECLARE 500 strike
          DECLARE 501 block
        """
        g = self.game
        args = arg.split()
        if len(args) < 2:
            print('Uso: DECLARE <card_id> <acao>')
            print(f'Acoes: {", ".join(sorted(COMBAT_ACTIONS))}')
            return

        card_id = args[0]
        action = args[1].lower()

        if action not in COMBAT_ACTIONS:
            print(f'Acão invalida: {action}')
            print(f'Acoes: {", ".join(sorted(COMBAT_ACTIONS))}')
            return

        if declare_action(g, card_id, action):
            print(f'  {card_id} declarou {action}')
        else:
            print(f'  Nao foi possivel declarar {action} para {card_id}.')

    def do_REVEAL(self, arg):
        """REVEAL - Revela todas as acoes de combate declaradas."""
        g = self.game
        if reveal_all(g):
            print('  Acoes reveladas!')
            summary = get_declaration_summary(g)
            for cid, action in summary.get('declarations', {}).items():
                print(f'    {cid}: {action}')
            if g.combat.last_to_declare:
                print(f'  Ultimo a Declarar: {g.combat.last_to_declare} '
                      f'(pode usar FEINT)')
        else:
            print('  Nao foi possivel revelar.')

    def do_FEINT(self, arg):
        """FEINT <card_id> <nova_acao> - Troca a acao usando Feint.

        So funciona no Reveal Step para quem declarou por ultimo.

        Exemplo:
          FEINT 502 strike
        """
        g = self.game
        args = arg.split()
        if len(args) < 2:
            print('Uso: FEINT <card_id> <nova_acao>')
            return

        card_id = args[0]
        new_action = args[1].lower()

        if feint_action(g, card_id, new_action):
            print(f'  {card_id} usou Feint! Nova acao: {new_action}')
        else:
            print(f'  {card_id} nao pode usar Feint agora.')

    def do_RESOLVE(self, arg):
        """RESOLVE - Resolve o combate atual.
        Avanca por withdrawal -> between_rounds -> end.
        """
        g = self.game
        if resolve_combat(g):
            print('  Dano aplicado!')
            # Avanca steps de auto-advance ate end
            from rage_web.game_engine.combat_queue import advance_combat_step
            while g.combat.is_active and g.combat.step not in ('end',):
                if not advance_combat_step(g):
                    break
            print('  Combate resolvido!')
        else:
            print('  Nao foi possivel resolver o combate.')

    def do_ENDCOMBAT(self, arg):
        """ENDCOMBAT - Encerra o combate forcadamente."""
        g = self.game
        if end_combat(g):
            print('  Combate encerrado.')
        else:
            print('  Nao ha combate ativo.')

    def do_PASS(self, arg):
        """PASS - Passa a vez (muda para o proximo jogador)."""
        g = self.game
        cp = g.current_player
        cp.pass_turn()

        # Verifica se todos passaram
        all_passed = all(p.has_passed for p in g.players)
        if all_passed:
            g.next_phase()
            for p in g.players:
                p.reset_pass()
            g.add_log(f'Todos passaram. Avancando para {g.phase}')
            print(f'  Todos passaram. Fase atual: {g.phase.upper()}')
        else:
            g.next_player()
            g.add_log(f'{cp.name} passou. Vez de {g.current_player.name}')
            print(f'  {cp.name} passou. Vez de {g.current_player.name}')

    def do_NEXT(self, arg):
        """NEXT - Avanca forcadamente para a proxima fase."""
        g = self.game
        old_phase = g.phase
        g.next_phase()
        g.add_log(f'Avancou: {old_phase} -> {g.phase}')
        print(f'  Fase: {old_phase.upper()} -> {g.phase.upper()}')

    def do_SAVE(self, arg):
        """SAVE [nome] - Salva o estado atual da partida.

        Exemplos:
          SAVE partida1
        """
        name = arg.strip() or f'partida_t{g.turn_number:03d}'
        path = os.path.join(self.save_dir, f'{name}.json')

        # Serializacao simples
        data = {
            'turn_number': self.game.turn_number,
            'phase': self.game.phase,
            'current_player_index': self.game.current_player_index,
            'log': self.game.log[-50:],
        }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f'  Partida salva em {path}')

    def do_LOAD(self, arg):
        """LOAD <nome> - Carrega uma partida salva.

        Exemplo:
          LOAD partida1
        """
        name = arg.strip()
        if not name:
            print('Uso: LOAD <nome>')
            return
        path = os.path.join(self.save_dir, f'{name}.json')
        if not os.path.exists(path):
            print(f'  Arquivo nao encontrado: {path}')
            return

        with open(path) as f:
            data = json.load(f)

        self.game.turn_number = data['turn_number']
        self.game.phase = data['phase']
        self.game.current_player_index = data['current_player_index']
        self.game.log = data['log']
        print(f'  Partida carregada de {path}')

    def do_CARDS(self, arg):
        """CARDS - Lista todas as cartas em jogo com seus IDs."""
        g = self.game
        print()
        for p in g.players:
            print(f'── {p.name} ──')
            for zone_name, cards in [
                ('Pack Home', p.pack_home),
                ('Hunting Grounds', p.hunting_grounds),
                ('Mao', p.hand),
                ('Deck Combate', p.deck_combat),
                ('Deck Sept', p.deck_sept),
            ]:
                if cards:
                    print(f'  {zone_name}:')
                    for c in cards:
                        print(f'    [{c.card_id}] {c.name} ({c.card_type}) '
                              f'{c.health_current}/{c.health}')
        print()

    def do_HELP(self, arg):
        """HELP [comando] - Mostra ajuda detalhada.

        Exemplos:
          HELP
          HELP ATTACK
        """
        if arg.strip():
            super().do_help(arg)
        else:
            print()
            print('Comandos disponiveis:')
            print('  STATUS      - Mostra o estado da partida')
            print('  DRAW        - Compra cartas (combat|sept)')
            print('  PLAY <n>    - Joga carta da mao no Pack Home')
            print('  ANUNCIAR <n> - Anuncia carta de efeito')
            print('  ESCOLHER <n> - Escolhe modo de carta modal')
            print('  ANULAR      - Anula o efeito anunciado')
            print('  ATTACK      - Inicia combate')
            print('  DECLARE     - Declara acao de combate')
            print('  REVEAL      - Revela acoes declaradas')
            print('  FEINT       - Troca acao (Ultimo a Declarar)')
            print('  RESOLVE     - Resolve combate')
            print('  ENDCOMBAT   - Encerra combate')
            print('  PASS        - Passa a vez')
            print('  NEXT       - Avanca fase')
            print('  CARDS      - Lista cartas em jogo')
            print('  SAVE       - Salva partida')
            print('  LOAD       - Carrega partida')
            print('  HELP <cmd> - Ajuda detalhada')
            print('  QUIT       - Sai')
            print()

    def do_QUIT(self, arg):
        """QUIT - Sai do debugger."""
        print('Saindo...')
        return True

    def emptyline(self):
        """Nada faz com linha vazia."""
        pass

    # ------------------------------------------------------------------
    # Utilitarios
    # ------------------------------------------------------------------

    def _find_card(self, card_id_str: str, player: PlayerState
                   ) -> Optional[CardInstance]:
        """Busca carta por ID em todas as zonas de um jogador."""
        target_id = card_id_str
        for c in player.pack_home:
            if str(c.card_id) == target_id or c.name.startswith(target_id):
                return c
        for c in player.hunting_grounds:
            if str(c.card_id) == target_id:
                return c
        for c in player.hand:
            if str(c.card_id) == target_id:
                return c
        return None

    def _melhor_alvo_hg(self):
        """Encontra o melhor alvo Victim/Enemy/Battlefield no Hunting Grounds."""
        game = self.game
        TIPOS_HG = {'victim', 'enemy', 'battlefield'}
        candidatos = []
        for c in game.hunting_grounds_cards:
            ct = (c.card_type or '').lower()
            if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                candidatos.append(c)
        for p in game.players:
            for c in p.hunting_grounds:
                ct = (c.card_type or '').lower()
                if any(t in ct for t in TIPOS_HG) and c.health_current > 0:
                    candidatos.append(c)
        if not candidatos:
            return None
        candidatos.sort(key=lambda c: (c.renown or 1) / max(c.health_current, 1),
                        reverse=True)
        return candidatos[0]


def main():
    """Ponto de entrada para o CLI de debug."""
    import argparse
    parser = argparse.ArgumentParser(description='Rage CCG - Terminal Debug')
    parser.add_argument('--seed', type=int, default=42,
                        help='Seed aleatoria para o jogo de exemplo')
    args = parser.parse_args()

    game = create_sample_game(seed=args.seed)
    cli = RageCLI(game=game)

    try:
        cli.cmdloop()
    except KeyboardInterrupt:
        print('\nSaindo...')
        sys.exit(0)


# ------------------------------------------------------------------
# Construir partida a partir de decks do banco de dados
# ------------------------------------------------------------------

def build_game_from_decks_n(*deck_ids: int, seed: int = 42) -> GameState:
    """Converte N decks do banco SQLite em uma partida.

    Args:
        *deck_ids: IDs dos decks, um por jogador.
        seed: Semente aleatoria.
    """
    if len(deck_ids) < 2:
        raise ValueError('Precisa de pelo menos 2 decks')

    g_rng = random.Random(seed)

    from rage_web import create_app
    from rage_web.ext.database import db
    from rage_web.models.deck import Deck, deck_cards
    from rage_web.models.card import Card as CardModel

    flask_app = create_app()

    def _load_deck(deck_id: int) -> list[CardInstance]:
        """Carrega as cartas de um deck do banco."""
        from rage_web.game_engine.effects import CARTAS_EXEMPLO

        cards = []
        with flask_app.app_context():
            d = db.session.get(Deck, deck_id)
            if not d:
                raise ValueError(f'Deck {deck_id} nao encontrado')

            stmt = db.select(deck_cards).where(deck_cards.c.deck_id == deck_id)
            rows = db.session.execute(stmt).fetchall()

            uid = 1
            for row in rows:
                card_model = db.session.get(CardModel, row.card_id)
                if not card_model:
                    continue
                qtd = row.quantity
                for _ in range(qtd):
                    slug = card_model.slug or f'card_{card_model.id}'
                    modelo_id = slug if slug in CARTAS_EXEMPLO else None

                    ci = CardInstance(
                        card_id=card_model.id,
                        name=card_model.name,
                        card_type=card_model.tipo,
                        zone=Zone.OUT_OF_PLAY,
                        owner_id='',
                        controller_id='',
                        rage=card_model.rage or 0,
                        gnosis=card_model.gnosis or 0,
                        health=card_model.health or 0,
                        health_current=card_model.health or 0,
                        renown=card_model.renown or 0,
                        damage=card_model.damage or '',
                        text=card_model.text or '',
                        keywords=card_model.keyword or '',
                        modelo_id=modelo_id,
                    )
                    cards.append(ci)
                    uid += 1
        return cards

    sept_types = {'Event', 'Action', 'Territory', 'Caern', 'Quest',
                  'Battlefield', 'Rite', 'Moot', 'Board Meeting',
                  'Gift', 'Ally', 'Ally - Victim', 'Ally - Enemy', 'Ally - Caern',
                  'Victim', 'Enemy',
                  'Equipment', 'Equipment - Fetish - Bane Fetish'}

    players = []
    for idx, did in enumerate(deck_ids):
        pid = f'p{idx+1}'
        p = PlayerState(id=pid, name=f'Jogador {idx+1} (Deck {did})')
        # Define renown_level baseado no renown_cap do deck
        with flask_app.app_context():
            d = db.session.get(Deck, did)
            if d and d.renown_cap:
                p.renown_level = d.renown_cap
        players.append(p)

    for idx, did in enumerate(deck_ids):
        cards = _load_deck(did)
        g_rng.shuffle(cards)
        player = players[idx]
        for c in cards:
            c.owner_id = player.id
            c.controller_id = player.id
            if 'Character' in c.card_type:
                c.zone = Zone.PACK_HOME
                c.health_current = c.health
                player.pack_home.append(c)
            elif c.card_type in sept_types:
                c.zone = Zone.DECK_SEPT
                player.deck_sept.append(c)
            else:
                c.zone = Zone.DECK_COMBAT
                player.deck_combat.append(c)

    g = GameState(players=players, rng=g_rng)

    # Registra passivas para personagens que ja comecaram em jogo
    for p in g.players:
        for c in p.pack_home:
            g.register_card_passives(c, p)

    # Processa efeitos de setup (equipar_inicial, etc)
    from rage_web.game_engine.effects import ResolvedorEfeitos, EfeitoTipo
    for p in g.players:
        for c in p.pack_home:
            modelo_key = c.modelo_id or f'card_{c.card_id}'
            from rage_web.game_engine.effects import CARTAS_EXEMPLO
            modelo = CARTAS_EXEMPLO.get(modelo_key)
            if modelo and modelo.modos:
                for modo in modelo.modos:
                    for efeito in modo.efeitos:
                        if efeito.tipo == EfeitoTipo.EQUIPAR_INICIAL:
                            resolvedor = ResolvedorEfeitos(g)
                            resolvedor.aplicar_efeito(efeito, c, p)

    for p in g.players:
        p.draw_combat(p.hand_size_combat)
        if p.deck_sept:
            p.draw_sept(p.hand_size_sept)

    return g


def build_game_from_decks(deck1_id: int, deck2_id: int,
                          seed: int = 42) -> GameState:
    """Converte dois decks do banco SQLite em uma partida (compatibilidade).

    Args:
        deck1_id: ID do deck do jogador 1.
        deck2_id: ID do deck do jogador 2.
        seed: Semente aleatoria.
    """
    return build_game_from_decks_n(deck1_id, deck2_id, seed=seed)


if __name__ == '__main__':
    main()
