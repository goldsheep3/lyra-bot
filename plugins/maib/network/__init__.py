"""network.py 网络请求核心模块"""

__all__ = [
    "request_bytes",

    "DivingFish",
    "MaichartConverts",
    "Lxns",
    "YuzuChaN",

    "get_qq_avatar",
]

from .tool import request_bytes
from .diving_fish import DivingFish
from .lxns import Lxns
from .converts import MaichartConverts
from .yuzuchan import YuzuChaN

from .qq import get_qq_avatar
