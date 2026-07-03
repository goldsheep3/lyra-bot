from datetime import date
from typing import Sequence, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from nonebot_plugin_datastore import create_session

from .models import Record, User, Group


def check_dict_consistency(input: dict, standard: dict) -> bool:
    """一致性检查"""
    return all(
        standard.get(k) == v
        for k, v in input.items()
    )


async def check_user(platform: str, user_id: str, **kwargs) -> User:
    """获取或更新用户配置，含初始化逻辑"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        if not user:
            user = User(platform=platform, user_id=user_id, **kwargs)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

        if not check_dict_consistency(kwargs, user.dict()):
            # 更新用户配置
            for key, value in kwargs.items():
                setattr(user, key, value)

            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

        return user


async def check_group(platform: str, group_id: str, **kwargs) -> Group:
    """获取或更新群组配置，含初始化逻辑"""
    async with create_session() as session:
        stmt = select(Group).where(Group.platform == platform, Group.group_id == group_id)
        group = (await session.execute(stmt)).scalar_one_or_none()
        
        if not group:
            group = Group(platform=platform, group_id=group_id, **kwargs)
            session.add(group)
            await session.commit()
            await session.refresh(group)
            return group

        if not check_dict_consistency(kwargs, group.dict()):
            # 更新群组配置
            for key, value in kwargs.items():
                if hasattr(group, key):
                    setattr(group, key, value)
            await session.commit()
            await session.refresh(group)
            return group

        return group



async def check_users_bulk(platform: str, users_data: list[dict]) -> dict[str, User]:
    """
    批量获取用户配置，如果不存在则批量初始化默认记录
    :param users_data: 包含 {"user_id": str, "is_bot": bool} 的列表
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
        user_map: dict[str, User] = {u.user_id: u for u in existing_users}
        
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
                    # 自增id和创建时间 不需要立即读取，refresh 先忽略
                    # await session.refresh(u) 
                    user_map[u.user_id] = u
            except Exception as e:
                await session.rollback()
                raise
                
        return user_map


async def get_today_partner(
    platform: str, group_id: str, user_id: str, *,
    session: Optional[AsyncSession] = None) -> Record:
    """获取用户今天在该群的伴侣记录"""
    
    async def _get_record_with_session(session: AsyncSession) -> tuple[Record, bool]:
        """带有 session 的内部复用函数"""
        stmt = select(Record).where(
            Record.record_date == date.today(),
            Record.platform == platform,
            Record.group_id == group_id,
            Record.user_id == user_id,
            )
        
        record = (await session.execute(stmt)).scalar_one_or_none()
        if not record:
            # 暂无记录，创建默认记录
            record = Record(
                record_date=date.today(),
                platform=platform,
                group_id=group_id,
                user_id=user_id,
                wife_id=None,
                husband_id=None,
                swap_count=-1,  # -1 标识为未初始化状态，jrlp抽选逻辑 +1 后计算为 0
                is_divorced=False
            )
            session.add(record)
            return record, True  # 返回 True 表示是新创建的记录
        return record, False  # 返回 False 表示是已有记录
    
    # 传入 session 直接使用
    if session:
        record, created = await _get_record_with_session(session)
        if created:
            await session.flush()  # 刷新该记录以保证一致性
        return record

    # 未传入 session 独立开启
    async with create_session() as session:
        record, _ = await _get_record_with_session(session)
        await session.commit()
        await session.refresh(record)  # 刷新该记录以保证一致性
        return record
    

async def set_today_wife(
    platform: str,
    group_id: str,
    user_id: str,
    wife_id: Optional[str],
    is_divorced: bool = False) -> Record:
    """设置或更新「今日老婆」"""
    wife_id = None if is_divorced else wife_id
    
    async with create_session() as session:
        user_record: Record = await get_today_partner(platform, group_id, user_id, session=session)
        user_wife_id_old = user_record.wife_id  # 记录旧的老婆 ID
        if user_wife_id_old == wife_id:
            return user_record  # 如果老婆没有变化，直接返回，不做后续处理
        
        user_record.wife_id = wife_id
        user_record.is_divorced = is_divorced
        user_record.swap_count += 1

        # 新 wife 存在，「解决」新 wife 的原 husband
        if wife_id is not None:
            
            # 处理老婆的记录，确保双方一致性
            new_wife_record: Record = await get_today_partner(platform, group_id, wife_id, session=session)
            new_wife_husband_id_old = new_wife_record.husband_id  # 记录老婆旧的老公 ID
            
            new_wife_record.husband_id = user_id
            
            if new_wife_husband_id_old is not None and new_wife_husband_id_old != user_id:
                # 如果老婆已经有老公了，且不是当前用户，则剥离旧老公的指针
                old_husband_record: Record = await get_today_partner(platform, group_id, new_wife_husband_id_old, session=session)
                if old_husband_record.wife_id == wife_id:
                    old_husband_record.wife_id = None  # 解绑旧老公的指针

        # 旧 wife 存在，「解决」旧 wife 的 husband 指针
        if user_wife_id_old is not None:
            old_wife_record: Record = await get_today_partner(platform, group_id, user_wife_id_old, session=session)
            if old_wife_record.husband_id == user_id:
                old_wife_record.husband_id = None  # 解绑旧老婆的指针
        
        await session.commit()
        await session.refresh(user_record)
    
        return user_record


async def set_today_husband(
    platform: str,
    group_id: str,
    user_id: str,
    husband_id: Optional[str],
    is_divorced: bool = False) -> Record:
    """设置或更新「今日老公」"""
    husband_id = None if is_divorced else husband_id
    
    async with create_session() as session:
        user_record: Record = await get_today_partner(platform, group_id, user_id, session=session)
        user_husband_id_old = user_record.husband_id
        if user_husband_id_old == husband_id:
            return user_record    # 如果老公没有变化，直接返回，不做后续处理
        
        user_record.husband_id = husband_id
        user_record.is_divorced = is_divorced
        user_record.swap_count += 1

        # 新 husband 存在，处理新 husband 以及他可能存在的原 wife
        if husband_id is not None:
            new_husband_record: Record = await get_today_partner(platform, group_id, husband_id, session=session)
            new_husband_wife_id_old = new_husband_record.wife_id
            
            new_husband_record.wife_id = user_id
    
            if new_husband_wife_id_old is not None and new_husband_wife_id_old != user_id:
                old_wife_record: Record = await get_today_partner(platform, group_id, new_husband_wife_id_old, session=session)
                if old_wife_record.husband_id == husband_id:
                    old_wife_record.husband_id = None

        # 旧 husband 存在，处理旧 husband
        if user_husband_id_old is not None:
            old_husband_record: Record = await get_today_partner(platform, group_id, user_husband_id_old, session=session)
            # 如果旧老公的老婆还是当前用户，解除绑定
            if old_husband_record.wife_id == user_id:
                old_husband_record.wife_id = None
        
        # 统一提交事务
        await session.commit()
        await session.refresh(user_record)
    
        return user_record


async def get_wifeable_targets(
    platform: str,
    group_id: str,
    active_member_ids: list[str] | None,
    current_user: User) -> dict[str, User]:
    """获取当前可用的「选老婆」抽选对象"""
    async with create_session() as session:
        
        # 查询符合条件{1,2,3,4}的用户
        user_stmt = select(User).where(
            User.platform == platform,
            # 过滤{2}: 排除在数据库中已关闭该功能 (is_enabled=False) 的人
            User.is_enabled == True,
            # 过滤{3}: 排除自己
            User.user_id != current_user.user_id,
        )
        if not current_user.allow_bot:
            # 过滤{4}: 根据当前用户的 allow_bot 设置，决定是否过滤机器人
            user_stmt = user_stmt.where(User.is_bot == False)
        if active_member_ids is not None:
            # 过滤{1}: 若存在传入列表，则只考虑活跃成员
            user_stmt = user_stmt.where(User.user_id.in_(active_member_ids))
        users: Sequence[User] = (await session.execute(user_stmt)).scalars().all()
        
        # 查询符合条件{5}的记录
        record_stmt = select(Record).where(
            Record.record_date == date.today(),
            Record.platform == platform,
            Record.group_id == group_id,
            # 过滤{5}: 排除今天在该群内已经被别人选走作为老婆的人
            Record.wife_id.is_not(None),
        )
        records: Sequence[Record] = (await session.execute(record_stmt)).scalars().all()
        taken_targets: set[str] = {r.wife_id for r in records if r.wife_id is not None}
        
        # 通过 users 列表和 taken_targets 集合，过滤出最终可选的对象
        targets: dict[str, User] = {user.user_id: user for user in users if user.user_id not in taken_targets}

        return targets
    

async def hope_for_user(platform: str, user_id: str, hope_id: Optional[str]) -> None:
    """设置用户的心愿单"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            user = User(platform=platform, user_id=user_id)
            session.add(user)
        
        user.hope_id = hope_id
        await session.commit()


async def update_user_setting(platform: str, user_id: str, **kwargs) -> None:
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


async def check_bot_settings(platform: str, user_id: str) -> None:
    """检查 bot 固有的 is_bot 和 is_enabled 设置，如果不符合预期则修正"""
    async with create_session() as session:
        stmt = select(User).where(User.platform == platform, User.user_id == user_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        
        # 不存在立即创建
        if not user:
            user = User(platform=platform, user_id=user_id, is_bot=True, is_enabled=False)
            session.add(user)
            await session.commit()
            return
        
        # 存在检查
        if (user.is_bot == True) and (user.is_enabled == False):
            return  # 已经符合预期，无需修改

        # 存在修改
        user.is_bot = True
        user.is_enabled = False
        await session.commit()
