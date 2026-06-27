from enum import IntEnum


class RelationType(IntEnum):
    WIFE = 0
    HUSBAND = 1


# 导入以启用 Matcher
from . import matcher, plugin_help
