from re import search as re_search
from random import choice

from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from messages import MESSAGES, ALCOHOL_NOTICE
from .menu import FOODS, DRINKS

__plugin_meta__ = PluginMetadata(
    name="吃什么",
    description="一个「吃什么」的查询插件。",
    usage="发送「吃什么」即可使用。",
)


on_what_food = on_regex(r"^(.*?)([吃喝])什么$", block=True)

@on_what_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    match = re_search(r"^(.*?)([吃喝])什么$", str(event.get_message()))
    if not match: return
    category = match.group(2)
    if category == "吃":
        food = choice(FOODS)
        message = choice(MESSAGES).format(food, match.group(1))
        await matcher.finish(MessageSegment.text(message))
    elif category == "喝":
        drink = choice(DRINKS)
        message = choice(MESSAGES).format(drink, match.group(1))
        if drink.endswith("⑨"):
            message = message[:len(message)-1] + "\n" + ALCOHOL_NOTICE
        await matcher.finish(MessageSegment.text(message))
    return
