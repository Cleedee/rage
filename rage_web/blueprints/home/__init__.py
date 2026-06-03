import os

from flask import Blueprint, current_app, render_template

import rage_web.ext.repository as rep

raiz = Blueprint(
    "home",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/")


@raiz.get('/')
def index():
    # Estatisticas
    total_cards = rep.count_cards()
    total_decks = len(rep.find_all_decks())

    # Cartas por tipo (top 10)
    tipos = rep.count_cards_by_tipo()

    # Cartas por expansao (top 10)
    expansoes = rep.count_cards_by_expansion()

    # Decks recentes (ultimos 5)
    decks = rep.find_all_decks()[-5:][::-1]

    # Contagem de imagens baixadas
    img_dir = os.path.join(current_app.instance_path, 'images')
    imagens_baixadas = 0
    if os.path.isdir(img_dir):
        imagens_baixadas = len([
            f for f in os.listdir(img_dir) if f.endswith('.jpg')
        ])

    return render_template(
        'home/index.html',
        total_cards=total_cards,
        total_decks=total_decks,
        imagens_baixadas=imagens_baixadas,
        tipos=tipos,
        expansoes=expansoes,
        decks=decks,
    )
