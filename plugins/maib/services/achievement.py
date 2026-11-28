from typing import Optional, Sequence

from ..utils.models import MaiChartAch, Server
from ..utils.report import MaiChartAchDiffReport
from ._refactoring import _sync


async def is_diving_fish_source_current(*, qq: int, hash: str) -> bool:
    """检查 DivingFish 数据源是否为最新。

    Args:
        qq: 用户 QQ 号。
        hash: 本次获取到的 DivingFish 数据哈希。
    """
    return await _sync.get_last_sy_hash(qq) == hash


async def update_achievements(*, qq: int, ach_list: Sequence[MaiChartAch], server: Server,
                              diving_fish_hash: Optional[str] = None) -> MaiChartAchDiffReport:
    """上传成绩并返回报告，支持自动更新 hash。

    Args:
        qq: 成绩所属用户的 QQ 号。
        ach_list: 待写入的成绩列表。
        server: 服务器类型。
        diving_fish_hash: 可选的 DivingFish 数据哈希，用于更新缓存。
    """
    report = await _sync.upd_ach_batch(qq, ach_list, server)
    if server == Server.CN and diving_fish_hash is not None:
        await _sync.set_last_sy_hash(qq, diving_fish_hash)
    return report
