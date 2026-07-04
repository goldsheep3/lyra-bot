"""services/id_remapper.py shortid 重映射相关 CRUD 操作"""
from typing import Optional, Sequence, cast

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import execute_func
from .models import MaiData, MaiChart, MaiChartAch, MaiAlias, MaiIDMap


__all__ = [
    # 获取需要 remap 的新旧 shortid 元组映射列表
    "get_pending_mappings",
    # 执行 shortid 重映射
    "resolve_id_mapping",    
]


async def get_pending_mappings(*, session: Optional[AsyncSession] = None) -> Sequence[tuple[int, int]]:
    """返回所有 mapped_id 不为 None 的待处理映射 (original_id, mapped_id)。"""
    async def _query(session: AsyncSession):
        stmt = select(MaiIDMap).where(MaiIDMap.mapped_id != None)
        rows = (await session.execute(stmt)).scalars().all()
        return cast(Sequence[tuple[int, int]], [(r.original_id, r.mapped_id) for r in rows])
    return await execute_func.select(_query, session=session)


async def resolve_id_mapping(original_id: int, mapped_id: int, *, session: Optional[AsyncSession] = None):
    """对单个 original_id -> mapped_id 执行迁移。"""
    async def _action(session: AsyncSession):
        # 获取 source
        source = (await session.execute(
            select(MaiData).options(
                selectinload(MaiData.charts).selectinload(MaiChart.achs),
                selectinload(MaiData.aliases),
            ).where(MaiData.shortid == original_id)
        )).scalar_one_or_none()

        if not source:
            await session.execute(delete(MaiIDMap).where(MaiIDMap.original_id == original_id))
            return

        # 获取 target
        target = (await session.execute(
            select(MaiData).options(
                selectinload(MaiData.charts).selectinload(MaiChart.achs),
                selectinload(MaiData.aliases),
            ).where(MaiData.shortid == mapped_id)
        )).scalar_one_or_none()

        target_charts_map = {tc.difficulty: tc for tc in target.charts} if target else {}

        async def _del(obj):
            try:
                await session.delete(obj)
            except Exception:
                pass

        def _merge_ach(target_ach: MaiChartAch, source_ach: MaiChartAch) -> None:
            target_ach.achievement = max(target_ach.achievement, source_ach.achievement)
            target_ach.dxscore = max(target_ach.dxscore, source_ach.dxscore)
            target_ach.combo = max(target_ach.combo, source_ach.combo)
            target_ach.sync = max(target_ach.sync, source_ach.sync)
            target_ach.dxrating = max(target_ach.dxrating, source_ach.dxrating)
            try:
                if source_ach.update_time > target_ach.update_time:
                    target_ach.update_time = source_ach.update_time
            except TypeError:
                if source_ach.update_time.timestamp() > target_ach.update_time.timestamp():
                    target_ach.update_time = source_ach.update_time

        if not target:
            # CASE A: 目标不存在 → 复制
            new_mdt = MaiData(
                shortid=mapped_id, title=source.title, bpm=source.bpm,
                artist=source.artist, genre=source.genre, cabinet=source.cabinet,
                version=source.version, version_cn=source.version_cn,
                converter=source.converter, zip_path=source.zip_path,
                jp_is_plate_required=source.jp_is_plate_required,
                cn_is_plate_required=source.cn_is_plate_required,
                is_utage=source.is_utage, utage_tag=source.utage_tag, buddy=source.buddy,
            )
            session.add(new_mdt)
            for sc in source.charts:
                new_chart = MaiChart(
                    shortid=mapped_id, difficulty=sc.difficulty, lv=sc.lv,
                    lv_cn=sc.lv_cn, lv_synh=sc.lv_synh, des=sc.des, inote=sc.inote,
                    notes=sc.notes,
                )
                new_mdt.charts.append(new_chart)
                for ach in sc.achs:
                    session.add(MaiChartAch(
                        shortid=mapped_id, chart=new_chart, difficulty=ach.difficulty,
                        server=ach.server, achievement=ach.achievement, dxscore=ach.dxscore,
                        combo=ach.combo, sync=ach.sync, update_time=ach.update_time,
                        user_id=ach.user_id, dxrating=ach.dxrating,
                    ))
            for sa in source.aliases:
                new_mdt.aliases.append(MaiAlias(
                    shortid=mapped_id, alias=sa.alias, create_qq=sa.create_qq,
                    create_qq_group=sa.create_qq_group, create_time=sa.create_time,
                ))
            for sc in list(source.charts):
                for ach in list(sc.achs):
                    await _del(ach)
                await _del(sc)
            for sa in list(source.aliases):
                await _del(sa)
            await _del(source)
        else:
            # CASE B: 目标存在 → 合并
            source_chart_map = {c.difficulty: c for c in source.charts}
            for sd, sc in source_chart_map.items():
                if sd in target_charts_map:
                    tc = target_charts_map[sd]
                    for ach in list(sc.achs):
                        existing_ach = (await session.execute(
                            select(MaiChartAch).where(
                                MaiChartAch.user_id == ach.user_id, MaiChartAch.server == ach.server,
                                MaiChartAch.shortid == mapped_id, MaiChartAch.difficulty == ach.difficulty,
                            )
                        )).scalar_one_or_none()
                        if existing_ach:
                            _merge_ach(existing_ach, ach)
                            await _del(ach)
                        else:
                            ach.shortid = mapped_id
                            ach.chart = tc
                    await _del(sc)
                else:
                    sc.shortid = mapped_id
                    sc.maidata = target
                    for ach in sc.achs:
                        ach.shortid = mapped_id
            for sa in list(source.aliases):
                dup = (await session.execute(
                    select(MaiAlias).where(MaiAlias.shortid == mapped_id, MaiAlias.alias == sa.alias)
                )).scalar_one_or_none()
                if dup:
                    await _del(dup)
                sa.shortid = mapped_id
            cnt_charts = (await session.execute(
                select(func.count()).select_from(MaiChart).where(MaiChart.shortid == original_id)
            )).scalar_one()
            cnt_aliases = (await session.execute(
                select(func.count()).select_from(MaiAlias).where(MaiAlias.shortid == original_id)
            )).scalar_one()
            cnt_achs = (await session.execute(
                select(func.count()).select_from(MaiChartAch).where(MaiChartAch.shortid == original_id)
            )).scalar_one()
            if cnt_charts == 0 and cnt_aliases == 0 and cnt_achs == 0:
                await _del(source)

        await session.execute(delete(MaiIDMap).where(MaiIDMap.original_id == original_id))

    await execute_func.action(_action, session=session)
