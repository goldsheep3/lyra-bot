"""services/user.py 用户相关 CRUD 操作"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import MaiUser


__all__ = [
    # 通过 user_id 获取用户对象
    "get_mu",
    "check_mu",
    # 通过 user_id 设置 username
    "set_mu_username",
    
    # 通过 telegram_id 获取用户对象
    "get_mu_from_tgid",
    # 通过 user_id 设置 telegram_id
    "set_mu_tgid",
    "del_mu_tgid",
]


async def get_mu(user_id: int,
                 *, session: Optional[AsyncSession] = None) -> Optional[MaiUser]:
    """通过 `user_id` 获取 `MaiUser`（唯一）"""
    async def _get_user_by_id(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.user_id == user_id)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()
    
    return await execute_func.select(_get_user_by_id, session=session)


async def check_mu(user_id: int,
                   *, session: Optional[AsyncSession] = None) -> MaiUser:
    """通过 `user_id` 获取用户数据，支持不存在自动创建"""
    async def _check_user_by_id(session: AsyncSession):
        user = await get_mu(user_id, session=session)
        if user:
            return user

        new_user = MaiUser(user_id=user_id)
        session.add(new_user)
        return new_user
    
    return await execute_func.action(_check_user_by_id, session=session, refresh=True)


async def set_mu_username(user_id: int, new_username: str,
                          *, session: Optional[AsyncSession] = None) -> None:
    """通过 `user_id` 设置 `MaiUser` 的 `username`"""
    async def _set_username(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.user_id == user_id)
        )
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        
        if user:
            user.username = new_username

    await execute_func.action(_set_username, session=session)


# --- telegram id 相关 ---

async def get_mu_from_tgid(telegram_id: int,
                           *, session: Optional[AsyncSession] = None) -> Optional[MaiUser]:
    """通过 `telegram_id` 获取 `MaiUser`（唯一）"""
    async def _get_user_by_telegram_id(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.user_telegram_id == telegram_id)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    return await execute_func.select(_get_user_by_telegram_id, session=session)


async def set_mu_tgid(user_id: int, telegram_id: int,
                      *, session: Optional[AsyncSession] = None) -> None:
    """通过 `user_id` 设置 `MaiUser` 的 `telegram_id`"""
    async def _set_telegram_id(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.user_id == user_id)
        )
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        
        if user:
            user.user_telegram_id = telegram_id
    
    await execute_func.action(_set_telegram_id, session=session)


async def del_mu_tgid(user_id: int,
                      *, session: Optional[AsyncSession] = None) -> None:
    """通过 `user_id` 移除 `MaiUser` 的 `telegram_id`"""
    async def _remove_telegram_id(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.user_id == user_id)
        )
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        
        if user:
            user.user_telegram_id = None
    
    await execute_func.action(_remove_telegram_id, session=session)
