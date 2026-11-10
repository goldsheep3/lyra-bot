"""dedupe maisync per user and align refresh_updated_at timezone

Revision ID: 9d1c4a7e2b60
Revises: cbbbe7571bfc
Create Date: 2026-11-10 10:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d1c4a7e2b60'
down_revision = 'cbbbe7571bfc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 每用户只保留一条 maisync 记录：优先保留未撤销的 token，其次保留最新一条。
    op.execute("""
        DELETE FROM maib_maisync
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY qq
                           ORDER BY token_revoked ASC, id DESC
                       ) AS rn
                FROM maib_maisync
            ) ranked
            WHERE rn = 1
        )
    """)

    with op.batch_alter_table('maib_maisync', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maisync_qq'))
        batch_op.create_index(batch_op.f('ix_maib_maisync_qq'), ['qq'], unique=True)

    with op.batch_alter_table('maib_mailxns', schema=None) as batch_op:
        batch_op.alter_column(
            'refresh_updated_at',
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('maib_mailxns', schema=None) as batch_op:
        batch_op.alter_column(
            'refresh_updated_at',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )

    with op.batch_alter_table('maib_maisync', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maisync_qq'))
        batch_op.create_index(batch_op.f('ix_maib_maisync_qq'), ['qq'], unique=False)
