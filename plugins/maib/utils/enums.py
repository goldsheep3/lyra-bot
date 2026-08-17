"""utils/enums.py 共通枚举与范围类型"""
from __future__ import annotations

from enum import IntEnum, StrEnum


__all__ = [
    "Server",
    "ServerScope",
    "SLevelSource",
    "UICode",
    
    "Difficulty",
]


class Server(StrEnum):
    JP = "JP"
    CN = "CN"

    @classmethod
    def parse(cls, value: str | Server) -> Server:
        if isinstance(value, cls):
            return value
        return cls(str(value).strip().upper())

    @property
    def version_field(self) -> str:
        field_map = {
            Server.JP: "version",
            Server.CN: "version_cn",
        }
        return field_map[self]


class ServerScope(StrEnum):
    JP = "JP"
    CN = "CN"
    ALL = "ALL"

    def to_server(self) -> Server:
        if self is ServerScope.ALL:
            raise ValueError("ALL cannot convert to Server")
        return Server(self.value)

    @classmethod
    def parse(cls, value: str | ServerScope | Server) -> ServerScope:
        if isinstance(value, cls):
            return value
        if isinstance(value, Server):
            return cls(value.value)
        return cls(str(value).strip().upper())

    @classmethod
    def from_server(cls, server: Server) -> ServerScope:
        return cls(server.value)


class SLevelSource(StrEnum):
    JP = "JP"
    CN = "CN"
    SYNH = "SYNH"

    @property
    def lv_field(self) -> str:
        field_map = {
            SLevelSource.JP: "lv",
            SLevelSource.CN: "lv_cn",
            SLevelSource.SYNH: "lv_synh",
        }
        return field_map[self]

    def to_server(self) -> Server | None:
        if self is SLevelSource.SYNH:
            return None
        return Server(self.value)

    @classmethod
    def parse(cls, value: str | SLevelSource | Server) -> SLevelSource:
        if isinstance(value, cls):
            return value
        if isinstance(value, Server):
            return cls(value.value)
        return cls(str(value).strip().upper())

    @classmethod
    def server(cls, server: Server) -> SLevelSource:
        # from server
        return cls(server.value)


class UICode(IntEnum):
    JP = 0
    INTL = 1
    USA = 2
    CN = 3
    CN_ALL = 4
    
    @property
    def is_cn_all(self) -> bool:
        """是否为新汉化"""
        return self == UICode.CN_ALL
        
    @property
    def is_cn(self) -> bool:
        """是否为国服汉化"""
        return self >= UICode.CN
    
    @property
    def is_jp(self) -> bool:
        """是否为日服"""
        return self == UICode.JP
    
    @property
    def is_intl(self) -> bool:
        """是否为国际服"""
        return UICode.INTL <= self <= UICode.USA
    
    @property
    def is_usa(self) -> bool:
        """是否为国际服-美服"""
        return self == UICode.USA

    @staticmethod
    def parse(value: str | int | UICode) -> UICode:        
        if isinstance(value, UICode):
            return value
        if isinstance(value, str):
            return UICode[value.strip().upper()]
        return UICode(int(value))


class Difficulty(IntEnum):
    NONE = 0
    EASY = 1
    BASIC = 2
    ADVANCED = 3
    EXPERT = 4
    MASTER = 5
    REMASTER = 6
    UTAGE = 7
