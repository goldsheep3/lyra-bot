from typing import Optional, TypeVar

from ._data import ComboID, ComboInfo, raw_combos
from .._normalize import normalize_evaluate as normalize


__all__ = [
    "Combos",
    "ComboID",
    "ComboInfo",
]


E = TypeVar("E")


def _index_name_id(raw_combos: dict[ComboID, ComboInfo]) -> dict[str, ComboID]:
    _dict: dict[str, ComboID] = {}
    
    for combo_id, combo_info in raw_combos.items():
        for key in combo_info.keys():
            _dict[normalize(key)] = combo_id

    return _dict


class Combos:
    _raw: dict[ComboID, ComboInfo] = raw_combos
    _index_name_id: dict[str, ComboID] = _index_name_id(raw_combos)

    # get: id -> info

    @classmethod
    def get(cls, combo_id: ComboID) -> Optional[ComboInfo]:
        """根据 `ComboID` 获取 `ComboInfo`"""
        return cls._raw.get(combo_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, combo_id: ComboID, index: str, *, default: E = None) -> str | E:
        """根据 `ComboID` 获取 `ComboInfo` 的指定文本属性"""
        info = cls.get(combo_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_full(cls, combo_id: ComboID, *, default: E = None) -> str | E:
        """根据 `ComboID` 获取 `ComboInfo` 的完整名称"""
        return cls._text(combo_id, index='full', default=default)

    @classmethod
    def text_short(cls, combo_id: ComboID, *, default: E = None) -> str | E:
        """根据 `ComboID` 获取 `ComboInfo` 的简写"""
        return cls._text(combo_id, index='short', default=default)

    @classmethod
    def text_cn(cls, combo_id: ComboID, *, default: E = None) -> str | E:
        """根据 `ComboID` 获取 `ComboInfo` 的汉化文本"""
        return cls._text(combo_id, index='cn', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str) -> Optional[ComboID]:
        """根据 连击名/简写 获取 `ComboID`"""
        return cls._index_name_id.get(normalize(name))

    @classmethod
    def find(cls, name: str) -> Optional[ComboInfo]:
        """根据 连击名/简写 获取 `ComboInfo`"""
        combo_id = cls.find_id(name)
        return cls.get(combo_id) if combo_id is not None else None

    # dict key/value/items

    @classmethod
    def id_list(cls) -> list[ComboID]:
        """获取所有连击 ID 列表"""
        return list(cls._raw.keys())
    
    @classmethod
    def list(cls) -> list[ComboInfo]:
        """获取所有连击信息列表"""
        return list(cls._raw.values())
    
    @classmethod
    def data(cls) -> dict[ComboID, ComboInfo]:
        """获取所有连击信息字典"""
        return cls._raw.copy()
