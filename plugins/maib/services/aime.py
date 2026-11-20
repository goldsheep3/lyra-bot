from typing import Optional

from ._refactoring import aime as _aime

AimeAlreadyLinkedError = _aime.AimeAlreadyLinkedError
AimeAlreadyLinkedSelfError = _aime.AimeAlreadyLinkedSelfError
AimeNotFoundError = _aime.AimeNotFoundError
AimeNotLinkedError = _aime.AimeNotLinkedError
AimeNotOwnerError = _aime.AimeNotOwnerError
AimeMultipleFoundError = _aime.AimeMultipleFoundError


async def link(access: str, *, qq: int) -> None:
    """绑定 Aime 卡片。

    Args:
        access: 完整 Aime 卡号。
        qq: 要绑定的用户 QQ 号。
    """
    return await _aime.link(access, qq=qq)


async def unlink(access: str, *, qq: int) -> None:
    """解绑 Aime 卡片。

    Args:
        access: 要解绑的完整 Aime 卡号。
        qq: 请求解绑的用户 QQ 号。
    """
    return await _aime.unlink(access, qq=qq)


async def find(access: str) -> Optional[_aime.AimeFoundInfo]:
    """查找 Aime 卡片绑定信息。

    Args:
        access: 要查询的完整 Aime 卡号。
    """
    return await _aime.find_aime(access)


async def find_by_access4(access4: str) -> _aime.AimeFoundInfo:
    """使用 Aime 卡片后四位查找绑定信息。

    Args:
        access4: Aime 卡号后四位。
    """
    return await _aime.find_aime_by_access4(access4)


async def list_for_user(*, qq: int):
    """列出用户绑定的所有 Aime 卡片。

    Args:
        qq: 要查询的用户 QQ 号。
    """
    return await _aime.get_aimes(qq=qq)
