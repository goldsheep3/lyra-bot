from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import execute_func
from ..models import MaiUser


__all__ = ["get_qq_from_tg"]

async def get_qq_from_tg(telegram_id: int) -> Optional[int]:
    async def _get_user_by_telegram_id(session: AsyncSession):
        statement = (
            select(MaiUser)
            .where(MaiUser.tg == telegram_id)
        )
        result = await session.execute(statement)
        user = result.scalar_one_or_none()
        return int(user.qq) if user else None

    return await execute_func.select(_get_user_by_telegram_id, session=None)
