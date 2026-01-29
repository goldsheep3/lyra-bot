import time
from typing import List, Optional

from sqlalchemy import select, or_, delete
from sqlalchemy.orm import selectinload

from .models import plugin_data, MaiData, MaiChart, MaiAlias


get_session = plugin_data.get_session if plugin_data else None


# --- 1. 通过 shortid 查询指定乐曲 ---
async def get_song_by_id(shortid: int) -> Optional[MaiData]:
    """通过 shortid 获取乐曲，同时加载其所有谱面和别名"""
    async with get_session() as session:
        # 使用 selectinload 预加载关联表，避免异步环境下的惰性加载错误
        statement = (
            select(MaiData)
            .where(MaiData.shortid == shortid)
            .options(selectinload(MaiData.charts), selectinload(MaiData.aliases))
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()


# --- 2. 通过曲名查询列表 (支持模糊) ---
async def search_songs_by_name(name: str) -> List[MaiData]:
    """模糊搜索曲名"""
    async with get_session() as session:
        statement = (
            select(MaiData)
            .where(MaiData.title.contains(name))  # 相当于 LIKE '%name%'
            .options(selectinload(MaiData.charts), selectinload(MaiData.aliases))
        )
        result = await session.execute(statement)
        return result.scalars().all()


# --- 3. 通过别名查询列表 (支持模糊) ---
async def search_songs_by_alias(alias_name: str) -> List[MaiData]:
    """模糊搜索别名，并返回对应的乐曲列表"""
    async with get_session() as session:
        statement = (
            select(MaiData)
            .join(MaiAlias)  # 默认是 INNER JOIN，会自动过滤掉没有对应 MaiData 的别名
            .where(MaiAlias.alias.contains(alias_name))
            .distinct()
            .options(selectinload(MaiData.charts), selectinload(MaiData.aliases))
        )
        result = await session.execute(statement)
        return result.scalars().all()


# --- 4. 通过曲名和别名联合查询 ---
async def smart_search(keyword: str) -> List[MaiData]:
    """综合搜索：关键词匹配曲名 OR 别名"""
    async with get_session() as session:
        statement = (
            select(MaiData)
            .outerjoin(MaiAlias)  # 使用外连接，防止没有别名的曲目被过滤掉
            .where(
                or_(
                    MaiData.title.contains(keyword),
                    MaiAlias.alias.contains(keyword)
                )
            )
            .options(selectinload(MaiData.charts), selectinload(MaiData.aliases))
            .distinct()
        )
        result = await session.execute(statement)
        return result.scalars().all()


# --- 5. 根据谱面难度 (lv) 筛选 shortid 列表 ---
async def get_shortids_by_lv(min_lv: float, max_lv: float) -> List[int]:
    """
    查询定数在指定范围内的所有乐曲 ID
    """
    async with get_session() as session:
        statement = (
            select(MaiChart.shortid)
            .where(MaiChart.lv >= min_lv, MaiChart.lv <= max_lv)
            .distinct()
        )
        result = await session.execute(statement)
        return result.scalars().all()


# --- 6. 别名的添加 ---
async def add_alias(shortid: int, alias_text: str, qq: int, group_id: Optional[int] = None) -> bool:
    """添加别名，若已存在则返回 False"""
    async with get_session() as session:
        # 检查是否已存在该别名
        check_stmt = select(MaiAlias).where(MaiAlias.shortid == shortid, MaiAlias.alias == alias_text)
        existing = await session.execute(check_stmt)
        if existing.scalar_one_or_none():
            return False

        new_alias = MaiAlias(
            shortid=shortid,
            alias=alias_text,
            create_time=int(time.time()),
            create_qq=qq,
            create_qq_group=group_id
        )
        session.add(new_alias)
        await session.commit()
        return True


# --- 7. 别名的鉴权和删除 ---
async def get_alias_info(alias_text: str) -> List[MaiAlias]:
    """获取别名详情"""
    async with get_session() as session:
        stmt = select(MaiAlias).where(MaiAlias.alias == alias_text)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_alias_info_from_shortid(shortid: int) -> List[MaiAlias]:
    """获取曲目所有别名详情"""
    async with get_session() as session:
        statement = select(MaiAlias).where(MaiAlias.shortid == shortid)
        result = await session.execute(statement)
        return list(result.scalars().all())


async def delete_alias_by_id(alias_id: int):
    """根据别名 ID 删除"""
    async with get_session() as session:
        stmt = delete(MaiAlias).where(MaiAlias.id == alias_id)
        await session.execute(stmt)
        await session.commit()
