from typing import Literal, Optional, cast

from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Event as OneBotV11Event
from nonebot.adapters.telegram import Event as TGEvent

from plugins.nonebot_plugin_i18n import reply

from .. import config, network, services, utils
from ..utils.enums import Server, ServerScope, SLevelSource
from ..utils import NoLinkQQError


ParsedArgs = tuple[Optional[int], Optional[ServerScope]]


def get_args(args_text: str) -> ParsedArgs:
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


async def get_maiuser(event: Event, user_id: int | None = None) -> utils.MaiUser:
    """Resolve the current platform user to a maimai user."""
    if user_id is None:
        raw_uid = event.get_user_id()
        try:
            user_id = int(raw_uid)
        except ValueError as e:
            raise ValueError(reply("error.invalid_user_id", raw_uid=raw_uid)) from e

    if isinstance(event, OneBotV11Event):
        mu = await services.check_mu(user_id)
    elif isinstance(event, TGEvent):
        mu = await services.get_mu_from_tgid(user_id)
        if mu is None:
            raise NoLinkQQError(reply("error.user_not_found"))
    else:
        raise ValueError(reply("error.unexpected"))

    if not mu.username:
        qq = mu.user_id
        data = await network.DivingFish.dev_player_records(
            qq=qq,
            developer_token=config.DIVING_FISH_DEVELOPER_TOKEN,
        )
        username = data.get("nickname", "maimai") if isinstance(data, dict) else "maimai"
        await services.set_mu_username(qq, username)
        mu.username = username

    return mu.to_utils()


async def get_maidata_with_ach(
    short_id: int,
    target_server: Server,
    user_id: int,
) -> Optional[tuple[utils.MaiData, Server]]:
    """Load music data with a user's achievement and apply server fallback."""
    mdt = await services.get_mdt.id(short_id, user_id)
    if not mdt:
        return None

    maidata = mdt.to_utils(achs_user_id=user_id)
    actual_server = Server.JP if (getattr(maidata, SLevelSource.server(target_server).lv_field, None) is None) else target_server
    return maidata, actual_server
