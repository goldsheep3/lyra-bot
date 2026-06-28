import time
import random
from pathlib import Path
from typing import Optional, Any, Literal

from . import services
from .models import User, RelationType

from nonebot import logger, on_regex, on_message
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot.permission import SUPERUSER
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Bot as OneBotV11Bot,
                                         Event as OneBotV11Event,
                                         Message as OneBotV11Message,
                                         MessageSegment as OneBotV11MessageSegment,
                                         MessageEvent as OneBotV11MessageEvent,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,)
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

from nonebot_plugin_localstore import get_plugin_data_dir
from plugins.nonebot_plugin_i18n import use_i18n, reply

# 暂不考虑支持 Telegram：TG Bot 无法直接获取 Telegram 群成员列表，而且不确定 ADMIN / OWNER 等权限的排布


# --- config variables ---

MAX_SWAP_COUNT = 3  # 每个用户每天换老婆的最大次数
HOPE_SUCCESS_RATE = 0.5  # 心愿单成功率，0.5 表示 50% 的概率抽中心愿单
ACTIVE_DAYS = 7  # 活跃成员的时间阈值，单位为天，表示在过去多少天内发过言的成员才算活跃


# --- i18n settings ---

i18n_dir = Path(__file__).parent / "assets" / "i18n"
i18n = use_i18n(i18n_dir)

# --- tool functions ---

async def build_msg(matcher: Matcher, event: Event, msg_segments: str | list[tuple[str, Any]], tag: Literal['send', 'finish'] = 'send') -> None:
    """根据事件类型构建并发送消息对象"""

    # 转化: 便于单字符串消息简化外部调用
    if isinstance(msg_segments, str):
        msg_segments = [("text", msg_segments)]
    
    if isinstance(event, OneBotV11Event):
        onebotv11_msg = OneBotV11Message()
        
        for type_, content in msg_segments:
            if type_ == "text":
                # content: str
                onebotv11_msg += OneBotV11MessageSegment.text(content)
            elif type_ == "image":
                # content: bytes
                onebotv11_msg += OneBotV11MessageSegment.image(content)
            elif type_ == "at":
                # content: tuple[str | None, str]  # (username, user_id)
                uid: str = content[1]
                onebotv11_msg += OneBotV11MessageSegment.at(uid) + ' '
            else:
                continue
                
        if not onebotv11_msg:
            return
        func = matcher.send if tag == 'send' else matcher.finish
        await func(onebotv11_msg)


def get_platform_and_user_id(event: Event) -> tuple[str, int]:
    """获取事件所属平台名称和用户ID"""
    platform = "unknown"
    user_id = -1

    if isinstance(event, OneBotV11Event):
        platform = "onebot-v11"
        user_id = int(event.get_user_id())

    return platform, user_id

def get_group_id(event: Event) -> Optional[int]:
    """获取事件所属群组ID"""
    if isinstance(event, OneBotV11GroupMessageEvent):
        return int(event.group_id)
    return None

def is_group_message(event: Event) -> bool:
    """判断事件是否为群消息"""
    return isinstance(event, OneBotV11GroupMessageEvent) and hasattr(event, 'group_id')

def is_private_message(event: Event) -> bool:
    """判断事件是否为私聊消息"""
    return isinstance(event, OneBotV11PrivateMessageEvent) and hasattr(event, 'user_id')


async def get_active_pool(bot: OneBotV11Bot, group_id: int) -> list[int]:
    """
    根据最后发言时间筛选活跃的群成员 ID 列表
    """
    try:
        member_list = await bot.get_group_member_list(group_id=group_id)
    except Exception as e:
        logger.error(f"拉取群成员失败: {e}")
        return []
        
    now = int(time.time())
    active_threshold = now - (ACTIVE_DAYS * 86400)
    
    # 活跃成员数据过滤
    active_members: list[dict] = []
    
    for member_info in member_list:
        if member_info.get("last_sent_time", 0) >= active_threshold:
            member_id = member_info["user_id"]
            is_bot = bool(member_info.get("is_bot")) or str(member_id) == str(bot.self_id)
            active_members.append({"user_id": member_id, "is_bot": is_bot})
            
    # 调用刚刚写好的批量接口，有且仅有 1 次数据库会话交互
    if active_members:
        await services.get_users_bulk(platform="onebot-v11", users_data=active_members)
        
    return [member["user_id"] for member in active_members]

async def get_user_display_name(bot: Bot, group_id: int, user_id: int) -> str:
    """获取用户的显示名称"""
    try:
        info = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
        if info.get("card"):
            return info["card"]
        elif info.get("nickname"):
            return info["nickname"]
    except Exception as e:
        logger.warning(f"获取群员信息失败: {e}")
    # 兜底
    return str(user_id)

def get_user_avatar_url(user_id: int) -> str:
    """获取用户的头像 URL"""
    return f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"


# --- rules and permissions ---

rule_only_group = Rule(is_group_message)
rule_only_private = Rule(is_private_message)

permission_sudo = GROUP_ADMIN | GROUP_OWNER | SUPERUSER


# --- matcher ---

jrlp = on_regex(r"^(今日老婆|jrlp)$", priority=5, block=True, rule=rule_only_group)
hlp = on_regex(r"^(换老婆|hlp)$", priority=5, block=True, rule=rule_only_group)
lh = on_regex(r"^(离婚|lh)$", priority=5, block=True, rule=rule_only_group)
qq = on_regex(r"^强娶", priority=5, block=True, rule=rule_only_group)
qq_private = on_regex(r"^强娶", priority=2, block=False, rule=rule_only_private)  # private 操作要比群的优先检查

jrlg = on_regex(r"^(今日老公|jrlg)$", priority=5, block=True, rule=rule_only_group)
hlg = on_regex(r"^(换老公|hlg)$", priority=5, block=True, rule=rule_only_group)
toggle_status = on_regex(r"^(不当老婆|当老婆|不娶bot|娶bot|我是bot|我不是bot)$", priority=5, block=True)

sudo = on_regex(r"^sudo\s+(jrlp|DailyPartner|daily_partner|今日老婆)\s+(.*)$", priority=1, block=True,
                permission=permission_sudo)  # sudo 权限命令


# =================================
# 业务逻辑
# =================================

def partner_gacha(targets: dict[int, User], hope_id: Optional[int] = None) -> Optional[User]:
    """抽选逻辑"""
    if not targets:
        return None
    
    if hope_id is not None and hope_id in targets:
        if random.random() < HOPE_SUCCESS_RATE:
            return targets[hope_id]
    
    return random.choice(list(targets.values()))  # 随机抽选


@jrlp.handle()
async def jrlp_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    """处理指令: jrlp"""
    # 将依赖注入返回的语言包数据注入当前协程上下文，供 reply() 读取
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)

    platform, user_id = get_platform_and_user_id(event)

    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return

    result = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.WIFE)
    if result:
        if result.is_divorced:
            # 离婚惩罚状态
            segments = [("at", (None, user_id)), ("text", reply("jrlp.failed.discovered"))]
            await build_msg(matcher, event, segments, tag='finish')
            return
        elif result.target_id is None:
            # 非惩罚无老婆状态 (被 hlg 换掉)，允许再次抽选
            pass
        else:
            # 已有老婆逻辑
            target_username = await get_user_display_name(bot, group_id, result.target_id)
            segments = [("at", (None, user_id)),
                        ("text", reply("jrlp.failed.already", username=target_username)),
                        ("image", get_user_avatar_url(result.target_id))]
            await build_msg(matcher, event, segments, tag='finish')
            return

    # 抽选逻辑
    if isinstance(bot, OneBotV11Bot):
        active_member_ids = await get_active_pool(bot, group_id)
    else:
        segments = [("at", (None, user_id)), ("text", reply("not_allow_platform"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    targets = await services.get_available_targets(platform, group_id, active_member_ids, user, relation_type=RelationType.WIFE)
    result = partner_gacha(targets, hope_id=user.hope_id)
    if not result:
        # 没有可选对象逻辑，设置自己
        await services.set_today_partner(platform, group_id, user_id, user_id, relation_type=RelationType.WIFE)
        segments = [("at", (None, user_id)), ("text", reply("jrlp.success.self"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 然后设置关系
    await services.set_today_partner(platform, group_id, user_id, result.user_id, relation_type=RelationType.WIFE)
    
    target_username = await get_user_display_name(bot, group_id, result.user_id)
    segments = [("at", (None, user_id)),
                ("text", reply("jrlp.success.common", username=target_username)),
                ("image", get_user_avatar_url(result.user_id))]
    await build_msg(matcher, event, segments, tag='finish')
    return
    

@hlp.handle()
async def hlp_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    """处理指令: hlp"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return
    
    # 没有老婆逻辑 / 无记录
    record = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.WIFE)
    if record is None:
        segments = [("at", (None, user_id)), ("text", reply("hlp.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 惩罚状态逻辑
    if record.is_divorced:
        segments = [("at", (None, user_id)), ("text", reply("hlp.failed.discovered"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 没有老婆逻辑 / 有记录但无老婆
    if record.target_id is None:
        segments = [("at", (None, user_id)), ("text", reply("hlp.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 更换次数过多逻辑
    if record.swap_count >= MAX_SWAP_COUNT:
        # 超过换老婆次数上限，对标主动离婚
        await services.set_today_partner(platform, group_id, user_id, target_id=None, relation_type=RelationType.WIFE, is_divorced=True)
        segments = [("at", (None, user_id)), ("text", reply("hlp.failed.limit"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    
    # 抽选逻辑
    if isinstance(bot, OneBotV11Bot):
        active_member_ids = await get_active_pool(bot, group_id)
    else:
        segments = [("at", (None, user_id)), ("text", reply("not_allow_platform"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    targets = await services.get_available_targets(platform, group_id, active_member_ids, user, relation_type=RelationType.WIFE)
    # 防止抽到想换掉的前任
    if record.target_id:
        targets.pop(record.target_id, None)
    result = partner_gacha(targets, hope_id=user.hope_id)
    if not result:
        if record.target_id == user_id:
            # 没有可换余地，不作更换
            segments = [("at", (None, user_id)), ("text", reply("hlp.failed.not_wife"))]
            await build_msg(matcher, event, segments, tag='finish')
            return
        else:
            # 没有可选对象逻辑，设置自己
            await services.set_today_partner(platform, group_id, user_id, user_id, relation_type=RelationType.WIFE)
            reply_key = "hlp.success.self.common" if record.swap_count + 1 < MAX_SWAP_COUNT else "hlp.success.self.last"
            segments = [("at", (None, user_id)), ("text", reply(reply_key))]
            await build_msg(matcher, event, segments, tag='finish')
            return
    # 然后设置关系
    await services.set_today_partner(platform, group_id, user_id, result.user_id, relation_type=RelationType.WIFE)
    # 若更换次数即将达到上限，提醒用户
    target_username = await get_user_display_name(bot, group_id, result.user_id)
    reply_key = "hlp.success.common" if record.swap_count + 1 < MAX_SWAP_COUNT else "hlp.success.last"
    segments = [("at", (None, user_id)), ("text", reply(reply_key, username=target_username)),
                ("image", get_user_avatar_url(result.user_id))]
    await build_msg(matcher, event, segments, tag='finish')

@lh.handle()
async def lh_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    """处理指令: lh"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return
    
    # 没有老婆逻辑 / 无记录
    record = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.WIFE)
    if record is None:
        segments = [("at", (None, user_id)), ("text", reply("lh.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 惩罚状态逻辑
    if record.is_divorced:
        segments = [("at", (None, user_id)), ("text", reply("lh.failed.already"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 没有老婆逻辑 / 有记录但无老婆
    if record.target_id is None:
        segments = [("at", (None, user_id)), ("text", reply("lh.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    
    # 允许离婚，批准
    await services.set_today_partner(platform, group_id, user_id, target_id=None, relation_type=RelationType.WIFE, is_divorced=True)
    reply_key = "lh.success.self" if record.target_id == user_id else "lh.success.common"
    target_username = await get_user_display_name(bot, group_id, record.target_id)
    segments = [("at", (None, user_id)), ("text", reply(reply_key, username=target_username)),
                ("image", get_user_avatar_url(record.target_id))]
    await build_msg(matcher, event, segments, tag='finish')

@qq.handle()
async def qq_handled(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理指令: qq"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return
    
    result = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.WIFE)
    if result:
        if result.is_divorced:
            # 离婚惩罚状态
            segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.discovered"))]
            await build_msg(matcher, event, segments, tag='finish')
            return
        elif result.swap_count >= MAX_SWAP_COUNT:
            # 超过换老婆次数上限，驳回请求
            segments = [("at", (None, user_id)), ("text", reply("hlp.failed.limit"))]
            await build_msg(matcher, event, segments, tag='finish')
            return

    # 获取强娶目标
    goal_user_id = None
    # 从 at 获取
    if hasattr(event, "get_message"):
        for segment in event.get_message():
            if segment.type == "at":
                goal_user_id = int(segment.data.get("qq", 0))
                break            
    # 从 regex 获取
    if goal_user_id is None and groups and groups[0]:
        if groups[0].isdigit():
            goal_user_id = int(groups[0])
    # [NO_LYRA] 如果目标是 bot 自身，特殊结束语驳回请求
    if getattr(event, 'to_me', False) or str(goal_user_id) == str(bot.self_id):
        segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.with_lyra"))]
        await build_msg(matcher, event, segments, tag='finish')
        return

    # 未获取到强娶目标，驳回请求
    if goal_user_id is None:
        segments = [("at", (None, user_id)), ("text", reply("qq.group.usage"))]
        await build_msg(matcher, event, segments, tag='finish')
        return

    # 被强娶对象不在群里，驳回请求
    if isinstance(bot, OneBotV11Bot):
        try:
            await bot.get_group_member_info(group_id=group_id, user_id=goal_user_id)
        except Exception:
            # 如果不在群里或 API 失败，会抛出异常
            segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.not_in_group"))]
            await build_msg(matcher, event, segments, tag='finish')
            return
    else:
        segments = [("at", (None, user_id)), ("text", reply("not_allow_platform"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 被强娶对象未开启功能，驳回请求
    target_user = await services.get_user(platform, goal_user_id)
    if target_user.is_enabled is False:
        segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.disabled"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    
    # 权限确定：如果被强娶对象已经有老婆，且强娶者不是超级用户或群管理员，则驳回请求
    target_record = await services.get_today_partner(platform, group_id, goal_user_id, relation_type=RelationType.WIFE)
    ntr = False
    if target_record and target_record.target_id is not None:
        if not (await permission_sudo(bot, event)):
            segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.married"))]
            await build_msg(matcher, event, segments, tag='finish')
            return
        else:
            ntr = True  # 权限狗 NTR 启动！
    
    # 执行强娶
    record = await services.set_today_partner(platform, group_id, user_id, target_id=goal_user_id, relation_type=RelationType.WIFE)

    if record.target_id == user_id:
        # 水仙
        segments = [("at", (None, user_id)), ("text", reply("qq.group.success.self")),
                    ("image", get_user_avatar_url(goal_user_id))]
        await build_msg(matcher, event, segments, tag='finish')
        return        

    if not ntr:
        # 若更换次数即将达到上限，提醒用户
        target_username = await get_user_display_name(bot, group_id, goal_user_id)
        reply_key = "qq.group.success.common" if record.swap_count + 1 < MAX_SWAP_COUNT else "qq.group.success.last"
        segments = [("at", (None, user_id)), ("text", reply(reply_key, username=target_username)),
                    ("image", get_user_avatar_url(goal_user_id))]
        await build_msg(matcher, event, segments, tag='finish')
    else:
        # 权限狗 NTR 成功
        target_username = await get_user_display_name(bot, group_id, goal_user_id)
        segments = [("at", (None, user_id)),
                    ("text", reply("qq.group.success.ntr", username=target_username)),
                    ("image", get_user_avatar_url(goal_user_id))]
        await build_msg(matcher, event, segments, tag='finish')
        return


@qq_private.handle()
async def qq_private_handled(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理指令: qq_private"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return

    # 获取心选目标
    goal_user_id = None  
    # 从 regex 获取
    if goal_user_id is None and groups and groups[0]:
        if groups[0].isdigit():
            goal_user_id = int(groups[0])
    # [NO_LYRA] 如果目标是 bot 自身，特殊结束语驳回请求
    if getattr(event, 'to_me', False) or str(goal_user_id) == str(bot.self_id):
        segments = [("at", (None, user_id)), ("text", reply("qq.group.failed.with_lyra"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    
    # 将心选加入愿望单
    # 这里忽略了心选是否启用功能 —— 万一心选想玩了呢（
    await services.update_user_setting(platform, user_id, hope_id=goal_user_id)
    reply_key = "qq.private.success" if goal_user_id else "qq.private.cleared"
    segments = [("at", (None, user_id)), ("text", reply(reply_key, qq=goal_user_id))]
    await build_msg(matcher, event, segments, tag='finish')

@jrlg.handle()
async def jrlg_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    """处理指令: jrlg"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return
    
    record = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.HUSBAND)
    # 没有老公逻辑
    if not record or record.target_id is None:
        segments = [("at", (None, user_id)), ("text", reply("jrlg.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 有老公逻辑，返回当前老公
    target_username = await get_user_display_name(bot, group_id, record.target_id)
    segments = [("at", (None, user_id)),
                ("text", reply("jrlg.success.common", username=target_username)),
                ("image", get_user_avatar_url(record.target_id))]
    await build_msg(matcher, event, segments, tag='finish')
    return

@hlg.handle()
async def hlg_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    """处理指令: hlg"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    group_id = get_group_id(event)
    if not group_id:
        return
    user = await services.get_user(platform, user_id)
    if user.is_enabled is False:
        # 这孩子不玩，直接静默返回
        return
    
    record = await services.get_today_partner(platform, group_id, user_id, relation_type=RelationType.HUSBAND)
    # 没有老公逻辑
    if not record or record.target_id is None:
        segments = [("at", (None, user_id)), ("text", reply("hlg.failed.none"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    # 更换次数上限
    if record.swap_count >= MAX_SWAP_COUNT:
        # 超过换老公次数上限，驳回请求
        segments = [("at", (None, user_id)), ("text", reply("hlp.failed.limit"))]
        await build_msg(matcher, event, segments, tag='finish')
        return
    
    # 执行休夫
    await services.set_today_partner(platform, group_id, user_id, target_id=None, relation_type=RelationType.HUSBAND)
    reply_key = "hlg.success.common" if record.swap_count + 1 < MAX_SWAP_COUNT else "hlg.success.last"
    target_username = await get_user_display_name(bot, group_id, record.target_id)
    segments = [("at", (None, user_id)), ("text", reply(reply_key, username=target_username)),
                ("image", get_user_avatar_url(record.target_id))]
    await build_msg(matcher, event, segments, tag='finish')

@toggle_status.handle()
async def toggle_status_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理指令: toggle_status"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    platform, user_id = get_platform_and_user_id(event)
    await services.get_user(platform, user_id)

    cmd = groups[0] if groups else event.get_plaintext().strip()
    
    if cmd == "不当老婆":
        await services.update_user_setting(platform, user_id, is_enabled=False)
        segments = [("at", (None, user_id)), ("text", reply("toggle.enable.disabled"))]
        await build_msg(matcher, event, segments, tag='finish')
        
    elif cmd == "当老婆":
        await services.update_user_setting(platform, user_id, is_enabled=True)
        segments = [("at", (None, user_id)), ("text", reply("toggle.enable.enabled"))]
        await build_msg(matcher, event, segments, tag='finish')
    
    elif cmd == "不娶bot":
        await services.update_user_setting(platform, user_id, allow_bot=False)
        segments = [("at", (None, user_id)), ("text", reply("toggle.allow_bot.disabled"))]
        await build_msg(matcher, event, segments, tag='finish')
        
    elif cmd == "娶bot":
        await services.update_user_setting(platform, user_id, allow_bot=True)
        segments = [("at", (None, user_id)), ("text", reply("toggle.allow_bot.enabled"))]
        await build_msg(matcher, event, segments, tag='finish')

    elif cmd == "我是bot":
        await services.update_user_setting(platform, user_id, is_bot=True)
        segments = [("at", (None, user_id)), ("text", reply("toggle.is_bot.enabled"))]
        await build_msg(matcher, event, segments, tag='finish')

    elif cmd == "我不是bot":
        await services.update_user_setting(platform, user_id, is_bot=False)
        segments = [("at", (None, user_id)), ("text", reply("toggle.is_bot.disabled"))]
        await build_msg(matcher, event, segments, tag='finish')

@sudo.handle()
async def sudo_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理指令: sudo"""
    from plugins.nonebot_plugin_i18n import current_i18n_data
    if _i18n:
        current_i18n_data.set(_i18n)
    _, cmd = groups  # groups[0] 是插件名，groups[1] 是命令内容
    cmd = cmd.strip()
    user_id = int(event.get_user_id())
    # Permission check 已经在 on_regex 的 permission 参数中完成，这里不再重复检查
    
    # sudo jrlp set_bot <bot_qq | @bot> <is_bot>
    if cmd.startswith("set_bot"):
        parts = cmd.split()
        
    segments = [("at", (None, user_id)), ("text", reply("sudo.failed"))]
    await build_msg(matcher, event, segments, tag='finish')
