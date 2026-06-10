"""Adiciona coluna tags ao card, reconcilia slug/tags nullability

A coluna tags foi adicionada ao modelo Card em Python mas nunca foi
versionada via Alembic. Esta migration adiciona tags e ajusta
nullability de slug e tags (card), alem de renown_cap (deck).

NOTA: SQLite batch_alter_table recria a tabela. Todas as alteracoes
na mesma tabela DEVEM ficar num unico batch_op.

Revision ID: 151aa422178f
Revises: c6639c054615
Create Date: 2026-06-10 17:40:16.874508

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '151aa422178f'
down_revision = 'c6639c054615'
branch_labels = None
depends_on = None


def _col_exists(conn, table: str, column: str) -> bool:
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()

    # ── Card: todas as alteracoes num unico batch_op ──
    has_tags = _col_exists(conn, 'card', 'tags')
    has_slug = _col_exists(conn, 'card', 'slug')

    if has_tags or has_slug:
        with op.batch_alter_table('card', schema=None) as batch_op:
            if has_tags:
                batch_op.alter_column('tags',
                       existing_type=sa.TEXT(),
                       type_=sa.String(),
                       nullable=False,
                       server_default=sa.text("''"))
            else:
                batch_op.add_column(
                    sa.Column('tags', sa.String(), nullable=False,
                              server_default=sa.text("''")))
            if has_slug:
                batch_op.alter_column('slug',
                       existing_type=sa.VARCHAR(length=200),
                       nullable=False,
                       server_default=sa.text("''"))

    # ── Deck: renown_cap nullable ──
    if _col_exists(conn, 'deck', 'renown_cap'):
        with op.batch_alter_table('deck', schema=None) as batch_op:
            batch_op.alter_column('renown_cap',
                   existing_type=sa.INTEGER(),
                   nullable=False,
                   server_default=sa.text('20'))


def downgrade():
    conn = op.get_bind()
    has_tags = _col_exists(conn, 'card', 'tags')
    has_slug = _col_exists(conn, 'card', 'slug')

    if has_tags or has_slug:
        with op.batch_alter_table('card', schema=None) as batch_op:
            if has_tags:
                batch_op.drop_column('tags')
            if has_slug:
                batch_op.alter_column('slug',
                       existing_type=sa.VARCHAR(length=200),
                       nullable=True,
                       server_default=sa.text("''"))

    if _col_exists(conn, 'deck', 'renown_cap'):
        with op.batch_alter_table('deck', schema=None) as batch_op:
            batch_op.alter_column('renown_cap',
                   existing_type=sa.INTEGER(),
                   nullable=True,
                   server_default=sa.text('20'))
