from typing import Literal, Optional, Sequence

from .. import config
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from nonebot_plugin_datastore import create_session as get_session

from ..utils.enums import Server, ServerScope
from ..utils.models import MaiData
from . import _models as db


LEGACY_DEFAULT_PROVIDER_BY_SERVER = {
    Server.JP: "lyrasync-oto",
    Server.CN: "diving-fish",
}

SearchMode = Literal["smart", "title", "name", "blur"]

class BlurSearchTooManyResultsError(ValueError):
    """模糊搜索结果过多错误"""

def _single_server_filter(*, qq: int, server: Server, provider: Optional[str]):
    """构建单服务器过滤条件"""
    if provider is None:
        selected_provider = LEGACY_DEFAULT_PROVIDER_BY_SERVER[server]
    else:
        selected_provider = provider
    return and_(
        db.MaiChartAch.qq == qq,
        db.MaiChartAch.server == server,
        db.MaiChartAch.provider == selected_provider,
    )

def _multi_server_filter(*, qq: int):
    """构建 ALL 服务器过滤条件"""
    return and_(
        db.MaiChartAch.qq == qq,
        or_(
            and_(
                db.MaiChartAch.server == Server.JP,
                db.MaiChartAch.provider == LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.JP],
            ),
            and_(
                db.MaiChartAch.server == Server.CN,
                db.MaiChartAch.provider == LEGACY_DEFAULT_PROVIDER_BY_SERVER[Server.CN],
            ),
        ),
    )

def _song_load_options(
    *,
    qq: Optional[int],
    scope: ServerScope,
    provider: Optional[str],
) -> tuple:
    """根据是否提供 qq 号来决定加载成绩或不加载成绩"""
    chart_loader = selectinload(db.MaiData.charts)
    if qq is None:
        return (
            chart_loader.noload(db.MaiChart.achs),
            selectinload(db.MaiData.aliases),
        )

    if scope == ServerScope.ALL:
        return (
            chart_loader.selectinload(
                db.MaiChart.achs.and_(_multi_server_filter(qq=qq))
            ),
            selectinload(db.MaiData.aliases),
        )
    else:
        return (
            chart_loader.selectinload(
                db.MaiChart.achs.and_(_single_server_filter(qq=qq, server=scope.to_server(), provider=provider))
            ),
            selectinload(db.MaiData.aliases),
        )

def _song_to_utils(
    song: db.MaiData,
    *,
    qq: Optional[int],
    keyword: Optional[str] = None,
) -> MaiData:
    """转换 db 对象为 utils 对象，如有则尝试加载成绩或匹配别名"""
    maidata = song.to_utils(achs_user_id=qq)
    if keyword is None or song.title.lower() == keyword.lower():
        return maidata

    normalized = keyword.lower()
    for alias in maidata.aliases:
        if normalized in alias.alias.lower():
            maidata._matched_alias = alias.alias
            break
    return maidata

async def _get_maidata(
    shortid: int,
    *,
    qq: Optional[int],
    scope: ServerScope,
    provider: Optional[str],
    session: AsyncSession,
) -> Optional[MaiData]:
    """根据 shortid 获取乐曲信息，可选择加载成绩和别名"""
    statement = (
        select(db.MaiData)
        .options(*_song_load_options(qq=qq, scope=scope, provider=provider))
        .where(db.MaiData.shortid == shortid)
    )
    db_song = (await session.execute(statement)).scalar_one_or_none()
    return _song_to_utils(db_song, qq=qq) if db_song is not None else None


async def _search_query(
    session: AsyncSession,
    keyword: str,
    mode: Literal["title", "name", "blur"],
    *,
    qq: Optional[int],
    scope: ServerScope,
    provider: Optional[str],
) -> list[db.MaiData]:
    """执行搜索查询，返回匹配的乐曲列表。"""
    normalized = keyword.lower()
    if mode == "title":
        filters = func.lower(db.MaiData.title) == normalized
    elif mode == "name":
        filters = or_(
            func.lower(db.MaiData.title) == normalized,
            func.lower(db.MaiAlias.name) == normalized,
        )
    else:
        filters = or_(
            func.lower(db.MaiData.title).contains(normalized),
            func.lower(db.MaiAlias.name).contains(normalized),
        )
        count = await session.scalar(
            select(func.count()).select_from(
                select(db.MaiData.shortid)
                .outerjoin(db.MaiAlias)
                .where(filters)
                .distinct()
                .subquery()
            )
        )
        if count is not None and count > config.MAX_BLUR_SEARCH_RESULTS:
            raise BlurSearchTooManyResultsError

    statement = (
        select(db.MaiData)
        .options(*_song_load_options(qq=qq, scope=scope, provider=provider))
        .outerjoin(db.MaiAlias)
        .where(filters)
        .distinct()
    )
    songs = list((await session.execute(statement)).scalars().all())
    return songs


async def _search_maidata(
    keyword: str,
    *,
    qq: Optional[int],
    scope: ServerScope,
    provider: Optional[str],
    mode: SearchMode,
    session: AsyncSession,
) -> list[MaiData]:
    """执行乐曲搜索。"""
    if mode not in {"smart", "title", "name", "blur"}:
        raise KeyError(f"Unknown mode: {mode}")

    query_mode: Literal["title", "name", "blur"]
    if mode == "smart":
        songs = await _search_query(
            session,
            keyword,
            "name",
            qq=qq,
            scope=scope,
            provider=provider,
        )
        if songs:
            query_mode = "name"
        else:
            query_mode = "blur"
            songs = await _search_query(
                session,
                keyword,
                query_mode,
                qq=qq,
                scope=scope,
                provider=provider,
            )
    else:
        query_mode = mode
        songs = await _search_query(
            session,
            keyword,
            query_mode,
            qq=qq,
            scope=scope,
            provider=provider,
        )
        
    return [_song_to_utils(song, qq=qq, keyword=keyword) for song in songs]


# ====== Public API ======

__all__ = [
    "get_maidata",      # [函数] 获取乐曲信息
    "search_maidata",   # [函数] 搜索乐曲信息
]

async def get_maidata(
    shortid: int,
    *,
    qq: Optional[int] = None,
    scope: ServerScope = ServerScope.CN,
    provider: Optional[str] = None
) -> Optional[MaiData]:
    """获取乐曲信息。

    Args:
        shortid: 乐曲 shortid。
        qq: 可选的 QQ 号；提供时会加载该用户的成绩。
        scope: 加载成绩时使用的服务器范围。
        provider: 可选的成绩数据提供方。
    """
    async with get_session() as session:
        song = await _get_maidata(
            shortid,
            qq=qq,
            scope=scope,
            provider=provider,
            session=session
        )
    return song


async def search_maidata(
    keyword: str,
    *,
    qq: Optional[int] = None,
    scope: ServerScope = ServerScope.CN,
    provider: Optional[str] = None,
    mode: Literal["smart", "title", "name", "blur"] = "smart"
) -> Sequence[MaiData]:
    """搜索乐曲信息。

    Args:
        keyword: 用于匹配曲名或别名的关键词。
        qq: 可选的 QQ 号；提供时会加载该用户的成绩。
        scope: 加载成绩时使用的服务器范围。
        provider: 可选的成绩数据提供方。
        mode: 搜索模式，可为智能、曲名、别名或模糊搜索。
    """
    async with get_session() as session:
        songs = await _search_maidata(keyword, qq=qq, scope=scope, provider=provider, mode=mode, session=session)
    return songs
