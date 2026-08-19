from typing import Optional, TypeVar

from ._data import GenreID, GenreInfo, raw_genres
from .._normalize import normalize_basic as normalize
from ...fuzzy import fuzzy_get


__all__ = [
    "Genres",
    "GenreID",
    "GenreInfo",
]


E = TypeVar("E")


def _index_name_id(raw_genres: dict[GenreID, GenreInfo]) -> dict[str, GenreID]:
    _dict: dict[str, GenreID] = {}
    
    for genre_id, genre_info in raw_genres.items():
        for key in genre_info.keys():
            _dict[normalize(key)] = genre_id

    return _dict


class Genres:
    _raw: dict[GenreID, GenreInfo] = raw_genres
    _index_name_id: dict[str, GenreID] = _index_name_id(raw_genres)

    # get: id -> info

    @classmethod
    def get(cls, genre_id: GenreID) -> Optional[GenreInfo]:
        """根据 `GenreID` 获取 `GenreInfo`"""
        return cls._raw.get(genre_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, genre_id: GenreID, index: str, *, default: E = None) -> str | E:
        """根据 `GenreID` 获取 `GenreInfo` 的指定文本属性"""
        info = cls.get(genre_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_jp(cls, genre_id: GenreID, *, default: E = None) -> str | E:
        """根据 `GenreID` 获取 `GenreInfo` 的完整名称"""
        return cls._text(genre_id, index='jp', default=default)

    @classmethod
    def text_intl(cls, genre_id: GenreID, *, default: E = None) -> str | E:
        """根据 `GenreID` 获取 `GenreInfo` 的国际化名称"""
        return cls._text(genre_id, index='intl', default=default)

    @classmethod
    def text_cn(cls, genre_id: GenreID, *, default: E = None) -> str | E:
        """根据 `GenreID` 获取 `GenreInfo` 的汉化文本"""
        return cls._text(genre_id, index='cn', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str, *, allow_fuzzy: bool = False) -> Optional[GenreID]:
        """根据 流派名/简写 获取 `GenreID`"""
        if allow_fuzzy:
            # fuzzy_get 会优先进行一次精确匹配，再尝试模糊查询
            return fuzzy_get(cls._index_name_id, normalize(name))
        else:
            return cls._index_name_id.get(normalize(name))

    @classmethod
    def find(cls, name: str, *, allow_fuzzy: bool = True) -> Optional[GenreInfo]:
        """根据 流派名/简写 获取 `GenreInfo`"""
        genre_id = cls.find_id(name, allow_fuzzy=allow_fuzzy)
        return cls.get(genre_id) if genre_id is not None else None

    # dict key/value/items

    @classmethod
    def id_list(cls) -> list[GenreID]:
        """获取所有流派 ID 列表"""
        return list(cls._raw.keys())
    
    @classmethod
    def list(cls) -> list[GenreInfo]:
        """获取所有流派信息列表"""
        return list(cls._raw.values())
    
    @classmethod
    def data(cls) -> dict[GenreID, GenreInfo]:
        """获取所有流派信息字典"""
        return cls._raw.copy()
