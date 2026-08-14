"""Aime 卡号长度 16→20

Revision ID: 0a1b2c3d4e5f
Revises: 79755df583d2
Create Date: 2026-08-11 02:11:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0a1b2c3d4e5f'
down_revision = '79755df583d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('maib_maimes', schema=None) as batch_op:
        batch_op.alter_column(
            'access',
            type_=sa.String(length=20),
            existing_type=sa.String(length=16),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('maib_maimes', schema=None) as batch_op:
        batch_op.alter_column(
            'access',
            type_=sa.String(length=16),
            existing_type=sa.String(length=20),
            nullable=False,
        )