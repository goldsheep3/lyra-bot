from typing import Optional, TypeVar

from ._data import int, DifficultyInfo, raw_difficulties
from .._normalize import normalize_basic as normalize


__all__ = [
    "Difficulties",
    "int",
    "DifficultyInfo",
]


E = TypeVar("E")


def _index_name_id(raw_difficulties: dict[int, DifficultyInfo]) -> dict[str, int]:
    _dict: dict[str, int] = {}
    
    for difficulty_id, difficulty_info in raw_difficulties.items():
        for key in difficulty_info.keys():
            _dict[normalize(key)] = difficulty_id

    return _dict


class Difficulties:
    _raw: dict[int, DifficultyInfo] = raw_difficulties
    _index_name_id: dict[str, int] = _index_name_id(raw_difficulties)
    
    # get: id -> info
    
    @classmethod
    def get(cls, difficulty_id: int) -> Optional[DifficultyInfo]:
        """根据 `int` 获取 `DifficultyInfo`"""
        return cls._raw.get(difficulty_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, difficulty_id: int, index: str, *, default: E = None) -> str | E:
        """根据 `int` 获取 `DifficultyInfo` 的指定文本属性"""
        info = cls.get(difficulty_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_jp(cls, difficulty_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `DifficultyInfo.jp`"""
        return cls._text(difficulty_id, index='jp', default=default)
    
    @classmethod
    def text_cn(cls, difficulty_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `DifficultyInfo.cn`"""
        return cls._text(difficulty_id, index='cn', default=default)

    @classmethod
    def text_cn_short(cls, difficulty_id: int, *, default: E = None) -> str | E:
        """根据 `int` 获取 `DifficultyInfo.cn_short`"""
        return cls._text(difficulty_id, index='cn_short', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str) -> Optional[int]:
        """根据 难度名/简写 获取 `int`"""
        return cls._index_name_id.get(normalize(name))

    @classmethod
    def find(cls, name: str) -> Optional[DifficultyInfo]:
        """根据 难度名/简写 获取 `DifficultyInfo`"""
        difficulty_id = cls.find_id(name)
        return cls.get(difficulty_id) if difficulty_id is not None else None

    # dict key/value/items

    @classmethod
    def id_list(cls) -> list[int]:
        """获取所有难度 ID 列表"""
        return list(cls._raw.keys())
    
    @classmethod
    def list(cls) -> list[DifficultyInfo]:
        """获取所有难度信息列表"""
        return list(cls._raw.values())
    
    @classmethod
    def data(cls) -> dict[int, DifficultyInfo]:
        """获取所有难度信息字典"""
        return cls._raw.copy()
