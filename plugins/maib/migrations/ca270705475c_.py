"""empty message

Revision ID: ca270705475c
Revises: 58124164bc13
Create Date: 2026-07-27 16:21:07.163646

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca270705475c'
down_revision = '58124164bc13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('maib_mairecords',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('record_hash', sa.String(length=64), nullable=False),
    sa.Column('shortid', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('cabinet', sa.String(length=2), nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('difficulty', sa.Integer(), nullable=False),
    sa.Column('server', sa.String(length=16), nullable=False),
    sa.Column('achievement', sa.Float(), nullable=False),
    sa.Column('dxscore', sa.Integer(), nullable=False),
    sa.Column('combo', sa.Integer(), nullable=False),
    sa.Column('sync', sa.Integer(), nullable=False),
    sa.Column('play_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('update_time', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_maib_mairecords'))
    )
    with op.batch_alter_table('maib_mairecords', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_mairecords_record_hash'), ['record_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_maib_mairecords_shortid'), ['shortid'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_mairecords_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.alter_column(
            'sync_hash',
            new_column_name='maisync_hash',
            existing_type=sa.String(),
            existing_nullable=True,
        )
        batch_op.drop_column('sync_allow_time')


def downgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sync_allow_time', sa.INTEGER(), nullable=True))
        batch_op.alter_column(
            'maisync_hash',
            new_column_name='sync_hash',
            existing_type=sa.String(),
            existing_nullable=True,
        )

    with op.batch_alter_table('maib_mairecords', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_mairecords_user_id'))
        batch_op.drop_index(batch_op.f('ix_maib_mairecords_shortid'))
        batch_op.drop_index(batch_op.f('ix_maib_mairecords_record_hash'))

    op.drop_table('maib_mairecords')
