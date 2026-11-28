from typing import Optional, TypedDict
import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from nonebot_plugin_datastore import create_session as get_session

from . import _models as db
from ._refactoring._user import check_mu
from ._refactoring._tool import execute_func


PAIRING_CODE_PREFIX = "maisync3:"
_PAIRING_CODE_LENGTH = 12
_PAIRING_CODE_ALPHABET = string.ascii_letters + string.digits
_ACCESS_TOKEN_BYTES = 48
_DEFAULT_PAIRING_TTL_SECONDS = 300


class PairingCodeError(ValueError):
    """配对码校验失败。"""


class AccessTokenError(ValueError):
    """访问令牌校验失败。"""


@dataclass(slots=True)
class PairingCodeIssueResult:
    code: str
    expires_at: datetime


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_access_token() -> str:
    return secrets.token_urlsafe(_ACCESS_TOKEN_BYTES)


def _normalize_pairing_code(code: str) -> str:
    normalized = str(code or "").strip()
    if not normalized:
        raise PairingCodeError("empty_code")
    if normalized.startswith(PAIRING_CODE_PREFIX):
        normalized = normalized[len(PAIRING_CODE_PREFIX):]
    if len(normalized) != _PAIRING_CODE_LENGTH:
        raise PairingCodeError("invalid_code")
    if any(ch not in _PAIRING_CODE_ALPHABET for ch in normalized):
        raise PairingCodeError("invalid_code")
    return normalized


def _normalize_device_id(device_id: str) -> str:
    normalized = str(device_id or "").strip()
    if not normalized or len(normalized) > 64:
        raise ValueError("invalid_device_id")
    return normalized


def _normalize_device_name(device_name: Optional[str]) -> str:
    normalized = str(device_name or "").strip()
    return normalized[:128]


async def _revoke_user_token(user_id: int, *, now: datetime, session: AsyncSession) -> None:
    rows = (
        await session.execute(
            select(db.MaiSync).where(
                db.MaiSync.qq == user_id,
                db.MaiSync.token_revoked.is_(False),
            )
        )
    ).scalars().all()
    for row in rows:
        row.token_revoked = True


async def exchange_pairing_code2(
    code: str,
    *,
    device_id: str,
    device_name: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> tuple[int, str]:
    normalized_code = _normalize_pairing_code(code)
    normalized_device_id = _normalize_device_id(device_id)
    normalized_device_name = _normalize_device_name(device_name)
    code_hash = _hash_text(normalized_code)

    async def _action(session: AsyncSession) -> tuple[int, str]:
        now = datetime.now(timezone.utc)
        pairing = (
            await session.execute(
                select(db.MaiSync).where(db.MaiSync.pairing_code == code_hash)
            )
        ).scalar_one_or_none()

        if pairing is None:
            raise PairingCodeError("invalid_code")
        if pairing.pairing_used_at is not None:
            raise PairingCodeError("used_code")
        if pairing.pairing_expires_at <= now:
            raise PairingCodeError("expired_code")

        pairing.pairing_used_at = now

        await _revoke_user_token(pairing.qq, now=now, session=session)

        plain_token = _generate_access_token()
        token_hash = _hash_text(plain_token)

        pairing.token = token_hash
        pairing.device_id = normalized_device_id
        pairing.device_name = normalized_device_name
        pairing.token_created_at = now
        pairing.token_last_used_at = now
        pairing.token_revoked = False

        return pairing.qq, plain_token

    return await execute_func.action(_action, session=session)


async def authenticate_access_token2(
    access_token: str,
    *,
    session: Optional[AsyncSession] = None,
) -> int:
    normalized = str(access_token or "").strip()
    if not normalized:
        raise AccessTokenError("empty_token")
    token_hash = _hash_text(normalized)

    async def _action(session: AsyncSession) -> int:
        token = (
            await session.execute(
                select(db.MaiSync).where(db.MaiSync.token == token_hash)
            )
        ).scalar_one_or_none()
        if token is None or token.token_revoked:
            raise AccessTokenError("invalid_token")

        token.token_last_used_at = datetime.now(timezone.utc)
        return token.qq

    return await execute_func.action(_action, session=session)

class PairingHash(TypedDict):
    secret: str
    hash: str
    
async def get_new_hash(session: AsyncSession) -> PairingHash:
    """生成哈希值，且保证数据库中无碰撞"""
    length = _PAIRING_CODE_LENGTH
    alpha = _PAIRING_CODE_ALPHABET
    while True:
        secret = "".join(secrets.choice(alpha) for _ in range(length))
        hash = _hash_text(secret)
        
        exists = (await session.execute(
            select(db.MaiSync.id).where(db.MaiSync.pairing_code == hash)
        )).scalar_one_or_none()
        if exists is None:
            return PairingHash(secret=secret, hash=hash)


async def create_pairing_code(*, qq: int, expire_seconds: int = 300) -> PairingCodeIssueResult:
    """创建并返回最新配对码。

    Args:
        qq: 要配对的用户 QQ 号。
        expire_seconds: 配对码有效期，单位为秒。
    """
    ttl_seconds = max(60, min(expire_seconds, 600))
    
    async with get_session() as session:
        await check_mu(qq, session=session)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        pairing_hash = await get_new_hash(session)

        # 每用户只保留一条记录：重新申请配对码时直接覆盖旧记录，
        # 旧配对码与旧 token 一并作废。
        row = (
            await session.execute(select(db.MaiSync).where(db.MaiSync.qq == qq))
        ).scalar_one_or_none()
        if row is None:
            row = db.MaiSync(qq=qq)
            session.add(row)
        row.pairing_code = pairing_hash["hash"]
        row.pairing_created_at = now
        row.pairing_expires_at = expires_at
        row.pairing_used_at = None
        row.token = _hash_text(f"pending:{pairing_hash['secret']}")
        row.token_created_at = now
        row.token_last_used_at = now
        row.token_revoked = True
        row.device_id = ""
        row.device_name = ""
        await session.commit()

    return PairingCodeIssueResult(
        code=f"{PAIRING_CODE_PREFIX}{pairing_hash['secret']}",
        expires_at=expires_at,
    )


async def exchange_pairing_code(*, code: str, device_id: str, device_name: Optional[str] = None) -> tuple[int, str]:
    """使用配对码换取 access token，返回用户 QQ。

    Args:
        code: 待交换的配对码。
        device_id: 客户端设备的唯一标识。
        device_name: 可选的设备显示名称。
    """
    return await exchange_pairing_code2(code, device_id=device_id, device_name=device_name)


async def authenticate_access_token(access_token: str) -> int:
    """验证 access token 并返回用户 QQ。

    Args:
        access_token: 要验证的访问令牌。
    """
    return await authenticate_access_token2(access_token)
