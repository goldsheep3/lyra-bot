"""services/alias.py 别名相关 CRUD 操作"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ASIA_SHANGHAI
from . import execute_func
from .models import MaiAlias, MaiData


__all__ = [
    # 别名文本获取别名对象
    "get_ma",
    # 通过 shortid 添加别名
    "add_ma",
    # 通过 shortid 批量添加别名
    "add_ma_batch",
    # 通过 alias_id 删除别名
    "del_ma"
]


async def get_ma(alias_text: str, shortid: int,
                 *, session: Optional[AsyncSession] = None) -> Optional[MaiAlias]:
    """通过 别名, `shortid` 获取 `MaiAlias`（唯一）"""
    async def _query(session: AsyncSession):
        stmt = select(MaiAlias).where(MaiAlias.alias == alias_text, MaiAlias.shortid == shortid)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    return await execute_func.select(_query, session=session)


async def add_ma(shortid: int, alias_text: str, create_qq: int, create_qq_group: Optional[int] = None,
                 *, session: Optional[AsyncSession] = None) -> bool:
    """通过 `shortid` 添加别名，返回 False 表示已存在"""
    async def _action(session: AsyncSession):
        existing = await session.execute(
            select(MaiAlias).where(MaiAlias.shortid == shortid, MaiAlias.alias == alias_text)
        )
        if existing.scalar_one_or_none():
            return False
        session.add(MaiAlias(
            shortid=shortid, alias=alias_text, create_qq=create_qq,
            create_qq_group=create_qq_group, create_time=datetime.now(ASIA_SHANGHAI)
        ))
        return True

    return await execute_func.action(_action, session=session)


async def add_ma_batch(data: list[tuple[int, str]], create_qq: int,
                       *, session: Optional[AsyncSession] = None) -> None:
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
            create_time = datetime.now(ASIA_SHANGHAI)
            
            existing_ids = set(
                (await session.execute(
                    select(MaiData.shortid).where(MaiData.shortid.in_({s for s, _ in chunk}))
                )).scalars().all()
            )
            if not existing_ids:
                continue

            full_data = [
                {"shortid": sid, "alias": alias, "create_qq": create_qq,
                 "create_qq_group": None, "create_time": create_time}
                for sid, alias in chunk if sid in existing_ids
            ]
            if not full_data:
                continue

            stmt = native_insert(MaiAlias).values(full_data)
            stmt = stmt.on_conflict_do_nothing(index_elements=["shortid", "alias"])
            
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

    await execute_func.action(_action, session=session)


async def del_ma(alias_id: int,
                 *, session: Optional[AsyncSession] = None) -> None:
    """通过 `alias_id` 删除 `MaiAlias`"""
    async def _action(session: AsyncSession):
        stmt = delete(MaiAlias).where(MaiAlias.id == alias_id)
        await session.execute(stmt)

    await execute_func.action(_action, session=session)
