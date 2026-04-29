# lyra-plugin-help
from nonebot import on_regex

_help = on_regex(r"^(帮助|help)\s*(whatfood|WhatFood|吃什么)$", priority=10, block=True)


@_help.handle()
async def _():
    await _help.finish("""
LyraHELP | what_food (吃什么)

1. 吃什么 / 喝什么
   (1) 在抽选范围内随机抽选食物或饮品。
   (2) 确定抽选范围，如「吃什么 好吃的」或「吃什么 猎奇的」。AI 会判别抽选范围的分数值，并在之后根据该权重抽选。
2. 吃这个 / 喝这个
   添加新菜品，通过 AI 自助给出默认评分。
3. 好吃吗 / 好喝吗
   给菜品评分，分数范围 1-5。
   不带评分数值的情况下，可以查询到当前的平均分。
4. 吃什么排行榜 / 喝什么排行榜
   [当前重构中，暂不可用]
   可以查询当前所有菜品的排行榜，按照平均分排序，默认为正向排序。
   页码支持负数，如 -1 代表倒数第一页（即倒序排行榜第 1 页）。

""".strip())