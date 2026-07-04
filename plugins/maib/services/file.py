"""services/file.py Telegram 文件缓存相关 CRUD 操作"""
from typing import Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import MaiData


__all__ = [
    # 更新 Telgram 文件 ID 以实现快速发送
    "upd_mdt_tg_fileid",
]


async def upd_mdt_tg_fileid(shortid: int, tg_file_id: str,
                            *, session: Optional[AsyncSession] = None):
    """通过 `shortid` 更新 `MaiData` 的 `tg_file_id_cache`"""
    async def _action(session: AsyncSession):
        stmt = (
            update(MaiData)
            .where(MaiData.shortid == shortid)
            .values(tg_file_id_cache=tg_file_id)
        )
        await session.execute(stmt)

    await execute_func.action(_action, session=session)
