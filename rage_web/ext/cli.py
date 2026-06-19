import logging
import os
import shutil
from datetime import datetime

import click

from rage_web.ext.database import db

logger = logging.getLogger(__name__)


BACKUP_DIR = 'backups'
DECK_EXPORT_DIR = 'data/decks'


def init_app(app):
    @app.cli.command("backup-db")
    @click.option("--dir", default=BACKUP_DIR, help="Diretório de backup.")
    def backup_db(dir):
        """Copia o banco SQLite para um arquivo de backup com timestamp."""
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
        if not db_path:
            db_path = 'rage_web/database.db'
        if not os.path.exists(db_path):
            click.echo(f"❌ Banco não encontrado: {db_path}")
            return
        os.makedirs(dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'database_{timestamp}.db'
        backup_path = os.path.join(dir, backup_name)
        shutil.copy2(db_path, backup_path)
        size_kb = os.path.getsize(backup_path) // 1024
        click.echo(f"✅ Backup salvo: {backup_path} ({size_kb} KB)")
        # Remove backups older than 30 days
        import time
        cutoff = time.time() - 30 * 86400
        for f in os.listdir(dir):
            fpath = os.path.join(dir, f)
            if os.path.isfile(fpath) and f.startswith('database_'):
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    click.echo(f"  🗑️  Backup antigo removido: {f}")
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

    @app.cli.command("export-decks")
    @click.option("--dir", default=DECK_EXPORT_DIR, help="Diretório de exportação.")
    def export_decks(dir):
        """Exporta todos os decks para arquivos JSON versionáveis."""
        from rage_web.models.deck import Deck
        from rage_web.models.card import Card, deck_cards

        os.makedirs(dir, exist_ok=True)
        decks = Deck.query.all()
        if not decks:
            click.echo("📭 Nenhum deck para exportar.")
            return

        for deck in decks:
            cards = (
                db.session.query(deck_cards.c.card_id, deck_cards.c.quantity, Card.name, Card.slug)
                .join(Card)
                .filter(deck_cards.c.deck_id == deck.id)
                .all()
            )
            total_ren = sum(
                (db.session.get(Card, cid).renown or 0) * qty
                for cid, qty, _, _ in cards
            )
            data = {
                "id": deck.id,
                "name": deck.name,
                "description": deck.description or '',
                "renown_cap": deck.renown_cap,
                "strategy": deck.strategy,
                "is_public": deck.is_public,
                "telegram_owner_id": deck.telegram_owner_id,
                "total_cards": sum(q for _, q, _, _ in cards),
                "total_renown": total_ren,
                "cards": [
                    {"card_id": cid, "slug": slug, "name": name, "quantity": qty}
                    for cid, qty, name, slug in cards
                ],
            }
            fname = f'deck{deck.id}.json'
            fpath = os.path.join(dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            click.echo(f"  ✅ {fname} — {deck.name} ({data['total_cards']} cartas)")

        click.echo(f"\n📦 {len(decks)} decks exportados para {dir}/")

    @app.cli.command("import-decks")
    @click.option("--dir", default=DECK_EXPORT_DIR, help="Diretório de importação.")
    @click.option("--dry-run", is_flag=True, help="Apenas mostra o que seria importado.")
    def import_decks(dir, dry_run):
        """Importa decks de arquivos JSON exportados anteriormente."""
        from rage_web.models.deck import Deck, deck_cards
        from rage_web.models.card import Card

        if not os.path.isdir(dir):
            click.echo(f"❌ Diretório não encontrado: {dir}")
            return

        importados = 0
        erros = 0
        for fname in sorted(os.listdir(dir)):
            if not fname.startswith('deck') or not fname.endswith('.json'):
                continue
            fpath = os.path.join(dir, fname)
            with open(fpath, encoding='utf-8') as f:
                data = json.load(f)

            did = data['id']
            if dry_run:
                click.echo(f"  [DRY] Deck {did}: {data['name']} ({len(data['cards'])} cartas)")
                importados += 1
                continue

            try:
                existing = Deck.query.get(did)
                if existing:
                    existing.name = data['name']
                    existing.description = data['description']
                    existing.renown_cap = data['renown_cap']
                    existing.strategy = data.get('strategy', 'midrange')
                    db.session.execute(deck_cards.delete().where(deck_cards.c.deck_id == did))
                    deck = existing
                else:
                    deck = Deck(
                        id=did, name=data['name'],
                        description=data['description'],
                        renown_cap=data['renown_cap'],
                        strategy=data.get('strategy', 'midrange'),
                        is_public=data.get('is_public', False),
                    )
                    db.session.add(deck)
                    db.session.flush()

                for card_entry in data['cards']:
                    cid = card_entry['card_id']
                    qty = card_entry['quantity']
                    if db.session.get(Card, cid):
                        db.session.execute(
                            deck_cards.insert().values(deck_id=did, card_id=cid, quantity=qty)
                        )

                db.session.commit()
                click.echo(f"  ✅ Deck {did}: {data['name']}")
                importados += 1
            except Exception as e:
                db.session.rollback()
                click.echo(f"  ❌ Deck {did} ({data['name']}): {e}")
                erros += 1

        click.echo(f"\n📦 {importados} decks importados, {erros} erros")

    @app.cli.command("db-health")
    def db_health():
        """Verifica a integridade do banco de dados."""
        from rage_web.models.card import Card, deck_cards
        from rage_web.models.deck import Deck

        warnings = 0

        # 1. Verifica se tabelas existem
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db.engine)
        tables = inspector.get_table_names()
        expected = {'card', 'deck', 'deck_cards', 'picture',
                     'tournament', 'tournament_player', 'tournament_match'}
        missing = expected - set(tables)
        if missing:
            click.echo(f"❌ Tabelas faltando: {', '.join(missing)}")
            warnings += 1
        else:
            click.echo("✅ Todas as tabelas existem")

        # 2. Contagem de cartas
        n_cards = Card.query.count()
        click.echo(f"✅ Cartas: {n_cards}")
        if n_cards != 1797:
            click.echo(f"  ⚠️  Esperado: 1797, diferente: {n_cards}")
            warnings += 1

        # 3. Contagem de decks
        n_decks = Deck.query.count()
        click.echo(f"✅ Decks: {n_decks}")
        for d in Deck.query.all():
            total = (
                db.session.query(db.func.sum(deck_cards.c.quantity))
                .filter(deck_cards.c.deck_id == d.id)
                .scalar() or 0
            )
            click.echo(f"  Deck {d.id}: {d.name} — {total} cartas")

        # 4. Amostra de cartas
        sample = Card.query.limit(3).all()
        for c in sample:
            click.echo(f"✅ Amostra: [{c.id}] {c.name} (slug={c.slug})")

        # 5. Slugs
        no_slug = Card.query.filter((Card.slug == '') | (Card.slug.is_(None))).count()
        if no_slug:
            click.echo(f"⚠️  Cartas sem slug: {no_slug}")
            warnings += 1

        if warnings:
            click.echo(f"\n⚠️  {warnings} aviso(s) encontrado(s)")
        else:
            click.echo(f"\n✅ Banco saudável!")


# Fora da funcao para poder usar json
import json


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
