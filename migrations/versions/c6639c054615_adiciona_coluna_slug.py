"""Adiciona coluna slug na tabela card

Revision ID: c6639c054615
Revises: 6bda8104262a
Create Date: 2026-06-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6639c054615'
down_revision = 'b80dd916bd48'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('card', sa.Column('slug', sa.String(length=200), nullable=False, server_default=''))
    op.create_index(op.f('ix_card_slug'), 'card', ['slug'])


def downgrade():
    op.drop_index(op.f('ix_card_slug'), table_name='card')
    op.drop_column('card', 'slug')
