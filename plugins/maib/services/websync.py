"""services/websync.py 在线同步配对码与令牌 CRUD"""
from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import MaiSync
from .user import check_mu


__all__ = [
    "PAIRING_CODE_PREFIX",
    "PairingCodeError",
    "AccessTokenError",
    "PairingCodeIssueResult",
    "create_pairing_code",
    "exchange_pairing_code",
    "authenticate_access_token",
]


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


def _generate_pairing_secret(length: int = _PAIRING_CODE_LENGTH) -> str:
    return "".join(secrets.choice(_PAIRING_CODE_ALPHABET) for _ in range(length))


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
            select(MaiSync).where(
                MaiSync.qq == user_id,
                MaiSync.token_revoked.is_(False),
            )
        )
    ).scalars().all()
    for row in rows:
        row.token_revoked = True


async def create_pairing_code(
    user_id: int,
    *,
    ttl_seconds: int = _DEFAULT_PAIRING_TTL_SECONDS,
    session: Optional[AsyncSession] = None,
) -> PairingCodeIssueResult:
    ttl_seconds = max(60, min(ttl_seconds, 600))

    async def _action(session: AsyncSession) -> PairingCodeIssueResult:
        await check_mu(user_id, session=session)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        while True:
            secret = _generate_pairing_secret()
            code_hash = _hash_text(secret)
            exists = (
                await session.execute(
                    select(MaiSync.id).where(MaiSync.pairing_code == code_hash)
                )
            ).scalar_one_or_none()
            if exists is None:
                break

        # 每用户只保留一条记录：重新申请配对码时直接覆盖旧记录，
        # 旧配对码与旧 token 一并作废。
        row = (
            await session.execute(select(MaiSync).where(MaiSync.qq == user_id))
        ).scalar_one_or_none()
        if row is None:
            row = MaiSync(qq=user_id)
            session.add(row)
        row.pairing_code = code_hash
        row.pairing_created_at = now
        row.pairing_expires_at = expires_at
        row.pairing_used_at = None
        row.token = _hash_text(f"pending:{secret}")
        row.token_created_at = now
        row.token_last_used_at = now
        row.token_revoked = True
        row.device_id = ""
        row.device_name = ""

        return PairingCodeIssueResult(
            code=f"{PAIRING_CODE_PREFIX}{secret}",
            expires_at=expires_at,
        )

    return await execute_func.action(_action, session=session)


async def exchange_pairing_code(
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
                select(MaiSync).where(MaiSync.pairing_code == code_hash)
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


async def authenticate_access_token(
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
                select(MaiSync).where(MaiSync.token == token_hash)
            )
        ).scalar_one_or_none()
        if token is None or token.token_revoked:
            raise AccessTokenError("invalid_token")

        token.token_last_used_at = datetime.now(timezone.utc)
        return token.qq

    return await execute_func.action(_action, session=session)
