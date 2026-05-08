# ==============================================================
# what_food
# 支持「吃什么」的抽选插件
# ==============================================================

import random
import time
from datetime import datetime
from pydantic import BaseModel

from nonebot import logger, get_plugin_config, require, on_regex
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent

from . import services, ai_service

try:
    from nonebot import get_driver
    driver = get_driver()
except ValueError:
    pass
else:
    # 依赖数据库
    require("nonebot_plugin_datastore")
    
    class Config(BaseModel):
        # 默认为千问轻量模型
        WHAT_FOOD_AI_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        WHAT_FOOD_AI_MODEL: str = "qwen3.5-flash-2026-02-23"
        WHAT_FOOD_AI_KEY: str | None = None

    __plugin_meta__ = PluginMetadata(
        name="what-food",
        description="一个支持「吃什么」的抽选插件。",
        usage="",
        config=Config,
    )

    AI_URL = get_plugin_config(Config).WHAT_FOOD_AI_URL
    AI_MODEL = get_plugin_config(Config).WHAT_FOOD_AI_MODEL
    AI_KEY = get_plugin_config(Config).WHAT_FOOD_AI_KEY

    AI_ENABLED = all([AI_URL, AI_MODEL, AI_KEY])

    if AI_ENABLED:
        ai_service.API_URL = AI_URL
        ai_service.API_MODEL = AI_MODEL
        ai_service.API_KEY = AI_KEY

LYRA_NICKNAMES = ("小梨", "Lyra", "莱茵", "Lyrandra", "小莱")

# --- 发言字典 ---

REPLY_DICT: dict[str, str | list[str]] = {
    # 吃什么
    'csm_no_items': "没有符合你当前「爱好」的餐点TT",
    'csm_success': [
        "小梨建议{user}试试{food}哦！",
        "小梨觉得{user}可以试试{food}哦！",
        "{user}来试试{food}！记得告诉小梨感想哦w",
        "莉莉丝阿姐昨天点的是{food}诶，{user}可以尝一下（",
    ],
    # 吃什么 / 设置偏好
    'kyc_success': "小梨已经记录了你的偏好啦！接下来你只会抽选出 {tip} 的餐点了哦！",
    'kuc_not_understand': "小梨不太理解你的偏好哦！可以直接输入数字，或者使用【好吃的、能吃的、都行的、正常的、好玩的、猎奇的】来表达偏好哦！",
    # 吃这个
    'czg_loading': "小梨准备将 {food} 写入菜单咯。",
    'czg_existing': "餐点 {food} 已经被写入菜单了喔。",
    'czg_success': "小梨已经将 {food} 写入菜单啦！",
    # 好吃吗
    'hcm_no_item': "菜单里没有找到 {food} 呀。",
    'hcm_score': "{food} 的平均分是 {current_score} 分哦！",
    'hcm_set_score': "小梨已经记录了 {user} 给 {food} 的 {score} 分评价啦！\n当前的分数为 {current_score} 。",
    'hcm_wrong_score': "评分应该是 1-5 的整数哦！",
    # 特殊提示
    'alcohol_warning': "未成年请勿饮酒，成年人也要适量饮酒喔！",
    'csm_to_lyra': "不用给小梨推荐啦！小梨的餐点都是莉莉丝阿姐一手包办的~",
    # ban相关
    'user_banned': "你被管理员暂停了菜单权限ww\n解禁时间是 {time}",
    'user_banned_with_reason': "你因为 {reason} 被管理员暂停了菜单权限ww\n解禁时间是 {time}",
}


# --- tool function ---

def get_reply(key: str, **kwargs) -> str:
    """获取回复文本"""
    template: str | list[str] = REPLY_DICT.get(key, "")
    if isinstance(template, list):
        template = random.choice(template)
    return template.format(**kwargs)

def format_unban_time(end_time: int) -> str:
    """格式化解禁时间为可读字符串"""
    current_time = int(time.time())
    remaining_seconds = end_time - current_time
    
    if remaining_seconds <= 0:
        return "已过期"
    
    # 计算剩余时间
    minutes = remaining_seconds // 60
    hours = minutes // 60
    days = hours // 24
    
    if days > 0:
        hours_remainder = hours % 24
        if hours_remainder > 0:
            time_str = f"{days}天{hours_remainder}小时"
        else:
            time_str = f"{days}天"
    elif hours > 0:
        minutes_remainder = minutes % 60
        if minutes_remainder > 0:
            time_str = f"{hours}小时{minutes_remainder}分钟"
        else:
            time_str = f"{hours}小时"
    else:
        time_str = f"{minutes}分钟"
    
    # 获取解禁的具体时间
    unban_dt = datetime.fromtimestamp(end_time)
    unban_time = unban_dt.strftime("%Y-%m-%d %H:%M:%S")
    
    return f"{time_str}后（{unban_time}）"

def pronoun_switch(text: str) -> str:
    """用户代词转换"""
    return text.replace("你", "他").replace("我", "你")

async def check_user_banned(event: MessageEvent, matcher: Matcher) -> bool:
    """检查用户是否被禁用，如果被禁用则直接返回禁用提示并返回True，否则返回False"""
    user_id = int(event.get_user_id())
    group_id = int(getattr(event, 'group_id', 0))
    
    is_banned, reason, end_time = await services.is_user_banned(user_id, group_id)
    if is_banned and end_time is not None:
        unban_time = format_unban_time(end_time)
        if reason:
            await matcher.finish(get_reply('user_banned_with_reason', reason=reason, time=unban_time))
        else:
            await matcher.finish(get_reply('user_banned', time=unban_time))
        return True
    
    return False


# ------ matcher ------

csm = on_regex(r"^(.*?)([吃喝])什么$", priority=5, block=True)
czg = on_regex(r"^([吃喝])这个\s*(.+?)$", priority=5, block=True)
hcm = on_regex(r"^好([吃喝])吗\s+(.+?)(?:\s+(-?\d+))?$", priority=5, block=True)
kyc = on_regex(r"^([吃喝])什么\s+(.*)$", priority=5, block=True)
phb = on_regex(r"^([吃喝])什么排行榜\s*(?:\s+(-?\d+))?$", priority=5, block=True)
admin = on_regex(r"^(sudo\s+(WhatFood|what_food|whatfood))\s+(.+)$", permission=SUPERUSER, rule=to_me(), priority=1)


# ------ functions ------

@csm.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理「吃什么」"""
    if await check_user_banned(event, matcher):
        return
    
    user_id = int(event.get_user_id())
    
    user_input, action = groups
    category = 'Food' if action == '吃' else 'Drink'

    preference_offset = await services.get_user_preference(user_id)

    item = await services.choice_item(category=category, offset=preference_offset)
    if not item:
        await matcher.finish(get_reply('csm_no_items'))
        return

    await matcher.finish(get_reply('csm_success', user=pronoun_switch(user_input), food=item.name))


@czg.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理「吃这个」"""
    if await check_user_banned(event, matcher):
        return
    
    user_id = int(event.get_user_id())
    
    action, food = groups
    category = 'Food' if action == '吃' else 'Drink'

    existing = await services.get_item_by_name(food, category)
    if existing:
       # 已存在该餐点
        await matcher.finish(get_reply('czg_existing', food=food))
        return

    await matcher.send(get_reply('czg_loading', food=food))

    ai_info = await ai_service.get_ai_service().analyze_food(food)
    alcohol = ai_info.get("contains_alcohol", False)

    await services.add_item(food, category, user_id, alcohol,
                            ai_score=ai_info.get("score", None), ai_reason=ai_info.get("reason", None))

    await matcher.finish(get_reply('czg_success', food=food) + (get_reply('alcohol_warning') if alcohol else ""))


@hcm.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理「好吃吗」"""
    if await check_user_banned(event, matcher):
        return
    
    user_id = int(event.get_user_id())
    
    action, food, score = groups
    category = 'Food' if action == '吃' else 'Drink'

    item = await services.get_item_by_name(food, category)
    if not item:
        await matcher.finish(get_reply('hcm_no_item', food=food))

    if not score:
        # 查询逻辑
        await matcher.finish(get_reply('hcm_score', food=food, current_score=item.current_score))
    else:
        # 评分逻辑
        try:
            score = int(score)
            if score < 1 or score > 5:
                raise ValueError
        except ValueError:
            await matcher.finish(get_reply('hcm_wrong_score'))
        current_score = await services.set_score(item.id, user_id, score)
        await matcher.finish(get_reply('hcm_set_score', food=food, score=score, current_score=current_score))


@kyc.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理「吃什么 好吃的」，设置 offset 倾向"""
    if await check_user_banned(event, matcher):
        return
    
    user_id = int(event.get_user_id())
    
    _, user_input = groups

    try:
        offset = float(user_input)
    except ValueError:
        offset = None

    if offset is None:
        level_map = {
            "好吃的": 3.8,
            "能吃的": 3.1,
            "都行的": 2.2,
            "正常的": 2.2,
            "好玩的": -3.2,
            "猎奇的": -2.2
        }
        # 解析文本偏好
        offset = level_map.get(user_input.strip(), None)

    if offset is None:
        # 借助 AI 解析偏好
        offset = await ai_service.get_ai_service().parse_user_preference(user_input)

    if offset is not None:
        tip = f"{'大于' if offset > 0 else '小于'}{offset}"
        await services.set_user_preference(user_id, offset)
        await matcher.finish(get_reply('kyc_success', tip=tip))
    else:
        await matcher.finish(get_reply('kuc_not_understand'))


@phb.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理「吃什么排行榜」，展示排行榜"""

    action, page = groups
    category = 'Food' if action == '吃' else 'Drink'
    page = int(page) if page else 1

    await matcher.finish("排行榜功能重构进行中！")
    return


@admin.handle()
async def _(event: MessageEvent, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理管理员命令"""
    _, _, command = groups
    
    cmd_parts = command.split()
    if not cmd_parts:
        return
    
    action = cmd_parts[0]

    # sudo whatfood enabled {itemname}  # 启用餐点
    if action == "enabled":
        if len(cmd_parts) < 2:
            await matcher.finish("用法：sudo whatfood enabled {itemname}")
        itemname = " ".join(cmd_parts[1:])
        item = await services.get_item_by_name(itemname, 'Food') or await services.get_item_by_name(itemname, 'Drink')
        if not item:
            await matcher.finish(f"找不到餐点 {itemname} 呀。")
        await services.set_item_enabled(item.id, True)
        await matcher.finish(f"已启用餐点 {itemname}。")
        return

    # sudo whatfood disabled {itemname}  # 禁用餐点
    elif action == "disabled":
        if len(cmd_parts) < 2:
            await matcher.finish("用法：sudo whatfood disabled {itemname}")
        itemname = " ".join(cmd_parts[1:])
        item = await services.get_item_by_name(itemname, 'Food') or await services.get_item_by_name(itemname, 'Drink')
        if not item:
            await matcher.finish(f"找不到餐点 {itemname} 呀。")
        await services.set_item_enabled(item.id, False)
        await matcher.finish(f"已禁用餐点 {itemname}。")
        return

    # sudo whatfood setscore {itemname} {score} [reason]  # 设置餐点的高权重管理员评分
    elif action == "setscore":
        if len(cmd_parts) < 3:
            await matcher.finish("用法：sudo whatfood setscore {itemname} {score} [reason]")
        
        itemname = cmd_parts[1]
        try:
            score = int(cmd_parts[2])
        except ValueError:
            await matcher.finish("评分应该是整数哦！")
            return
        
        reason = " ".join(cmd_parts[3:]) if len(cmd_parts) > 3 else None
        
        item = await services.get_item_by_name(itemname, 'Food') or await services.get_item_by_name(itemname, 'Drink')
        if not item:
            await matcher.finish(f"找不到餐点 {itemname} 呀。")
            return
        
        new_score = await services.set_admin_score(item.id, score, reason)
        await matcher.finish(f"已为 {itemname} 设置管理员评分 {score} 分。\n当前的分数为 {new_score}。")
        return

    # sudo whatfood ban {userid} {time(d/h/m/s)} [reason]  # 禁止用户使用插件一段时间（支持小数，单位：d/h/m/s）
    elif action == "ban":
        group_id = int(getattr(event, 'group_id', 0))
        
        if len(cmd_parts) < 3:
            await matcher.finish("用法：sudo whatfood ban {userid} {time} [reason]\n时间格式：1.5d(天) 2h(小时) 30m(分钟) 60s(秒)，支持小数")
        
        try:
            user_id = int(cmd_parts[1])
        except ValueError:
            await matcher.finish("用户ID应该是整数哦！")
            return
        
        # 解析时间输入，支持单位 d(天) h(小时) m(分钟) s(秒)
        time_input = cmd_parts[2]
        if time_input[-1].lower() in ['d', 'h', 'm', 's']:
            unit = time_input[-1].lower()
            value_str = time_input[:-1]
        else:
            # 默认单位为秒
            unit = 's'
            value_str = time_input
        
        try:
            value = float(value_str)
        except ValueError:
            await matcher.finish("禁用时长格式错误！请输入数字，可选单位：d(天) h(小时) m(分钟) s(秒)")
            return
        
        # 转换为秒数
        if unit == 'd':
            ban_seconds = int(value * 86400)  # 1天 = 86400秒
        elif unit == 'h':
            ban_seconds = int(value * 3600)   # 1小时 = 3600秒
        elif unit == 'm':
            ban_seconds = int(value * 60)     # 1分钟 = 60秒
        else:  # 's'
            ban_seconds = int(value)
        
        if ban_seconds <= 0:
            await matcher.finish("禁用时长应该是正数哦！")
            return
        
        reason = " ".join(cmd_parts[3:]) if len(cmd_parts) > 3 else None
        
        await services.ban_user(user_id, group_id, ban_seconds, reason)
        
        # 计算可读的时间字符串（约分到分钟为最小单位）
        minutes = ban_seconds // 60
        hours = minutes // 60
        days = hours // 24
        
        if days > 0:
            time_str = f"{days}天" if hours % 24 == 0 else f"{days}天{hours % 24}小时"
        elif hours > 0:
            time_str = f"{hours}小时" if minutes % 60 == 0 else f"{hours}小时{minutes % 60}分钟"
        else:
            time_str = f"{minutes}分钟"
        
        await matcher.finish(f"已禁用用户 {user_id} {time_str}。\n原因：{reason or '未填写'}")
        return

    # sudo whatfood unban {userid}  # 解除用户禁令
    elif action == "unban":
        group_id = int(getattr(event, 'group_id', 0))
        
        if len(cmd_parts) < 2:
            await matcher.finish("用法：sudo whatfood unban {userid}")
        
        try:
            user_id = int(cmd_parts[1])
        except ValueError:
            await matcher.finish("用户ID应该是整数哦！")
            return
        
        success = await services.unban_user(user_id, group_id)
        
        if success:
            await matcher.finish(f"已解除用户 {user_id} 的禁令。")
        else:
            await matcher.finish(f"用户 {user_id} 没有禁用记录呀。")
        return

    # sudo whatfood init  # 将初始菜品填入数据库
    elif action == "init":
        await matcher.finish("暂时还不支持 init 指令喵（）请等待从旧版本将默认菜单迁移过来qwq")

    # sudo whatfood update  # 从 JSON/NPZ 文件更新数据
    elif action == "update":
        require("nonebot_plugin_localstore")
        from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir
        from .json_update import full_migrate_old_data
        food_json_path = get_plugin_data_dir() / "Food.json"
        drink_json_path = get_plugin_data_dir() / "Drink.json"
        food_score_path = get_plugin_cache_dir() / "food_scores.npz"
        drink_score_path = get_plugin_cache_dir() / "drink_scores.npz"
        user_offset_json_path = get_plugin_data_dir() / "user_offset.json"
        if not any([food_json_path.exists(), drink_json_path.exists(), food_score_path.exists(), drink_score_path.exists()]):
            await matcher.finish("未找到旧数据文件，无法执行更新操作。")
        await full_migrate_old_data(
            food_json_path=food_json_path,
            drink_json_path=drink_json_path,
            food_npz_path=food_score_path,
            drink_npz_path=drink_score_path,
            user_offset_json_path=user_offset_json_path
        )
        await matcher.finish("数据更新完成！旧数据已迁移到数据库，并已随机打乱ID。")
        return

    return
