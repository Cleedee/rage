import logging
import os

import click

from rage_web.ext.database import db

logger = logging.getLogger(__name__)


def init_app(app):
    @app.cli.command("init-database")
    def create_all():
        db.create_all()
        click.echo("Banco de dados criado.")

    @app.cli.command("import-cards")
    @click.option("--dry-run", is_flag=True, help="Apenas mostra o que seria importado.")
    @click.option("--fonte", type=click.Choice(["oficial", "conclave_test", "playtest", "todas"]),
                  default="todas", help="Qual fonte importar.")
    def import_cards(dry_run, fonte):
        """Importa cartas do Rage CCG a partir dos arquivos TSV do LackeyCCG."""
        from rage_web.ext.importer import import_all, import_tsv, TSV_URLS

        if fonte == "todas":
            stats = import_all(dry_run=dry_run)
        else:
            url = dict(TSV_URLS).get(fonte)
            if not url:
                click.echo(f"Fonte desconhecida: {fonte}")
                return
            stats = [import_tsv(fonte, url, dry_run=dry_run)]

        click.echo("\nResumo da importação:")
        click.echo("-" * 50)
        total_criadas = 0
        total_ignoradas = 0
        total_erros = 0
        for s in stats:
            status = "[DRY RUN]" if dry_run else ""
            click.echo(f"  {s['fonte']}: {s['criadas']} criadas, "
                       f"{s['ignoradas']} ignoradas, {s['erros']} erros {status}")
            total_criadas += s['criadas']
            total_ignoradas += s['ignoradas']
            total_erros += s['erros']

        if not dry_run:
            click.echo("-" * 50)
            click.echo(f"  Total: {total_criadas} cartas importadas, "
                       f"{total_ignoradas} ignoradas, {total_erros} erros")

    @app.cli.command("import-deck")
    @click.argument("arquivo", required=False)
    @click.option("--url", help="URL do deck (.dek ou texto).")
    @click.option("--nome", help="Nome do deck.")
    @click.option("--texto", help="Texto do deck (entre aspas).")
    def import_deck(arquivo, url, nome, texto):
        """Importa um deck a partir de arquivo, URL ou texto."""
        from rage_web.ext.deck_importer import import_deck_from_text, import_deck_from_url

        if arquivo:
            with open(arquivo, 'r') as f:
                texto = f.read()
        elif url:
            stats = import_deck_from_url(url, deck_name=nome or '')
            _show_deck_stats(stats)
            return
        elif not texto:
            click.echo("Forneça --arquivo, --url ou --texto.")
            return

        stats = import_deck_from_text(texto, deck_name=nome or '')
        _show_deck_stats(stats)


    @app.cli.command("download-images")
    @click.option("--max-workers", default=8, help="Número de downloads paralelos.")
    @click.option("--dry-run", is_flag=True, help="Apenas mostra o que seria baixado.")
    def download_images(max_workers, dry_run):
        """Baixa imagens das cartas do servidor LackeyCCG."""
        from rage_web.ext.image_downloader import download_card_images
        from flask import current_app

        dest_dir = os.path.join(current_app.instance_path, 'images')
        click.echo(f'Baixando imagens para {dest_dir}...')
        stats = download_card_images(dest_dir, max_workers=max_workers,
                                      dry_run=dry_run)

        if dry_run:
            click.echo(f'[DRY RUN] {stats["total"]} cartas, '
                       f'imagens a baixar')
        else:
            click.echo(f'\nResumo:')
            click.echo(f'  Total de arquivos: {stats["total"]}')
            click.echo(f'  Baixados: {stats["baixadas"]}')
            click.echo(f'  Já existiam: {stats["puladas"]}')
            click.echo(f'  Erros: {stats["erros"]}')


def _show_deck_stats(stats):
    click.echo("\nResumo da importação do deck:")
    click.echo("-" * 50)
    click.echo(f"  Total de linhas: {stats['total']}")
    click.echo(f"  Cartas encontradas: {stats['encontradas']}")
    click.echo(f"  Cartas NÃO encontradas: {stats['nao_encontradas']}")
    if stats['nao_encontradas']:
        click.echo("\n  Cartas não encontradas no banco:")
        for c in stats['cards']:
            if not c['found']:
                click.echo(f"    - {c['name']}")
