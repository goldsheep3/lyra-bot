"""不向调用方暴露 ORM 的 B50 聚合查询。"""

from __future__ import annotations

from typing import Literal

from nonebot import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ... import utils
from ...utils.enums import Server, ServerScope
from ...utils.map import Versions
from .. import get_session
from ..models import MaiChart, MaiChartAch, MaiData, MaiUser
from .catalog import LEGACY_DEFAULT_PROVIDER_BY_SERVER


def _format_update_at(user: MaiUser | None, server: Server) -> str:
    if user is None:
        return "Not Updated"
    return user.to_utils().get_formated_time(server)


def _build_entry(ach: MaiChartAch) -> tuple[utils.MaiData, int] | None:
    chart = ach.chart
    if chart is None or chart.maidata is None:
        return None
    maidata = chart.maidata.to_utils()
    target_chart = maidata.get_chart(chart.difficulty)
    if target_chart is None:
        return None
    target_chart.set_ach(ach.to_utils(dxscore_max=chart.dxscore_max))
    return maidata, chart.difficulty


async def _select_entries(
    session: AsyncSession,
    *,
    qq: int,
    server: Server,
    provider: str,
    cut_version: int,
    target: Literal["b35", "b15"],
) -> tuple[list[tuple[utils.MaiData, int]], int]:
    version_field = getattr(MaiData, server.version_field, MaiData.version_jp)
    statement = (
        select(MaiChartAch)
        .join(MaiChartAch.chart)
        .join(MaiChart.maidata)
        .options(
            selectinload(MaiChartAch.chart)
            .selectinload(MaiChart.maidata)
            .options(
                selectinload(MaiData.charts).noload(MaiChart.achs),
                selectinload(MaiData.aliases),
            )
        )
        .where(
            MaiChartAch.qq == qq,
            MaiChartAch.server == server,
            MaiChartAch.provider == provider,
            MaiData.is_utage.is_(False),
        )
        .order_by(
            MaiChartAch.dxrating_cache.desc(),
            MaiChartAch.achievement.desc(),
        )
    )
    if target == "b35":
        statement = statement.where(version_field < cut_version).limit(35)
    else:
        statement = statement.where(version_field >= cut_version).limit(15)

    logger.debug(
        "[b50.get_b50_data] query "
        f"target={target} qq={qq} server={server.value} provider={provider} "
        f"cut_version={cut_version} statement={statement}"
    )
    achievements = list((await session.execute(statement)).scalars().all())
    entries = [entry for ach in achievements if (entry := _build_entry(ach)) is not None]
    dxrating = sum(ach.dxrating_cache for ach in achievements)
    logger.debug(
        "[b50.get_b50_data] query result "
        f"target={target} achievements={len(achievements)} entries={len(entries)} "
        f"dxrating={dxrating}"
    )
    return entries, dxrating


async def get_b50_data(
    qq: int,
    scope: ServerScope = ServerScope.CN,
    *,
    provider: str | None = None,
    current_version: int | None = None,
    special_tag: str | None = None,
) -> utils.B50Data:
    """返回单服 B50 DTO；ALL 聚合保留给后续专用实现。"""
    if scope is ServerScope.ALL:
        raise ValueError("get_b50_data currently requires a non-ALL scope")

    server = scope.to_server()
    resolved_provider = provider or LEGACY_DEFAULT_PROVIDER_BY_SERVER[server]
    resolved_version = current_version if current_version is not None else Versions.latest(server)
    cut_version = Versions.b50_cut_version(resolved_version)

    logger.debug(
        "[b50.get_b50_data] start "
        f"qq={qq} scope={scope.value} provider={resolved_provider} "
        f"current_version={resolved_version} cut_version={cut_version}"
    )
    async with get_session() as session:
        user = await session.get(MaiUser, qq)
        b35, b35_dxrating = await _select_entries(
            session,
            qq=qq,
            server=server,
            provider=resolved_provider,
            cut_version=cut_version,
            target="b35",
        )
        b15, b15_dxrating = await _select_entries(
            session,
            qq=qq,
            server=server,
            provider=resolved_provider,
            cut_version=cut_version,
            target="b15",
        )

        all_provider: utils.AllStr = {
            "JP": LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.JP],
            "CN": LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.CN],
        }
        all_provider[scope.value] = resolved_provider
        all_update_at: utils.AllStr = {
            "JP": _format_update_at(user, Server.JP),
            "CN": _format_update_at(user, Server.CN),
        }
        return utils.B50Data(
            dxrating=b35_dxrating + b15_dxrating,
            current_version=resolved_version,
            scope=scope,
            special_tag=special_tag,
            b35=b35,
            b15=b15,
            all_provider=all_provider,
            all_update_at=all_update_at,
        )


__all__ = ["get_b50_data"]
