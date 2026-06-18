#!/usr/bin/env python3
"""Gera JSONs de efeitos estruturados para cartas em decks que ainda não têm JSON.

Prioriza cartas que estão em uso em decks registrados, tentando inferir
efeitos do texto quando possível.

Uso:
    .venv/bin/python3 scripts/gerar_deck_cards_jsons.py [--dry]
"""

import json, os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['ENVIRONMENT'] = 'default'

from rage_web import create_app
app = create_app('default')

CARDS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'cards')


def slug_curto(card) -> str:
    slug = card.slug or f'card_{card.id}'
    return f'card_{card.id}' if len(slug) > 40 else slug


def txt(card):
    return (card.text or '').strip()


def t_lower(card):
    return txt(card).lower()


def efeito_tipo_valido(t):
    """Verifica se um tipo de efeito existe no enum EfeitoTipo."""
    from rage_web.game_engine.effects import EfeitoTipo
    return t in set(e.value for e in EfeitoTipo)


def gerar_json(card):
    """Gera JSON para uma carta em deck sem JSON."""
    slug = slug_curto(card)
    nome = card.name
    texto = txt(card)
    tl = t_lower(card)
    ctype = (card.tipo or '').strip()
    ctype_lower = ctype.lower()
    json_id = card.slug if card.slug and len(card.slug) <= 40 else f'card_{card.id}'

    # ── Skip playtest / empty ──
    if not texto or 'playtesting' in tl:
        return None

    desc = nome
    efeitos = []

    # ── Action cards ──
    if ctype_lower == 'action':
        if 'friends in high places' in tl:
            efeitos.append({"tipo": "fugir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 99, "params": {"termina_combate": True, "sem_frenesi": True}})
            desc = "Termina 1 combate (sem frenesi)"
        elif 'sneak attack' in tl:
            efeitos.append({"tipo": "iniciar_combate", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"circunda_protocolo": True}})
            desc = "Ataca qualquer personagem/ally/enemy (circunda protocolo)"
        elif 'lend a hand' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"junta_combate_defensor": True}})
            desc = "Junta combate no lado do defensor"
        elif 'taunt' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"forca_aceitar_desafio": True, "entra_frenesi": True}})
            desc = "Forca inimigo a aceitar desafio e entrar em frenesi"
        elif 'stand like a fool' in tl:
            efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"tipo_acao": "combat_action", "duracao": "proximo_round"}})
            desc = "Oponente nao joga Combat Actions no prox round"
        elif 'shapeshift' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"muda_forma": True}})
            desc = "Muda de forma (Crinos <-> breed)"
        elif 'step sideways' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"zona": "umbra", "gauntlet_base": 3}})
            desc = "Step sideways para a Umbra (Gauntlet 3)"
        elif 'fast shift' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"zona": "umbra", "ignora_gauntlet": True}})
            desc = "Entra na Umbra imediatamente (ignora Gauntlet)"
        elif 'kid love' in tl or 'kids love' in tl:
            efeitos.append({"tipo": "destruir", "condicao_alvo": "territorio_inimigo",
                            "quantidade": 1, "params": {"remove_jogador_por_1_turno": True}})
            desc = "Remove 1 Territory (usuario sai por 1 turno)"
        elif 'legal chicanery' in tl:
            efeitos.append({"tipo": "remover_do_jogo", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"filtro": "homid_victim_ou_gaia_ally"}})
            desc = "Remove Homid victim ou Gaia ally do jogo"
        elif 'dominance' in tl:
            efeitos.append({"tipo": "anular", "condicao_alvo": "carta_em_jogo",
                            "quantidade": 0, "params": {"tipo_alvo": "action", "condicao": "renome_menor_ou_igual"}})
            desc = "Cancela Action card (Renome <= usuario)"
        elif 'recycle' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador",
                            "quantidade": 1, "params": {"condicao": "primeiro_ou_segundo_turno"}})
            desc = "Draw 1 sept card (se turno 1 ou 2)"
        elif 'animal attraction' in tl:
            efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"tipo": "ally_nao_spirit", "recruta_para_pack": True}})
            desc = "Recruta non-Spirit Ally para o pack"
        elif 'dust storm' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"restricao": "sem_acoes_pack", "duracao": "este_combate"}})
            desc = "Oponentes nao usam pack actions (Fera)"
        else:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
            desc = f"{nome} (REVISAO MANUAL)"

    # ── Event cards ──
    elif 'event' in ctype_lower or 'combat event' in ctype_lower:
        if 'mass pollution' in tl:
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "wyrm", "duracao": "permanente"}})
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_inimiga",
                            "quantidade": -1, "params": {"filtro": "nao_wyrm", "duracao": "permanente"}})
            desc = "Wyrm +1 Gnosis, non-Wyrm -1 Gnosis"
        elif 'beast-of-war' in tl or 'beast of war' in tl:
            efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                            "quantidade": 3, "params": {"duracao": "permanente"}})
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                            "quantidade": -1, "params": {"duracao": "permanente"}})
            desc = "+3 Rage, -1 Gnosis para o pack"
        elif 'iron will' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "imune_efeitos_acao_gift", "duracao": "permanente"}})
            desc = "Imune a efeitos de Combat Action/Gift que forcam perder acoes"
        elif 'spirit backlash' in tl:
            efeitos.append({"tipo": "destruir", "condicao_alvo": "equipamento_inimigo",
                            "quantidade": 0, "params": {"filtro": "fetish_gnosis>=5", "destruir_todos": True}})
            desc = "Destroi todo Fetish Equipment Gnosis >=5"
        elif 'new moon' in tl:
            efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"nao_pode_frenesi": True, "duracao": "permanente"}})
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "ragabash", "duracao": "permanente"}})
            desc = "Ninguem frenesi, Ragabash +1 Gnosis"
        elif 'urban renewal' in tl:
            efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"tipo_acao": "atacar_hg", "duracao": "este_turno"}})
            desc = "Alphas nao atacam Hunting Grounds este turno"
        elif 'saving face' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"forca_ser_alpha": True, "duracao": "proximo_combate"}})
            desc = "Alvo deve ser pack alpha no proximo Combat Phase"
        elif 'clashing boom boom' in tl or 'clashing boom' in tl:
            efeitos.append({"tipo": "dano", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"texto_original": texto[:120]}})
            desc = f"{nome} (Totem de guerra)"
        elif 'beast-of-war' in tl:
            pass  # already handled above
        elif 'boar' in tl:
            efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                            "quantidade": 2, "params": {"filtro": "homid_animal", "duracao": "permanente"}})
            efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "metis", "duracao": "permanente"}})
            desc = "+2 Health Homid/Animal, +1 Health Metis"
        elif 'checking the classifieds' in tl:
            efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"busca_no_sept_deck": True, "tipo_busca": "territory"}})
            desc = "Buscar Territory do sept deck"
        elif 'chimera' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"atributos": ["sept_hand_size"], "valor": 1, "duracao": "permanente"}})
            desc = "+1 sept hand size"
        elif 'corporate take-over' in tl or 'corporate takeover' in tl:
            efeitos.append({"tipo": "descarte", "condicao_alvo": "equipamento_inimigo",
                            "quantidade": 0, "params": {"filtro": "pentex", "descarta_1_equip": True}})
            desc = "Pentex descarta 1 Equipment cada"
        elif 'crescent moon' in tl:
            efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "spirit", "duracao": "permanente"}})
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "theurge", "duracao": "permanente"}})
            desc = "Spirits +1 Rage, Theurges +1 Gnosis"
        elif 'defiler' in tl:
            efeitos.append({"tipo": "equipar", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"toma_caern": True, "ignora_requisitos": True}})
            desc = "Toma qualquer Caern (ignora requisitos)"
        elif 'dragon' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"alpha_action_extra": True, "condicao": "mais_wyrm_que_gaia"}})
            desc = "+1 alpha action se mais Wyrm que Gaia"
        elif 'eater-of-souls' in tl or 'eater of souls' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "pode_equipar_fetish", "duracao": "permanente"}})
            desc = "Pack pode equipar Fetish Equipment"
        elif 'ethereal wind' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "ganha_kailindo", "duracao": "ate_fim_turno"}})
            desc = "1 criatura ganha Kailindo ate fim do turno"
        elif 'falcon' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["renown_moot"], "valor": 1, "duracao": "permanente"}})
            desc = "+1 Renown para moot voting"
        elif 'fog' in tl and 'cancela' not in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"restricao": "sem_combat_events_vs_nao_alpha", "duracao": "permanente"}})
            desc = "Oponentes nao usam Combat Events vs nao-alpha"
        elif 'fox frenzy' in tl:
            efeitos.append({"tipo": "remover_do_combate", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"fuga_combate": True}})
            desc = "Remove personagem do combate (fox frenzy)"
        elif 'frenzy' in tl and 'combat event' in ctype_lower:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"entra_frenesi": True}})
            desc = "Personagem entra em frenesi"
        elif 'full moon' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"crinos_livre": True, "ahroun_bonus": True, "duracao": "permanente"}})
            desc = "Crinos livre, Ahroun bonus"
        elif 'gaia\'s breath' in tl or "gaia's breath" in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"regeneracao_extra": 2, "filtro": "umbra", "duracao": "ate_equip_ally"}})
            desc = "Gaia na Umbra regenera +2 dano"
        elif 'gang beating' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador",
                            "quantidade": 1, "params": {"por_oponente_extra": True}})
            desc = "+1 combat card por oponente extra"
        elif 'gibbous moon' in tl:
            efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"filtro": "todos_garou", "condicao": "vs_enemy", "duracao": "permanente"}})
            desc = "Garou jogam damage cards +1 Rage vs Enemy"
        elif 'grandfather thunder' in tl:
            efeitos.append({"tipo": "modificar_rage", "condicao_alvo": "criatura_inimiga",
                            "quantidade": -1, "params": {"duracao": "permanente", "condicao": "vs_pack_member"}})
            desc = "Oponentes -1 Rage vs pack members"
        elif 'hunting party' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"pack_attack": True}})
            desc = "Pack attack (todos membros juntam)"
        elif 'lunar eclipse' in tl:
            efeitos.append({"tipo": "remover_do_jogo", "condicao_alvo": "carta_em_jogo",
                            "quantidade": 0, "params": {"remove_lunar_phase": True, "remove_auspice_gifts": True}})
            desc = "Remove Lunar Phase + todos Auspice Gifts"
        elif 'monsoon' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["renown"], "valor": 2, "condicao": "battlefields_pack_actions", "duracao": "este_turno"}})
            desc = "+2 Renown para Battlefields e pack actions"
        elif 'mountain sentai' in tl:
            desc = f"{nome} (REVISAO MANUAL - requisito complexo)"
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        elif 'no escape' in tl:
            efeitos.append({"tipo": "impedir_retirada", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"combate_continua": True}})
            desc = "Oponente nao pode retirar do combate"
        elif 'owl' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"restricao": "ver_mao_oponente", "duracao": "permanente", "frequencia": "1_vez_a_cada_2_turnos"}})
            desc = "Ver mao do oponente 1x a cada 2 turnos"
        elif 'pack defense' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"pack_defense": True, "max_renome": 15}})
            desc = "Pack defense (ate 15 Renome)"
        elif 'pegasus' in tl:
            efeitos.append({"tipo": "modificar_gnosis", "condicao_alvo": "criatura_aliada",
                            "quantidade": 1, "params": {"duracao": "permanente"}})
            desc = "+1 Gnosis para cada pack member"
        elif 'rally to battle' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador",
                            "quantidade": 3, "params": {"condicao": "3+_pack_members_em_combate"}})
            desc = "Draw 3 combat cards (se 3+ pack members em combate)"
        elif 'red alert' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "battle_form_imediata", "duracao": "2_turnos"}})
            desc = "Wyrm pode assumir Battle Form imediatamente"
        elif 'reinforcements' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"reforcos": True, "max_renome": 10, "apos_R3": True}})
            desc = "Ate 10 Renome em reforcos (apos R3)"
        elif 'rewards of leadership' in tl:
            efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"busca_no_deck": True, "tipo_busca": "ally/equipment/territory", "apos_junta": True}})
            desc = "Buscar Ally/Equipment/Territory do deck (apos Junta)"
        elif 'shieldmate' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"shieldmate": True}})
            desc = "Packmate junta como shieldmate + draw 1 combat card"
        elif 'sniper fire' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"sniper": True, "requer_firearm": True}})
            desc = "Packmate com Firearm junta combate"
        elif 'spiritual revelation' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"zona": "umbra", "filtro": "bane"}})
            desc = "Todos Bane vao para a Umbra"
        elif 'spring the trap' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"animal_form_join": True}})
            desc = "Packmate em Animal form junta combate"
        elif 'stuck sideways' in tl:
            efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"preso_umbra": True, "duracao": "ate_proxima_redraw"}})
            desc = "Personagem preso na Umbra ate prox Redraw"
        elif 'superior tactics' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"restricao": "so_pode_atacar_2_escolhidos", "duracao": "este_combate"}})
            desc = "Oponente so ataca 2 personagens escolhidos"
        elif 'surprise ally' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"surprise_ally": True}})
            desc = "Ally adicional junta combate"
        elif 'taking the death blow' in tl:
            efeitos.append({"tipo": "redirecionar", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"redireciona_dano_mortal": True}})
            desc = "Redireciona ferida mortal para outro pack member"
        elif 'the tide' in tl:
            efeitos.append({"tipo": "comprar_ate", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"busca_no_sept_deck": True, "tipo_busca": "human", "1x_por_turno": True}})
            desc = "Buscar Human do sept deck (1x/turno)"
        elif 'the whole nine yards' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"entra_frenesi_total": True, "imune_prevencao": True}})
            desc = "Frenesi total (imune a prevencao)"
        elif 'thrall of the wyrm' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"restricao": "ca_nao_bluff_vira_aleatorio", "duracao": "permanente"}})
            desc = "CA nao-bluff podem virar bluff aleatorio"
        elif 'town meeting' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"wyrm_pode_board_meeting": True, "kinfolk_vota": True}})
            desc = "Wyrm chama Board Meeting, Kinfolk vota"
        elif 'tzinzie' in tl:
            desc = f"{nome} (REVISAO MANUAL - efeito complexo)"
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        elif 'umbral wave' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"zona": "breed_form", "filtro": "umbra"}})
            desc = "Todos na Umbra revertem para breed form"
        elif 'unicorn' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"regeneracao_extra": 1, "duracao": "permanente"}})
            desc = "1 pack member regenera +1 carta de dano"
        elif 'visit from white father' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador",
                            "quantidade": 3, "params": {"condicao": "menos_vp"}})
            desc = "Pack com menos VP compra 3 sept cards"
        elif 'weasel' in tl:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "descarta_por_combat_action", "duracao": "permanente"}})
            desc = "Descarta 1 combat card p/ nao jogar CA este round"
        elif 'wendigo' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "jogador",
                            "quantidade": 0, "params": {"atributos": ["combat_hand_size"], "valor": 1, "duracao": "permanente"}})
            desc = "+1 combat hand size"
        elif 'whippoorwill' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "carta_em_jogo",
                            "quantidade": 0, "params": {"zona": "victory_pile", "filtro": "victim_ally_descartado", "face_down": True, "vpl": 1}})
            desc = "Victim/Ally descartado vai p/ VP face down (1 VP)"
        elif 'wyldstorm' in tl:
            desc = f"{nome} (REVISAO MANUAL - shuffle)"
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        elif 'wyrm taint' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_inimiga",
                            "quantidade": 0, "params": {"atributos": ["renown_moot"], "valor": -1, "filtro": "glass_walkers", "duracao": "permanente"}})
            desc = "Glass Walkers -1 Renown em moots"
        elif 'alaskan wolf hunt' in tl:
            efeitos.append({"tipo": "mover_para", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"zona": "hunting_grounds", "filtro": "red_talons", "forcado": True}})
            desc = "Red Talons vao para Hunting Grounds"
        elif 'ass whuppin' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"pack_attack_hunting_grounds": True}})
            desc = "Pack attack vs victim no HG"
        elif 'attacking the wyrm' in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"pack_attack_enemy_hg": True}})
            desc = "Pack attack vs enemy no HG"
        elif 'battle fervor' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 2})
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"restricao": "+1_combat_action_por_round", "duracao": "este_combate"}})
            desc = "+1 CA por round, draw 2 combat cards"
        elif 'close gauntlet' in tl:
            efeitos.append({"tipo": "impedir_acoes", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"tipo_acao": "step_sideways", "duracao": "este_turno"}})
            desc = "Ninguem step sideways este turno"
        elif 'covering fire' in tl:
            desc = f"{nome} (sem texto)"
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": ""}})
        elif 'cornered rat' in tl:
            efeitos.append({"tipo": "comprar", "condicao_alvo": "jogador", "quantidade": 3})
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"entra_frenesi_limitado": True}})
            desc = "Frenesi limitado + draw 3 combat cards"
        elif 'cub\'s cry' in tl or "cub's cry" in tl:
            efeitos.append({"tipo": "combar_acao", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"pack_action_cubs_cry": True}})
            desc = "Pack members leais juntam combate + draw 2"
        elif 'distracting spirits' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "carta_em_jogo",
                            "quantidade": 0, "params": {"atributos": ["engaging_renown"], "valor": -2, "filtro": "battlefields", "duracao": "1_turno"}})
            desc = "Battlefields -2 engaging Renown por 1 turno"
        elif 'crinos adapt' in tl:
            desc = f"{nome} (sem texto)"
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": ""}})
        else:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
            desc = f"{nome} (REVISAO MANUAL)"

    # ── Equipment with effects ──
    elif 'equipment' in ctype_lower or 'equip' in ctype_lower:
        if 'manling pendant' in tl:
            efeitos.append({"tipo": "modificar_vida", "condicao_alvo": "criatura_aliada",
                            "quantidade": 2, "params": {"duracao": "permanente"}})
            desc = "+2 Health"
        elif 'klaive' in tl and 'desert' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["dano_arma"], "valor": 4, "duracao": "permanente"}})
            desc = "Weapon: +4 dano"
        elif 'klaive' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["dano_arma"], "valor": 3, "duracao": "permanente"}})
            desc = "Weapon: +3 dano"
        elif 'pine dagger' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["dano_arma"], "valor": 1, "duracao": "permanente"}})
            desc = "Weapon: +1 dano"
        elif 'bane sword' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["dano_arma"], "valor": 3, "duracao": "permanente", "bane_fetish": True}})
            desc = "Bane Weapon: +3 dano"
        elif 'churjuroc' in tl:
            efeitos.append({"tipo": "modificar_atributo", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"atributos": ["dano_arma"], "valor": 2, "duracao": "permanente"}})
            desc = "Weapon: +2 dano"
        else:
            efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                            "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
            desc = f"{nome} (REVISAO MANUAL)"

    # ── Enemy ──
    elif 'enemy' in ctype_lower:
        # Most enemies are vanilla (just stats)
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Enemy - stats no banco)"

    # ── Ally ──
    elif 'ally' in ctype_lower:
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Ally - stats no banco)"

    # ── Victim ──
    elif 'victim' in ctype_lower:
        # Victims are vanilla
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_inimiga",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Victim - stats no banco)"

    # ── Caern ──
    elif 'caern' in ctype_lower:
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Caern - stats no banco)"

    # ── Moot ──
    elif 'moot' in ctype_lower:
        desc = f"{nome} (Moot)"
        efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})

    # ── Character (Gaia/Wyrm) ──
    elif 'character' in ctype_lower:
        # Characters are vanilla, stats in DB
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Character - stats no banco)"

    # ── Territory ──
    elif 'territory' in ctype_lower:
        efeitos.append({"tipo": "restringir", "condicao_alvo": "criatura_aliada",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})
        desc = f"{nome} (Territory - stats no banco)"

    # ── Generic / Unknown ──
    else:
        desc = f"{nome} ({ctype})"
        efeitos.append({"tipo": "restringir", "condicao_alvo": "todas_criaturas",
                        "quantidade": 0, "params": {"efeito_pendente": True, "texto_original": texto[:120]}})

    if not efeitos:
        return None

    modelo = {
        "id": json_id,
        "nome": nome,
        "tipo": ctype,
        "modos": [{
            "descricao": desc,
            "efeitos": efeitos
        }],
        "_metadata": {
            "fonte": "gerador_deck_cards_jsons",
            "card_id": card.id,
            "texto_original": texto,
            "keywords": card.keyword or "",
            "gnosis": card.gnosis or 0,
            "rage": card.rage or 0,
            "health": card.health or 0,
            "precisa_revisao": True,
            "slug": slug
        }
    }

    return modelo


def main():
    dry_run = '--dry' in sys.argv

    with app.app_context():
        from rage_web.game_engine.effects import CARTAS_EXEMPLO
        from rage_web.ext.database import db
        from rage_web.models.card import Card

        # Find all unique cards in decks
        from sqlalchemy import text as sa_text
        rows = db.session.execute(sa_text('''
            SELECT DISTINCT c.id FROM deck_cards dc JOIN card c ON c.id = dc.card_id
        ''')).fetchall()

        pendentes = []
        for (cid,) in rows:
            card = db.session.get(Card, cid)
            if not card:
                continue
            key = card.slug if card.slug else f'card_{cid}'
            if key not in CARTAS_EXEMPLO and f'card_{cid}' not in CARTAS_EXEMPLO:
                pendentes.append(card)

        print(f'Cartas em decks sem JSON: {len(pendentes)}')
        gerados = 0
        erros = 0
        pulados = 0

        for card in sorted(pendentes, key=lambda c: c.id):
            slug = slug_curto(card)
            try:
                modelo = gerar_json(card)
                if modelo is None:
                    print(f'  ⏭️  {card.name:<40s} (ID:{card.id})')
                    pulados += 1
                    continue

                path = os.path.join(CARDS_DIR, f'{slug}.json')
                if dry_run:
                    print(f'  📄 {slug}.json — {card.name:<40s} (ID:{card.id})')
                else:
                    with open(path, 'w') as f:
                        json.dump(modelo, f, indent=2, ensure_ascii=False)
                    print(f'  ✅ {slug}.json — {card.name:<40s} (ID:{card.id})')
                gerados += 1

            except Exception as e:
                print(f'  ❌ {card.name:<40s} (ID:{card.id}) — ERRO: {e}')
                import traceback; traceback.print_exc()
                erros += 1

        print(f'\nResumo: {gerados} gerados, {pulados} pulados, {erros} erros de {len(pendentes)}')


if __name__ == '__main__':
    main()
