"""services/maime.py Aime Access 相关 CRUD 操作"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import Maime


__all__ = [
    "get_user_aimes",
    "get_aime",
    "get_aime_with_access4",
    "add_aime",
    "unlink_aime",
]


async def get_user_aimes(user_id: int, *, session: Optional[AsyncSession] = None) -> Sequence[Maime]:
    """通过 user_id 获取用户的 Aime 卡号"""
    async def _query(session: AsyncSession):
        stmt = select(Maime).where(Maime.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    return await execute_func.select(_query, session=session)


async def get_aime(access: str, *, session: Optional[AsyncSession] = None) -> Optional[Maime]:
    """通过 Aime 卡号获取绑定数据"""
    async def _query(session: AsyncSession):
        stmt = select(Maime).where(Maime.access == access)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    return await execute_func.select(_query, session=session)


async def get_aime_with_access4(access4: str, *, session: Optional[AsyncSession] = None) -> Sequence[Maime]:
    """通过 Aime 卡号后四位获取绑定数据"""
    async def _query(session: AsyncSession):
        stmt = select(Maime).where(Maime.access4 == access4)
        result = await session.execute(stmt)
        return result.scalars().all()

    return await execute_func.select(_query, session=session)


async def add_aime(access: str, user_id: int, *, session: Optional[AsyncSession] = None) -> bool:
    """添加 Aime 绑定数据，返回 False 表示已存在且已被绑定"""
    async def _action(session: AsyncSession):
        access4 = access[-4:]  # 获取 Aime 卡号后四位
        existing = (
            await session.execute(
                select(Maime).where(Maime.access == access)
            )
        ).scalar_one_or_none()

        if existing is not None:
            if existing.user_id is not None:
                return False  # 已被他人绑定
            # 已存在但未绑定（解绑过的），直接复用
            existing.user_id = user_id
            existing.create_at = datetime.now()
            return True

        session.add(Maime(
            access=access, user_id=user_id, access4=access4, create_at=datetime.now()
        ))
        return True

    return await execute_func.action(_action, session=session)


async def unlink_aime(access: str, *, session: Optional[AsyncSession] = None) -> bool:
    """解绑 Aime 绑定数据，仅置空 user_id，返回 False 表示不存在或未绑定"""
    async def _action(session: AsyncSession):
        maime = (
            await session.execute(
                select(Maime).where(Maime.access == access)
            )
        ).scalar_one_or_none()

        if maime is None or maime.user_id is None:
            return False

        maime.user_id = None
        return True

    return await execute_func.action(_action, session=session)