from typing import Optional, TypeVar

from ._data import VersionID, VersionInfo, raw_versions
from ._func import mapping_jp_to_cn, b50_cut_version, get_server, is_finale_frame
from .._normalize import normalize_version as normalize
from ...enums import Server


__all__ = [
    "Versions",
    "VersionID",
    "VersionInfo",
]


E = TypeVar("E")


def _index_name_id(raw_versions: dict[VersionID, VersionInfo]) -> dict[str, VersionID]:
    _dict: dict[str, VersionID] = {}
    
    for version_id, version_info in raw_versions.items():
        for key in (version_info.name, *version_info.code):
            _dict[normalize(key)] = version_id
    
    return _dict


def _index_plate_ids(raw_versions: dict[VersionID, VersionInfo]) -> dict[Server, dict[str, tuple[VersionID, ...]]]:
    _dict: dict[Server, dict[str, tuple[VersionID, ...]]] = {server: {} for server in Server}
    
    for version_id, version_info in raw_versions.items():
        for server in (Server.JP, Server.CN):
            # 旧框版本同时存在于 JP/CN 服务器，非旧框版本只存在于对应服务器  
            if not is_finale_frame(version_id) and get_server(version_id) != server:
                continue
            
            for key in version_info.plate:
                normalized_key = normalize(key)
                target = _dict[server].get(normalized_key, ())
                if version_id not in target:
                    _dict[server][normalized_key] = target + (version_id,)
            
    return _dict


class Versions:
    _raw: dict[VersionID, VersionInfo] = raw_versions
    _index_name_id: dict[str, VersionID] = _index_name_id(raw_versions)
    _index_plate_ids: dict[Server, dict[str, tuple[VersionID, ...]]] = _index_plate_ids(raw_versions)

    # get: id -> info

    @classmethod
    def get(cls, version_id: VersionID) -> Optional[VersionInfo]:
        """根据 `VersionID` 获取 `VersionInfo`"""
        return cls._raw.get(version_id)

    # text: id -> info.text

    @classmethod
    def _text(cls, version_id: VersionID, index: str, *, default: E = None) -> str | E:
        """根据 `VersionID` 获取 `VersionInfo` 的指定文本属性"""
        info = cls.get(version_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def _texts(cls, version_id: VersionID, index: str, *, default: E = None) -> tuple[str, ...] | E:
        """根据 `VersionID` 获取 `VersionInfo` 的指定文本属性列表"""
        info = cls.get(version_id)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_name(cls, version_id: VersionID, *, default: E = None) -> str | E:
        """根据 `VersionID` 获取版本名"""
        return cls._text(version_id, index='name', default=default)

    @classmethod
    def texts_code(cls, version_id: VersionID, *, default: E = None) -> tuple[str, ...] | E:
        """根据 `VersionID` 获取版本简写列表"""
        return cls._texts(version_id, index='code', default=default)

    # find: name -> id/info

    @classmethod
    def find_id(cls, name: str, *, default: E = None) -> VersionID | E:
        """根据 版本名/版本简写 获取 `VersionID`"""
        return cls._index_name_id.get(normalize(name), default)

    @classmethod
    def find(cls, name: str) -> Optional[VersionInfo]:
        """根据 版本名/版本简写 获取 `VersionInfo`"""
        if version_id := cls.find_id(name):
            return cls.get(version_id)
        return None

    @classmethod
    def find_id_with_plate(cls, name: str, server: Server = Server.JP) -> tuple[VersionID, ...]:
        """根据 牌子名 和 对应版本 获取 `VersionID` 元组"""
        plate_map = cls._index_plate_ids[server]
        result = plate_map.get(normalize(name), ())
        if not result and server == Server.CN:
            # CN 服务器未找到，尝试 JP 服务器
            raw_result = cls._index_plate_ids[Server.JP].get(normalize(name), ())
            result = tuple(dict.fromkeys(mapping_jp_to_cn(v) for v in raw_result if v in cls._raw))
        return result

    @classmethod
    def find_with_plate(cls, name: str, server: Server = Server.JP) -> tuple[VersionInfo, ...]:
        """根据 牌子名 和 对应版本 获取 `VersionInfo` 元组"""
        version_ids = cls.find_id_with_plate(name, server)
        result = [cls.get(v) for v in version_ids if v in cls._raw]
        return tuple(r for r in result if r is not None)

    # dict key/value/items

    @classmethod
    def id_list(cls) -> list[VersionID]:
        """获取所有版本 ID 列表"""
        return list(cls._raw.keys())

    @classmethod
    def list(cls) -> list[VersionInfo]:
        """获取所有版本信息列表"""
        return list(cls._raw.values())

    @classmethod
    def data(cls) -> dict[VersionID, VersionInfo]:
        """获取所有版本信息字典"""
        return cls._raw.copy()

    # ====== 功能性方法 ======
    
    @classmethod
    def latest(cls, server: Server) -> VersionID:
        """获取最新版本 ID"""
        if server == Server.JP:
            jp_versions = [v for v in cls._raw.keys() if v < 2000]
            return max(jp_versions) if jp_versions else 13
        elif server == Server.CN:
            cn_versions = [v for v in cls._raw.keys() if v >= 2000]
            return max(cn_versions) if cn_versions else 2020
        else:
            raise KeyError(f"Unknown server: {server}")

    @classmethod
    def b50_cut_version(cls, version_id: VersionID) -> VersionID:
        """依据特定版本号获取 B50 分段所需的 cut_version"""
        return b50_cut_version(version_id)

    @classmethod
    def b50_cut_version_with_server(cls, server: Server) -> VersionID:
        """依据特定服务器获取 B50 分段所需的 cut_version"""
        version_id = cls.latest(server)
        return cls.b50_cut_version(version_id)
