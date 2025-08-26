from datetime import datetime

from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot import logger

from .core import get_main_fortune, get_sub_fortune
from .desc import SUB_FORTUNE_TITLES
from .msg import build_fortune_message


__plugin_meta__ = PluginMetadata(
    name="简单运势",
    description="一个基于SHA256的运势查询插件。",
    usage="发送「今日运势」「运势」「抽签」「签到」「打卡」即可获得今日专属运势。",
)


on_fortune = on_regex(r"^(今日运势|运势|抽签|签到|打卡)$", block=True)

@on_fortune.handle()
async def _(event: MessageEvent, matcher: Matcher):
    user_id = event.user_id
    today = datetime.now()
    try:
        main_title = get_main_fortune(user_id, today)
        sub_fortunes = get_sub_fortune(user_id, today, count=len(SUB_FORTUNE_TITLES))
        output = build_fortune_message(main_title, user_id, today, sub_fortunes)
    except Exception as e:
        logger.error(f"生成运势时发生错误。{e}")
        return
    await matcher.finish(MessageSegment.text(output))
