#!/usr/bin/env python3
"""Estrutura as regras do Rage CCG em arquivos markdown por capitulo/topico."""

import os
import re

RAW_DIR = 'docs/game-rules'
OUT_DIR = 'docs/game-rules'


def load_all_text() -> str:
    """Carrega todo o texto dos PDFs extraidos."""
    parts = []
    for fname in sorted(os.listdir(RAW_DIR)):
        if not fname.endswith('.md') or fname.startswith('00-'):
            continue
        path = os.path.join(RAW_DIR, fname)
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        # Remove cabecalho do markitdown
        text = re.sub(r'^# .*?\n\n_Extraido de:.*?_\n\n---\n\n', '', text, count=1)
        parts.append(text)
    return '\n\n'.join(parts)


def split_by_chapters(text: str) -> list[dict]:
    """Divide o texto completo pelos capitulos numerados.

    Retorna lista de dicts: {num, title, content, subtopics}
    """
    # Procura marcadores de capitulo
    pattern = re.compile(
        r'^(CHAPTER\s+(\d+)\s*[:\-–]\s*(.*?))(?:\n|$)',
        re.IGNORECASE | re.MULTILINE
    )

    chunks = []
    prev_end = 0
    prev_num = None

    for match in pattern.finditer(text):
        start = match.start()
        if prev_end > 0:
            content = text[prev_end:start].strip()
            chunks[-1]['content'] = content

        num = int(match.group(2))
        title = match.group(3).strip()
        chunks.append({
            'num': num,
            'title': title,
            'content': '',
            'raw_match': match.group(1),
        })
        prev_end = match.end()

    # Ultimo chunk
    if chunks:
        chunks[-1]['content'] = text[prev_end:].strip()

    return chunks


def split_into_sections(content: str) -> list[tuple[str, str]]:
    """Divide o conteudo de um capitulo em secoes numeradas (X.Y)."""
    sections = []
    # Procura secoes como "1.1 TITLE", "1.2 TITLE"
    pattern = re.compile(
        r'^(\d+\.\d+)\s+(.*?)(?:\n|$)',
        re.MULTILINE
    )

    prev_end = 0
    prev_section = None

    for match in pattern.finditer(content):
        start = match.start()
        if prev_end > 0:
            sec_content = content[prev_end:start].strip()
            sections.append((prev_section, sec_content))

        section_num = match.group(1)
        section_title = match.group(2).strip()
        prev_section = (section_num, section_title)
        prev_end = match.end()

    if prev_section and prev_end > 0:
        sections.append((prev_section, content[prev_end:].strip()))

    return sections


def build_chapter_files():
    """Cria um arquivo markdown para cada capitulo."""
    text = load_all_text()
    chapters = split_by_chapters(text)

    mapping = {
        1: '01-areas-de-jogo',
        2: '02-jogo-basico',
        3: '03-timing-e-regras',
        4: '04-cartas-em-detalhe',
        5: '05-umbra',
        6: '06-combate',
    }

    for ch in chapters:
        num = ch['num']
        slug = mapping.get(num, f'{num:02d}-capitulo-{num}')
        title = ch['title']
        content = ch['content']

        filepath = os.path.join(OUT_DIR, f'{slug}.md')

        md = f'# Capítulo {num}: {title}\n\n'
        md += f'_Baseado nas regras oficiais do Rage CCG (Abril 2018)._\n\n---\n\n'
        md += content

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)

        print(f'  {slug}.md - Capitulo {num}: {title} ({len(content)} chars)')


def build_thematic_files():
    """Cria arquivos tematicos que cruzam referencias entre capitulos."""
    text = load_all_text()

    temas = {
        '11-personagens': {
            'title': 'Personagens, Tribos e Renome',
            'keywords': [
                'Character', 'Garou', 'Werewolf', 'Tribe', 'Breed',
                'Homid', 'Lupus', 'Metis', 'Alpha', 'Rank', 'Renown',
                'Pack', 'Totem', 'Crinos', 'Shapechange', 'Morph',
                'Rage', 'Gnosis', 'Health', 'Death',
            ],
        },
        '12-equipamentos': {
            'title': 'Equipamentos e Fetiches',
            'keywords': [
                'Equipment', 'Fetish', 'Weapon', 'Armor', 'Item',
                'Equip', 'Bane Fetish', 'Attach',
            ],
        },
        '13-gifts': {
            'title': 'Gifts (Dons)',
            'keywords': [
                'Gift of', 'Breed Gift', 'Tribal Gift',
                'Gift of Gaia', 'Gift of the Wyrm',
            ],
        },
        '14-ritos-moots': {
            'title': 'Ritos, Moots e Eventos',
            'keywords': [
                'Rite', 'Ritual', 'Moot', 'Event', 'Vote',
                'Board Meeting', 'Challenge', 'Ceremony',
            ],
        },
        '15-acoes-e-eventos': {
            'title': 'Ações, Eventos de Combate e Efeitos',
            'keywords': [
                'Action', 'Combat Action', 'Combat Event',
                'Reveal', 'Strike', 'Feint', 'Instinctive',
                'Alternative Combat Action', 'Playing Multiple',
            ],
        },
        '16-glossario': {
            'title': 'Glossário de Termos',
            'keywords': [
                'VP', 'Victory Point', 'Victory Pile',
                'Umbra', 'Gauntlet', 'Out of Play',
                'Removed from the Game', 'Unique',
                'Global Effect', 'Stack', 'Target',
            ],
        },
    }

    paragraphs = text.split('\n\n')

    for tema_id, info in temas.items():
        title = info['title']
        keywords = [k.upper() for k in info['keywords']]

        relevant = []
        seen = set()
        for i, para in enumerate(paragraphs):
            para_u = para.upper()
            if any(kw in para_u for kw in keywords):
                if para not in seen:
                    seen.add(para)
                    relevant.append(para)

        if not relevant:
            print(f'  Aviso: {tema_id} - nenhum paragrafo encontrado')
            continue

        filepath = os.path.join(OUT_DIR, f'{tema_id}.md')
        md = f'# {title}\n\n'
        md += f'_{len(relevant)} parágrafos extraídos das regras._\n\n---\n\n'
        for p in relevant:
            md += p + '\n\n---\n\n'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)

        print(f'  {tema_id}.md - {title} ({len(relevant)} paragrafos)')


def build_index():
    """Cria indice geral da base de conhecimento."""
    files_info = [
        ('01-areas-de-jogo', 'Capítulo 1: Áreas de Jogo'),
        ('02-jogo-basico', 'Capítulo 2: O Jogo Básico (turnos, setup, VP)'),
        ('03-timing-e-regras', 'Capítulo 3: Timing e Visão Geral das Regras'),
        ('04-cartas-em-detalhe', 'Capítulo 4: As Cartas em Detalhe'),
        ('05-umbra', 'Capítulo 5: Regras para a Umbra'),
        ('06-combate', 'Capítulo 6: Combate'),
        ('11-personagens', 'Personagens, Tribos e Renome'),
        ('12-equipamentos', 'Equipamentos e Fetiches'),
        ('13-gifts', 'Gifts (Dons)'),
        ('14-ritos-moots', 'Ritos, Moots e Eventos'),
        ('15-acoes-e-eventos', 'Ações, Eventos de Combate e Efeitos'),
        ('16-glossario', 'Glossário de Termos'),
    ]

    lines = [
        '# Base de Conhecimento - Regras do Rage CCG\n\n',
        'Esta base foi extraída dos PDFs oficiais de regras do Rage CCG '
        '(Atualização de Abril de 2018).\n\n',
        '## Capítulos\n\n',
    ]

    for slug, desc in files_info:
        path = os.path.join(OUT_DIR, f'{slug}.md')
        size = os.path.getsize(path) // 1024 if os.path.exists(path) else 0
        lines.append(f'- [{desc}]({slug}.md) ({size} KB)\n')

    lines.append('\n---\n\n')
    lines.append('_Total de arquivos: {}_\n'.format(len(files_info)))
    lines.append('_Extraído por: Rage CCG Web_\n')

    with open(os.path.join(OUT_DIR, '00-indice.md'), 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print('00-indice.md atualizado')


def main():
    print('=== Criando arquivos por capitulo ===')
    build_chapter_files()

    print('\n=== Criando arquivos tematicos ===')
    build_thematic_files()

    print('\n=== Atualizando indice ===')
    build_index()

    print('\nConcluido!')


if __name__ == '__main__':
    main()
