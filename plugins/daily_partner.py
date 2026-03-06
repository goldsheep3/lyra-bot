import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from atomicwrites import atomic_write
from nonebot import on_regex, logger, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_cache_dir

# --- 配置与常量 ---
# 活跃时间判定（14天）
ACTIVE_DAYS: int = 14
# 更换伴侣次数上限
MAX_CHANGE_COUNT: int = 3

# 插件数据目录
DATA_DIR: Path = get_plugin_cache_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)


# --- Matchers ---
jrlp = on_regex(r"^(今日老婆|jrlp)$", priority=5, block=True)
lihun = on_regex(r"^(离婚)$", priority=5, block=True)
huanlp = on_regex(r"^(换老婆|hlp)$", priority=5, block=True)


# --- 数据处理核心函数 ---

def get_today_file(group_id: int) -> Path:
    """获取指定群聊今天的JSON数据文件路径"""
    today_str = datetime.now().strftime("%Y%m%d")
    return DATA_DIR / f"{today_str}_{group_id}.json"


def read_data(file_path: Path) -> Dict[str, Dict[str, Any]]:
    """读取数据文件，文件不存在则返回空字典"""
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"读取数据文件 {file_path} 失败: {e}")
        return {}


def write_data(file_path: Path, data: Dict[str, Dict[str, Any]]) -> None:
    """
    使用原子操作将数据写入JSON文件，防止并发冲突。
    """
    try:
        # atomic_write会先写入一个临时文件，成功后再移动到目标路径
        with atomic_write(file_path, overwrite=True, encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logger.error(f"写入数据文件 {file_path} 失败: {e}")


async def get_active_members(bot: Bot, group_id: int) -> List[str]:
    """获取群内14天内发言的成员QQ号列表"""
    try:
        member_list = await bot.get_group_member_list(group_id=group_id)
    except Exception as e:
        logger.error(f"获取群 {group_id} 成员列表失败: {e}")
        return []

    active_members = []
    current_timestamp = int(datetime.now().timestamp())
    for member in member_list:
        if current_timestamp - member.get("last_sent_time", 0) < ACTIVE_DAYS * 24 * 3600:
            active_members.append(str(member["user_id"]))
    return active_members


def get_user_data(data: Dict[str, Dict[str, Any]], user_id: str) -> Dict[str, Any]:
    """获取用户的配对数据，不存在则创建默认值"""
    return data.get(user_id, {"partner_id": None, "change_count": 0})


# --- 消息构造函数 ---

async def build_message(bot: Bot, group_id: int, at_user_id: str, text: str, partner_user_id: Optional[str] = None) -> Message:
    """
    构造回复消息。
    :param bot: Bot 实例
    :param group_id: 群号
    :param at_user_id: 需要 at 的用户 QQ
    :param text: 回复的文本内容，可包含 {qq} 占位符
    :param partner_user_id: 伴侣的 QQ，用于获取头像和昵称
    """
    display_user_id = partner_user_id or at_user_id
    
    try:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(display_user_id))
        nickname = user_info.get("card", "") or user_info.get("nickname", "")
    except Exception as e:
        logger.warning(f"获取群成员 {display_user_id} 信息失败: {e}")
        nickname = ""
    
    user_display = nickname or display_user_id
    final_text = text.replace("{qq}", str(user_display))

    result = [
        MessageSegment.at(at_user_id),
        MessageSegment.text(' '),
        MessageSegment.text(final_text)
    ]
    
    # 只有在伴侣ID存在时才添加图片
    if partner_user_id:
        result.append(MessageSegment.image(f"http://q1.qlogo.cn/g?b=qq&nk={partner_user_id}&s=640"))

    return Message(result)


# --- 事件响应 ---

@jrlp.handle()
async def handle_jrlp(bot: Bot, event: GroupMessageEvent):
    """处理「今日老婆」命令"""
    user_id = str(event.user_id)
    group_id = event.group_id
    file_path = get_today_file(group_id)
    data = read_data(file_path)

    if user_id in data:
        partner_id = data[user_id].get("partner_id")
        if partner_id is None:
            # 已离婚状态
            msg = Message(f"[CQ:at,qq={user_id}] 你已经离婚了！不可以再找老婆了！")
        elif partner_id == user_id:
            # 自己是老婆
            msg = await build_message(bot, group_id, user_id, "你今天的老婆是自己哦=w=", partner_user_id=partner_id)
        else:
            # 已有老婆
            msg = await build_message(bot, group_id, user_id, "你今天的老婆是：{qq}", partner_user_id=partner_id)
        await jrlp.finish(msg)

    active_members = await get_active_members(bot, group_id)
    bot_id = str(bot.self_id)
    
    candidates = [m for m in active_members if m not in data and m != user_id and m != bot_id]

    if not candidates:
        partner_id = user_id
        data[user_id] = {"partner_id": user_id, "change_count": 0}
        msg = await build_message(bot, group_id, user_id, "你今天的老婆是自己哦=w=", partner_user_id=partner_id)
    else:
        partner_id = random.choice(candidates)
        data[user_id] = {"partner_id": partner_id, "change_count": 0}
        data[partner_id] = {"partner_id": user_id, "change_count": 0}
        msg = await build_message(bot, group_id, user_id, "你今天的老婆是：{qq}", partner_user_id=partner_id)

    write_data(file_path, data)
    await jrlp.finish(msg)


@lihun.handle()
async def handle_lihun(bot: Bot, event: GroupMessageEvent):
    """处理「离婚」命令"""
    user_id = str(event.user_id)
    group_id = event.group_id
    file_path = get_today_file(group_id)
    data = read_data(file_path)

    if user_id not in data:
        await lihun.finish("你还没有一个香香软软的亲亲老婆，怎么就想着当个负心汉了！😡😡")

    user_info = data[user_id]
    partner_id = user_info.get("partner_id")

    if partner_id is None:
        await lihun.finish("你已经离过婚了！干嘛！😡😡")
    
    if partner_id == user_id:
        await lihun.finish("水仙也要离婚吗（大脑过载）")

    # [FIXED] 直接删除前伴侣的记录，使其可以重新参与匹配
    if partner_id in data:
        del data[partner_id]

    user_info["partner_id"] = None

    write_data(file_path, data)

    # 离婚消息，at自己，并告知前任是谁
    msg = await build_message(
        bot,
        group_id,
        user_id,
        "你已经和 {qq} 离婚了。（记笔记）",
        partner_user_id=partner_id
    )
    await lihun.finish(msg)


@huanlp.handle()
async def handle_huanlp(bot: Bot, event: GroupMessageEvent):
    """处理「换老婆」命令，有次数限制"""
    user_id = str(event.user_id)
    group_id = event.group_id
    file_path = get_today_file(group_id)
    data = read_data(file_path)

    if user_id not in data:
        await huanlp.finish("你还没有一个香香软软的亲亲老婆，怎么就想着换一个了！😡😡")

    user_info = get_user_data(data, user_id)
    original_partner_id = user_info.get("partner_id")

    if original_partner_id is None:
        await huanlp.finish("你已经离过婚了！干嘛！😡😡")

    change_count = user_info.get("change_count", 0)
    if change_count >= MAX_CHANGE_COUNT:
        if original_partner_id in data:
            del data[original_partner_id]
        user_info["partner_id"] = None
        user_info["change_count"] += 1
        write_data(file_path, data)
        await huanlp.finish("换太多次啦！你现在没有香香软软的亲亲老婆了！😡😡")

    active_members = await get_active_members(bot, group_id)
    bot_id = str(bot.self_id)
    
    new_candidates = [m for m in active_members if m not in data and m != user_id and m != bot_id]

    if not new_candidates:
        await huanlp.finish("恭喜你，在没有其他可以更换的人选了（")

    if original_partner_id and original_partner_id in data:
        del data[original_partner_id]
    
    new_partner_id = random.choice(new_candidates)
    user_info["partner_id"] = new_partner_id
    user_info["change_count"] += 1
    
    data[user_id] = user_info
    data[new_partner_id] = {"partner_id": user_id, "change_count": 0}

    write_data(file_path, data)

    if user_info["change_count"] == MAX_CHANGE_COUNT:
        text = "再换你就没老婆啦！你现在的老婆是：{qq}"
    else:
        text = random.choice([
            "好吧好吧，给你换了。",
            "换好了喔。"
        ]) + "你现在的老婆是：{qq}"
    msg = await build_message(bot, group_id, user_id, text, partner_user_id=new_partner_id)
    await huanlp.finish(msg)
