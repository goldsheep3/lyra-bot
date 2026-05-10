"""add last_sy_hash to maiusers

Revision ID: 7b2d13f1aa77
Revises: fa004c568421
Create Date: 2026-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b2d13f1aa77'
down_revision = 'fa004c568421'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_sy_hash', sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.drop_column('last_sy_hash')
