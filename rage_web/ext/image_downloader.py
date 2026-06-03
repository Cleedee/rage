"""
Download de imagens das cartas do Rage CCG.
Fonte: http://www.werepenguin.com/rage/lackey/high/

Respeita rate limit do servidor com backoff exponencial.
"""

import logging
import os
import time
from urllib.request import urlopen, HTTPError
from urllib.error import URLError

from rage_web.ext.database import db
from rage_web.models.card import Card

logger = logging.getLogger(__name__)

IMAGE_BASE_URL = 'http://www.werepenguin.com/rage/lackey/high/'
DELAY_BETWEEN_REQUESTS = 0.5  # segundos entre downloads
MAX_RETRIES = 5


def get_image_paths(image_file: str) -> list[str]:
    """Retorna lista de nomes de arquivos de imagem a partir do campo image_file."""
    if not image_file:
        return []
    return [f.strip() for f in image_file.split(',') if f.strip()]


def download_image(filename: str, dest_dir: str) -> bool:
    """Baixa uma imagem do servidor LackeyCCG com backoff exponencial.

    Retorna True se baixou com sucesso, False caso contrário.
    """
    dest_path = os.path.join(dest_dir, filename + '.jpg')

    if os.path.exists(dest_path):
        return True

    url = IMAGE_BASE_URL + filename + '.jpg'

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urlopen(url, timeout=30) as resp:
                if resp.status == 200:
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with open(dest_path, 'wb') as f:
                        f.write(resp.read())
                    return True
                else:
                    logger.warning(f'HTTP {resp.status} para {url}')
                    return False

        except HTTPError as e:
            if e.code == 429:
                wait = min(2 ** attempt * 2, 120)  # 4s, 8s, 16s, 32s, 64s
                logger.warning(f'429 Too Many Requests - {url}. '
                              f'Esperando {wait}s (tentativa {attempt}/{MAX_RETRIES})')
                time.sleep(wait)
                continue
            else:
                logger.warning(f'Erro HTTP {e.code} para {url}')
                return False
        except URLError as e:
            logger.warning(f'Erro de URL {url}: {e.reason}')
            return False
        except Exception as e:
            logger.warning(f'Erro ao baixar {url}: {e}')
            return False

    logger.error(f'Desistiu de {url} após {MAX_RETRIES} tentativas')
    return False


def download_card_images(dest_dir: str, max_workers: int = 1,
                         dry_run: bool = False,
                         delay: float = 0.5) -> dict:
    """Baixa imagens de todas as cartas sequencialmente (respeita rate limit).

    Args:
        dest_dir: Diretório destino.
        max_workers: Ignorado (sempre 1 para respeitar rate limit).
        dry_run: Apenas mostra o que seria baixado.
        delay: Segundos entre requisições.

    Retorna estatísticas.
    """
    stats = {'total': 0, 'baixadas': 0, 'ja_existiam': 0, 'erros': 0}

    cards = Card.query.filter(Card.image_file != '').all()
    stats['total'] = len(cards)

    all_filenames = set()
    for card in cards:
        for fname in get_image_paths(card.image_file):
            all_filenames.add(fname)

    stats['arquivos_unicos'] = len(all_filenames)

    if dry_run:
        logger.info(f'[DRY RUN] {len(cards)} cartas, '
                    f'{len(all_filenames)} arquivos de imagem únicos')
        return stats

    os.makedirs(dest_dir, exist_ok=True)

    baixadas = 0
    ja_existiam = 0
    erros = 0
    total = len(all_filenames)

    for idx, fname in enumerate(sorted(all_filenames), 1):
        dest_path = os.path.join(dest_dir, fname + '.jpg')
        if os.path.exists(dest_path):
            ja_existiam += 1
        else:
            if download_image(fname, dest_dir):
                baixadas += 1
            else:
                erros += 1

        if idx % 50 == 0 or idx == total:
            logger.info(f'Progresso: {idx}/{total} arquivos '
                        f'({baixadas} baixadas, {ja_existiam} existentes, '
                        f'{erros} erros)')

        time.sleep(delay)

    stats['baixadas'] = baixadas
    stats['ja_existiam'] = ja_existiam
    stats['erros'] = erros

    logger.info(f'Download concluído: {baixadas} baixadas, '
                f'{ja_existiam} já existiam, {erros} erros')

    return stats


def get_card_image_url(card: Card) -> str | None:
    """Retorna URL da primeira imagem disponível para uma carta.

    Retorna None se a imagem não existir localmente.
    """
    if not card.image_file:
        return None
    first_img = card.image_file.split(',')[0].strip()
    if not first_img:
        return None
    from flask import current_app
    instance_path = current_app.instance_path
    local_path = os.path.join(instance_path, 'images', first_img + '.jpg')
    if os.path.exists(local_path):
        return f'/instance/images/{first_img}.jpg'
    return None
