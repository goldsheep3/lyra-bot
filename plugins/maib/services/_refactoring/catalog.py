"""不向调用方暴露 ORM 与 session 的曲库维护用例。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from nonebot import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ... import config, utils
from ...utils.enums import Server, ServerScope, SLevelSource
from ...utils.exceptions import BlurSearchTooManyResultsError
from .._tool import get_session
from .._fetch import set_mct_level_batch, set_mdt_version_batch, sync_mdt_list
from .._models import MaiAlias, MaiChart, MaiChartAch, MaiData
from .._refresh import rfs_dxra_batch


__all__ = [
    "sync_song_library",
    "apply_cn_metadata",
    "has_song_library",
    "get_maidata",
    "search_maidata",
]


SearchMode = Literal["smart", "title", "name", "blur"]

LEGACY_DEFAULT_PROVIDER_BY_SERVER = {
    Server.JP: "lyrasync-oto",
    Server.CN: "diving-fish",
}


async def sync_song_library(songs: Sequence[utils.MaiData]) -> None:
    """将 utils 曲目同步到数据库，并在 services 内完成 ORM 映射。"""
    if not songs:
        return

    orm_songs = [MaiData.from_utils(song) for song in songs]
    async with get_session() as session:
        await sync_mdt_list(orm_songs, session=session)
        await session.commit()


async def apply_cn_metadata(
    version_updates: Sequence[tuple[int, int]],
    level_updates: Sequence[Mapping[str, int | float]],
) -> None:
    """在一个事务中更新国服版本、定数及相关 DX Rating 缓存。"""
    if not version_updates and not level_updates:
        return

    normalized_levels = [
        {
            "shortid": int(item["shortid"]),
            "difficulty": int(item["difficulty"]),
            "level": float(item["level"]),
        }
        for item in level_updates
    ]

    async with get_session() as session:
        if version_updates:
            await set_mdt_version_batch(
                list(version_updates),
                Server.CN,
                session=session,
            )
        if normalized_levels:
            await set_mct_level_batch(
                normalized_levels,
                SLevelSource.CN,
                session=session,
            )
            chart_keys = list(
                dict.fromkeys(
                    (item["shortid"], item["difficulty"])
                    for item in normalized_levels
                )
            )
            await rfs_dxra_batch(chart_keys, Server.CN, session=session)
        await session.commit()


async def has_song_library() -> bool:
    """返回数据库中是否至少存在一首曲目。"""
    async with get_session() as session:
        shortid = await session.scalar(select(MaiData.shortid).limit(1))
        return shortid is not None


def _achievement_filter(
    qq: int,
    server: ServerScope,
    provider: str | None,
):
    if server is ServerScope.ALL:
        if provider is not None:
            return and_(
                MaiChartAch.qq == qq,
                MaiChartAch.server.in_((Server.JP, Server.CN)),
                MaiChartAch.provider == provider,
            )
        return and_(
            MaiChartAch.qq == qq,
            or_(
                and_(
                    MaiChartAch.server == Server.JP,
                    MaiChartAch.provider == LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.JP],
                ),
                and_(
                    MaiChartAch.server == Server.CN,
                    MaiChartAch.provider == LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.CN],
                ),
            ),
        )

    selected_server = server.to_server()
    selected_provider = provider or LEGACY_DEFAULT_PROVIDER_BY_SERVER[selected_server]
    return and_(
        MaiChartAch.qq == qq,
        MaiChartAch.server == selected_server,
        MaiChartAch.provider == selected_provider,
    )


def _song_load_options(
    qq: int | None,
    server: ServerScope,
    provider: str | None,
):
    chart_loader = selectinload(MaiData.charts)
    if qq is None:
        return (
            chart_loader.noload(MaiChart.achs),
            selectinload(MaiData.aliases),
        )
    return (
        chart_loader.selectinload(
            MaiChart.achs.and_(_achievement_filter(qq, server, provider))
        ),
        selectinload(MaiData.aliases),
    )


def _provider_description(server: ServerScope, provider: str | None) -> str:
    if provider is not None:
        return provider
    if server is ServerScope.ALL:
        return ",".join(
            f"{item.value}:{LEGACY_DEFAULT_PROVIDER_BY_SERVER[item]}"
            for item in (Server.JP, Server.CN)
        )
    selected_server = server.to_server()
    return LEGACY_DEFAULT_PROVIDER_BY_SERVER[selected_server]


def _loaded_achievement_count(songs: Sequence[MaiData], qq: int | None) -> int:
    if qq is None:
        return 0
    return sum(len(chart.achs) for song in songs for chart in song.charts)


def _to_utils_song(
    song: MaiData,
    *,
    qq: int | None,
    keyword: str | None = None,
) -> utils.MaiData:
    maidata = song.to_utils(achs_user_id=qq)
    if keyword is None or song.title.lower() == keyword.lower():
        return maidata

    normalized = keyword.lower()
    for alias in maidata.aliases:
        if normalized in alias.alias.lower():
            maidata._matched_alias = alias.alias
            break
    return maidata


async def get_maidata(
    shortid: int,
    *,
    qq: int | None = None,
    server: ServerScope = ServerScope.CN,
    provider: str | None = None,
) -> utils.MaiData | None:
    """按 shortid 返回 utils 曲目，并按 scope/provider 可选加载成绩。"""
    logger.debug(
        "[catalog.get_maidata] start "
        f"shortid={shortid} qq={qq} server={server.value} "
        f"provider={_provider_description(server, provider) if qq is not None else 'noload'}"
    )
    async with get_session() as session:
        statement = (
            select(MaiData)
            .options(*_song_load_options(qq, server, provider))
            .where(MaiData.shortid == shortid)
        )
        song = (await session.execute(statement)).scalar_one_or_none()
        logger.debug(
            "[catalog.get_maidata] result "
            f"shortid={shortid} found={song is not None} "
            f"loaded_achievements={_loaded_achievement_count([song], qq) if song is not None else 0}"
        )
        return _to_utils_song(song, qq=qq) if song is not None else None


async def _search_query(
    session: AsyncSession,
    keyword: str,
    mode: Literal["title", "name", "blur"],
    *,
    qq: int | None,
    server: ServerScope,
    provider: str | None,
) -> list[MaiData]:
    normalized = keyword.lower()
    if mode == "title":
        filters = func.lower(MaiData.title) == normalized
    elif mode == "name":
        filters = or_(
            func.lower(MaiData.title) == normalized,
            func.lower(MaiAlias.name) == normalized,
        )
    else:
        filters = or_(
            func.lower(MaiData.title).contains(normalized),
            func.lower(MaiAlias.name).contains(normalized),
        )
        count = await session.scalar(
            select(func.count()).select_from(
                select(MaiData.shortid)
                .outerjoin(MaiAlias)
                .where(filters)
                .distinct()
                .subquery()
            )
        )
        logger.debug(
            "[catalog.search_maidata] blur count "
            f"keyword={keyword!r} count={count} limit={config.MAX_BLUR_SEARCH_RESULTS}"
        )
        if count is not None and count > config.MAX_BLUR_SEARCH_RESULTS:
            raise BlurSearchTooManyResultsError(
                f"模糊搜索结果过多（{count} 条），请尝试更精确的关键词进行搜索喵qwq"
            )

    statement = (
        select(MaiData)
        .options(*_song_load_options(qq, server, provider))
        .outerjoin(MaiAlias)
        .where(filters)
        .distinct()
    )
    songs = list((await session.execute(statement)).scalars().all())
    logger.debug(
        "[catalog.search_maidata] query result "
        f"mode={mode} keyword={keyword!r} songs={len(songs)} "
        f"loaded_achievements={_loaded_achievement_count(songs, qq)}"
    )
    return songs


async def search_maidata(
    keyword: str,
    *,
    qq: int | None = None,
    server: ServerScope = ServerScope.CN,
    provider: str | None = None,
    mode: SearchMode = "smart",
) -> list[utils.MaiData]:
    """按标题或别名搜索 utils 曲目，并可按 scope/provider 加载成绩。"""
    if mode not in {"smart", "title", "name", "blur"}:
        raise KeyError(f"Unknown mode: {mode}")

    logger.debug(
        "[catalog.search_maidata] start "
        f"mode={mode} keyword={keyword!r} qq={qq} server={server.value} "
        f"provider={_provider_description(server, provider) if qq is not None else 'noload'}"
    )
    async with get_session() as session:
        query_mode: Literal["title", "name", "blur"]
        if mode == "smart":
            songs = await _search_query(
                session,
                keyword,
                "name",
                qq=qq,
                server=server,
                provider=provider,
            )
            if songs:
                query_mode = "name"
            else:
                logger.debug(
                    "[catalog.search_maidata] smart fallback "
                    f"keyword={keyword!r} exact_matches=0"
                )
                query_mode = "blur"
                songs = await _search_query(
                    session,
                    keyword,
                    query_mode,
                    qq=qq,
                    server=server,
                    provider=provider,
                )
        else:
            query_mode = mode
            songs = await _search_query(
                session,
                keyword,
                query_mode,
                qq=qq,
                server=server,
                provider=provider,
            )

        return [_to_utils_song(song, qq=qq, keyword=keyword) for song in songs]
