from re import search as re_search
from random import choice

from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment

from .messages import MESSAGES, ALCOHOL_NOTICE, SPECIAL_NOTICE, NICKNAMES
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
    
    pre_message = match.group(1)
    category = match.group(2)
    
    food = choice({"吃": FOODS, "喝": DRINKS}.get(category, ()))
    wine = False
    if not food: return  # 不存在的分类
    if food.endswith("⑨"):
        wine = True
        food = food[:len(food)-1]
    
    # 内容替换规则
    to_lyra: bool = any(i in pre_message for i in NICKNAMES)
    pre_message = pre_message.replace("你", "他")
    pre_message = pre_message.replace("我", "你")

    message = choice(MESSAGES).format(food, pre_message)
    if wine:
        message += "\n" + ALCOHOL_NOTICE
    if to_lyra:
        message = SPECIAL_NOTICE

    await matcher.finish(MessageSegment.text(message))
