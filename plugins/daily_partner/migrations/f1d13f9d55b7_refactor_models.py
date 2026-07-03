"""refactor_models

Revision ID: f1d13f9d55b7
Revises: fe62315a285e
Create Date: 2026-07-02 23:45:44.000000

"""
# 手动编写的迁移脚本。协助：Gemini 3.1 Pro

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1d13f9d55b7'
down_revision = 'fe62315a285e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ==========================================
    # User 表修改
    # ==========================================
    with op.batch_alter_table('daily_partner_user', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.BIGINT(), type_=sa.String(length=50), existing_nullable=False, postgresql_using="user_id::varchar")
        batch_op.alter_column('hope_id', existing_type=sa.BIGINT(), type_=sa.String(length=50), existing_nullable=True, postgresql_using="hope_id::varchar")

    # ==========================================
    # Record 表修改
    # ==========================================
    # --- 阶段 1. 添加新字段并修改旧字段类型 ---
    with op.batch_alter_table('daily_partner_record', schema=None) as batch_op:
        
        # 添加新字段
        batch_op.add_column(sa.Column('wife_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('husband_id', sa.String(length=50), nullable=True))

        # 转化现有类型
        batch_op.alter_column('group_id', existing_type=sa.BIGINT(), type_=sa.String(length=50), existing_nullable=False, postgresql_using="group_id::varchar")
        batch_op.alter_column('user_id', existing_type=sa.BIGINT(), type_=sa.String(length=50), existing_nullable=False, postgresql_using="user_id::varchar")


    # --- 阶段 2: 数据清洗与合并 ---
    # 1. 将 type=0 (娶老婆) 的 target_id 直接赋给 wife_id
    conn.execute(sa.text("""
        UPDATE daily_partner_record
        SET wife_id = CAST(target_id AS VARCHAR)
        WHERE relation_type = 0
    """))

    # 2. 查出所有 type=1 (嫁老公) 的记录，准备合并
    # 加上取 id，方便后续精准操作单行
    records = conn.execute(sa.text("""
        SELECT id, record_date, platform, group_id, user_id, target_id
        FROM daily_partner_record
        WHERE relation_type = 1
    """)).fetchall()

    for record in records:
        # 查找同属于该用户当天的 type=0 记录
        corresponding_wife = conn.execute(sa.text("""
            SELECT id
            FROM daily_partner_record
            WHERE record_date = :record_date 
              AND platform = :platform 
              AND group_id = :group_id 
              AND user_id = :user_id 
              AND relation_type = 0
        """), {
            "record_date": record.record_date,
            "platform": record.platform,
            "group_id": record.group_id,
            "user_id": record.user_id
        }).fetchone()

        if corresponding_wife:
            # 存在对应的老婆记录 -> 把 target_id 作为 husband_id 更新到老婆那条记录中
            conn.execute(sa.text("""
                UPDATE daily_partner_record
                SET husband_id = :husband_id
                WHERE id = :wife_record_id
            """), {
                "husband_id": str(record.target_id) if record.target_id is not None else None,
                "wife_record_id": corresponding_wife.id
            })
            # 合并完成，精准删除当前这条多余的 type=1 记录
            conn.execute(sa.text("""
                DELETE FROM daily_partner_record
                WHERE id = :record_id
            """), {"record_id": record.id})
        else:
            # 没有对应的老婆记录 -> 没必要新增，直接就地把这条 type=1 的记录当主记录，更新字段即可
            conn.execute(sa.text("""
                UPDATE daily_partner_record
                SET husband_id = CAST(target_id AS VARCHAR)
                WHERE id = :record_id
            """), {"record_id": record.id})


    # --- 阶段 3: 清理旧字段与建立新约束 ---
    with op.batch_alter_table('daily_partner_record', schema=None) as batch_op:
        # 移除旧索引（需确认 Alembic 之前生成的具体索引名称，通常自带 ix_ 前缀）
        batch_op.drop_index('ix_daily_partner_record_target_id')
        
        # 移除旧的联合唯一约束
        batch_op.drop_constraint('uq_daily_relation', type_='unique')

        # 移除旧字段
        batch_op.drop_column('target_id')
        batch_op.drop_column('relation_type')

        # 创建新的联合唯一约束
        batch_op.create_unique_constraint('uq_daily_relation', ['record_date', 'platform', 'group_id', 'user_id'])


def downgrade() -> None:
    conn = op.get_bind()

    # 阶段 1: Record 表 - 加回旧字段
    with op.batch_alter_table('daily_partner_record', schema=None) as batch_op:
        # 恢复 target_id 和 relation_type
        batch_op.add_column(sa.Column('target_id', sa.BIGINT(), nullable=True))
        batch_op.add_column(sa.Column('relation_type', sa.Integer(), nullable=True))

    # 阶段 2: 数据拆分与恢复 (核心逻辑)
    # 1. 恢复原本只娶了老婆的记录 (以及同时娶妻嫁夫的主记录)
    conn.execute(sa.text("""
        UPDATE daily_partner_record
        SET target_id = CAST(wife_id AS BIGINT), relation_type = 0
        WHERE wife_id IS NOT NULL
    """))

    # 2. 恢复原本只嫁了老公的记录 (wife_id 为空的情况，直接原地修改)
    conn.execute(sa.text("""
        UPDATE daily_partner_record
        SET target_id = CAST(husband_id AS BIGINT), relation_type = 1
        WHERE husband_id IS NOT NULL AND wife_id IS NULL
    """))

    # 3. 处理同时有老婆和老公的记录：
    # 主记录在第一步已经被标记为 relation_type = 0，
    # 现在我们需要额外 INSERT 一条 relation_type = 1 的记录来保存老公信息。
    conn.execute(sa.text("""
        INSERT INTO daily_partner_record 
            (record_date, platform, group_id, user_id, target_id, relation_type, swap_count, is_divorced)
        SELECT 
            record_date, platform, group_id, user_id, CAST(husband_id AS BIGINT), 1, swap_count, is_divorced
        FROM daily_partner_record
        WHERE wife_id IS NOT NULL AND husband_id IS NOT NULL
    """))

    # 阶段 3: 清理与恢复约束、索引和类型
    with op.batch_alter_table('daily_partner_record', schema=None) as batch_op:
        # 将 relation_type 设置为不可为空 (因为上面数据已经填充完毕)
        # 注意: 某些 SQLite 版本在此操作时可能需要保持 nullable=True，如果报错可将此行注释
        batch_op.alter_column('relation_type', existing_type=sa.Integer(), nullable=False)

        # 恢复旧的联合唯一约束
        batch_op.drop_constraint('uq_daily_relation', type_='unique')
        batch_op.create_unique_constraint('uq_daily_relation', ['record_date', 'platform', 'group_id', 'user_id', 'relation_type'])
        
        # 恢复索引
        batch_op.create_index(batch_op.f('ix_daily_partner_record_target_id'), ['target_id'], unique=False)

        # 删除新字段
        batch_op.drop_column('wife_id')
        batch_op.drop_column('husband_id')

        # 恢复 user_id 和 group_id 为 BIGINT
        batch_op.alter_column('group_id', 
                              existing_type=sa.String(length=50), 
                              type_=sa.BIGINT(), 
                              postgresql_using="group_id::bigint")
        batch_op.alter_column('user_id', 
                              existing_type=sa.String(length=50), 
                              type_=sa.BIGINT(), 
                              postgresql_using="user_id::bigint")

    # 阶段 4: User 表 - 恢复类型
    with op.batch_alter_table('daily_partner_user', schema=None) as batch_op:
        batch_op.alter_column('user_id', 
                              existing_type=sa.String(length=50), 
                              type_=sa.BIGINT(), 
                              postgresql_using="user_id::bigint")
        batch_op.alter_column('hope_id', 
                              existing_type=sa.String(length=50), 
                              type_=sa.BIGINT(), 
                              postgresql_using="hope_id::bigint")
