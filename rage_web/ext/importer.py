"""
Importador de cartas do Rage CCG a partir dos arquivos TSV do LackeyCCG.

Fontes de dados:
  - http://www.werepenguin.com/rage/lackey/setinfo.txt      (cartas oficiais)
  - http://www.werepenguin.com/rage/lackey/conclavetest.txt  (cartas de teste)
  - http://www.werepenguin.com/rage/lackey/hyplaytest.txt    (cartas de playtest)
"""

import csv
import io
import logging
from urllib.request import urlopen

from rage_web.ext.database import db
from rage_web.models.card import Card

logger = logging.getLogger(__name__)

TSV_URLS = [
    ('oficial', 'http://www.werepenguin.com/rage/lackey/setinfo.txt'),
    ('conclave_test', 'http://www.werepenguin.com/rage/lackey/conclavetest.txt'),
    ('playtest', 'http://www.werepenguin.com/rage/lackey/hyplaytest.txt'),
]

COLUMN_MAP = {
    'Name': 'name',
    'Expansion': 'expansion',
    'ImageFile': 'image_file',
    'Sealed': 'sealed',
    'Type': 'tipo',
    'Notes': 'notes',
    'Requires': 'requires',
    'Keywords': 'keyword',
    'Renown': 'renown',
    'Rage': 'rage',
    'Gnosis': 'gnosis',
    'Health': 'health',
    'CRage': 'rage_morph',
    'CGnosis': 'gnosis_morph',
    'CHealth': 'health_morph',
    'Damage': 'damage',
    'Text': 'text',
    'Errata': 'errata',
}

INT_FIELDS = {'renown', 'rage', 'gnosis', 'health', 'rage_morph', 'gnosis_morph', 'health_morph'}


def parse_int(value: str) -> int:
    """Converte string para int, retornando 0 se vazio/inválido."""
    value = value.strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def download_tsv(url: str) -> str:
    """Baixa o conteúdo de um arquivo TSV."""
    logger.info(f'Baixando {url}...')
    with urlopen(url, timeout=30) as resp:
        data = resp.read()
        # Tenta detectar encoding
        encoding = resp.headers.get_content_charset() or 'utf-8'
        return data.decode(encoding, errors='replace')


def parse_tsv(content: str) -> list[dict]:
    """Analisa o conteúdo TSV e retorna lista de dicionários."""
    reader = csv.DictReader(
        io.StringIO(content),
        delimiter='\t',
        quoting=csv.QUOTE_NONE,
        restval='',
    )
    return list(reader)


def normalize_row(row: dict) -> dict:
    """Normaliza uma linha do TSV para os campos do modelo Card."""
    normalized = {}
    for tsv_col, model_col in COLUMN_MAP.items():
        raw = row.get(tsv_col, '').strip()
        if model_col in INT_FIELDS:
            normalized[model_col] = parse_int(raw)
        else:
            # Remove quotes surrounding some card names
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw[1:-1]
            normalized[model_col] = raw
    return normalized


def card_exists(session, name: str, expansion: str) -> bool:
    """Verifica se já existe uma carta com mesmo nome e expansão."""
    return session.query(
        db.exists().where(
            Card.name == name,
            Card.expansion == expansion,
        )
    ).scalar()


def import_tsv(source_label: str, url: str, dry_run: bool = False) -> dict:
    """Importa cartas de um arquivo TSV.

    Retorna estatísticas da importação.
    """
    stats = {'total': 0, 'criadas': 0, 'ignoradas': 0, 'erros': 0}

    content = download_tsv(url)
    rows = parse_tsv(content)
    stats['total'] = len(rows)

    if dry_run:
        logger.info(f'[DRY RUN] {source_label}: {len(rows)} cartas encontradas')
        return stats

    for i, row in enumerate(rows):
        try:
            if not row.get('Name', '').strip():
                stats['ignoradas'] += 1
                continue

            data = normalize_row(row)

            # Pula se já existe
            if card_exists(db.session, data['name'], data['expansion']):
                stats['ignoradas'] += 1
                continue

            card = Card(**data)
            db.session.add(card)
            stats['criadas'] += 1

            # Commit em lotes para não acumular muitas operações
            if stats['criadas'] % 100 == 0:
                db.session.commit()
                logger.info(f'  ... {stats["criadas"]} cartas importadas de {source_label}')

        except Exception as e:
            logger.error(f'Erro ao importar linha {i + 1} de {source_label}: {e}')
            stats['erros'] += 1

    # Commit final
    db.session.commit()
    logger.info(f'{source_label}: {stats["criadas"]} criadas, '
                f'{stats["ignoradas"]} ignoradas, {stats["erros"]} erros')

    return stats


def import_all(dry_run: bool = False) -> list[dict]:
    """Importa todas as fontes de dados."""
    all_stats = []
    for label, url in TSV_URLS:
        stats = import_tsv(label, url, dry_run=dry_run)
        all_stats.append({'fonte': label, **stats})
    return all_stats
