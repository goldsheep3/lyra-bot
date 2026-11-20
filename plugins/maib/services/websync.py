from typing import Optional

from ._refactoring import _websync

PairingCodeError = _websync.PairingCodeError
AccessTokenError = _websync.AccessTokenError


async def create_pairing_code(*, qq: int, expire_seconds: int = 300) -> _websync.PairingCodeIssueResult:
    """创建并返回最新配对码。

    Args:
        qq: 要配对的用户 QQ 号。
        expire_seconds: 配对码有效期，单位为秒。
    """
    return await _websync.create_pairing_code(qq, ttl_seconds=expire_seconds)


async def exchange_pairing_code(*, code: str, device_id: str, device_name: Optional[str] = None) -> tuple[int, str]:
    """使用配对码换取 access token，返回用户 QQ。

    Args:
        code: 待交换的配对码。
        device_id: 客户端设备的唯一标识。
        device_name: 可选的设备显示名称。
    """
    return await _websync.exchange_pairing_code(code, device_id=device_id, device_name=device_name)


async def authenticate_access_token(access_token: str) -> int:
    """验证 access token 并返回用户 QQ。

    Args:
        access_token: 要验证的访问令牌。
    """
    return await _websync.authenticate_access_token(access_token)
