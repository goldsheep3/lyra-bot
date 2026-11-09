"""refactor maib persistence fields

Revision ID: 499fde437f07
Revises: 82b34846262c
Create Date: 2026-11-09 20:53:29.664540

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '499fde437f07'
down_revision = '82b34846262c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE maib_maidatas SET artist = '' WHERE artist IS NULL")
    op.execute("UPDATE maib_maichartachs SET achievement = achievement * 10000")

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('create_by', sa.Integer(), nullable=True))
        batch_op.alter_column(
            'create_time',
            new_column_name='create_at',
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        batch_op.drop_column('create_qq_group')

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('provider', sa.String(length=16), nullable=False, server_default='unknown'))
        batch_op.alter_column('user_id', new_column_name='qq', existing_type=sa.BigInteger(), existing_nullable=True)
        batch_op.alter_column(
            'update_time',
            new_column_name='update_at',
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        batch_op.alter_column('dxrating', new_column_name='dxrating_cache', existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column('achievement',
               existing_type=sa.FLOAT(),
               type_=sa.Integer(),
               existing_nullable=False,
               postgresql_using='achievement::integer')
        batch_op.drop_constraint(batch_op.f('uq_maib_maichartachs_user_id'), type_='unique')
        batch_op.alter_column('provider', server_default=None)

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_maib_maichartachs_qq_shortid_difficulty_provider_server',
            ['qq', 'shortid', 'difficulty', 'provider', 'server'],
        )

    op.execute("""
        UPDATE maib_maichartachs
        SET provider = CASE server
            WHEN 'JP' THEN 'lyrasync-oto'
            WHEN 'CN' THEN 'diving-fish'
            ELSE 'unknown'
        END
    """)

    with op.batch_alter_table('maib_maicharts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maicharts_lv'))
        batch_op.drop_index(batch_op.f('ix_maib_maicharts_lv_synh'))
        batch_op.alter_column('lv', new_column_name='lv_jp', existing_type=sa.Float(), existing_nullable=False)
        batch_op.alter_column('lv_synh', new_column_name='lv_fit', existing_type=sa.Float(), existing_nullable=True)
        batch_op.alter_column('des', new_column_name='designer', existing_type=sa.String(), existing_nullable=False)

    with op.batch_alter_table('maib_maicharts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maicharts_difficulty'), ['difficulty'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maicharts_lv_fit'), ['lv_fit'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maicharts_lv_jp'), ['lv_jp'], unique=False)

    with op.batch_alter_table('maib_maidatas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('img_path', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('_tg_zip_id_cache', sa.String(), nullable=True))
        batch_op.alter_column('version', new_column_name='version_jp', existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column('converter', new_column_name='provider', existing_type=sa.String(), existing_nullable=True)
        batch_op.alter_column('tg_file_id_cache', new_column_name='_tg_adx_id_cache', existing_type=sa.String(), existing_nullable=True)
        batch_op.alter_column('artist',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.alter_column('zip_path',
               existing_type=sa.VARCHAR(),
               nullable=True)

    op.execute("UPDATE maib_maidatas SET provider = 'unknown' WHERE provider IS NULL")
    op.execute("""
        UPDATE maib_maidatas
        SET img_path = CASE
            WHEN zip_path IS NULL OR zip_path = '' THEN ''
            ELSE zip_path || '/bg.png'
        END
    """)
    with op.batch_alter_table('maib_maidatas', schema=None) as batch_op:
        batch_op.alter_column('provider', existing_type=sa.String(), nullable=False)
        batch_op.alter_column('img_path', existing_type=sa.String(), nullable=False)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maiusers_user_telegram_id'))
        batch_op.alter_column('user_id', new_column_name='qq', existing_type=sa.BigInteger(), existing_nullable=False)
        batch_op.alter_column('user_telegram_id', new_column_name='tg', existing_type=sa.BigInteger(), existing_nullable=True)
        batch_op.alter_column('jp_update_time', new_column_name='jp_update_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('cn_update_time', new_column_name='cn_update_at', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('last_sy_hash', new_column_name='_diving_fish_records_hash_cache', existing_type=sa.String(), existing_nullable=True)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maiusers_tg'), ['tg'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maiusers_tg'))
        batch_op.alter_column('qq', new_column_name='user_id', existing_type=sa.BigInteger(), existing_nullable=False)
        batch_op.alter_column('tg', new_column_name='user_telegram_id', existing_type=sa.BigInteger(), existing_nullable=True)
        batch_op.alter_column('jp_update_at', new_column_name='jp_update_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('cn_update_at', new_column_name='cn_update_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('_diving_fish_records_hash_cache', new_column_name='last_sy_hash', existing_type=sa.String(), existing_nullable=True)

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maiusers_user_telegram_id'), ['user_telegram_id'], unique=True)

    op.execute("UPDATE maib_maidatas SET zip_path = '' WHERE zip_path IS NULL")
    with op.batch_alter_table('maib_maidatas', schema=None) as batch_op:
        batch_op.alter_column('version_jp', new_column_name='version', existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column('provider', new_column_name='converter', existing_type=sa.String(), existing_nullable=False)
        batch_op.alter_column('_tg_adx_id_cache', new_column_name='tg_file_id_cache', existing_type=sa.String(), existing_nullable=True)
        batch_op.alter_column('zip_path',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.alter_column('artist',
               existing_type=sa.VARCHAR(),
               nullable=True)
        batch_op.drop_column('_tg_zip_id_cache')
        batch_op.drop_column('img_path')

    with op.batch_alter_table('maib_maicharts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maib_maicharts_lv_jp'))
        batch_op.drop_index(batch_op.f('ix_maib_maicharts_lv_fit'))
        batch_op.drop_index(batch_op.f('ix_maib_maicharts_difficulty'))
        batch_op.alter_column('lv_jp', new_column_name='lv', existing_type=sa.Float(), existing_nullable=False)
        batch_op.alter_column('lv_fit', new_column_name='lv_synh', existing_type=sa.Float(), existing_nullable=True)
        batch_op.alter_column('designer', new_column_name='des', existing_type=sa.String(), existing_nullable=False)

    with op.batch_alter_table('maib_maicharts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maib_maicharts_lv_synh'), ['lv_synh'], unique=False)
        batch_op.create_index(batch_op.f('ix_maib_maicharts_lv'), ['lv'], unique=False)

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.drop_constraint('uq_maib_maichartachs_qq_shortid_difficulty_provider_server', type_='unique')

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.alter_column('qq', new_column_name='user_id', existing_type=sa.BigInteger(), existing_nullable=True)
        batch_op.alter_column('update_at', new_column_name='update_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.alter_column('dxrating_cache', new_column_name='dxrating', existing_type=sa.Integer(), existing_nullable=False)
        batch_op.alter_column('achievement',
               existing_type=sa.Integer(),
               type_=sa.FLOAT(),
               existing_nullable=False,
               postgresql_using='achievement::double precision')

    with op.batch_alter_table('maib_maichartachs', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_maib_maichartachs_user_id'), ['user_id', 'shortid', 'difficulty', 'server'])
        batch_op.drop_column('provider')

    op.execute("UPDATE maib_maichartachs SET achievement = achievement / 10000.0")

    with op.batch_alter_table('maib_maialiases', schema=None) as batch_op:
        batch_op.add_column(sa.Column('create_qq_group', sa.BigInteger(), nullable=True))
        batch_op.alter_column('create_at', new_column_name='create_time', existing_type=sa.DateTime(timezone=True), existing_nullable=False)
        batch_op.drop_column('create_by')
