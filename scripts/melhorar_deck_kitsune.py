#!/usr/bin/env python3
"""Melhora o deck Kitsune — Raposas da Fortuna (ID 1045).

Problema: Rage media 1.8 (todos personagens R1-R2).
Solucao: Trocar personagens fracos por versoes mais fortes.

Mudancas:
  1. Mei-Fei Quan (R1 G1 H1, Renown 1) → Morgan the Unworthy (R4 G6 H3, Renown 3)
  2. Ozatu Junichiro (R2 G4 H1, Renown 3) → Freide Counts-the-Scalps (R3 G3 H3, Renown 3)

Nova media de Rage: (4+3+2+2+2)/5 = 2.6 (era 1.8)
Novo Renown de personagens: 3+3+4+6+5 = 21 (era 19)
"""

import os, sys, json

DECK_ID = 1045
NOVO_PREFIXO = 'deckkitsune'

# Templates JSON para as novas cartas
NOVOS_TEMPLATES = {
    193: {  # Morgan the Unworthy
        "id": "morgan-the-unworthy",
        "nome": "Morgan the Unworthy",
        "tipo": "Character - Gaia",
        "modos": [
            {
                "descricao": "Gifts e Rites podem falhar aleatoriamente",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["gnosis"],
                            "valor": 1,
                            "filtro": "nome=Morgan the Unworthy"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 193,
            "texto_original": "Born mad as a hatter, Morgan has embraced the half moon of his birth sign. Every time Morgan uses a Gift or Rite decide randomly whether it works or is discarded (equal chance for each).",
            "precisa_revisao": True,
            "slug": "morgan-the-unworthy"
        }
    },
    70: {  # Freide Counts-the-Scalps
        "id": "freide-counts-the-scalps",
        "nome": "Freide Counts-the-Scalps",
        "tipo": "Character - Gaia",
        "modos": [
            {
                "descricao": "Once per game, double 1 statistic",
                "efeitos": [
                    {
                        "tipo": "modificar_atributo_passivo",
                        "condicao_alvo": "criatura_aliada",
                        "params": {
                            "atributos": ["rage"],
                            "valor": 0,
                            "filtro": "nome=Freide Counts-the-Scalps"
                        }
                    }
                ]
            }
        ],
        "_metadata": {
            "fonte": "novo_deck_kitsune",
            "card_id": 70,
            "texto_original": "Freide has inherited the madness of Gaia's sister Luna. Once per game, she may double any 1 of her statistics (Rage, Gnosis, or Health) for 1 full turn as she looks to the moon for insight.",
            "precisa_revisao": True,
            "slug": "freide-counts-the-scalps"
        }
    }
}


def criar_json_direto(card_id: int, prefix: str):
    """Cria JSON de efeito para uma carta."""
    json_path = f'data/cards/auto_{prefix}_{card_id}.json'
    if os.path.exists(json_path):
        print(f'  JSON ja existe: {json_path}')
        return True

    template = NOVOS_TEMPLATES.get(card_id)
    if not template:
        print(f'  [AVISO] Sem template para card_id={card_id}')
        return False

    with open(json_path, 'w') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    print(f'  JSON criado: {json_path}')
    return True


def main():
    os.environ['ENVIRONMENT'] = 'default'
    sys.path.insert(0, '/workspace')

    from rage_web.ext.database import db
    from rage_web import create_app
    from rage_web.models.card import Card
    from rage_web.models.deck import Deck
    import rage_web.ext.repository as rep
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        d = Deck.query.get(DECK_ID)
        if not d:
            print(f'[ERRO] Deck {DECK_ID} nao encontrado!')
            return

        print(f'Deck: {d.name} (ID {d.id})')

        substituicoes = [
            (1676, 193, "Mei-Fei (R1) → Morgan (R4)"),
            (1679, 70, "Ozatu (R2) → Freide (R3)"),
        ]

        for remover_id, adicionar_id, razao in substituicoes:
            remover = Card.query.get(remover_id)
            adicionar = Card.query.get(adicionar_id)

            if not remover:
                print(f'  [ERRO] Carta {remover_id} para remover nao encontrada!')
                continue
            if not adicionar:
                print(f'  [ERRO] Carta {adicionar_id} para adicionar nao encontrada!')
                continue

            qty = db.session.execute(
                text('SELECT quantity FROM deck_cards WHERE deck_id = :did AND card_id = :cid'),
                {'did': DECK_ID, 'cid': remover_id}
            ).fetchone()

            if not qty or qty[0] == 0:
                print(f'  [AVISO] {remover.name} (ID {remover_id}) nao esta no deck. Pulando.')
                continue

            print(f'\n  Removendo: {remover.name} (R{remover.rage} H{remover.health} Renown={remover.renown})')
            rep.deck_remove_card(d, remover)

            print(f'  Adicionando: {adicionar.name} (R{adicionar.rage} G{adicionar.gnosis} H{adicionar.health} Renown={adicionar.renown})')
            print(f'  Razao: {razao}')
            rep.deck_add_card(d, adicionar, 1)

        # Atualizar descricao
        d.description = 'Kitsune (werefoxes) Hengeyokai Renown 20. Místicos e estrategistas. Melhorado: Rage media 2.6.'

        db.session.commit()

        print(f'\n--- Deck atualizado ---')
        print(f'Cartas agora: {len(d.cards)}')

        chars = []
        for card in d.cards:
            if 'character' in (card.tipo or '').lower():
                chars.append(card)

        chars_sorted = sorted(chars, key=lambda c: c.rage, reverse=True)
        avg_rage = sum(c.rage for c in chars_sorted) / len(chars_sorted) if chars_sorted else 0
        print(f'Personagens: {len(chars_sorted)}, Rage media: {avg_rage:.1f}')
        for c in chars_sorted:
            print(f'  {c.name:30s} R{c.rage} G{c.gnosis} H{c.health} Renown={c.renown}')

        # Gerar JSONs
        print(f'\n--- Gerando JSONs ---')
        for remover_id, adicionar_id, _ in substituicoes:
            criar_json_direto(adicionar_id, NOVO_PREFIXO)
            # Remover JSON da carta antiga (opcional: manter para referencia)
            json_antigo = f'data/cards/auto_{NOVO_PREFIXO}_{remover_id}.json'
            if os.path.exists(json_antigo):
                os.remove(json_antigo)
                print(f'  JSON removido: auto_{NOVO_PREFIXO}_{remover_id}.json')

        # Checklist
        print(f'\n--- Checklist ---')
        import subprocess
        subprocess.run(
            ['python3', 'scripts/gerar_checklist.py', str(DECK_ID)],
            cwd='/workspace'
        )


if __name__ == '__main__':
    main()
