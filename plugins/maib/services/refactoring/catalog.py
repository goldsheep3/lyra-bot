"""不向调用方暴露 ORM 与 session 的曲库维护用例。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import select

from ... import utils
from ...utils.enums import Server, SLevelSource
from .. import get_session
from ..fetch import set_mct_level_batch, set_mdt_version_batch, sync_mdt_list
from ..models import MaiData
from ..refresh import rfs_dxra_batch


__all__ = [
    "sync_song_library",
    "apply_cn_metadata",
    "has_song_library",
]


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
