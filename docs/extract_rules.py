#!/usr/bin/env python3
"""Extrai texto dos PDFs de regras do Rage CCG e gera arquivos markdown."""

import os
import re
from markitdown import MarkItDown

RAW_DIR = 'docs/raw'
OUT_DIR = 'docs/game-rules'

PDF_FILES = [
    '01-RageRules.pdf',
    '02-RageRules.pdf',
    '03-RageRules.pdf',
    '04-RageRules.pdf',
    '05-RageRules.pdf',
    '06-RageRules.pdf',
]


def clean_text(text: str) -> str:
    """Limpa e normaliza o texto extraido."""
    # Remove quebras de linha duplicadas excessivas
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove espacos no inicio/fim de cada linha
    lines = [l.strip() for l in text.split('\n')]
    # Remove linhas vazias consecutivas (max 1)
    cleaned = []
    prev_empty = False
    for line in lines:
        if not line:
            if prev_empty:
                continue
            prev_empty = True
        else:
            prev_empty = False
        cleaned.append(line)
    text = '\n'.join(cleaned)
    # Corrige espacamento antes de pontuacao
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)
    return text


def extract_all() -> dict[str, str]:
    """Extrai texto de todos os PDFs e retorna dict nome->texto."""
    md = MarkItDown()
    results = {}
    for pdf in PDF_FILES:
        path = os.path.join(RAW_DIR, pdf)
        print(f'Extraindo {pdf}...')
        result = md.convert(path)
        text = clean_text(result.text_content)
        results[pdf] = text
        print(f'  -> {len(text)} caracteres')
    return results


def split_by_chapters(text: str) -> list[tuple[str, str]]:
    """Tenta dividir o texto por capítulos numerados.

    Retorna lista de (titulo_do_capitulo, texto_do_capitulo).
    """
    # Procura padrao "CHAPTER X:" ou "CHAPTER X -" ou numeracao similar
    chapter_pattern = re.compile(
        r'^(CHAPTER\s+\d+[.:\s-]+.*?)$',
        re.IGNORECASE | re.MULTILINE
    )
    # Procura tambem secoes numeradas como "1.1", "1.2" etc
    section_pattern = re.compile(
        r'^((?:\d+\.)+\d+\s+.*?)$',
        re.MULTILINE
    )

    chapters = []
    parts = chapter_pattern.split(text)

    if len(parts) < 2:
        # Fallback: divide por paginas numeradas
        return [('Texto Completo', text)]

    # O primeiro elemento e o preambulo (antes do primeiro capitulo)
    preamble = parts[0].strip()
    if preamble:
        chapters.append(('Introducao', preamble))

    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ''
        chapters.append((title, content))

    return chapters


def save_rulebook_text(results: dict[str, str]):
    """Salva cada PDF como um arquivo markdown completo."""
    for pdf_name, text in results.items():
        # Gera nome amigavel: "01 - Rage Rules"
        base = pdf_name.replace('-RageRules.pdf', '').strip()
        num = base[:2]
        title = f'{num} - Regras (Parte {int(num)})'
        filepath = os.path.join(OUT_DIR, f'{base}.md')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f'# {title}\n\n')
            f.write(f'_Extraido de: {pdf_name}_\n\n---\n\n')
            f.write(text)
        print(f'Salvo: {filepath} ({len(text)} chars)')


def build_index():
    """Cria arquivo de indice da base de conhecimento."""
    lines = [
        '# Base de Conhecimento - Regras do Rage CCG\n\n',
        'Esta base foi extraída dos PDFs oficiais de regras do Rage CCG '
        '(Atualização de Abril de 2018).\n\n',
        '## Arquivos\n\n',
    ]
    for fname in sorted(os.listdir(OUT_DIR)):
        if fname.endswith('.md') and fname != '00-indice.md':
            size = os.path.getsize(os.path.join(OUT_DIR, fname))
            title = fname.replace('.md', '')
            lines.append(f'- [{title}]({fname}) ({size // 1024} KB)\n')

    with open(os.path.join(OUT_DIR, '00-indice.md'), 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f'Indice salvo: 00-indice.md')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print('Extraindo textos dos PDFs...')
    results = extract_all()

    print('\nSalvando arquivos...')
    save_rulebook_text(results)

    print('\nCriando indice...')
    build_index()

    print('\nConcluido!')


if __name__ == '__main__':
    main()
