from datetime import date, timedelta
from typing import Sequence, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from nonebot_plugin_datastore import create_session

from . import RelationType
from .models import User, Record

async def get_user(
    platform: str,
    user_id: int,
    is_bot: bool = False) -> User:
    """获取用户配置，如果不存在则初始化一条默认记录"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            user = User(platform=platform, user_id=user_id, is_bot=is_bot)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
        return user

async def get_users_bulk(platform: str, users_data: list[dict]) -> dict[int, User]:
    """
    批量获取用户配置，如果不存在则批量初始化默认记录（仅占用 1 个数据库连接）
    :param users_data: 包含 {"user_id": int, "is_bot": bool} 的列表
    :return: 返回一个字典 {user_id: User对象}
    """
    if not users_data:
        return {}

    user_ids = [u["user_id"] for u in users_data]
    is_bot_map = {u["user_id"]: u["is_bot"] for u in users_data}

    async with create_session() as session:
        # 1. 一次性查询所有已存在的用户（核心优化：一条 SQL 搞定）
        stmt = select(User).where(User.platform == platform, User.user_id.in_(user_ids))
        result = await session.execute(stmt)
        existing_users = result.scalars().all()
        
        # 建立已存在用户的映射表
        user_map: dict[int, User] = {u.user_id: u for u in existing_users}
        
        # 2. 找出哪些用户不在数据库中，进行批量创建
        new_users = []
        for user_id in user_ids:
            if user_id not in user_map:
                new_user = User(
                    platform=platform, 
                    user_id=user_id, 
                    is_bot=is_bot_map[user_id]
                )
                session.add(new_user)
                new_users.append(new_user)
        
        # 3. 如果有新用户，统一提交一次
        if new_users:
            try:
                await session.commit()
                # 顺便把新生成的对象也塞进 map 里返回
                for u in new_users:
                    # 如果后续业务不需要立刻读取数据库自动生成的字段（如自增id/创建时间），
                    # 甚至可以不写 refresh，性能会更好。
                    await session.refresh(u) 
                    user_map[u.user_id] = u
            except Exception as e:
                await session.rollback()
                raise e
                
        return user_map

async def get_today_partner(
    platform: str, 
    group_id: int, 
    user_id: int, 
    relation_type: RelationType, 
    *, 
    session: Optional[AsyncSession] = None) -> Optional[Record]:
    """获取用户今天在该群的伴侣记录"""
    
    # 1. 构造通用的查询语句
    stmt = select(Record).where(
        Record.record_date == date.today(),
        Record.platform == platform,
        Record.group_id == group_id,
        Record.user_id == user_id,
        Record.relation_type == relation_type
    )
    
    # 2. 如果外部传了有效 session，直接复用它进行查询
    if session:
        return (await session.execute(stmt)).scalar_one_or_none()
        
    # 3. 如果外部没传，才自己开启并管理生命周期（比如单独调用该函数时）
    async with create_session() as new_session:
        return (await new_session.execute(stmt)).scalar_one_or_none()

async def set_today_partner(
    platform: str, 
    group_id: int, 
    user_id: int, 
    target_id: Optional[int], 
    relation_type: RelationType, 
    is_divorced: bool = False) -> Record:
    """设置或更新今天的伴侣（包含多方连带剥离的原子性操作）"""
    if is_divorced:
        target_id = None  # 离婚状态下，目标 ID 一定为 None

    opposite_type = RelationType.HUSBAND if relation_type == RelationType.WIFE else RelationType.WIFE

    async with create_session() as session:
        # 1. 查询当前用户的今日记录
        stmt = select(Record).where(
            Record.record_date == date.today(),
            Record.platform == platform,
            Record.group_id == group_id,
            Record.user_id == user_id,
            Record.relation_type == relation_type
        )
        record = (await session.execute(stmt)).scalar_one_or_none()
        record_old_target_id: Optional[int] = None

        if record:
            record_old_target_id = record.target_id  # 记录旧的目标 ID
            record.target_id = target_id
            record.is_divorced = is_divorced
            if target_id is not None:
                record.swap_count += 1
        else:
            # 新增初始化
            record = Record(
                record_date=date.today(),
                platform=platform,
                group_id=group_id,
                user_id=user_id,
                target_id=target_id,
                relation_type=relation_type,
                swap_count=0,
                is_divorced=is_divorced
            )
            session.add(record)

        # 2. 双方记录一致性及【连带被动剥离】处理
        # 注意：下面的 get_today_partner 必须显式传入 session 参数
        
        # 情况 A：当前用户绑定了新目标 (娶妻 或 嫁夫)
        if target_id is not None:
            # 查一下这个新目标今天的关系记录
            target_record = await get_today_partner(
                platform, group_id, target_id, relation_type=opposite_type, session=session
            )
            
            if target_record:
                old_partner_of_target = target_record.target_id
                # 【核心拦截】：如果新目标心里已经有别人了(old_partner_of_target)，且不是当前用户
                # 此时说明触发了“强娶”或“换伴侣”，这个“前任倒霉蛋”的对象被抢走了！
                if old_partner_of_target is not None and old_partner_of_target != user_id:
                    ex_partner_record = await get_today_partner(
                        platform, group_id, old_partner_of_target, relation_type=relation_type, session=session
                    )
                    if ex_partner_record:
                        ex_partner_record.target_id = None  # 强行剥离！倒霉蛋的目标变回 ×，完美触发路由2/7
                
                # 更新新目标的方向指针，指向当前用户
                target_record.target_id = user_id
            else:
                # 新目标今天还没生成记录，直接为对方新建一条
                new_target_record = Record(
                    record_date=date.today(),
                    platform=platform,
                    group_id=group_id,
                    user_id=target_id,
                    target_id=user_id,
                    relation_type=opposite_type,
                    swap_count=0
                )
                session.add(new_target_record)

        # 情况 B：当前用户主动抛弃了旧目标 (主动离婚 或 主动换人)
        if record_old_target_id is not None and record_old_target_id != target_id:
            # 找到旧目标的记录
            old_target_record = await get_today_partner(
                platform, group_id, record_old_target_id, relation_type=opposite_type, session=session
            )
            # 如果旧目标还指着当前用户，解绑它
            if old_target_record and old_target_record.target_id == user_id:
                old_target_record.target_id = None

        await session.commit()
        await session.refresh(record)
        return record

async def get_available_targets(
    platform: str,
    group_id: int,
    active_member_ids: list[int],
    current_user: User,
    relation_type: RelationType) -> dict[int, User]:
    """
    获取当前可用的抽选对象，核心过滤逻辑：
    1. 必须在传入的活跃成员列表 (active_member_ids) 中
    2. 排除自己
    3. 排除在数据库中已关闭该功能 (is_enabled=False) 的人
    4. 排除今天在该群内已经被别人选走的人（防止一妻多夫/一夫多妻）
    5. 根据当前用户的 allow_bot 设置，决定是否过滤机器人
    """
    if not active_member_ids:
        return {}

    async with create_session() as session:
        # 1. 批量查出群内活跃成员的 User 配置
        user_stmt = select(User).where(
            User.platform == platform,
            User.user_id.in_(active_member_ids),  # 过滤{1}: 活跃成员
            User.is_enabled == True  # 过滤{3}: 开启功能
        )
        users: Sequence[User] = (await session.execute(user_stmt)).scalars().all()

        # 2. 查出今天该群内已经被占用的 target_id 集合
        record_stmt = select(Record.target_id).where(
            Record.record_date == date.today(),
            Record.platform == platform,
            Record.group_id == group_id,
            Record.relation_type == relation_type
        )
        taken_targets = set((await session.execute(record_stmt)).scalars().all())

        # 3. 执行内存过滤
        targets: dict[int, User] = {
            u.user_id: u for u in users if not any([
                u.user_id == current_user.user_id,  # 过滤{2}: 不包括自己
                u.user_id in taken_targets,         # 过滤{4}: 不包括已被选走的人
                not current_user.allow_bot and u.is_bot  # 过滤{5}: 根据当前用户的 allow_bot 设置，决定是否过滤机器人
            ])
        }

        return targets

async def get_husband_record(platform: str, group_id: int, user_id: int) -> Optional[Record]:
    """查询谁把当前用户当成了老婆（即查询当前用户的老公）"""
    async with create_session() as session:
        stmt = select(Record).where(
            Record.record_date == date.today(),
            Record.platform == platform,
            Record.group_id == group_id,
            Record.target_id == user_id,       # 注意这里是 target_id
            Record.relation_type == RelationType.WIFE,
            Record.is_divorced == False        # 没有离婚
        )
        return (await session.execute(stmt)).scalar_one_or_none()

async def divorce_record(record_id: int) -> None:
    """通过记录 ID 标记离婚状态"""
    async with create_session() as session:
        record = await session.get(Record, record_id)
        if record:
            record.is_divorced = True
            await session.commit()

async def hope_for_user(platform: str, user_id: int, hope_id: Optional[int]) -> None:
    """设置用户的心愿单"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(platform=platform, user_id=user_id)
            session.add(user)
        
        user.hope_id = hope_id
        await session.commit()

async def update_user_setting(platform: str, user_id: int, **kwargs) -> None:
    """更新用户配置（例如开启/关闭分配、允许bot等）"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(platform=platform, user_id=user_id)
            session.add(user)
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await session.commit()
