from typing import Optional, TypeVar

from ._data import int, SyncInfo, raw_syncs
from .._normalize import normalize_evaluate as normalize


__all__ = [
    "Syncs",
    "int",
    "SyncInfo",
]


E = TypeVar("E")


def _index_name_id(raw_syncs: dict[int, SyncInfo]) -> dict[str, int]:
    _dict: dict[str, int] = {}
    
    for sync_id, sync_info in raw_syncs.items():
        for key in sync_info.keys():
            _dict[normalize(key)] = sync_id

    return _dict


class Syncs:
    _raw: dict[int, SyncInfo] = raw_syncs
    _index_name_id: dict[str, int] = _index_name_id(raw_syncs)

    # get: id -> info

    @classmethod
    def get(cls, sync_id: int) -> Optional[SyncInfo]:
        """根据 `int` 获取 `SyncInfo`"""
        return cls._raw.get(sync_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, sync_id: int, index: str, *, default: E = None) -> str | E:
        """根据 `int` 获取 `SyncInfo` 的指定文本属性"""
        info = cls.get(sync_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_full(cls, sync_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `SyncInfo` 的完整名称"""
        return cls._text(sync_id, index='full', default=default)

    @classmethod
    def text_short(cls, sync_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `SyncInfo` 的简写"""
        return cls._text(sync_id, index='short', default=default)

    @classmethod
    def text_cn(cls, sync_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `SyncInfo` 的汉化文本"""
        return cls._text(sync_id, index='cn', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str) -> Optional[int]:
        """根据 同步名/简写 获取 `int`"""
        return cls._index_name_id.get(normalize(name))

    @classmethod
    def find(cls, name: str) -> Optional[SyncInfo]:
        """根据 同步名/简写 获取 `SyncInfo`"""
        sync_id = cls.find_id(name)
        return cls.get(sync_id) if sync_id is not None else None

    # dict key/value/items


    @classmethod
    def id_list(cls) -> list[int]:
        """获取所有同步 ID 列表"""
        return list(cls._raw.keys())
    
    @classmethod
    def list(cls) -> list[SyncInfo]:
        """获取所有同步信息列表"""
        return list(cls._raw.values())
    
    @classmethod
    def data(cls) -> dict[int, SyncInfo]:
        """获取所有同步信息字典"""
        return cls._raw.copy()
