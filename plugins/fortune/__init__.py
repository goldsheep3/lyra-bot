from datetime import datetime

from nonebot import require
from nonebot.plugin import on_regex
from nonebot.internal.matcher import Matcher
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import Event, Message, MessageEvent
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN

from .utils import get_fortune, get_fortune_items, add_fortune_item, build_fortune_message

require("nonebot_plugin_localstore")


jrys = on_regex(r"^(今日运势|运势|抽签|签到|打卡|jrys)$", block=True)
jrys_history = on_regex(r"^历史运势$", block=True)

add_item = on_regex(r"^添加运势\s+(.+)$", permission=SUPERUSER | GROUP_ADMIN, block=True)

@jrys.handle()
async def _(event: MessageEvent, matcher: Matcher):
    # 获取基本信息
    user_id: int = event.user_id
    group_id: int | None = getattr(event, "group_id", None)
    today_timestamp: int = int(datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

    if not group_id:
        await matcher.finish("不可以悄悄查运势喔！=w=")
        return

    fortune_items: list[str] = [str(today_timestamp), *(await get_fortune_items(group_id))]
    fortunes: list[str] = get_fortune(today_timestamp, user_id, fortune_items)

    message: Message = await build_fortune_message(today_timestamp, user_id, list(zip(fortune_items, fortunes)))

    await matcher.finish(message)


@jrys_history.handle()
async def _(event: MessageEvent, matcher: Matcher):
    await matcher.finish("历史运势功能正在开发中，敬请期待！=w=\n截止目前，历史运势还未被记录（")
    

@add_item.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    item = groups[0].strip()
    group_id: int | None = getattr(event, "group_id", None)
    if not group_id:
        # 静默返回
        return
    success = await add_fortune_item(group_id, item)
    if success:
        await matcher.finish(f"新增运势！{item}")
    else:
        await matcher.finish("该运势项已经存在啦！")
