from typing import Optional

from ..utils.models import MaiUser
from ._refactoring import link as _link
from ._refactoring import user as _user


async def get_or_create_from_qq(qq: int) -> MaiUser:
    """获取或创建 QQ 用户。

    Args:
        qq: 用户 QQ 号。
    """
    return await _user.get_or_create_maiuser_from_qq(qq)


async def get_or_create_from_telegram(telegram_id: int) -> MaiUser:
    """获取或创建 Telegram 用户。

    Args:
        telegram_id: Telegram 用户 ID。
    """
    return await _user.get_or_create_maiuser_from_tg(telegram_id)


async def get_qq_from_telegram(telegram_id: int) -> Optional[int]:
    """查询 Telegram 绑定的 QQ。

    Args:
        telegram_id: Telegram 用户 ID。
    """
    return await _link.get_qq_from_tg(telegram_id)
