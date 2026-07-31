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
from .models import MaiSyncPairingCode, MaiSyncToken
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
    stmt = select(MaiSyncToken).where(MaiSyncToken.user_id == user_id)
    token = (await session.execute(stmt)).scalar_one_or_none()
    if token is not None:
        token.revoked_at = now


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

        existing_codes = (
            await session.execute(
                select(MaiSyncPairingCode).where(
                    MaiSyncPairingCode.user_id == user_id,
                    MaiSyncPairingCode.used_at.is_(None),
                    MaiSyncPairingCode.revoked.is_(False),
                )
            )
        ).scalars().all()
        for row in existing_codes:
            row.revoked = True
            row.used_at = now

        await _revoke_user_token(user_id, now=now, session=session)

        while True:
            secret = _generate_pairing_secret()
            code_hash = _hash_text(secret)
            exists = (
                await session.execute(
                    select(MaiSyncPairingCode.id).where(MaiSyncPairingCode.code_hash == code_hash)
                )
            ).scalar_one_or_none()
            if exists is None:
                break

        session.add(MaiSyncPairingCode(
            user_id=user_id,
            code_hash=code_hash,
            expires_at=expires_at,
            create_time=now,
        ))
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
                select(MaiSyncPairingCode).where(MaiSyncPairingCode.code_hash == code_hash)
            )
        ).scalar_one_or_none()

        if pairing is None:
            raise PairingCodeError("invalid_code")
        if pairing.revoked:
            raise PairingCodeError("revoked_code")
        if pairing.used_at is not None:
            raise PairingCodeError("used_code")
        if pairing.expires_at <= now:
            raise PairingCodeError("expired_code")

        pairing.used_at = now

        sibling_codes = (
            await session.execute(
                select(MaiSyncPairingCode).where(
                    MaiSyncPairingCode.user_id == pairing.user_id,
                    MaiSyncPairingCode.used_at.is_(None),
                    MaiSyncPairingCode.id != pairing.id,
                )
            )
        ).scalars().all()
        for row in sibling_codes:
            row.revoked = True
            row.used_at = now

        plain_token = _generate_access_token()
        token_hash = _hash_text(plain_token)

        token = (
            await session.execute(
                select(MaiSyncToken).where(MaiSyncToken.user_id == pairing.user_id)
            )
        ).scalar_one_or_none()
        if token is None:
            session.add(MaiSyncToken(
                user_id=pairing.user_id,
                token_hash=token_hash,
                device_id=normalized_device_id,
                device_name=normalized_device_name,
                create_time=now,
                last_used_at=now,
                revoked_at=None,
            ))
        else:
            token.token_hash = token_hash
            token.device_id = normalized_device_id
            token.device_name = normalized_device_name
            token.create_time = now
            token.last_used_at = now
            token.revoked_at = None

        return pairing.user_id, plain_token

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
                select(MaiSyncToken).where(MaiSyncToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if token is None or token.revoked_at is not None:
            raise AccessTokenError("invalid_token")

        token.last_used_at = datetime.now(timezone.utc)
        return token.user_id

    return await execute_func.action(_action, session=session)
