import re
from random import choice
from typing import Literal

from nonebot import logger
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.internal.matcher import Matcher

from nonebot.adapters.onebot.v11 import MessageEvent

from .messages import MESSAGES, ALCOHOL_NOTICE, SPECIAL_NOTICE, NICKNAMES
from .utils import Food, Drink, Menu, content_cut


__plugin_meta__ = PluginMetadata(
    name="吃什么",
    description="一个「吃什么」的查询插件。",
    usage="发送「吃什么」即可使用。",
)


# 初始化菜单数据类
menu = Menu()


on_what_food = on_regex(r"^(.*?)([吃喝])什么$", block=True)

@on_what_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃什么 / 喝什么"""

    match = re.search(r"^(.*?)([吃喝])什么$", str(event.get_message()))
    if not match: return

    pre_message = match.group(1)
    category = match.group(2)
    # todo: 对评分的处理
    foods = menu.get_foods() if category == "吃" else menu.get_drinks()
    food = choice(foods)

    # 内容替换规则
    if any(i in pre_message for i in NICKNAMES):
        await matcher.finish(SPECIAL_NOTICE)
    pre_message = pre_message.replace("你", "他")
    pre_message = pre_message.replace("我", "你")
    message = choice(MESSAGES).format(food.name, pre_message)
    if food.is_wine:
        message += "\n" + ALCOHOL_NOTICE
    await matcher.finish(message)


on_this_is_wine = on_regex(r"^([吃喝])这个\s+(.+)\s+((没)?有)酒$", priority=5, block=True)

@on_this_is_wine.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃这个 xxx 有酒/ 喝这个 xxx 没有酒"""
    matched = matcher.state["_matched"]

    user_id = int(event.user_id)
    action = matched.group(1)  # 吃/喝
    food_origin = matched.group(2)  # 食物名称
    has_wine = matched.group(4)  # None或有"没"
    is_wine = has_wine is None  # 有酒 -> True, 没有酒 -> False

    foods = content_cut(food_origin)
    if len(foods) > 1:
        await matcher.finish("如果要设置餐点的酒精属性，小梨每次只能确认一个哦！")
        return
    food = foods[0]

    # 查找对应的食物或饮品，如果不存在则直接添加，否则修改酒精属性
    category: Literal["Food", "Drink"] = "Food" if action == "吃" else "Drink"
    existing_item_id = menu.find_by_name(category, food)
    if existing_item_id:
        if category == "Food":
            menu.set_food_wine(existing_item_id, is_wine, user_id), getattr(event, "group_id", -1)
            await matcher.finish(
                f"小梨确认！已经将[F{existing_item_id}]:「{food}」确认为「{'含酒精' if is_wine else '不含酒精'}」的食品了喔。")
        else:
            menu.set_drink_wine(existing_item_id, is_wine, user_id), getattr(event, "group_id", -1)
            await matcher.finish(
                f"小梨确认！已经将[D{existing_item_id}]:「{food}」确认为「{'含酒精' if is_wine else '不含酒精'}」的饮品了喔。")

    else:
        if category == "Food":
            new_item = Food(food, user_id, menu.food_score, is_wine=is_wine)
        else:
            new_item = Drink(food, user_id, menu.drink_score, is_wine=is_wine)
        menu.add_eatables([new_item], user_id, getattr(event, "group_id", -1))
        await matcher.finish(f"小梨已经把餐点「{food}」添加到{('食物' if category == '吃' else '饮品')}列表，并且已经标记含有酒精啦！")


on_this_food = on_regex(r"^([吃喝])这个\s+(.+)$", priority=3, block=True)

@on_this_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃这个 xxx / 喝这个 xxx"""

    matched = matcher.state["_matched"]

    user_id = int(event.user_id)
    category = matched.group(1)
    content = matched.group(2)
    if category == "吃":
        food_list = [Food(name, user_id, menu.food_score) for name in content_cut(content)]
    elif category == "喝":
        food_list = [Drink(name, user_id, menu.drink_score) for name in content_cut(content)]
    else: return

    new_food_list = menu.add_eatables(food_list, user_id, getattr(event, "group_id", -1))

    if not new_food_list:
        await matcher.finish(f"这些餐点在小梨的菜单上已经都有了喔——")
    await matcher.finish(
        f"小梨已经把以下的餐点添加到{('食物' if category == '吃' else '饮品')}列表啦！\n" +
        f"{'；'.join([i.name for i in new_food_list])}")


on_score_set = on_regex(r"^好([吃喝])吗\s+(\d+)\s+([0-9])$", priority=4, block=True)

@on_score_set.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 好吃吗 123 4 / 好喝吗 456 3"""
    ...


on_score_get = on_regex(r"^好([吃喝])吗\s+(\d+)$", priority=2, block=True)

@on_score_get.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 好吃吗 123 / 好喝吗 456"""
    ...


on_score_filter = on_regex(r"^可以吃\s+(.+)$", priority=1, block=True)

@on_score_filter.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 可以吃 xxx"""
    """
    - `可以吃 好的`: `吃什么`只会给出3.8分以上的餐品
    - `可以吃 能吃的`: `吃什么`只会给出3.0分以上的餐品
    - `可以吃 都行`: `吃什么`会给出2.0分以上的餐品，但3.0分以上的餐品更容易被给出
    - `可以吃 好玩的`: `吃什么`只会给出3.2分以下的餐品
    - `可以吃 猎奇的`: `吃什么`只会给出2.2分以下的餐品，且分数越低的餐品越容易被给出
    """
    ...


on_score_rank = on_regex(r"^([吃喝])什么排行榜\s*(\d*)$", priority=10, block=True)

@on_score_rank.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃什么排行榜 / 喝什么排行榜2"""
    ...
