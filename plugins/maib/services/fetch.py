"""services/fetch.py 定数、版本等 fetch 相关 CRUD 操作"""
from typing import Optional, Literal, cast

from sqlalchemy import Table, select, update, bindparam
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import MaiData, MaiChart
from ..utils.enums import Server, SLevelSource


__all__ = [
    # 设置谱面对象定数
    "set_mct_level",
    "set_mct_level_batch",
    # 设置曲目对象版本
    "set_mct_version",
    "set_mdt_version_batch",
    # 同步曲目列表
    "sync_mdt_list",
]


async def set_mct_level(mct: MaiChart | tuple[int, int], source: SLevelSource, level: float,
                        *, session: Optional[AsyncSession] = None):
    """
    设置 `MaiChart` 的 `level`
    :param mct: `(shortid, difficulty)`，或直接提供`MaiChart`
    """ 
    async def _action(session: AsyncSession):
        chart = mct if isinstance(mct, MaiChart) else (
            await session.execute(
                select(MaiChart).where(MaiChart.shortid == mct[0], MaiChart.difficulty == mct[1])
            )
        ).scalar_one_or_none()
        if not chart:
            return
        setattr(chart, source.lv_field, level)

    await execute_func.action(_action, session=session)


async def set_mct_level_batch(data: list[dict], source: SLevelSource,
                              *, session: Optional[AsyncSession] = None):
    """批量设置谱面定数"""
    if not data:
        return

    async def _action(session: AsyncSession):
        table = cast(Table, MaiChart.__table__)
        value = getattr(table.c, source.lv_field)

        stmt = (
            update(table)
            .where(table.c.shortid == bindparam("b_shortid"))
            .where(table.c.difficulty == bindparam("b_diff"))
            .values({value: bindparam("b_level")})
            .execution_options(synchronize_session=False)
        )

        await session.execute(
            stmt,
            [
                {
                    "b_shortid": int(d["shortid"]),
                    "b_diff": int(d["difficulty"]),
                    "b_level": float(d["level"]),
                }
                for d in data
            ]
        )

    await execute_func.action(_action, session=session)


async def set_mct_version(shortid: int, version: int, server: Server,
                          *, session: Optional[AsyncSession] = None) -> None:
    """通过 `shortid, server` 设置 `MaiData` 的 `version`"""
    async def _set_mct_version(session: AsyncSession):
        statement = (
            select(MaiData)
            .where(MaiData.shortid == shortid)
        )
        result = await session.execute(statement)
        mdt = result.scalar_one_or_none()

        if mdt:
            setattr(mdt, SLevelSource.server(server).lv_field, version)
        return

    await execute_func.action(_set_mct_version, session=session)


async def set_mdt_version_batch(data: list[tuple[int, int]], server: Server,
                                *, session: Optional[AsyncSession] = None) -> None:
    """
    [批量] 设置 `MaiData` 的 `version`
    :param data: 格式为 `[(shortid, version), ...]`
    """
    if not data:
        return

    async def _set_mdt_version_batch(session: AsyncSession):
        # 1. 映射服务器标签到数据库字段
        table = MaiData.__table__
        target = getattr(table.c, server.version_field)

        # 2. 构建动态批量更新语句
        statement = (
            update(table)  # type: ignore
            .where(table.c.shortid == bindparam("b_shortid"))
            .values({target: bindparam("b_version")})
            .execution_options(synchronize_session=False)
        )

        # 3. 执行批量更新
        await session.execute(statement, [{"b_shortid": sid, "b_version": version} for sid, version in data])
    
    await execute_func.action(_set_mdt_version_batch, session=session)


async def sync_mdt_list(mdt_list: list[MaiData],
                        *, session: Optional[AsyncSession] = None):
    """高效同步曲目列表：自动处理新增与更新"""
    if not mdt_list:
        return
    async def _action(session: AsyncSession):
        sids = [m.shortid for m in mdt_list]
        existing_map = {
            m.shortid: m for m in
            (await session.execute(
                select(MaiData).where(MaiData.shortid.in_(sids)).options(selectinload(MaiData.charts))
            )).scalars().all()
        }
        for new_mdt in mdt_list:
            existing = existing_map.get(new_mdt.shortid)
            if not existing:
                session.add(new_mdt)
            else:
                for f in ['title', 'bpm', 'artist', 'genre', 'cabinet',
                          'version', 'version_cn', 'converter', 'zip_path',
                          'jp_is_plate_required', 'cn_is_plate_required',
                          'is_utage', 'utage_tag', 'buddy']:
                    setattr(existing, f, getattr(new_mdt, f))
                existing_charts = {c.difficulty: c for c in existing.charts}
                for new_mct in new_mdt.charts:
                    ec = existing_charts.get(new_mct.difficulty)
                    if ec:
                        for f in ['lv', 'lv_cn', 'lv_synh', 'des', 'inote']:
                            setattr(ec, f, getattr(new_mct, f))
                        ec.notes = new_mct.notes
                    else:
                        existing.charts.append(new_mct)

    await execute_func.action(_action, session=session)
