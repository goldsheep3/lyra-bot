"""empty message

Revision ID: 91f4b7918c4a
Revises: ca270705475c
Create Date: 2026-07-27 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '91f4b7918c4a'
down_revision = 'ca270705475c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('maib_maisync_pairing_codes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('create_time', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_maib_maisync_pairing_codes'))
    )
    with op.batch_alter_table('maib_maisync_pairing_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maisync_pairing_codes_code_hash'), ['code_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_maib_maisync_pairing_codes_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maisync_pairing_codes_user_id'), ['user_id'], unique=False)

    op.create_table('maib_maisync_tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('device_name', sa.String(length=128), nullable=False),
    sa.Column('create_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_maib_maisync_tokens')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_maib_maisync_tokens_token_hash')),
    sa.UniqueConstraint('user_id', name=op.f('uq_maib_maisync_tokens_user_id'))
    )
    with op.batch_alter_table('maib_maisync_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maisync_tokens_token_hash'), ['token_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maisync_tokens_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.drop_column('maisync_hash')


def downgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('maisync_hash', sa.VARCHAR(), nullable=True))

    with op.batch_alter_table('maib_maisync_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maisync_tokens_user_id'))
        batch_op.drop_index(batch_op.f('ix_maib_maisync_tokens_token_hash'))

    op.drop_table('maib_maisync_tokens')

    with op.batch_alter_table('maib_maisync_pairing_codes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maisync_pairing_codes_user_id'))
        batch_op.drop_index(batch_op.f('ix_maib_maisync_pairing_codes_expires_at'))
        batch_op.drop_index(batch_op.f('ix_maib_maisync_pairing_codes_code_hash'))

    op.drop_table('maib_maisync_pairing_codes')
