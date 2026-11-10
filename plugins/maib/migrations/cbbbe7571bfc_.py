"""merge maisync persistence and rename record timestamps

Revision ID: cbbbe7571bfc
Revises: 499fde437f07
Create Date: 2026-11-09 22:23:03.435209

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cbbbe7571bfc'
down_revision = '499fde437f07'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('maib_mailxns',
    sa.Column('qq', sa.BigInteger(), nullable=False),
    sa.Column('refresh_token', sa.String(length=512), nullable=False),
    sa.Column('refresh_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('refresh_scope', sa.String(length=255), nullable=False),
    sa.Column('refresh_is_active', sa.Boolean(), nullable=False),
    sa.Column('refresh_created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('refresh_updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('qq', name=op.f('pk_maib_mailxns'))
    )
    op.create_table('maib_maisync',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('qq', sa.BigInteger(), nullable=False),
    sa.Column('pairing_code', sa.String(length=64), nullable=False),
    sa.Column('pairing_created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('pairing_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('pairing_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('token', sa.String(length=64), nullable=False),
    sa.Column('token_created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('device_name', sa.String(length=128), nullable=False),
    sa.Column('token_last_used_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('token_revoked', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_maib_maisync'))
    )
    with op.batch_alter_table('maib_maisync', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maisync_pairing_code'), ['pairing_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_maib_maisync_qq'), ['qq'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maisync_token'), ['token'], unique=True)

    # Preserve the old pairing records as expired/revoked tokens.  The old
    # schema stores pairing codes and long-lived tokens in separate tables,
    # while MaiSync stores both in one row.
    op.execute("""
        INSERT INTO maib_maisync (
            qq, pairing_code, pairing_created_at, pairing_expires_at,
            pairing_used_at, token, token_created_at, device_id,
            device_name, token_last_used_at, token_revoked
        )
        SELECT
            user_id, code_hash, create_time, expires_at,
            used_at, code_hash, create_time, '', '', create_time, TRUE
        FROM maib_maisync_pairing_codes
    """)
    op.execute("""
        INSERT INTO maib_maisync (
            qq, pairing_code, pairing_created_at, pairing_expires_at,
            pairing_used_at, token, token_created_at, device_id,
            device_name, token_last_used_at, token_revoked
        )
        SELECT
            user_id, token_hash, create_time, create_time,
            create_time, token_hash, create_time, device_id,
            device_name, last_used_at,
            CASE WHEN revoked_at IS NULL THEN FALSE ELSE TRUE END
        FROM maib_maisync_tokens
    """)
    op.drop_table('maib_maisync_pairing_codes')
    op.drop_table('maib_maisync_tokens')

    with op.batch_alter_table('maib_mairecords', schema=None) as batch_op:
        batch_op.alter_column('play_time', new_column_name='play_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('update_time', new_column_name='update_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diving_fish_sub', sa.Integer(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.drop_column('diving_fish_sub')

    with op.batch_alter_table('maib_mairecords', schema=None) as batch_op:
        batch_op.alter_column('play_at', new_column_name='play_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('update_at', new_column_name='update_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)

    op.create_table('maib_maisync_pairing_codes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('create_time', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_maib_maisync_pairing_codes')),
        sa.UniqueConstraint('code_hash', name=op.f('uq_maib_maisync_pairing_codes_code_hash')),
    )
    with op.batch_alter_table('maib_maisync_pairing_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maisync_pairing_codes_code_hash'), ['code_hash'], unique=False)
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
        sa.UniqueConstraint('user_id', name=op.f('uq_maib_maisync_tokens_user_id')),
        sa.UniqueConstraint('token_hash', name=op.f('uq_maib_maisync_tokens_token_hash')),
    )
    with op.batch_alter_table('maib_maisync_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maisync_tokens_token_hash'), ['token_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maisync_tokens_user_id'), ['user_id'], unique=False)

    op.execute("""
        INSERT INTO maib_maisync_pairing_codes (
            user_id, code_hash, expires_at, used_at, revoked, create_time
        )
        SELECT
            qq, pairing_code, pairing_expires_at, pairing_used_at,
            CASE WHEN pairing_used_at IS NULL THEN FALSE ELSE TRUE END,
            pairing_created_at
        FROM maib_maisync
    """)
    op.execute("""
        INSERT INTO maib_maisync_tokens (
            user_id, token_hash, device_id, device_name,
            create_time, last_used_at, revoked_at
        )
        SELECT
            qq, token, device_id, device_name,
            token_created_at, token_last_used_at,
            CASE WHEN token_revoked THEN token_last_used_at ELSE NULL END
        FROM maib_maisync
        WHERE token_revoked = 0
    """)

    with op.batch_alter_table('maib_maisync', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maisync_token'))
        batch_op.drop_index(batch_op.f('ix_maib_maisync_qq'))
        batch_op.drop_index(batch_op.f('ix_maib_maisync_pairing_code'))

    op.drop_table('maib_maisync')
    op.drop_table('maib_mailxns')
