from typing import Optional

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (GroupMessageEvent as OneBotV11GroupMessageEvent,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import services
from . import i18n_data, i18n, reply
from .context import get_maiuser



maime_link = on_regex(r'^绑定(aime|卡号|卡片)\s*(\d{4}(?:\s?\d{4}){4})$', priority=5, block=True)

maime_unlink = on_regex(r'^解绑(aime|卡号|卡片)\s*(\d{4}(?:\s?\d{4}){4})$', priority=5, block=True)

maime_lost = on_regex(r'^(挂失|捡到|拾获)(aime|卡号|卡片)\s*(\d{4}|\d{4}(?:\s?\d{4}){4})$', priority=5, block=True)


@maime_link.handle()
async def maime_link_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 绑定(aime|卡号|卡片) <aime卡号>"""
    i18n_data.set(_i18n)
    
    _, access = groups
    access = access.replace(" ", "")

    maime = await services.get_aime(access)
    if maime is not None:
        await matcher.finish(reply("maime.link.error.linked"))
        return

    try:
        maiuser = await get_maiuser(event)
    except ValueError as e:
        await matcher.finish(str(e))
        return

    qq = maiuser.user_id
    result = await services.add_aime(access, qq)
    if result:
        await matcher.finish(reply("maime.link.success"))
        return
    else:
        await matcher.finish(reply("maime.link.error.unknown"))
        return    


@maime_unlink.handle()
async def maime_unlink_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 解绑(aime|卡号|卡片) <aime卡号>"""
    i18n_data.set(_i18n)
    
    _, access = groups
    access = access.replace(" ", "")

    maime = await services.get_aime(access)
    if maime is None:
        await matcher.finish(reply("maime.unlink.error.not_found"))
        return

    try:
        maiuser = await get_maiuser(event)
    except ValueError as e:
        await matcher.finish(str(e))
        return

    qq = maiuser.user_id
    if maime.user_id != qq:
        await matcher.finish(reply("maime.unlink.error.not_owner"))
        return

    result = await services.unlink_aime(access)
    if not result:
        await matcher.finish(reply("maime.unlink.error.not_found"))
        return
    await matcher.finish(reply("maime.unlink.success"))


@maime_lost.handle()
async def maime_lost_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 拾获(aime|卡号|卡片) <aime卡号>"""
    i18n_data.set(_i18n)
    
    _, _, access = groups
    
    access = access.replace(" ", "")
    if len(access) == 4:
        maimes = await services.get_aime_with_access4(access)
        if not maimes:
            await matcher.finish(reply("maime.lost.error.not_found"))
            return
        elif len(maimes) > 1:
            await matcher.finish(reply("maime.lost.error.multiple_found"))
            return
        else:
            maime = maimes[0]
    else:
        maime = await services.get_aime(access)
        if maime is None:
            await matcher.finish(reply("maime.lost.error.not_found"))
            return

    maime_user_id = maime.user_id
    if maime_user_id is None:
        await matcher.finish(reply("maime.lost.error.not_found"))
        return

    await matcher.finish(reply("maime.lost.success", qq=maime_user_id))
    return


maime_list = on_regex(r'^(查看卡片|查看完整卡片)$', priority=5, block=True)


@maime_list.handle()
async def maime_list_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: 查看卡片"""
    i18n_data.set(_i18n)
    full = (groups[0] == "查看完整卡片")

    try:
        maiuser = await get_maiuser(event)
    except ValueError as e:
        await matcher.finish(str(e))
        return

    qq = maiuser.user_id
    maimes = await services.get_user_aimes(qq)

    if not maimes:
        await matcher.finish(reply("maime.list.empty"))
        return

    lines = [reply("maime.list.header")]
    for m in maimes:
        time_str = m.create_at.strftime("%Y-%m-%d %H:%M")
        if full:
            card_display = m.access
            item_key = "maime.list.item_full"
        else:
            card_display = m.access[:4] + "************" + m.access[-4:]
            item_key = "maime.list.item"
        lines.append(
            reply(item_key, access=card_display, masked=card_display, create_at=time_str)
        )

    await matcher.finish("\n".join(lines))