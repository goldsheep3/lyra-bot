"""services/mlist.py 获取对象列表相关 CRUD 操作"""
from typing import Optional, Sequence, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..constants import server
from . import execute_func
from .models import MaiData, MaiChart, MaiChartAch


__all__ = [
    # 便携导出
    "get_b50",

    # `MaiData` <- 流派/版本筛选
    "get_mdt_list",
    # `MaiChart` <- 等级定数筛选
    "get_mct_list",
    # `MaiChartAch` <- 完成率/ra筛选
    "get_mca_list",
]


class get_mdt_list:
    
    @staticmethod
    async def genre(genre: int, achs_user_id: Optional[int] = None,
                    *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """通过 流派ID 获取 `MaiData`（列表）"""
        async def _query(session: AsyncSession):
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .where(MaiData.genre == genre)
            )
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def version(ver: int | tuple[int, int], achs_user_id: Optional[int] = None, allow_utage: bool = False,
                      *, session: Optional[AsyncSession] = None) -> Sequence[MaiData]:
        """通过 版本范围 获取 `MaiData`（列表）"""
        async def _query(session: AsyncSession):
            if isinstance(ver, tuple):
                min_ver, max_ver = min(ver), max(ver)
            else:
                min_ver, max_ver = ver, ver
            stmt = (
                select(MaiData)
                .options(
                    selectinload(MaiData.charts)
                        .selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiData.aliases),
                )
                .where(
                    MaiData.version >= min_ver,
                    MaiData.version <= max_ver
                )
                .order_by(MaiData.version.desc(), MaiData.shortid.asc())
            )
            if not allow_utage:
                stmt = stmt.where(MaiData.is_utage == False)
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)


class get_mct_list:
    
    @staticmethod
    async def level(lv: float | tuple[float, float], server: server, achs_user_id: Optional[int] = None, allow_utage: bool = False,
                    *, session: Optional[AsyncSession] = None) -> Sequence[MaiChart]:
        """通过 等级范围 获取 `MaiChart`（列表）"""
        async def _query(session: AsyncSession):
            if isinstance(lv, tuple):
                min_lv, max_lv = min(lv), max(lv)
            else:
                min_lv, max_lv = lv, lv
            level_field = {
                "CN": MaiChart.lv_cn,
                "JP": MaiChart.lv,
            }.get(server, MaiChart.lv)

            stmt = (
                select(MaiChart)
                .options(
                    selectinload(MaiChart.achs.and_(MaiChartAch.user_id == achs_user_id)),
                    selectinload(MaiChart.maidata).selectinload(MaiData.aliases),
                )
                .where(level_field >= min_lv, level_field <= max_lv)
                .order_by(level_field.desc(), MaiChart.shortid.asc(), MaiChart.difficulty.asc())
            )
            if not allow_utage:
                stmt = stmt.join(MaiChart.maidata).where(MaiData.is_utage == False)
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)


class get_mca_list:

    @staticmethod
    async def user(user_id: int, server: server, allow_utage: bool = False,
                   *, session: Optional[AsyncSession] = None) -> Sequence[MaiChartAch]:
        """通过用户 ID 和服务器获取 `MaiChartAch`（列表）"""
        async def _query(session: AsyncSession):
            stmt = (
                select(MaiChartAch)
                .where(MaiChartAch.user_id == user_id, MaiChartAch.server == server)
            )
            if not allow_utage:
                stmt = stmt.join(MaiChartAch.chart).join(MaiChart.maidata).where(MaiData.is_utage == False)
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def b50(user_id: int, server: server, cut_version: int,
                  *, session: Optional[AsyncSession] = None) -> tuple[Sequence[MaiChartAch], Sequence[MaiChartAch]]:
        """
        通过 `user_id, server, cut_version` 获取 `MaiChartAch`（列表）（用于 best 50 生成）
        Returns:
        - b35 列表（版本 < cut_version，按 DX Rating 降序，最多 35 条）
        - b15 列表（版本 >= cut_version，按 DX Rating 降序，最多 15 条）
        """
        async def _select(target: Literal["b35", "b15"], session: AsyncSession) -> Sequence[MaiChartAch]:
            statement = (
                select(MaiChartAch)
                .join(MaiChartAch.chart)
                .join(MaiChart.maidata)
                .options(
                    selectinload(MaiChartAch.chart)
                    .selectinload(MaiChart.maidata)
                    .selectinload(MaiData.charts),
                )
                .where(
                    MaiChartAch.user_id == user_id,
                    MaiChartAch.server == server,
                    MaiData.is_utage == False
                )
                .order_by(MaiChartAch.dxrating.desc(), MaiChartAch.achievement.desc())
            )

            if server == "JP":
                version_field = MaiData.version
            elif server == "CN":
                version_field = MaiData.version_cn
            else:
                raise KeyError(f"Unknown server: {server}")

            if target == "b35":
                statement = statement.where(version_field < cut_version).limit(35)
            elif target == "b15":
                statement = statement.where(version_field >= cut_version).limit(15)
            return (await session.execute(statement)).scalars().all()

        async def _result(session: AsyncSession) -> tuple[Sequence[MaiChartAch], Sequence[MaiChartAch]]:
            best35_achs = await _select("b35", session)
            best15_achs = await _select("b15", session)
            return best35_achs, best15_achs

        return await execute_func.select(_result, session=session)


    @staticmethod
    async def achievement(ach: float | tuple[float, float], server: server, achs_user_id: int, allow_utage: bool = False,
                          *, session: Optional[AsyncSession] = None) -> Sequence[MaiChartAch]:
        """通过 完成率范围 获取 `MaiChartAch`（列表）"""
        async def _query(session: AsyncSession):
            if isinstance(ach, tuple):
                min_ach, max_ach = min(ach), max(ach)
            else:
                min_ach, max_ach = ach, ach

            stmt = (
                select(MaiChartAch)
                .options(
                    selectinload(MaiChartAch.chart)
                        .selectinload(MaiChart.maidata)
                        .selectinload(MaiData.aliases),
                )
                .where(MaiChartAch.user_id == achs_user_id)
                .where(MaiChartAch.server == server)
                .where(MaiChartAch.achievement >= min_ach, MaiChartAch.achievement <= max_ach)
                .order_by(
                    MaiChartAch.achievement.desc(),
                    MaiChartAch.dxrating.desc(),
                    MaiChartAch.shortid.asc(),
                    MaiChartAch.difficulty.asc(),
                )
            )
            if not allow_utage:
                stmt = stmt.join(MaiChartAch.chart).join(MaiChart.maidata).where(MaiData.is_utage == False)
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

    @staticmethod
    async def dxrating(dxra: float | tuple[float, float], server: server, achs_user_id: int,
                       *, session: Optional[AsyncSession] = None) -> Sequence[MaiChartAch]:
        """通过 DXRating 范围 获取 `MaiChartAch`（列表）"""
        async def _query(session: AsyncSession):
            if isinstance(dxra, tuple):
                min_dxra, max_dxra = min(dxra), max(dxra)
            else:
                min_dxra, max_dxra = dxra, dxra

            stmt = (
                select(MaiChartAch)
                .options(
                    selectinload(MaiChartAch.chart)
                        .selectinload(MaiChart.maidata)
                        .selectinload(MaiData.aliases),
                )
                .where(
                    MaiChartAch.user_id == achs_user_id,
                    MaiChartAch.server == server,
                    MaiChartAch.dxrating >= min_dxra,
                    MaiChartAch.dxrating <= max_dxra,
                    MaiData.is_utage == False
                )
                .order_by(
                    MaiChartAch.dxrating.desc(),
                    MaiChartAch.achievement.desc(),
                    MaiChartAch.shortid.asc(),
                    MaiChartAch.difficulty.asc(),
                )
            )
            return (await session.execute(stmt)).scalars().all()

        return await execute_func.select(_query, session=session)

# --- 便携导出 ---

get_b50 = get_mca_list.b50
