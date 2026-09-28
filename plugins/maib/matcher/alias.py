from typing import Optional
import re

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import services
from . import i18n_data, i18n, reply
from .context import get_maiuser


# 设置乐曲别名
mai_alias = on_regex(r"^(添加|删除)别名\s+(?:(?:id)?(\d+)\s+)?([^\s]+)$", priority=5, block=True)


@mai_alias.handle()
async def mai_alias_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 添加别名 id11451 xxx / 添加别名 xxx（从回复取 ID）"""
    i18n_data.set(_i18n)

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
        await matcher.finish(reply("info.invalid_id"))
        return

    try:
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
            await matcher.finish(reply("alias.add.success", shortid=str(short_id), alias=alias))
        else:
            await matcher.finish(reply("alias.add.already_exists"))
    else:
        await matcher.finish(reply("alias.remove.deletion_not_supported"))
