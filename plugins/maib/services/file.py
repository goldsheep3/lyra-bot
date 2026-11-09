"""services/file.py Telegram 文件缓存相关 CRUD 操作"""
from typing import Literal, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from . import execute_func
from .models import MaiData


__all__ = [
    # 更新 Telgram 文件 ID 以实现快速发送
    "upd_mdt_tg_fileid",
]


async def upd_mdt_tg_fileid(shortid: int, tg_file_id: str, endname: Literal["adx", "zip"] = "adx",
                            *, session: Optional[AsyncSession] = None):
    """通过 `shortid` 更新 `MaiData` 的 `tg_file_id_cache`"""
    async def _action(session: AsyncSession):
        stmt = (
            update(MaiData)
            .where(MaiData.shortid == shortid)
        )
        if endname == "adx":
            stmt = stmt.values(_tg_adx_id_cache=tg_file_id)
        elif endname == "zip":
            stmt = stmt.values(_tg_zip_id_cache=tg_file_id)
        else:
            raise ValueError(f"Invalid endname: {endname}")
        await session.execute(stmt)

    await execute_func.action(_action, session=session)
