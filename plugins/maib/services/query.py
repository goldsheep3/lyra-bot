from typing import Optional, Sequence

from ..utils.models import MaiChart, MaiChartAch, MaiData, Server
from ._refactoring import _mlist as _query


async def list_maidata_by_genre(genre: int, *, qq: Optional[int] = None) -> Sequence[MaiData]:
    """通过流派获取乐曲列表。

    Args:
        genre: 流派 ID。
        qq: 可选的 QQ 号；提供时会附带该用户的成绩。
    """
    return [item.to_utils() for item in await _query.get_mdt_list.genre(genre, achs_user_id=qq)]


async def list_maidata_by_version(ver: int | tuple[int, int], allow_utage: bool = False, *, qq: Optional[int] = None) -> Sequence[MaiData]:
    """通过版本获取乐曲列表。

    Args:
        ver: 单个版本 ID，或版本 ID 的范围。
        allow_utage: 是否包含宴会场谱面。
        qq: 可选的 QQ 号；提供时会附带该用户的成绩。
    """
    return [item.to_utils() for item in await _query.get_mdt_list.version(ver, achs_user_id=qq, allow_utage=allow_utage)]


async def list_charts_by_level(lv: float | tuple[float, float], server: Server, allow_utage: bool = False, *, qq: Optional[int] = None) -> Sequence[MaiChart]:
    """通过难度获取谱面列表。

    Args:
        lv: 单个等级定数，或等级定数范围。
        server: 查询定数使用的服务器。
        allow_utage: 是否包含宴会场谱面。
        qq: 可选的 QQ 号；提供时会附带该用户的成绩。
    """
    return [item.to_utils() for item in await _query.get_mct_list.level(lv, server, achs_user_id=qq, allow_utage=allow_utage)]


async def list_achievements_by_user(server: Server, allow_utage: bool = False, *, qq: int) -> Sequence[MaiChartAch]:
    """通过用户获取成绩列表。

    Args:
        server: 要查询的服务器。
        allow_utage: 是否包含宴会场谱面成绩。
        qq: 要查询的用户 QQ 号。
    """
    return [item.to_utils() for item in await _query.get_mca_list.user(qq, server, allow_utage=allow_utage)]


async def list_achievements_by_rate(ach: float | tuple[float, float], server: Server, allow_utage: bool = False, *, qq: int) -> Sequence[MaiChartAch]:
    """通过达成率获取成绩列表。

    Args:
        ach: 单个达成率百分比，或达成率范围。
        server: 要查询的服务器。
        allow_utage: 是否包含宴会场谱面成绩。
        qq: 要查询的用户 QQ 号。
    """
    return [item.to_utils() for item in await _query.get_mca_list.achievement(ach, server, qq, allow_utage=allow_utage)]


async def list_achievements_by_dxrating(dxra: float | tuple[float, float], server: Server, *, qq: int) -> Sequence[MaiChartAch]:
    """通过 DX Rating 获取成绩列表。

    Args:
        dxra: 单个 DX Rating，或 DX Rating 范围。
        server: 要查询的服务器。
        qq: 要查询的用户 QQ 号。
    """
    return [item.to_utils() for item in await _query.get_mca_list.dxrating(dxra, server, qq)]
