"""不向调用方暴露 ORM 与 session 的 Aime 用例。"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .. import get_session
from ..models import Maime, MaiUser


_DEFAULT_HINT = "Target QQ: {qq}"


class AimeError(Exception):
    """Aime 用例的公开异常基类。"""


class AimeAlreadyLinkedError(AimeError):
    """卡片已经绑定到其他用户。"""


class AimeAlreadyLinkedSelfError(AimeError):
    """卡片已经绑定到当前用户。"""


class AimeNotFoundError(AimeError):
    """没有符合条件的卡片记录。"""


class AimeNotLinkedError(AimeError):
    """卡片有历史记录，但当前未绑定。"""


class AimeNotOwnerError(AimeError):
    """卡片不属于当前用户。"""


class AimeMultipleFoundError(AimeError):
    """后四位对应多张历史卡片。"""


class AimeFoundInfo(TypedDict):
    access: str
    qq: int
    hint: str


class AimeInfo(TypedDict):
    access: str
    create_at: datetime


__all__ = [
    "AimeError",
    "AimeAlreadyLinkedError",
    "AimeAlreadyLinkedSelfError",
    "AimeNotFoundError",
    "AimeNotLinkedError",
    "AimeNotOwnerError",
    "AimeMultipleFoundError",
    "AimeFoundInfo",
    "AimeInfo",
    "link",
    "unlink",
    "find_aime",
    "find_aime_by_access4",
    "get_aimes",
]


def _normalize_access(access: str) -> str:
    normalized = access.replace(" ", "").replace("-", "")
    if len(normalized) != 20 or not normalized.isascii() or not normalized.isdigit():
        raise ValueError("Aime access must contain exactly 20 ASCII digits")
    return normalized


def _normalize_access4(access4: str) -> str:
    normalized = access4.strip()
    if len(normalized) != 4 or not normalized.isascii() or not normalized.isdigit():
        raise ValueError("Aime access suffix must contain exactly 4 ASCII digits")
    return normalized


def _raise_linked(owner: int, qq: int) -> None:
    if owner == qq:
        raise AimeAlreadyLinkedSelfError
    raise AimeAlreadyLinkedError


async def link(access: str, *, qq: int) -> None:
    """将卡片绑定到用户；新建与重新绑定均在一个事务中完成。"""
    access_code = _normalize_access(access)

    async with get_session() as session:
        maime = await session.get(Maime, access_code)
        if maime is not None and maime.user_id is not None:
            _raise_linked(maime.user_id, qq)

        if await session.get(MaiUser, qq) is None:
            session.add(MaiUser(qq=qq))

        now = datetime.now()
        if maime is not None:
            result = await session.execute(
                update(Maime)
                .where(Maime.access == access_code, Maime.user_id.is_(None))
                .values(user_id=qq, create_at=now)
                .returning(Maime.access)
            )
            if result.scalar_one_or_none() is not None:
                await session.commit()
                return
            await session.rollback()
            owner = await session.scalar(
                select(Maime.user_id).where(Maime.access == access_code)
            )
            if owner is not None:
                _raise_linked(owner, qq)
            raise AimeError("failed to bind an existing Aime record")

        session.add(
            Maime(
                access=access_code,
                access4=access_code[-4:],
                user_id=qq,
                create_at=now,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # A concurrent link may insert the same primary key after our
            # initial lookup. Re-read it to expose a stable domain error.
            await session.rollback()
            owner = await session.scalar(
                select(Maime.user_id).where(Maime.access == access_code)
            )
            if owner is not None:
                _raise_linked(owner, qq)
            raise


async def unlink(access: str, *, qq: int) -> None:
    """仅允许所有者解绑，并保留卡片历史记录。"""
    normalized = _normalize_access(access)

    async with get_session() as session:
        maime = await session.get(Maime, normalized)
        if maime is None or maime.user_id is None:
            raise AimeNotFoundError
        if maime.user_id != qq:
            raise AimeNotOwnerError
        maime.user_id = None
        await session.commit()


async def find_aime(access: str) -> AimeFoundInfo | None:
    """按完整卡号查找当前绑定；已解绑记录不会被返回。"""
    normalized = _normalize_access(access)

    async with get_session() as session:
        row = (
            await session.execute(
                select(Maime.access, Maime.user_id)
                .where(Maime.access == normalized, Maime.user_id.is_not(None))
            )
        ).one_or_none()
        if row is None:
            return None
        access_value, owner = row
        assert owner is not None
        hint = _DEFAULT_HINT.format(qq=owner)
        return {"access": access_value, "qq": owner, "hint": hint}


async def find_aime_by_access4(access4: str) -> AimeFoundInfo:
    """按后四位查找历史记录，包括已解绑卡片。"""
    normalized = _normalize_access4(access4)

    async with get_session() as session:
        rows = (
            await session.execute(
                select(Maime.access, Maime.user_id)
                .where(Maime.access4 == normalized)
            )
        ).all()

        if not rows:
            raise AimeNotFoundError
        if len(rows) > 1:
            raise AimeMultipleFoundError

        access_value, owner = rows[0]
        if owner is None:
            raise AimeNotLinkedError
        hint = _DEFAULT_HINT.format(qq=owner)
        return {"access": access_value, "qq": owner, "hint": hint}


async def get_aimes(*, qq: int) -> list[AimeInfo]:
    """返回用户当前绑定的全部卡片。"""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Maime.access, Maime.create_at)
                .where(Maime.user_id == qq)
                .order_by(Maime.create_at, Maime.access)
            )
        ).all()
        return [
            {"access": access, "create_at": create_at}
            for access, create_at in rows
        ]
