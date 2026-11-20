"""不向调用方暴露 ORM 与 session 的曲目别名用例。"""

from __future__ import annotations

from typing import Literal, TypeAlias
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ._tool import get_session, execute_func
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


async def add_ma_batch(data: list[tuple[int, str]], create_qq: int) -> None:
    """
    批量添加别名 (完美兼容 SQLite 与 PostgreSQL)
    :param data: 格式为 `[(shortid, alias), ...]`
    """
    if not data:
        return

    async def _sqlite_postgresql_action(native_insert, session: AsyncSession):
        chunk_size = 512
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            create_time = datetime.now()
            
            existing_ids = set(
                (await session.execute(
                    select(MaiData.shortid).where(MaiData.shortid.in_({s for s, _ in chunk}))
                )).scalars().all()
            )
            if not existing_ids:
                continue

            full_data = [
                {"shortid": sid, "name": alias, "create_qq": create_qq,
                 "create_at": create_time}
                for sid, alias in chunk if sid in existing_ids
            ]
            if not full_data:
                continue

            stmt = native_insert(MaiAlias).values(full_data)
            stmt = stmt.on_conflict_do_nothing(index_elements=["shortid", "name"])
            
            await session.execute(stmt)

    async def _action(session: AsyncSession):
        bind_engine = session.get_bind()
        dialect_name = bind_engine.dialect.name
        
        if dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as native_insert
            await _sqlite_postgresql_action(native_insert, session)
        elif dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as native_insert
            await _sqlite_postgresql_action(native_insert, session)
        else:
            raise NotImplementedError(f"当前方案暂不支持数据库: {dialect_name}")

    await execute_func.action(_action, session=None)


__all__ = [
    "AliasAddStatus",
    "AliasRemoveStatus",
    "add_alias",
    "remove_alias",
]
