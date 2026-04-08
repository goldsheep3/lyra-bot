# lyra-plugin-help
from random import choice

from nonebot import on_regex
from nonebot.rule import to_me


SPECIAL_MESSAGE = [
    "小梨喜欢你！",
]

_help = on_regex(r"^(帮助|help)$", priority=10, rule=to_me(), block=True)

@_help.handle()
async def _():
    await _help.finish("""
{{special_message}}

帮助 | LyraBot
输入 help [功能] 获取对应功能的帮助信息。

1. maib
   小梨音游核心，提供围绕 maimai 的各种功能。
2. fortune
   运势占卜，提供每日运势、抽签等功能。
3. what_food
   「吃什么」，提供食物随机抽选和评分功能。
4. daily_partner
   支持「一夫一妻制」的「今日老婆」。

""".strip().format(special_message=choice(SPECIAL_MESSAGE)))