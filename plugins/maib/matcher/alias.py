from typing import Optional

from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (GroupMessageEvent as OneBotV11GroupMessageEvent,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import services
from . import build_msg, i18n_data, i18n, reply, get_maiuser, mai_alias


# --- mai_alias ---

@mai_alias.handle()
async def mai_alias_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 添加别名 id11451 xxx / 删除别名 id11451 xxx"""
    i18n_data.set(_i18n)

    action, shortid, alias = groups
    try:
        short_id = int(shortid)
        mdt: Optional[services.MaiData] = await services.get_mdt.id(short_id)
        if not mdt:
            raise ValueError
    except (ValueError, TypeError):
        await matcher.finish(reply("info.invalid_id"))
        return
    
    try:
        maiuser = await get_maiuser(event)
    except ValueError as e:
        await matcher.finish(str(e))
        return

    qq = maiuser.user_id
    if isinstance(event, OneBotV11GroupMessageEvent):
        group_id = event.group_id
    elif isinstance(event, TGEvent):
        group_id = -3  # 标记：来自于 Telegram
    else:
        group_id = None

    if action == "添加":
        # 添加别名
        new_alias = await services.add_ma(short_id, alias, qq, group_id)
        if new_alias:
            await matcher.finish(reply("alias.add.success", shortid=shortid, alias=alias))
        else:
            await matcher.finish(reply("alias.add.already_exists"))
    else:
        await matcher.finish(reply("alias.remove.deletion_not_supported"))
