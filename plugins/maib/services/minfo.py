"""services/query.py 获取对象相关 CRUD 操作"""
from typing import Optional, Sequence, Literal

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..utils.exceptions import BlurSearchTooManyResultsError
from ..constants import server
from .. import config
from . import execute_func
from .models import MaiData, MaiChart, MaiChartAch, MaiAlias


__all__ = [
    # 曲目数据读写
    "get_mdt",
    # 曲目/谱面数据新增
    "add_mdt",
    "add_mct",
    # 成绩数据获取
    "get_mca",
]


class get_mdt:
    
    @staticmethod
    async def id(shortid: int, achs_user_id: Optional[int] = None,
                 *, session: Optional[AsyncSession] = None) -> Optional[MaiData]:
        """通过 `shortid` 获取 `MaiData`（唯一）"""
        async def _query(session: AsyncSession):
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .where(MaiData.shortid == shortid)
            )
            return (await session.execute(stmt)).scalar_one_or_none()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def title(keyword: str, achs_user_id: Optional[int] = None, way: Literal['title', 'name', 'blur', 'smart'] = 'smart',
                    *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """
        :param keyword: 曲名/别名
        :param achs_user_id: 用户 ID，用于获取该用户的谱面成绩
        :param way: 查询方式
        - title: 精确匹配 title
        - name: 精确匹配 title/alias
        - blur: 模糊匹配 title/alias
        - smart: 智能匹配 title/alias（先精确匹配 title/alias，再模糊匹配 title/alias）
        """
                
        async def _smart(session: AsyncSession):
            result = await get_mdt._name(keyword, achs_user_id=achs_user_id, session=session)
            if not result:
                result = await get_mdt._blur(keyword, achs_user_id=achs_user_id, session=session)
            return result
        
        if way == 'smart':
            # 智能匹配 title/alias
            return await execute_func.select(_smart, session=session)
        elif way == 'title':
            # 精确匹配 title
            return await get_mdt._title(keyword, achs_user_id=achs_user_id, session=session)
        elif way == 'name':
            # 精确匹配 title/alias
            return await get_mdt._name(keyword, achs_user_id=achs_user_id, session=session)
        elif way == 'blur':
            # 模糊匹配 title/alias
            return await get_mdt._blur(keyword, achs_user_id=achs_user_id, session=session)

        raise KeyError(f"Unknown way: {way}")

    @staticmethod
    async def _title(title: str, achs_user_id: Optional[int] = None,
                     *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """通过 `曲名` 获取 `MaiData`（列表）"""
        async def _query(session: AsyncSession):
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .outerjoin(MaiAlias)
                .where(MaiData.title == title)
                .distinct()
            )
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def _name(keyword: str, achs_user_id: Optional[int] = None,
                    *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """通过 曲名/别名 精确获取 `MaiData`（列表）"""
        async def _query(session: AsyncSession):
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .outerjoin(MaiAlias)
                .where(or_(MaiData.title == keyword, MaiAlias.alias == keyword))
                .distinct()
            )
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def _blur(keyword: str, achs_user_id: Optional[int] = None,
                    *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """通过 曲名/别名 模糊获取 `MaiData`（列表）"""
        async def _query(session: AsyncSession):
            filters = or_(MaiData.title.contains(keyword), MaiAlias.alias.contains(keyword))
            count = (await session.execute(
                select(func.count()).select_from(
                    select(MaiData.shortid).outerjoin(MaiAlias).where(filters).distinct().subquery()
                )
            )).scalar_one()
            if count > config.MAX_BLUR_SEARCH_RESULTS:
                raise BlurSearchTooManyResultsError(f"模糊搜索结果过多（{count} 条），请尝试更精确的关键词进行搜索喵qwq")
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .outerjoin(MaiAlias)
                .where(filters)
                .distinct()
            )
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)


async def add_mdt(mdt: MaiData,
                  *, session: Optional[AsyncSession] = None) -> None:
    """新增 `MaiData`"""
    async def _action(session: AsyncSession):
        session.add(mdt)
    
    await execute_func.action(_action, session=session)


async def add_mct(shortid: int, mct: MaiChart,
                  *, session: Optional[AsyncSession] = None) -> None:
    """通过 `shortid` 新增 `MaiChart`"""
    async def _action(session: AsyncSession):
        mdt = (await session.execute(
            select(MaiData)
            .where(MaiData.shortid == shortid)
        )).scalar_one_or_none()
        if mdt:
            mdt.charts.append(mct)

    await execute_func.action(_action, session=session)



async def get_mca(user_id: int, server: server, shortid: int, difficulty: int,
                  *, session: AsyncSession) -> Optional[MaiChartAch]:
    """通过 `user_id, server, shortid, difficulty` 获取 `MaiChartAch`（唯一）"""
    async def _select(session: AsyncSession):
        statement = (
            select(MaiChartAch)
            .where(
                MaiChartAch.user_id == user_id,
                MaiChartAch.server == server,
                MaiChartAch.shortid == shortid,
                MaiChartAch.difficulty == difficulty
            )
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    return await execute_func.select(_select, session=session)
