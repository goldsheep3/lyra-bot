"""services/refresh.py DXRating 缓存刷新相关 CRUD 操作"""
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import utils
from ..constants import DEFAULT_DATETIME, VERSION_MAP, server as Server
from . import execute_func
from .mlist import get_b50
from .models import MaiChartAch, MaiUser


__all__ = [
    # 直接刷新用户 dxra 缓存
    "rfs_mu_dxra",
    "rfs_mu_dxra_batch",
    # 刷新该谱面所有用户 dxra 缓存，并刷新相关用户 dxra 韩村
    "rfs_dxra_mct",
    "rfs_dxra_batch",
    # 刷新指定用户在该谱面 dxra 缓存，并刷新该用户 dxra 汇总缓存
    "rfs_mu_dxra_with_mct",
    "rfs_mu_dxra_with_mct_batch",
]


def _calc_mca_dxrating(mca: MaiChartAch, current_version: Optional[int] = None) -> int:
    """计算单条成绩当前应缓存的 DXRating"""
    chart = mca.chart
    if chart is None:
        raise ValueError("MaiChartAch.chart is required to calculate DXRating")

    version = current_version if current_version is not None else VERSION_MAP.get_latest_version_id(mca.server)
    ap_bonus = utils.get_ap_bonus_value(version)

    if mca.server == "JP":
        level = chart.lv
    else:
        level = chart.lv_cn
        if level is None:
            return 0

    return utils.get_dxrating(mca.achievement, level, ap_bonus, combo=mca.combo)


def _dxrating_stats(achs: Sequence[MaiChartAch]) -> tuple[int, int, int]:
    """返回 total, max, min；调用方保证 achs 已按 DXRating 降序排列。"""
    total = sum(ach.dxrating for ach in achs)
    max_dxrating = achs[0].dxrating if achs else 0
    min_dxrating = achs[-1].dxrating if achs else 0
    return total, max_dxrating, min_dxrating


def _normalize_chart_keys(chart_keys: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    return list(dict.fromkeys((shortid, difficulty) for shortid, difficulty in chart_keys))


async def _refresh_single_user_dxrating_cache(
    user_id: int,
    server: Server,
    *,
    session: AsyncSession,
) -> None:
    cut_version = VERSION_MAP.get_cut_version(server)
    current_version = VERSION_MAP.get_latest_version_id(server)

    b35, b15 = await get_b50(
        user_id=user_id,
        server=server,
        cut_version=cut_version,
        session=session,
    )
    b35_total, b35_max, b35_min = _dxrating_stats(b35)
    b15_total, b15_max, b15_min = _dxrating_stats(b15)

    latest_update_stmt = (
        select(func.max(MaiChartAch.update_time))
        .where(
            MaiChartAch.user_id == user_id,
            MaiChartAch.server == server,
        )
    )
    latest_update_time = (
        (await session.execute(latest_update_stmt)).scalar_one_or_none()
        or DEFAULT_DATETIME
    )

    user_stmt = select(MaiUser).where(MaiUser.user_id == user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if user is None:
        user = MaiUser(user_id=user_id)
        session.add(user)

    if server == "CN":
        user.cn_current_version = current_version
        user.cn_update_time = latest_update_time
        user.cn_dxra_total = b35_total + b15_total
        user.cn_dxra_b35_total = b35_total
        user.cn_dxra_b35_max = b35_max
        user.cn_dxra_b35_min = b35_min
        user.cn_dxra_b15_total = b15_total
        user.cn_dxra_b15_max = b15_max
        user.cn_dxra_b15_min = b15_min
    else:
        user.jp_current_version = current_version
        user.jp_update_time = latest_update_time
        user.jp_dxra_total = b35_total + b15_total
        user.jp_dxra_b35_total = b35_total
        user.jp_dxra_b35_max = b35_max
        user.jp_dxra_b35_min = b35_min
        user.jp_dxra_b15_total = b15_total
        user.jp_dxra_b15_max = b15_max
        user.jp_dxra_b15_min = b15_min


async def rfs_mu_dxra(
    user_id: int,
    server: Server,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """重算单个用户在指定服务器的 DXRating 汇总缓存。"""
    async def _action(session: AsyncSession) -> None:
        await _refresh_single_user_dxrating_cache(
            user_id=user_id,
            server=server,
            session=session,
        )

    await execute_func.action(_action, session=session)


async def rfs_mu_dxra_batch(
    user_ids: Sequence[int],
    server: Server,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """批量重算用户 DXRating 汇总缓存。"""
    unique_user_ids = list(dict.fromkeys(user_id for user_id in user_ids if user_id is not None))
    if not unique_user_ids:
        return

    async def _action(session: AsyncSession) -> None:
        for user_id in unique_user_ids:
            await _refresh_single_user_dxrating_cache(
                user_id=user_id,
                server=server,
                session=session,
            )

    await execute_func.action(_action, session=session)


async def rfs_dxra_mct(
    shortid: int,
    difficulty: int,
    server: Server,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """谱面定数变动后，刷新该谱面所有成绩及受影响用户缓存。"""
    await rfs_dxra_batch(
        chart_keys=[(shortid, difficulty)],
        server=server,
        session=session,
    )


async def rfs_dxra_batch(
    chart_keys: Sequence[tuple[int, int]],
    server: Server,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """批量刷新指定谱面的所有成绩及受影响用户缓存。"""
    unique_chart_keys = _normalize_chart_keys(chart_keys)
    if not unique_chart_keys:
        return

    async def _action(session: AsyncSession) -> None:
        target_server = server
        current_version = VERSION_MAP.get_latest_version_id(target_server)
        shortids = [shortid for shortid, _ in unique_chart_keys]
        difficulties = [difficulty for _, difficulty in unique_chart_keys]
        key_set = set(unique_chart_keys)
        statement = (
            select(MaiChartAch)
            .options(selectinload(MaiChartAch.chart))
            .where(
                MaiChartAch.shortid.in_(shortids),
                MaiChartAch.difficulty.in_(difficulties),
                MaiChartAch.server == target_server,
            )
        )
        mca_list = [
            mca
            for mca in (await session.execute(statement)).scalars().all()
            if (mca.shortid, mca.difficulty) in key_set
        ]
        affected_user_ids: set[int] = set()

        for mca in mca_list:
            mca.dxrating = _calc_mca_dxrating(mca, current_version)
            if mca.user_id is not None:
                affected_user_ids.add(mca.user_id)

        if mca_list:
            await session.flush()

        for user_id in affected_user_ids:
            await _refresh_single_user_dxrating_cache(
                user_id=user_id,
                server=target_server,
                session=session,
            )

    await execute_func.action(_action, session=session)


async def rfs_mu_dxra_with_mct(
    shortid: int,
    difficulty: int,
    server: Server,
    user_id: int,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """刷新指定用户在指定谱面的 DXRating，并重算该用户汇总缓存。"""
    await rfs_mu_dxra_with_mct_batch(
        chart_keys=[(shortid, difficulty)],
        server=server,
        user_id=user_id,
        session=session,
    )


async def rfs_mu_dxra_with_mct_batch(
    chart_keys: Sequence[tuple[int, int]],
    server: Server,
    user_id: int,
    *,
    session: Optional[AsyncSession] = None,
) -> None:
    """批量刷新指定用户在指定谱面的 DXRating，并重算该用户汇总缓存。"""
    unique_chart_keys = _normalize_chart_keys(chart_keys)
    if not unique_chart_keys:
        return

    async def _action(session: AsyncSession) -> None:
        current_version = VERSION_MAP.get_latest_version_id(server)
        shortids = [shortid for shortid, _ in unique_chart_keys]
        difficulties = [difficulty for _, difficulty in unique_chart_keys]
        key_set = set(unique_chart_keys)
        statement = (
            select(MaiChartAch)
            .options(selectinload(MaiChartAch.chart))
            .where(
                MaiChartAch.shortid.in_(shortids),
                MaiChartAch.difficulty.in_(difficulties),
                MaiChartAch.server == server,
                MaiChartAch.user_id == user_id,
            )
        )
        mca_list = [
            mca
            for mca in (await session.execute(statement)).scalars().all()
            if (mca.shortid, mca.difficulty) in key_set
        ]

        for mca in mca_list:
            mca.dxrating = _calc_mca_dxrating(mca, current_version)

        if mca_list:
            await session.flush()

        await _refresh_single_user_dxrating_cache(
            user_id=user_id,
            server=server,
            session=session,
        )

    await execute_func.action(_action, session=session)
