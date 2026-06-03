import logging

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
