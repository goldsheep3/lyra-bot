import re
from random import choice
from typing import Set, Tuple, Literal, List, cast

from nonebot import logger, require, get_driver
from nonebot.plugin import on_regex, on_startswith, PluginMetadata
from nonebot.internal.matcher import Matcher

from nonebot.adapters.onebot.v11 import MessageEvent

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir

from .messages import MESSAGES, ALCOHOL_NOTICE, SPECIAL_NOTICE, NICKNAMES
from .utils import Eatable, Food, Drink, MenuManager, content_cut, EatableMenu

__plugin_meta__ = PluginMetadata(
    name="吃什么",
    description="一个「吃什么」的查询插件。",
    usage="发送「吃什么」即可使用。",
)

# 初始化菜单数据类
super_user_str: Set[str] = get_driver().config.superusers
super_user_int: Set[int] = set()
for sus in super_user_str:
    super_user_int.add(int(sus))
menu_manager = MenuManager(
    data_dir_path=get_plugin_data_dir(),
    cache_dir_path=get_plugin_cache_dir(),
    super_users=super_user_int,
    nb_logger=logger
)


def get_event_info(event: MessageEvent) -> Tuple[int, int]:
    """辅助函数：获取适配器事件信息"""
    user_id = getattr(event, "user_id", -1)
    group_id = getattr(event, "group_id", -1)
    return user_id, group_id


def item_show_id_text(item: Eatable) -> str:
    """辅助函数：返回格式化 id，如`[F1]`"""
    return f"[{str(item.category)[:1]}{item.num}]"


on_what_food = on_regex(r"^(.*?)([吃喝])什么$", block=True)


@on_what_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃什么 / 喝什么"""

    matched = matcher.state["_matched"]  # 返回`re.search()`匹配组结果

    content, category = matched.groups()
    user_id, _ = get_event_info(event)

    menu = menu_manager.get_menu(category)
    item = menu.choice(menu_manager.get_offset(user_id))

    # 内容替换规则
    if any(i in content for i in NICKNAMES):
        await matcher.finish(SPECIAL_NOTICE)
    content = content.replace("你", "他")
    content = content.replace("我", "你")
    message = choice(MESSAGES).format(item.name, content)
    if item.is_wine:
        message += "\n" + ALCOHOL_NOTICE
    await matcher.finish(message)


on_this_food = on_regex(r"^(吃|喝)这个\s+([^有没\s]+.*?)(?:\s+(有酒|没有酒))?$", priority=5, block=True)


@on_this_food.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 吃这个 xxx 有酒/ 喝这个 xxx 没有酒"""
    user_id, group_id = get_event_info(event)
    matched = matcher.state["_matched"]
    category, content, wine = matched.groups()
    menu = menu_manager.get_menu(category)
    is_wine = False
    if wine and len(wine) < 3:
        is_wine = True

    item_names = content_cut(content)

    new_items: List[Eatable] = list()
    exist_items: List[Eatable] = list()

    # 预检查
    for item_name in item_names:
        try:
            int(item_name)
            await matcher.finish("真的有纯数字的餐点吗（\n使用餐点ID或纯数字餐点名称会导致问题，不可以这么做哦")
            return
        except (ValueError, TypeError):
            pass

    for item_name in item_names:
        # 查找对应的食物或饮品，如果不存在则直接添加，否则修改酒精属性
        item_id = menu.get_item_id_by_name(item_name)
        if item_id >= 0:
            # 存在
            item = menu.get_item(item_id)
            if item.is_wine == is_wine:
                continue  # 不需要改
            # 进行调整
            menu.set_is_wine(item_id, is_wine, user_id, group_id)
            exist_items.append(item)
        else:
            new_item = menu.cls(
                name=item_name,
                adder=user_id,
                score=menu.score,
                is_wine=is_wine
            )
            menu.add_item(new_item, group_id)
            item = menu.get_item_by_name(item_name)
            new_items.append(item)
    msg: List[str] = list()
    if new_items:
        msg.append(f"小梨已经把以下{"含有" if is_wine else "不含"}酒精的餐点添加到餐点列表咯！\n"
                   f"{'；'.join([f"{item_show_id_text(item)}{item.name}" for item in new_items])}")
    if exist_items:
        msg.append(f"小梨已经把以下的餐点标记为{"含有" if is_wine else "不含"}酒精咯！\n"
                   f"{'；'.join([f"{item_show_id_text(item)}{item.name}" for item in exist_items])}")
    if len(msg) <= 0:
        await matcher.finish("这些餐点在小梨的菜单上已经都有了喔——")
        return
    while len(msg) > 0:
        await matcher.send(msg[-1])
    return


on_score = on_regex(r"^好([吃喝])吗\s+(.+?)(?:\s+(-?\d+))?$", priority=3, block=True)


@on_score.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """统一处理：没有分数则查询；有分数则评分（支持 id 或 名称）"""
    user_id, group_id = get_event_info(event)
    matched = matcher.state["_matched"]
    category, item_key_str, score_str = matched.groups()
    menu = menu_manager.get_menu(category)

    key = item_key_str.strip()

    # 先尝试把 key 转为 int 来判断是 id 还是名称
    try:
        item_id = int(key)
        item = menu.get_item(item_id)
    except (ValueError, KeyError):
        # 不是整数或通过 id 未找到，就按名称查找
        item = menu.get_item_by_name(key)
    if item is None:
        await matcher.finish(f"小梨没在菜单找到这个餐点诶qwq")

    # 如果没有附带分数，走查询分数路径
    if score_str is None:
        await matcher.finish(f"据小梨的菜单数据，{item_show_id_text(item)}{item.name} 现在是 {item.get_score():.2f} 分喔！")
        return

    # 有分数，走评分路径
    score = int(score_str)
    if user_id in super_user_int:
        # superuser 可以提交任意整数分
        r = menu.set_score_from_super_user({item.num: score}, user_id, group_id)
        if r // 1 == 1:
            await matcher.finish(
                f"小梨已经收到 Superuser Score 数据 ({user_id} -> {score})！\n"
                f"Score: {item_show_id_text(item)}{item.name} -> {item.get_score():.2f}"
            )
        else:
            await matcher.finish("Superuser Score 提交失败。")
    else:
        # 普通用户评分限制为 1~5
        if 0 < score < 6:
            menu.set_score(item.num, cast(Literal[1, 2, 3, 4, 5], score), user_id, group_id)
            await matcher.finish(
                f"已经记录评分！你当前为 {item_show_id_text(item)}{item.name} 给出了{score}分的分数。"
                f"目前评分均值在{item.get_score():.2f}"
            )
        else:
            await matcher.finish("评分只能用1~5的整数评分哦~")


on_score_filter = on_regex(r"^可以吃\s+(.+)$", priority=1, block=True)


@on_score_filter.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """处理命令: 可以吃 xxx"""
    user_id, group_id = get_event_info(event)
    matched = matcher.state["_matched"]
    level = matched.group(1)

    level_map = {
        "好": 3.8,
        "能吃": 3.1,
        "都行": 2.2,
        "正常": 2.2,
        "好玩": -3.2,
        "猎奇": -2.2
    }

    offset = level_map.get(level, None)
    offset = offset if offset else level_map.get(level[:-1], None)
    if offset is None:
        await matcher.finish("小梨不确定你的接受范围喔！可以使用以下五种范围指标（默认为「都行的」）：\n好的；能吃的；都行的；好玩的；猎奇的")
        return
    menu_manager.set_offset(user_id, offset, group_id)
    await matcher.finish(
        f"小梨已经记录你的「吃什么」可接受范围！在该范围下，抽选结果评分一定{"大" if offset >= 0 else "小"}于{abs(offset):.1f}分喔。")


on_score_rank = on_regex(r"^([吃喝])什么排行榜\s*(\d*)$", priority=10, block=True)


@on_score_rank.handle()
async def _(matcher: Matcher):
    """处理命令: 吃什么排行榜 / 喝什么排行榜2"""
    return  # 暂时不可用
    matched = matcher.state["_matched"]
    category, page = matched.groups()
    menu = menu_manager.get_menu(category)
    page = int(page) if page else 1

    rank_list: List[Tuple[Eatable, float]] = menu.item_avg_pairs[10 * (page - 1):10 * page]
    max_rank_len = len(str(page * 10))
    rank_msg_list = [
        f"{i + (page - 1) * 10 + 1:>{max_rank_len}} "        # 0001_
        f"[{str(item.category)[:1]}{item.num}] {item.name}"  # [F42]_FoodName
        f"{''*4}(Score: {avg:02d})"                          # ____(Score:_3.75)
        for i, item, avg in enumerate(rank_list)
    ]

    await matcher.finish(f"小梨的「{category}什么」菜单评分排行榜！(第{page}页)\n{"\n".join(rank_msg_list)}\n\n")


on_superuser = on_regex(r"^suLyra\s+WhatFood(.*?)$")


@on_superuser.handle()
async def _(event: MessageEvent, matcher: Matcher):
    """Superuser 操作：批量获取未评分内容/统一评分"""
    user_id, group_id = get_event_info(event)
    if user_id not in super_user_int:
        return  # 非 superuser 不返回消息
    matched = matcher.state["_matched"]
    content = matched.group(1)

    content_list = content.split("\n")
    commands = content_list[0].split(" ")
    if commands[1] == "获取未评分项目":
        def get_no_score(m: EatableMenu, u: int):
            return m.get_items_if_no_score(u)

        if len(commands) >= 3:
            no_score_items_all = get_no_score(menu_manager.get_menu(commands[2]), user_id)
        else:
            # 获取所有类别未评分项目
            no_score_items_all = get_no_score(menu_manager.food, user_id) + \
                                 get_no_score(menu_manager.drink, user_id)

        if len(no_score_items_all) > 20:
            no_score_items = no_score_items_all[:20]
        elif len(no_score_items_all) < 1:
            await matcher.finish("[Superuser] 目前没有需要评分的项目。")
            return
        else:
            no_score_items = no_score_items_all
        await matcher.finish(
            f"[Superuser] 待评分项目 ({len(no_score_items)}/{len(no_score_items_all)})\n" +
            '\n'.join([f"{item_show_id_text(item)} {item.name}" for item in no_score_items]))
    elif commands[1] == "批量评分":
        score_infos = [re.match(r"([DF])\s*(\d+)\s*(-?\d+)", text).groups() for text in content_list[1:]]  # 除首行外的数据
        result_food = menu_manager.food.set_score_from_super_user(
            {i: s for i, s in [(int(item[1]), int(item[2])) for item in score_infos if item[0] == "F"]},
            user_id, group_id)
        result_drink = menu_manager.drink.set_score_from_super_user(
            {i: s for i, s in [(int(item[1]), int(item[2])) for item in score_infos if item[0] == "D"]},
            user_id, group_id)
        result = result_food + result_drink
        await matcher.finish(f"[Superuser] 成功评分率:{result*100:.4f}%。检查日志以获取详细信息。")
    elif commands[1] in ["禁用", "恢复"]:
        if len(commands) < 3:
            await matcher.finish("[Superuser] 缺少FullID参数。")
            return
        category, item_id = re.match(r"([DF])(\d+)", commands[2]).groups()
        if not all([category, item_id]):
            await matcher.finish("[Superuser] 不正确的FullID参数。")
            return
        menu = menu_manager.get_menu(category)
        menu.set_enabled(item_id, False if commands[1] == "禁用" else True, user_id)
        await matcher.finish(f"[Superuser] 已{commands[1]} {category}{item_id} 。")
    else:
        await matcher.finish("""[Superuser] 当前可用命令：
- 获取未评分项目 (<类别>)
- 批量评分  // 后续多行输入评分数据<类别><ID><分数>
- 删除 <FullID>
- 恢复 <FullID>""")
