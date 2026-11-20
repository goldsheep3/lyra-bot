"""不向调用方暴露 ORM 与 session 的曲目别名用例。"""

from __future__ import annotations

from typing import Literal, TypeAlias

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .._tool import get_session
from .._models import MaiAlias, MaiData


AliasAddStatus: TypeAlias = Literal["success", "exists", "missing"]
AliasRemoveStatus: TypeAlias = Literal[
    "success",
    "not_exists",
    "not_owner",
    "missing",
]


async def _song_exists(session: AsyncSession, shortid: int) -> bool:
    return await session.scalar(
        select(MaiData.shortid).where(MaiData.shortid == shortid)
    ) is not None


async def add_alias(shortid: int, alias: str, *, qq: int) -> AliasAddStatus:
    """添加曲目别名，并在同一事务内完成曲目及重复校验。"""
    async with get_session() as session:
        if not await _song_exists(session, shortid):
            return "missing"

        existing = await session.scalar(
            select(MaiAlias.id).where(
                MaiAlias.shortid == shortid,
                MaiAlias.name == alias,
            )
        )
        if existing is not None:
            return "exists"

        session.add(MaiAlias(shortid=shortid, name=alias, create_qq=qq))
        try:
            await session.commit()
        except IntegrityError:
            # 并发添加由数据库唯一约束裁决；回查以避免吞掉其他完整性错误。
            await session.rollback()
            existing = await session.scalar(
                select(MaiAlias.id).where(
                    MaiAlias.shortid == shortid,
                    MaiAlias.name == alias,
                )
            )
            if existing is not None:
                return "exists"
            if not await _song_exists(session, shortid):
                return "missing"
            raise
        return "success"


async def remove_alias(shortid: int, alias: str, *, qq: int) -> AliasRemoveStatus:
    """删除本人添加的别名；仅允许 ``create_qq == qq``。"""
    async with get_session() as session:
        if not await _song_exists(session, shortid):
            return "missing"

        existing = await session.scalar(
            select(MaiAlias).where(
                MaiAlias.shortid == shortid,
                MaiAlias.name == alias,
            )
        )
        if existing is None:
            return "not_exists"
        if existing.create_qq != qq:
            return "not_owner"

        await session.delete(existing)
        await session.commit()
        return "success"


__all__ = [
    "AliasAddStatus",
    "AliasRemoveStatus",
    "add_alias",
    "remove_alias",
]
