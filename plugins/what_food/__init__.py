import re
from typing import Tuple

import yaml
from random import choice

from nonebot import require
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.internal.matcher import Matcher

from nonebot.adapters.onebot.v11 import MessageEvent

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file

from .messages import MESSAGES, ALCOHOL_NOTICE, SPECIAL_NOTICE, NICKNAMES
from .menu import FOODS, DRINKS, WINES


__plugin_meta__ = PluginMetadata(
    name="吃什么",
    description="一个「吃什么」的查询插件。",
    usage="发送「吃什么」即可使用。",
)


class Food:
    is_wine: bool = False
    def __init__(self, name: str):
        self.name = name

class Drink(Food):
    pass

class Wine(Food):
    is_wine: bool = True


# 初始化
def init_food_data(fpath, dpath, wpath) -> Tuple[list[Food], list[Drink]]:
    def _init_list(p, d, cls):
        if not p.exists():
            with open(p, "w", encoding="utf-8") as file:
                yaml.dump(d, file)
        with open(fpath, "r", encoding="utf-8") as file:
            l = [cls(n) for n in yaml.safe_load(file)]
        return l

    foods: list[Food] = _init_list(fpath, FOODS, Food)
    drinks: list[Drink] = _init_list(dpath, DRINKS, Drink)
    wines: list[Wine] = _init_list(wpath, WINES, Wine)
    drinks += wines  # 酒类加入饮品列表
    return foods, drinks

history_path = get_data_file("menu_add_history.log")
food_path = get_data_file("foods.yml")
drink_path = get_data_file("drinks.yml")
wine_path = get_data_file("wines.yml")
food_list, drink_list = init_food_data(food_path, drink_path, wine_path)


on_what_food = on_regex(r"^(.*?)([吃喝])什么$", block=True)

@on_what_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃什么 / 喝什么"""

    match = re.search(r"^(.*?)([吃喝])什么$", str(event.get_message()))
    if not match: return

    pre_message = match.group(1)
    category = match.group(2)

    food = choice({"吃": food_list, "喝": drink_list}.get(category, ()))
    wine = food.is_wine

    # 内容替换规则
    to_lyra: bool = any(i in pre_message for i in NICKNAMES)
    pre_message = pre_message.replace("你", "他")
    pre_message = pre_message.replace("我", "你")

    message = choice(MESSAGES).format(food, pre_message)
    if wine:
        message += "\n" + ALCOHOL_NOTICE
    if to_lyra:
        message = SPECIAL_NOTICE

    await matcher.finish(message)


on_this_food = on_regex(r"^([吃喝])这个\s+(.+)$", block=True)

@on_this_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃这个 xxx / 喝这个 xxx"""

    match = re.search(r"^([吃喝])这个\s+(.+)$", str(event.get_message()))
    if not match: return

    category = match.group(1)
    foods = match.group(2)
    foods = (foods
             .replace(",", " ")
             .replace(".", " ")
             .replace(";", " ")
             .replace("，", " ")
             .replace("。", " ")
             .replace("；", " "))

    new_food_list = [f for f in foods.split(" ") if f]
    path = food_path if category == "吃" else drink_path

    # 读取旧数据，合并新数据，写回文件
    with open(path, "r", encoding="utf-8") as file:
        old_food_list = yaml.safe_load(file) or []
    newest_food_list = old_food_list + new_food_list
    with open(path, "w", encoding="utf-8") as file:
        yaml.dump(newest_food_list, file)

    # 刷新内存数据
    global food_list, drink_list
    food_list, drink_list = init_food_data(food_path, drink_path, wine_path)

    # 记录日志
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_category = "Food" if category == "吃" else "Drink"
    with open(history_path, "a", encoding="utf-8") as file:
        for nf in new_food_list:
            # [2004-06-01 12:00:00] 2940119626 Add a Food: "FOOD" (from group: 987654321)
            file.write(f"[{now}] {event.user_id} Add a {log_category}: \"{nf}\" (from group: {event.group_id})\n")

    await matcher.finish(
        f"小梨已经把以下的餐点添加到{('食物' if category == '吃' else '饮品')}列表啦！\n{'；'.join(new_food_list)}。")
