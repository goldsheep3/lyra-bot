"""rename maib alias and update chart-achievement uniqueness

Revision ID: cd1009338f05
Revises: b7d19a6e2f40
Create Date: 2026-11-12 11:38:03.007309

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd1009338f05'
down_revision = 'b7d19a6e2f40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite batch mode reflects indexes before rebuilding the table.  Keep
    # the index/constraint removal, column rename, and recreation in separate
    # batches so Alembic never tries to attach the old ``alias`` index to the
    # rebuilt table after the column has become ``name``.
    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.alter_column('create_qq',
               existing_type=sa.BIGINT(),
               nullable=True)
        batch_op.drop_index(batch_op.f('ix_maib_maialiases_alias'))
        batch_op.drop_constraint(batch_op.f('uq_maib_maialiases_shortid'), type_='unique')

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.alter_column(
            'alias',
            new_column_name='name',
            existing_type=sa.String(),
            existing_nullable=False,
        )

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_maib_maialiases_shortid'), ['shortid', 'name'])
        batch_op.create_index(batch_op.f('ix_maib_maialiases_name'), ['name'], unique=False)

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_maib_maichartachs_qq_shortid_difficulty_provider_server'), type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_maib_maichartachs_qq'), ['qq', 'chart_id', 'provider', 'server'])

def downgrade() -> None:
    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_maib_maichartachs_qq'), type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_maib_maichartachs_qq_shortid_difficulty_provider_server'), ['qq', 'shortid', 'difficulty', 'provider', 'server'])

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maialiases_name'))
        batch_op.drop_constraint(batch_op.f('uq_maib_maialiases_shortid'), type_='unique')

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.alter_column(
            'name',
            new_column_name='alias',
            existing_type=sa.String(),
            existing_nullable=False,
        )

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_maib_maialiases_shortid'), ['shortid', 'alias'])
        batch_op.create_index(batch_op.f('ix_maib_maialiases_alias'), ['alias'], unique=False)
        batch_op.alter_column('create_qq',
               existing_type=sa.BIGINT(),
               nullable=False)
