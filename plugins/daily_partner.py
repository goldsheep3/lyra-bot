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
qiangqu = on_regex(r"^强娶", priority=5, block=True)


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
    """使用原子操作将数据写入JSON文件"""
    try:
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
    """构造回复消息"""
    nickname = ""
    if partner_user_id:
        try:
            user_info = await bot.get_group_member_info(group_id=group_id, user_id=int(partner_user_id))
            nickname = user_info.get("card", "") or user_info.get("nickname", "")
        except Exception as e:
            logger.warning(f"获取群成员 {partner_user_id} 信息失败: {e}")

    user_display = nickname or partner_user_id or ""
    final_text = text.replace("{qq}", str(user_display))

    result = [MessageSegment.at(at_user_id), MessageSegment.text(' \n'), MessageSegment.text(final_text)]
    
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
            msg = await build_message(bot, group_id, user_id, "你今天已经离过婚了！不可以再找老婆了！")
        elif partner_id == user_id:
            msg = await build_message(bot, group_id, user_id, "你今天的老婆是自己哦=w=", partner_user_id=partner_id)
        else:
            msg = await build_message(bot, group_id, user_id, "你今天的老婆是：{qq}", partner_user_id=partner_id)
        await jrlp.finish(msg)

    active_members = await get_active_members(bot, group_id)
    bot_id = str(bot.self_id)
    candidates = [m for m in active_members if m not in data and m != user_id and m != bot_id]

    if not candidates:
        partner_id = user_id
        data[user_id] = {"partner_id": user_id, "change_count": 0}
        msg = await build_message(bot, group_id, user_id, "今天群里没有其他单身人士了，你的老婆是你自己哦！", partner_user_id=partner_id)
    else:
        partner_id = random.choice(candidates)
        data[user_id] = {"partner_id": partner_id, "change_count": 0}
        data[partner_id] = {"partner_id": user_id, "change_count": 0}
        msg = await build_message(bot, group_id, user_id, "你今天的老婆是：{qq}", partner_user_id=partner_id)
        logger.info(f"群({group_id})配对成功: {user_id} <-> {partner_id}")

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
        msg = await build_message(bot, group_id, user_id, "你还没有一个香香软软的亲亲老婆，怎么就想着当个负心汉了！😡😡")
        await lihun.finish(msg)

    user_info = data[user_id]
    partner_id = user_info.get("partner_id")

    if partner_id is None:
        msg = await build_message(bot, group_id, user_id, "你已经离过婚了！干嘛！😡😡")
        await lihun.finish(msg)
    
    if partner_id == user_id:
        msg = await build_message(bot, group_id, user_id, "水仙也要离婚吗（大脑过载）")
        await lihun.finish(msg)

    if partner_id in data:
        del data[partner_id]
    user_info["partner_id"] = None
    write_data(file_path, data)

    logger.info(f"群({group_id})离婚成功: 用户 {user_id} 与 {partner_id} 离婚")
    msg = await build_message(bot, group_id, user_id, "你已经和 {qq} 离婚了。（记笔记）", partner_user_id=partner_id)
    await lihun.finish(msg)


@huanlp.handle()
async def handle_huanlp(bot: Bot, event: GroupMessageEvent):
    """处理「换老婆」命令"""
    user_id = str(event.user_id)
    group_id = event.group_id
    file_path = get_today_file(group_id)
    data = read_data(file_path)

    user_info = get_user_data(data, user_id)
    original_partner_id = user_info.get("partner_id")

    if original_partner_id is None:
        msg = await build_message(bot, group_id, user_id, "你已经离过婚或还没有老婆，不能换哦！")
        await huanlp.finish(msg)

    if user_info.get("change_count", 0) >= MAX_CHANGE_COUNT:
        msg = await build_message(bot, group_id, user_id, "你的更换次数已达上限！")
        await huanlp.finish(msg)

    active_members = await get_active_members(bot, group_id)
    bot_id = str(bot.self_id)
    new_candidates = [m for m in active_members if m not in data and m != user_id and m != bot_id]

    if not new_candidates:
        msg = await build_message(bot, group_id, user_id, "恭喜你，现在没有其他可以更换的人选了（")
        await huanlp.finish(msg)

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


@qiangqu.handle()
async def handle_qiangqu(bot: Bot, event: GroupMessageEvent):
    """处理「强娶」命令"""
    user_id = str(event.user_id)
    group_id = event.group_id
    file_path = get_today_file(group_id)
    data = read_data(file_path)

    # 提取被@的用户
    target_user_id = None
    for seg in event.message:
        if seg.type == "at":
            target_user_id = str(seg.data["qq"])
            break
    if not target_user_id:
        msg = await build_message(bot, group_id, user_id, "若想强娶那个TA，请勇敢地@出来=w=")
        await qiangqu.finish(msg)

    if target_user_id == str(bot.self_id):
        await qiangqu.finish("小梨不能跟你们玩这种游戏啦！莉莉丝阿姐听说了会生气的qwq")

    # 检查目标是否可被强娶
    if target_user_id in data:
        msg = await build_message(bot, group_id, user_id, "不可以哦——破坏他人关系是不好的！")
        await qiangqu.finish(msg)

    user_info = get_user_data(data, user_id)
    original_partner_id = user_info.get("partner_id")
    change_count = user_info.get("change_count", 0)

    # [逻辑修改] 根据用户是否有老婆，执行不同逻辑
    if not original_partner_id:
        # 用户单身，直接建立新关系
        if user_id in data and data[user_id].get("partner_id") is None:
            # 今天离过婚的用户不能再配对
            msg = await build_message(bot, group_id, user_id, "你今天已经离过婚了，不可以再找新老婆了！")
            await qiangqu.finish(msg)
        
        # 建立新关系
        data[user_id] = {"partner_id": target_user_id, "change_count": 0}
        data[target_user_id] = {"partner_id": user_id, "change_count": 0}
        write_data(file_path, data)
        logger.info(f"群({group_id})强娶成功: 单身用户 {user_id} 强娶了 {target_user_id}")
        msg = await build_message(bot, group_id, user_id, "怎么还有强制play（）总之恭喜娶到 {qq} ！", partner_user_id=target_user_id)

    else:
        # 用户已有老婆，执行更换逻辑
        if change_count >= MAX_CHANGE_COUNT:
            msg = await build_message(bot, group_id, user_id, "再换老婆你可就没有老婆了，今天安安心心过这日子吧（")
            await qiangqu.finish(msg)

        if original_partner_id in data:
            del data[original_partner_id] # 释放前任

        user_info["partner_id"] = target_user_id
        user_info["change_count"] += 1
        data[user_id] = user_info
        data[target_user_id] = {"partner_id": user_id, "change_count": 0}
        write_data(file_path, data)
        
        logger.info(f"群({group_id})强娶更换成功: {user_id} 从 {original_partner_id} 换为 {target_user_id}")
        msg = await build_message(bot, group_id, user_id, "怎么还有强制play（）总之恭喜娶到 {qq} ！", partner_user_id=target_user_id)

    await qiangqu.finish(msg)
