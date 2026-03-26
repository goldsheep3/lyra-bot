import asyncio
import random
import re
import shutil
import tarfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Literal
from pathlib import Path

import anyio
import orjson
from pydantic import BaseModel

from nonebot import get_driver, get_plugin_config, logger, on_regex, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.exception import ActionFailed, NetworkError
from nonebot.plugin import PluginMetadata

require('nonebot_plugin_localstore')
from nonebot_plugin_localstore import get_plugin_cache_dir, get_plugin_data_dir

# --- 插件配置 ---
class Config(BaseModel):
    PARTNER_ACTIVE_DAYS: int = 14
    PARTNER_MAX_CHANGE_COUNT: int = 3

__plugin_meta__ = PluginMetadata(
    name="今日老婆",
    description="支持群友「结婚」的娱乐插件，支持「一夫一妻制」。",
    usage="今日老婆, 换老婆, 强娶 [QQ], 离婚, 当老婆, 不当老婆, 娶bot, 不娶bot",
    config=Config,
)

plugin_conf = get_plugin_config(Config)
ACTIVE_DAYS = plugin_conf.PARTNER_ACTIVE_DAYS
MAX_COUNT = plugin_conf.PARTNER_MAX_CHANGE_COUNT

# --- 发言字典 ---
REPLY_DICT: Dict[str, str] = {
    # jrlp: 成功、自己、已婚
    "jrlp_success": "你今天的老婆是：{qq}",
    "jrlp_self": "你今天的老婆是自己哦=w=",
    "jrlp_already": "你今天的老婆已经是 {qq} 啦！",
    # hlp: 成功、上限、自己、没有老婆了
    "hlp_success1": "好吧好吧，给你换了。你现在的老婆是：{qq}",
    "hlp_success2": "换好了喔。你现在的老婆是：{qq}",
    "hlp_last": "再换你就没老婆啦！你现在的老婆是：{qq}",
    "hlp_self": "恭喜你，现在没有其他可以更换的人选了，恭喜水仙（",
    "hlp_limit": "换太多次啦！你现在没有香香软软的亲亲老婆了！😡😡",
    "hlp_lh": "（翻笔记）你现在不能换老婆了（叉腰）",
    # hlg: 成功、还没有老公
    "hlg_success": "休夫，立即执行！{qq} 已经是你的前任了。",
    "hlg_none": "还没有人娶到你喔ww",
    # qq: 成功、自己、未指定、对方已婚、上限、离过婚了
    "qq_success": "怎么还有强制play（）总之恭喜娶到 {qq} ！",
    "qq_success_ntr": "我去，还有大权限NTR（）{qq} 现在已经被你强娶了。让我们可怜原配三秒钟（",
    "qq_self": "终归是要水仙啊……那我先磕！",
    "qq_usage": "若想强娶那个TA，请勇敢地@出来=w=",
    "qq_with_bot_self": "小梨不能跟你们玩这种游戏啦！莉莉丝阿姐听说了会生气的qwq",
    "qq_fail_married": "不可以哦——TA已经有老婆了，TA的老婆会闹情绪的！",
    "qq_fail_limit": "再换老婆你可就没有老婆了，今天安安心心过这日子吧（",
    "qq_fail_lh": "你今天已经离过婚了，不可以再找新老婆了！",
    "qq_fail_not_allowed": "TA似乎不太愿意玩这个喔……",
    # lh: 成功、自己、还没有老婆
    "lh_success": "你已经和 {qq} 离婚了。（记笔记）",
    "lh_self": "水仙也要离婚吗（大脑过载）\n那便如此吧（",
    "lh_none": "你还没有一个香香软软的亲亲老婆，怎么就想着当个负心汉了！😡😡",
    # jrlg: 有老公、还没有老公
    "jrlg_status": "你现在的老公是：{qq}",
    "jrlg_none": "还没有人娶到你喔ww",
    # hope/toggle: 设置hope成功、已拒绝、已允许、已排除机器人、已加入机器人
    "hope_set": "已悄悄将 {qq} 记入你的心愿单。",
    "not_allowed": "设置成功：你已拒绝分配给任何人。",
    "allowed": "设置成功：你已重新进入分配池！",
    "not_allow_bot": "设置成功：你的择偶标准已排除机器人。",
    "allow_bot": "设置成功：机器人现已加入你的择偶池！",
}

# --- 数据模型 ---
class MemberData(BaseModel):
    wife: Optional[int] = None
    husband: Optional[int] = None
    count: int = 0

class GroupInstance:
    def __init__(self, group_id: int, data: dict):
        self.group_id = group_id
        self.members: Dict[int, MemberData] = {
            int(uid): MemberData(**info) for uid, info in data.items()
        }
        self._lock = asyncio.Lock()

    def get_member(self, user_id: int) -> MemberData:
        if user_id not in self.members:
            self.members[user_id] = MemberData()
        return self.members[user_id]

    def _update_relation(self, user_a: int, user_b: int) -> None:
        a = self.get_member(user_a)
        b = self.get_member(user_b)
        a.wife, b.husband = user_b, user_a

    def _clear_relation(self, user_id: int, target: Literal['wife', 'husband', 'both']) -> None:
        """清除关系，确保双向解绑"""
        user = self.get_member(user_id)
        # 清理老婆
        if user.wife and target in ('wife', 'both'):
            wife = self.get_member(user.wife)
            wife.husband = None
            user.wife = None
            if wife.count == -1 or wife.count > MAX_COUNT:
                wife.count = MAX_COUNT - 1
        # 清理老公
        if user.husband and target in ('husband', 'both'):
            husband = self.get_member(user.husband)
            husband.wife = None
            user.husband = None
            if husband.count == -1 or husband.count > MAX_COUNT:
                husband.count = MAX_COUNT - 1

    def random_partner(self, pool: List[int], user_id: int, hope: Optional[int] = None, ex_partner_id: Optional[int] = None) -> int:
        # 双重过滤：避免抽到自己、前任，且不选择已与他人绑定的对象。
        others = [
            m
            for m in pool
            if m != user_id
            and m != ex_partner_id
            and (not self.get_member(m).husband or self.get_member(m).husband == user_id)
        ]
        if not others:
            return user_id
        if hope in others and random.random() < 0.5:
            return hope
        return random.choice(others)

    async def handle_jrlp(self, user_id: int, pool: List[int], hope: Optional[int]) -> Tuple[str, int | None]:
        async with self._lock:
            member = self.get_member(user_id)
            # 检查是否已离婚 (count = -1)
            if member.count == -1:
                return "qq_fail_lh", None
            if member.wife: 
                return "jrlp_already", member.wife
            
            target_id = self.random_partner(pool, user_id, hope)
            self._update_relation(user_id, target_id)
            return ("jrlp_self" if target_id == user_id else "jrlp_success"), target_id

    async def handle_hlp(self, user_id: int, pool: List[int], hope: Optional[int]) -> Tuple[str, Optional[int]]:
        async with self._lock:
            member = self.get_member(user_id)
            
            # 离婚状态检查
            if member.count == -1:
                return "hlp_lh", None

            # 解除关系并记录前任ID
            ex_partner_id = member.wife
            self._clear_relation(user_id, 'wife')

            # 次数限制检查
            if member.count >= MAX_COUNT:
                return "hlp_limit", None
            
            member.count += 1
            clean_pool = [m for m in pool if m != ex_partner_id]
            target_id = self.random_partner(clean_pool, user_id, hope, ex_partner_id)
            self._update_relation(user_id, target_id)
            
            # 4. 文案分支判断
            if target_id == user_id:
                return "hlp_self", target_id
            if member.count == MAX_COUNT:
                return "hlp_last", target_id
            
            # 随机返回 hlp_success1 或 2
            return random.choice(["hlp_success1", "hlp_success2"]), target_id

    async def handle_hlg(self, user_id: int) -> Tuple[str, Optional[int]]:
        async with self._lock:
            member = self.get_member(user_id)
            if not member.husband: 
                return "hlg_none", None
            husband_id = member.husband
            member.count += 1
            self._clear_relation(user_id, 'husband')
            return ("hlp_limit" if member.count > MAX_COUNT else "hlg_success"), husband_id

    async def handle_qq(self, user_id: int, target_id: int, bot_id: int, is_admin: bool = False) -> Tuple[str, int | None]:
        async with self._lock:
            member = self.get_member(user_id)
            
            # 离婚判定
            if member.count == -1:
                return "qq_fail_lh", None
            # 次数判定
            if member.count >= MAX_COUNT: 
                return "qq_fail_limit", None
            # 强娶机器人判定
            if target_id == bot_id:
                return "qq_with_lyra", None

            target_member = self.get_member(target_id)
            if target_member.husband:
                if not is_admin:
                    return "qq_fail_married", None
                # 管理员NTR已婚对象，先清理对方关系
                self._clear_relation(target_id, 'husband')
                success_key = "qq_success_ntr"
            elif target_id == user_id:
                # 水仙
                success_key = "qq_self"
            else:
                success_key = "qq_success"

            self._clear_relation(user_id, 'wife')
            member.count += 1
            self._update_relation(user_id, target_id)
            return success_key, target_id

    async def handle_lh(self, user_id: int) -> Tuple[str, Optional[int]]:
        async with self._lock:
            member = self.get_member(user_id)
            if not member.wife:
                return "lh_none", None
            
            partner_id = member.wife
            status = "lh_self" if partner_id == user_id else "lh_success"
            
            self._clear_relation(user_id, 'wife')
            # 设置离婚标记：count 为 -1
            member.count = -1 
            return status, partner_id

# --- 单例管理器 ---
class PluginManager:
    _instance: Optional["PluginManager"] = None
    
    # 使用标准库的 Path 类型进行注解
    # TODO: 可以考虑设置清理机制，避免内存占用过大
    groups: Dict[Tuple[int, str], GroupInstance]
    config_path: Path 

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.groups = {}
            # get_plugin_data_dir() 返回的是 pathlib.Path
            cls._instance.config_path = get_plugin_data_dir() / "config.json"
        return cls._instance

    async def get_group(self, group_id: int, date_str: str) -> GroupInstance:
        group_key = (group_id, date_str)
        if group_key not in self.groups:
            path = get_plugin_cache_dir() / date_str / f"{group_id}.json"
            data = {}
            if path.exists():
                try:
                    content_bytes = await anyio.Path(path).read_bytes()
                    data = orjson.loads(content_bytes)
                except (ValueError, KeyError, orjson.JSONDecodeError) as e:
                    logger.warning(f"读取群 {group_id} 数据异常，启用空配置: {e}")
                except Exception as e:
                    logger.error(f"未知异常读取缓存: {e}")
            self.groups[group_key] = GroupInstance(group_id, data)
        return self.groups[group_key]

    async def save_group(self, group_id: int, date_str: str) -> None:
        path = get_plugin_cache_dir() / date_str / f"{group_id}.json"
        group_key = (group_id, date_str)
        instance = self.groups.get(group_key)
        if not instance:
            return

        await anyio.Path(path.parent).mkdir(parents=True, exist_ok=True)
        dumped_dict = {str(k): getattr(v, "model_dump", v.model_dump)() for k, v in instance.members.items()}
        dumped_bytes = orjson.dumps(dumped_dict, option=orjson.OPT_INDENT_2)
        await anyio.Path(path).write_bytes(dumped_bytes)

    async def load_config(self) -> dict:
        if not self.config_path.exists():
            default_config = {"allowed": {}, "not_allowed": []}
            await anyio.Path(self.config_path.parent).mkdir(parents=True, exist_ok=True)
            await anyio.Path(self.config_path).write_bytes(orjson.dumps(default_config, option=orjson.OPT_INDENT_2))
            return default_config
        try:
            content_bytes = await anyio.Path(self.config_path).read_bytes()
            return orjson.loads(content_bytes)
        except (ValueError, KeyError, orjson.JSONDecodeError) as e:
            logger.warning(f"读取配置文件异常: {e}")
            return {"allowed": {}, "not_allowed": []}
        except Exception as e:
            logger.error(f"未知异常读取配置文件: {e}")
            return {"allowed": {}, "not_allowed": []}

    async def save_config(self, config_data: dict) -> None:
        try:
            await anyio.Path(self.config_path.parent).mkdir(parents=True, exist_ok=True)
            dumped_bytes = orjson.dumps(config_data, option=orjson.OPT_INDENT_2)
            await anyio.Path(self.config_path).write_bytes(dumped_bytes)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

plugin_manager = PluginManager()

# --- 定时与启动任务 ---
driver = get_driver()

def _archive_last_week_data():
    now = datetime.now()
    base_dir = get_plugin_cache_dir()
    
    last_monday = now - timedelta(days=now.weekday() + 7)
    target_dates = [(last_monday + timedelta(days=i)).strftime("%Y%m%d") for i in range(7)]
    
    dirs_to_archive = [base_dir / d for d in target_dates if (base_dir / d).exists() and (base_dir / d).is_dir()]
    if not dirs_to_archive:
        return

    archive_name = base_dir / f"archive_{target_dates[0]}_{target_dates[-1]}.tar.gz"
    try:
        with tarfile.open(archive_name, "w:gz") as tar:
            for d in dirs_to_archive:
                tar.add(d, arcname=d.name)
                
        for d in dirs_to_archive:
            shutil.rmtree(d)
            
        logger.info(f"上周数据已压缩至 {archive_name} 并清理原文件夹。")
    except Exception as e:
        logger.error(f"压缩上周数据失败: {e}")

@driver.on_startup
async def check_and_archive_data():
    if datetime.now().weekday() == 0:
        await asyncio.to_thread(_archive_last_week_data)

# --- 工具函数 ---
async def build_message(bot: Bot, group_id: int, user_id: int, template: str, partner_id: Optional[int] = None, intent: str = "wife") -> Message:
    display = "你自己"
    if partner_id and partner_id != user_id:
        try:
            info = await bot.get_group_member_info(group_id=group_id, user_id=partner_id)
            display = info.get("card") or info.get("nickname") or str(partner_id)
        except (ActionFailed, NetworkError) as e:
            logger.warning(f"获取群员信息失败: {e}")
            display = str(partner_id)
        except Exception as e:
            logger.error(f"未知异常导致无法获取昵称: {e}")
            display = str(partner_id)

    text = template.replace("{qq}", display)
    msg = Message([MessageSegment.at(user_id), MessageSegment.text(f"\n{text}")])
    if partner_id: 
        msg.append(MessageSegment.image(f"http://q1.qlogo.cn/g?b=qq&nk={partner_id}&s=640"))
    return msg

async def get_pool(bot: Bot, group_id: int, user_id: int, config: dict, group_instance: GroupInstance) -> List[int]:
    pref = config["allowed"].get(str(user_id), {})
    try:
        member_list = await bot.get_group_member_list(group_id=group_id)
    except (ActionFailed, NetworkError) as e:
        logger.warning(f"拉取群成员列表失败: {e}")
        return []
    except Exception as e:
        logger.error(f"未知异常导致拉取群成员失败: {e}")
        return []
        
    now = datetime.now().timestamp()
    pool = []
    for member_info in member_list:
        member_id: int = member_info["user_id"]
        if str(member_id) in config["not_allowed"] or member_id == user_id: 
            continue
        member_data = group_instance.get_member(member_id)
        if member_data.husband and member_data.husband != user_id:
            continue
        if not pref.get("allow_bot") and (member_info.get("is_bot") or str(member_id) == bot.self_id): 
            continue
        if now - member_info.get("last_sent_time", 0) > ACTIVE_DAYS * 86400: 
            continue
        pool.append(member_id)
    return pool

# --- 响应器 ---
help = on_regex(r"^(今日老婆|jrlp)\s*(帮助|help)$", priority=5, block=True)
jrlp = on_regex(r"^(今日老婆|jrlp)$", priority=5, block=True)
hlp = on_regex(r"^(换老婆|hlp)$", priority=5, block=True)
hlg = on_regex(r"^(换老公|hlg)$", priority=5, block=True)
qq = on_regex(r"^强娶", priority=5, block=True)
lh = on_regex(r"^(离婚|lh)$", priority=5, block=True)
jrlg = on_regex(r"^(今日老公|jrlg)$", priority=5, block=True)
toggle_status = on_regex(r"^(不当老婆|当老婆|不娶bot|娶bot)$", priority=5, block=True)

@help.handle()
async def _():
    await help.finish("""
帮助 | DailyPartner（今日老婆）

1. 今日老婆 / jrlp
   随机抽选一个「老婆」，每日一次，各群独立
2. 今日老公 / jrlg
   根据「今日老婆」的抽选结果，显示当前锚定的「老公」
3. 换老婆 / hlp
   重新抽选一个「老婆」（有次数限制）
4. 换老公 / hlg
   和当前的「老公」离婚（有次数限制）
5. 强娶 [QQ 或 at]
   尝试指定某个群友为你的「老婆」（有次数等限制）
6. 离婚 / lh
   和当前的「老婆」离婚（谨慎！）
7. 当老婆 / 不当老婆
   配置项：控制你是否可以参与抽选，以及是否可以被抽选
8. 娶bot / 不娶bot
   配置项：控制你是否可以娶该群的QQ官方机器人作为「老婆」
""".strip())

@jrlp.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))
    if not isinstance(event, GroupMessageEvent): return
    now_date = datetime.now().strftime("%Y%m%d")
    config = await plugin_manager.load_config()
    if user_id in config["not_allowed"]: 
        return  # 直接返回，保持沉默

    group = await plugin_manager.get_group(group_id, now_date)
    pool = await get_pool(bot, group_id, user_id, config, group)
    status, partner_id = await group.handle_jrlp(user_id, pool, config["allowed"].get(str(user_id), {}).get("hope"))
    
    await plugin_manager.save_group(group_id, now_date)
    await jrlp.finish(await build_message(bot, group_id, user_id, REPLY_DICT[status], partner_id))

@hlp.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))
    if not isinstance(event, GroupMessageEvent): return
    now_date = datetime.now().strftime("%Y%m%d")
    config = await plugin_manager.load_config()
    group = await plugin_manager.get_group(group_id, now_date)
    pool = await get_pool(bot, group_id, user_id, config, group)
    status, partner_id = await group.handle_hlp(user_id, pool, config["allowed"].get(str(user_id), {}).get("hope"))
    
    await plugin_manager.save_group(group_id, now_date)
    await hlp.finish(await build_message(bot, group_id, user_id, REPLY_DICT[status], partner_id))

@hlg.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))
   
    if not isinstance(event, GroupMessageEvent): return
    now_date = datetime.now().strftime("%Y%m%d")
    group = await plugin_manager.get_group(group_id, now_date)
    status, partner_id = await group.handle_hlg(user_id)
    
    await plugin_manager.save_group(group_id, now_date)
    await hlg.finish(await build_message(bot, group_id, user_id, REPLY_DICT[status], partner_id, "husband"))

@qq.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))

    target_id = None
    for segment in event.get_message():
        if segment.type == "at":
            target_id = int(segment.data["qq"])
            break
      
    if getattr(event, 'to_me', None):
        await qq.finish(REPLY_DICT["qq_with_bot_self"])
      
    if not target_id:
        text = event.get_plaintext().strip()
        match = re.search(r'\d+', text)
        if match:
            target_id = int(match.group())

    if not target_id:
        await qq.finish(REPLY_DICT["qq_usage"])
        return

    if isinstance(event, PrivateMessageEvent):
        # 设定 hope 的私聊接口
        config = await plugin_manager.load_config()
        uid_str = str(user_id)
        if uid_str not in config["allowed"]:
            config["allowed"][uid_str] = {}
        config["allowed"][uid_str]["hope"] = target_id
        await plugin_manager.save_config(config)
        await qq.finish(REPLY_DICT["hope_set"].replace("{qq}", str(target_id)))
        return

    if isinstance(event, GroupMessageEvent):
        # 群内的「强娶」逻辑线
        config = await plugin_manager.load_config()
        if str(target_id) in config["not_allowed"]:
            await qq.finish(REPLY_DICT["qq_fail_not_allowed"])
            return
        now_date = datetime.now().strftime("%Y%m%d")
        is_admin = event.sender.role in ("owner", "admin")  # 管理员权限检查

        group = await plugin_manager.get_group(group_id, now_date)
        status, partner_id = await group.handle_qq(user_id, target_id, int(bot.self_id), is_admin=is_admin)
        
        await plugin_manager.save_group(group_id, now_date)
        await qq.finish(await build_message(bot, group_id, user_id, REPLY_DICT[status], partner_id))

@lh.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))

    if not isinstance(event, GroupMessageEvent): return
    now_date = datetime.now().strftime("%Y%m%d")
    group = await plugin_manager.get_group(group_id, now_date)
    status, partner_id = await group.handle_lh(user_id)

    await plugin_manager.save_group(group_id, now_date)
    await lh.finish(await build_message(bot, group_id, user_id, REPLY_DICT[status], partner_id))

@jrlg.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, group_id = int(event.user_id), int(getattr(event, "group_id", -1))

    if not isinstance(event, GroupMessageEvent): return
    now_date = datetime.now().strftime("%Y%m%d")
    group = await plugin_manager.get_group(group_id, now_date)
    member = group.get_member(user_id)
    if not member.husband: 
        await jrlg.finish(REPLY_DICT["jrlg_none"])
        
    await jrlg.finish(await build_message(bot, group_id, user_id, REPLY_DICT["jrlg_status"], member.husband, "husband"))

@toggle_status.handle()
async def _(bot: Bot, event: MessageEvent):
    user_id, _group_id = int(event.user_id), int(getattr(event, "group_id", -1))

    if not isinstance(event, GroupMessageEvent): return
    cmd = event.get_plaintext().strip()
    config = await plugin_manager.load_config()
    uid_str = str(user_id)
    
    if cmd == "不当老婆":
        if user_id not in config["not_allowed"]:
            config["not_allowed"].append(user_id)
            await plugin_manager.save_config(config)
        await toggle_status.finish(REPLY_DICT["not_allowed"])
        
    elif cmd == "当老婆":
        if user_id in config["not_allowed"]:
            config["not_allowed"].remove(user_id)
            await plugin_manager.save_config(config)
        await toggle_status.finish(REPLY_DICT["allowed"])
        
    elif cmd == "不娶bot":
        if uid_str not in config["allowed"]:
            config["allowed"][uid_str] = {}
        config["allowed"][uid_str]["allow_bot"] = False
        await plugin_manager.save_config(config)
        await toggle_status.finish(REPLY_DICT["not_allow_bot"])
        
    elif cmd == "娶bot":
        if uid_str not in config["allowed"]:
            config["allowed"][uid_str] = {}
        config["allowed"][uid_str]["allow_bot"] = True
        await plugin_manager.save_config(config)
        await toggle_status.finish(REPLY_DICT["allow_bot"])
