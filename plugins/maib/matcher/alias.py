import re
from typing import Literal, Optional

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import services
from . import Reply, reply
from .context import get_or_create_maiuser
from ..utils import NoLinkQQError


# 设置乐曲别名
mai_alias = on_regex(r"^(添加|删除)别名\s+(?:(?:id)?(\d+)\s+)?([^\s]+)$", priority=5, block=True)


@mai_alias.handle()
async def mai_alias_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), reply: Reply = reply):
    """处理命令: 添加别名 id11451 xxx / 添加别名 xxx（从回复取 ID）"""
    action, shortid, alias = groups

    # 从命令或回复中解析 short_id
    short_id: Optional[int] = None
    if shortid:
        short_id = int(shortid)
    else:
        # 从回复消息中提取 ID
        if isinstance(event, OneBotV11Event):
            if reply_msg := getattr(event, "reply", None):
                match = re.search(r"(\d+)", str(reply_msg.message))
                if match:
                    short_id = int(match.group(1))
        elif isinstance(event, TGEvent):
            if reply_to_message := getattr(event, "reply_to_message", None):
                replied = str(getattr(reply_to_message, "text", "")) or str(getattr(reply_to_message, "caption", ""))
                match = re.search(r"(\d+)", replied)
                if match:
                    short_id = int(match.group(1))

    if short_id is None:
        await matcher.finish(await reply("info.invalid_id"))
        return

    try:
        maiuser = await get_or_create_maiuser(event)
    except NoLinkQQError:
        await matcher.finish(await reply("link.get_more_info"))
        return
    except ValueError as e:
        await matcher.finish(str(e))
        return
    else:
        qq = maiuser.user_id

    if action in ("添加",):
        add_status = await services.refactoring.alias.add_alias(short_id, alias, qq=qq)
        if add_status == "missing":
            await matcher.finish(await reply("info.invalid_id"))
            return
        elif add_status == "exists":
            await matcher.finish(await reply("alias.add.already_exists"))
            return
        elif add_status == "success":
            await matcher.finish(await reply("alias.add.success", shortid=str(short_id), alias=alias))
            return
        else:
            await matcher.finish(await reply("alias.add.failed.unknown"))
            return

    elif action in ("删除",):
        del_status = await services.refactoring.alias.remove_alias(short_id, alias, qq=qq)
        if del_status == "missing":
            await matcher.finish(await reply("info.invalid_id"))
            return
        elif del_status == "not_exists":
            await matcher.finish(await reply("alias.remove.not_found"))
            return
        elif del_status == "not_owner":
            await matcher.finish(await reply("alias.remove.not_owner"))
            return
        elif del_status == "success":
            await matcher.finish(await reply("alias.remove.success", shortid=str(short_id), alias=alias))
            return
        else:
            await matcher.finish(await reply("alias.remove.failed.unknown"))
            return
