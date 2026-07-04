"""services/ach.py 成绩更新相关 CRUD 操作"""
from collections import defaultdict
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import utils
from ..constants import ASIA_SHANGHAI, server as Server
from . import execute_func
from .models import MaiChart, MaiChartAch, MaiUser
from .refresh import rfs_mu_dxra_with_mct_batch


__all__ = [
    # 成绩更新
    "set_mca",
    "upd_ach_batch",
    # sy hash
    "get_last_sy_hash",
    "set_last_sy_hash",
]


_ChartKey = tuple[int, int]
_AchKey = tuple[int, int, Server]


def _normalize_ach(ach: utils.MaiChartAch, user_id: int) -> utils.MaiChartAch:
    """复制输入成绩，避免服务层原地修改调用方对象。"""
    return utils.MaiChartAch(
        shortid=ach.shortid,
        difficulty=ach.difficulty,
        server=ach.server,
        achievement=ach.achievement,
        dxscore=ach.dxscore,
        dxscore_max=ach.dxscore_max,
        combo=ach.combo,
        sync=ach.sync,
        update_time=ach.update_time,
        user_id=user_id,
    )


def _deduplicate_achs(
    user_id: int,
    ach_list: Sequence[utils.MaiChartAch],
) -> dict[_AchKey, utils.MaiChartAch]:
    unique: dict[_AchKey, utils.MaiChartAch] = {}

    for ach in ach_list:
        normalized = _normalize_ach(ach, user_id)
        key = (normalized.shortid, normalized.difficulty, normalized.server)
        previous = unique.get(key)
        if previous is None:
            unique[key] = normalized
        elif normalized > previous:
            unique[key] = previous + normalized

    return unique


def _build_diff(
    chart: MaiChart,
    new_ach: utils.MaiChartAch,
    old_ach: Optional[utils.MaiChartAch],
) -> utils.MaiChartAchDiff:
    title = chart.maidata.title if chart.maidata else f"id{chart.shortid}"
    return utils.MaiChartAchDiff(
        shortid=chart.shortid,
        title=title,
        difficulty=chart.difficulty,
        server=new_ach.server,
        new_ach=new_ach,
        old_ach=old_ach,
    )


def _apply_merged_ach(mca: MaiChartAch, merged: utils.MaiChartAch) -> None:
    mca.achievement = merged.achievement
    mca.dxscore = merged.dxscore
    mca.combo = merged.combo
    mca.sync = merged.sync
    mca.update_time = merged.update_time


async def _load_chart_map(
    shortids: Sequence[int],
    *, session: AsyncSession,
) -> dict[_ChartKey, MaiChart]:
    statement = (
        select(MaiChart)
        .options(selectinload(MaiChart.maidata))
        .where(MaiChart.shortid.in_(shortids))
    )
    charts = (await session.execute(statement)).scalars().all()
    return {(chart.shortid, chart.difficulty): chart for chart in charts}


async def _load_existing_ach_map(
    user_id: int,
    shortids: Sequence[int],
    *, session: AsyncSession,
) -> dict[_AchKey, MaiChartAch]:
    statement = (
        select(MaiChartAch)
        .options(selectinload(MaiChartAch.chart))
        .where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.shortid.in_(shortids),
        )
    )
    rows = (await session.execute(statement)).scalars().all()
    return {
        (ach.shortid, ach.difficulty, ach.server): ach
        for ach in rows
    }


async def set_mca(
    ach: utils.MaiChartAch,
    *, session: Optional[AsyncSession] = None,
) -> Optional[utils.MaiChartAchDiff]:
    """设置单条成绩，返回该成绩的变更信息。"""
    report = await upd_ach_batch(
        user_id=ach.user_id,
        ach_list=[ach],
        session=session,
    )

    if report.new_song:
        return report.new_song[0]
    if report.updated_song:
        return report.updated_song[0]
    if report.no_data_song:
        shortid, _, difficulty = report.no_data_song[0]
        raise KeyError(f"Chart not found: shortid={shortid}, difficulty={difficulty}")
    return None


async def upd_ach_batch(
    user_id: int,
    ach_list: Sequence[utils.MaiChartAch],
    *, session: Optional[AsyncSession] = None,
) -> utils.MaiChartAchDiffReport:
    """批量上传成绩并返回结构化变更报告。"""
    unique_incoming = _deduplicate_achs(user_id, ach_list)

    async def _action(session: AsyncSession) -> utils.MaiChartAchDiffReport:
        report = utils.MaiChartAchDiffReport()
        if not unique_incoming:
            return report

        shortids = list(dict.fromkeys(shortid for shortid, _, _ in unique_incoming))
        chart_map = await _load_chart_map(shortids, session=session)
        existing_map = await _load_existing_ach_map(user_id, shortids, session=session)
        affected_chart_keys: dict[Server, set[_ChartKey]] = defaultdict(set)

        for (shortid, difficulty, target_server), incoming in unique_incoming.items():
            chart = chart_map.get((shortid, difficulty))
            if chart is None:
                report.no_data_song.append((shortid, f"id{shortid}", difficulty))
                continue

            existing_mca = existing_map.get((shortid, difficulty, target_server))
            if existing_mca is None:
                incoming.update_time = datetime.now(ASIA_SHANGHAI)
                session.add(MaiChartAch.from_utils(incoming, chart_id=chart.id))
                report.new_song.append(_build_diff(chart, incoming, None))
                affected_chart_keys[target_server].add((shortid, difficulty))
                continue

            old_ach = existing_mca.to_utils()
            if not (incoming > old_ach):
                report.no_update_song_count += 1
                continue

            merged = old_ach + incoming
            _apply_merged_ach(existing_mca, merged)
            report.updated_song.append(_build_diff(chart, merged, old_ach))
            affected_chart_keys[target_server].add((shortid, difficulty))

        await session.flush()

        for target_server, chart_keys in affected_chart_keys.items():
            await rfs_mu_dxra_with_mct_batch(
                chart_keys=list(chart_keys),
                server=target_server,
                user_id=user_id,
                session=session,
            )

        return report

    return await execute_func.action(_action, session=session)

# --- sy hash ---

async def get_last_sy_hash(user_id: int,
                           *, session: Optional[AsyncSession] = None) -> Optional[str]:
    """获取用户上次水鱼 records 的哈希值。"""
    async def _select(session: AsyncSession):
        stmt = select(MaiUser.last_sy_hash).where(MaiUser.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    return await execute_func.select(_select, session=session)


async def set_last_sy_hash(user_id: int, sy_hash: str,
                           *, session: Optional[AsyncSession] = None):
    """写入用户最新的水鱼 records 哈希值。"""
    async def _action(session: AsyncSession):
        stmt = select(MaiUser).where(MaiUser.user_id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = MaiUser(user_id=user_id)
            session.add(user)
            await session.flush()
        user.last_sy_hash = sy_hash
    
    await execute_func.action(_action, session=session)    
