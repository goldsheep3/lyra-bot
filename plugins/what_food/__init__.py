import re
import yaml
from random import choice
from typing import Tuple

from nonebot import require, logger
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.internal.matcher import Matcher

from nonebot.adapters.onebot.v11 import MessageEvent

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file

from .messages import MESSAGES, ALCOHOL_NOTICE, SPECIAL_NOTICE, NICKNAMES
from .utils import Food, Drink, Wine, Menu, content_cut


__plugin_meta__ = PluginMetadata(
    name="吃什么",
    description="一个「吃什么」的查询插件。",
    usage="发送「吃什么」即可使用。",
)


# 初始化菜单数据类
menu = Menu(
    foods_path=get_data_file("foods.yml"),
    drinks_path=get_data_file("drinks.yml"),
    wines_path=get_data_file("wines.yml"),
    history_path=get_data_file("menu_add_history.log")
)


on_what_food = on_regex(r"^(.*?)([吃喝])什么$", block=True)

@on_what_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃什么 / 喝什么"""

    match = re.search(r"^(.*?)([吃喝])什么$", str(event.get_message()))
    if not match: return

    pre_message = match.group(1)
    category = match.group(2)
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


on_this_food = on_regex(r"^([吃喝])这个\s+(.+)$", block=True)

@on_this_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃这个 xxx / 喝这个 xxx"""

    match = re.search(r"^([吃喝])这个\s+(.+)$", str(event.get_message()))
    if not match: return

    category = match.group(1)
    content = match.group(2)
    if category == "吃":
        food_list = [Food(name) for name in content_cut(content)]
    elif category == "喝":
        food_list = [Drink(name) for name in content_cut(content)]
    else: return

    new_food_list = menu.add_foods(food_list, event.user_id, getattr(event, "group_id", -1))

    if not new_food_list:
        await matcher.finish(f"这些餐点在小梨的菜单上已经都有了喔——")
    await matcher.finish(
        f"小梨已经把以下的餐点添加到{('食物' if category == '吃' else '饮品')}列表啦！\n{'；'.join([i.name for i in new_food_list])}")
