from typing import Optional, TypeVar

from ._data import SyncID, SyncInfo, raw_syncs
from .._normalize import normalize_evaluate as normalize


__all__ = [
    "Syncs",
    "SyncID",
    "SyncInfo",
]


E = TypeVar("E")


def _index_name_id(raw_syncs: dict[SyncID, SyncInfo]) -> dict[str, SyncID]:
    _dict: dict[str, SyncID] = {}
    
    for sync_id, sync_info in raw_syncs.items():
        for key in sync_info.keys():
            _dict[normalize(key)] = sync_id

    return _dict


class Syncs:
    _raw: dict[SyncID, SyncInfo] = raw_syncs
    _index_name_id: dict[str, SyncID] = _index_name_id(raw_syncs)

    # get: id -> info

    @classmethod
    def get(cls, sync_id: SyncID) -> Optional[SyncInfo]:
        """根据 `SyncID` 获取 `SyncInfo`"""
        return cls._raw.get(sync_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, sync_id: SyncID, index: str, *, default: E = None) -> str | E:
        """根据 `SyncID` 获取 `SyncInfo` 的指定文本属性"""
        info = cls.get(sync_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_full(cls, sync_id: SyncID, *, default: E = None) -> str | E:
        """根据 `SyncID` 获取 `SyncInfo` 的完整名称"""
        return cls._text(sync_id, index='full', default=default)

    @classmethod
    def text_short(cls, sync_id: SyncID, *, default: E = None) -> str | E:
        """根据 `SyncID` 获取 `SyncInfo` 的简写"""
        return cls._text(sync_id, index='short', default=default)

    @classmethod
    def text_cn(cls, sync_id: SyncID, *, default: E = None) -> str | E:
        """根据 `SyncID` 获取 `SyncInfo` 的汉化文本"""
        return cls._text(sync_id, index='cn', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str) -> Optional[SyncID]:
        """根据 同步名/简写 获取 `SyncID`"""
        return cls._index_name_id.get(normalize(name))

    @classmethod
    def find(cls, name: str) -> Optional[SyncInfo]:
        """根据 同步名/简写 获取 `SyncInfo`"""
        sync_id = cls.find_id(name)
        return cls.get(sync_id) if sync_id is not None else None

    # dict key/value/items


    @classmethod
    def id_list(cls) -> list[SyncID]:
        """获取所有同步 ID 列表"""
        return list(cls._raw.keys())
    
    @classmethod
    def list(cls) -> list[SyncInfo]:
        """获取所有同步信息列表"""
        return list(cls._raw.values())
    
    @classmethod
    def data(cls) -> dict[SyncID, SyncInfo]:
        """获取所有同步信息字典"""
        return cls._raw.copy()
