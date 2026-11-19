from typing import Literal, Optional, cast

from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Event as OneBotV11Event
from nonebot.adapters.telegram import Event as TGEvent

from . import Reply, reply
from .. import config, network, services, utils
from ..utils.enums import Server, ServerScope, SLevelSource
from ..utils import NoLinkQQError


def get_args(args_text: str) -> tuple[Optional[int], Optional[ServerScope]]:
    """Parse optional target user id and target server arguments."""
    target_user_id: Optional[int] = None
    target_server: Optional[ServerScope] = None

    for arg in args_text.split():
        if arg.isdigit() and target_user_id is None:
            target_user_id = int(arg)
        
        if target_server is None:
            try:
                target_server = ServerScope.parse(arg)
            except Exception:
                target_server = None

        _map = {
            "全服": ServerScope.ALL,
            
            "日服": ServerScope.JP,
            "日": ServerScope.JP,
            
            "国服": ServerScope.CN,
            "简中服": ServerScope.CN,
            "国": ServerScope.CN,
            "简中": ServerScope.CN,
        }
        if arg in _map:
            target_server = _map[arg]

    return target_user_id, target_server



async def get_or_create_maiuser(event: Event, target_id: int | None = None) -> utils.MaiUser:
    if isinstance(event, OneBotV11Event):
        qq = target_id if target_id is not None else int(event.get_user_id())
        return await services.refactoring.user.get_or_create_maiuser_from_qq(qq)
    elif isinstance(event, TGEvent):
        tg_id = target_id if target_id is not None else int(event.get_user_id())
        return await services.refactoring.user.get_or_create_maiuser_from_tg(tg_id)
    else:
        raise ValueError("Unsupported event type")


async def get_maidata_with_ach(
    short_id: int,
    target_server: Server,
    user_id: int,
) -> Optional[tuple[utils.MaiData, Server]]:
    """Load music data with a user's achievement and apply server fallback."""
    maidata = await services.refactoring.catalog.get_maidata(
        short_id,
        qq=user_id,
        # 需要保留目标服缺少定数时回退 JP 的成绩，因此一次加载两服默认 provider。
        server=ServerScope.ALL,
    )
    if maidata is None:
        return None

    level_field = SLevelSource.from_server(target_server).lv_field
    has_target_level = any(
        getattr(chart, level_field, None) is not None
        for chart in maidata.charts.values()
    )
    actual_server = target_server if has_target_level else Server.JP
    return maidata, actual_server
