"""Reconcilia schema (card.slug nullable, card.tags type/nullable, deck.renown_cap nullable)

Revision ID: 151aa422178f
Revises: c6639c054615
Create Date: 2026-06-10 17:40:16.874508

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '151aa422178f'
down_revision = 'c6639c054615'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite: batch_alter_table recria a tabela. Precisamos de um default
    # constante (string literal) ou nenhum server_default.
    with op.batch_alter_table('card', schema=None) as batch_op:
        batch_op.alter_column('slug',
               existing_type=sa.VARCHAR(length=200),
               nullable=False,
               server_default=sa.text("''"))

    with op.batch_alter_table('card', schema=None) as batch_op:
        batch_op.alter_column('tags',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               nullable=False,
               server_default=sa.text("''"))

    with op.batch_alter_table('deck', schema=None) as batch_op:
        batch_op.alter_column('renown_cap',
               existing_type=sa.INTEGER(),
               nullable=False,
               server_default=sa.text('20'))


def downgrade():
    # Retorna ao estado anterior (nullable=True, sem server_default)
    with op.batch_alter_table('deck', schema=None) as batch_op:
        batch_op.alter_column('renown_cap',
               existing_type=sa.INTEGER(),
               nullable=True,
               server_default=sa.text('20'))

    with op.batch_alter_table('card', schema=None) as batch_op:
        batch_op.alter_column('tags',
               existing_type=sa.String(),
               type_=sa.TEXT(),
               nullable=True,
               server_default=sa.text("''"))
        batch_op.alter_column('slug',
               existing_type=sa.VARCHAR(length=200),
               nullable=True,
               server_default=sa.text("''"))
