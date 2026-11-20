from typing import Optional

from ..utils.enums import ServerScope
from ..utils.models import MaiB50Data
from ._refactoring import b50 as _b50


async def get_b50_data(qq: int, scope: ServerScope = ServerScope.CN, *, provider: Optional[str] = None, current_version: Optional[int] = None, special_tag: Optional[str] = None) -> MaiB50Data:
    """获取 B50 曲目列表。

    Args:
        qq: 要查询的用户 QQ 号。
        scope: 要查询的服务器范围，不支持 ``ALL``。
        provider: 可选的成绩数据提供方。
        current_version: 可选的当前版本 ID。
        special_tag: 可选的特殊标签，用于区分成绩来源。
    """
    return await _b50.get_b50_data(qq, scope, provider=provider, current_version=current_version, special_tag=special_tag)
