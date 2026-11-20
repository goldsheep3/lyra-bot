from typing import Literal

from ._refactoring import _file


async def update_telegram_file_id(shortid: int, tg_file_id: str, endname: Literal["adx", "zip"] = "adx") -> None:
    """更新乐曲谱面包的 Telegram 文件缓存。

    Args:
        shortid: 乐曲 shortid。
        tg_file_id: Telegram 返回的文件 ID。
        endname: 谱面包扩展名类型。
    """
    await _file.upd_mdt_tg_fileid(shortid, tg_file_id, endname=endname)
