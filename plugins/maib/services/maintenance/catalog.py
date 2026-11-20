from collections.abc import Mapping, Sequence

from ...utils.models import MaiData, SLevelSource
from .._refactoring import _fetch
from .._refactoring import catalog as _catalog


async def sync_song_library(songs: Sequence[MaiData]) -> None:
    """同步乐曲数据库。

    Args:
        songs: 用于覆盖同步的乐曲 DTO 列表。
    """
    return await _catalog.sync_song_library(songs)


async def apply_cn_metadata(version_updates: Sequence[tuple[int, int]], level_updates: Sequence[Mapping[str, int | float]]) -> None:
    """应用国服版本和定数更新。

    Args:
        version_updates: ``(shortid, version)`` 形式的国服版本更新。
        level_updates: 含谱面标识及定数的国服定数更新。
    """
    return await _catalog.apply_cn_metadata(version_updates, level_updates)


async def apply_fit_levels(data: list[dict]) -> None:
    """应用拟合定数更新。

    Args:
        data: 拟合定数数据列表。
    """
    return await _fetch.set_mct_level_batch(data=data, source=SLevelSource.FIT)


async def has_song_library() -> bool:
    """检查乐曲数据库是否存在数据。"""
    return await _catalog.has_song_library()
