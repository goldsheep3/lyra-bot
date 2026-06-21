import base64
import hashlib
import re
import time
import random
from pathlib import Path
from typing import Optional, List, Any, cast

import aiofiles
import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import utils, services, image_gen, bot_services, network, models
from .napcat_stream import NapCatStreamFile
# from .report import build_achievements_report, build_import_report
from .report import MaiChartAchDiffReport, build_diff_report
from .utils import MaiChart, MaiChartAch, link_cache, link_hash_index, NoLinkQQError
from .constants import *
from .bot_registry import PluginRegistry

from nonebot import logger, on_regex, on_message
from nonebot.rule import Rule
from nonebot.params import RegexGroup
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
from nonebot.adapters.onebot.v11.exception import ActionFailed

from nonebot.adapters.telegram import (Bot as TGBot,
                                       Event as TGEvent,
                                       Message as TGMessage,
                                       MessageSegment as TGMessageSegment,)
from nonebot.adapters.telegram.event import PrivateMessageEvent as TGPrivateMessageEvent
from nonebot.adapters.telegram.message import (Entity as TGMessageEntity,
                                               File as TGMessageFile)

from nonebot_plugin_localstore import get_plugin_data_dir

# --- config variables ---

LOW_MEMORY_MODE: bool = False  # 低内存模式，会阻止 B50 等大型图片合成
LOW_MEMORY_TIP: str | None = None
DEVELOPER_TOKEN: Optional[str] = None


# --- rule ---

# 规则：必须是私聊事件，且消息段中包含 file
# # TODO TG 适配
# def is_private_file():
#     async def _check(event: MessageEvent) -> bool:
#         return isinstance(event, PrivateMessageEvent) and \
#                any(seg.type == "file" for seg in event.get_message())
#     return Rule(_check)

# --- matcher ---

# 下载谱面
adx_download = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (id / info)
mai_info = on_regex(r"^(id|info)(\d+)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (是什么歌)
mai_what_song = on_regex(r"^(.+?)是什么歌([?？]?)$", priority=10, block=True)
# 设置乐曲别名
mai_alias = on_regex(r'^(添加|删除)别名\s+(?:id)?(\d+)\s+([^\s]+)$', priority=5, block=True)
# 列表查询（完成表/进度/列表）
scorelist = on_regex(r'^(.*?)\s*(完成表|进度|列表)$', priority=5, block=True)
# 同步水鱼数据
sytb = on_regex(r'^sytb$', priority=5, block=True)
# b50 查询
b50 = on_regex(r'^(b50|kkb)\s*(.*)$', priority=1, block=True)
# ra 计算
ra_calc = on_regex(r"^ra\s+(\S+)?\s+(\S+)", priority=5, block=True)
# 上传 JSON 配置数据
file_receiver = on_message(priority=25)
# 获取同步码
get_sync_code = on_regex(r"^获取同步码$", priority=5, block=True)
# link 查询与绑定
link = on_regex(r"^(查询|获取|绑定|解除|解绑)?link(?:\s+(\S+))?$", priority=5, block=True)


# --- reply dict ---

_REPLY_DICT: dict[str, str | list[str]] = {
    # link 查询与绑定
    "link_query_disabled": "查询功能正在开发中，敬请期待！",
    "link_only_qq": "此操作仅支持通过 QQ 进行",
    "link_tip": "请在其他平台的 LyraBot 中输入以下命令完成绑定，该信息五分钟内有效。",
    "link_invalid_hash": "提供的 hash 值无效或已过期",
    "link_not_found": "未找到匹配的绑定信息",
    "link_success": "绑定成功！",
    "link_unlink_success": "解绑成功！",
    "link_not_platform": "未知平台",
    "link_not_linked": "你似乎还没有绑定 QQ 号~请使用「绑定link」尝试绑定",
    "link_onebot_no_bind": "你可以直接操作的（）QQ 之间不能绑定的",
    "link_get_more_info": "你还没有绑定 QQ 号，绑定后可以同步游玩数据哦！",
    # adx_download (ad)
    "ad_no_maidata": "没有找到id为{short_id}的谱面的数据！可能还没被收录，请联系监护人确认喔qwq",
    "ad_bad_id": "请提供正确的乐曲 ID 哦qwq",
    "ad_no_chart_file": "谱面文件不存在！可能还没被收录，请联系监护人确认喔qwq",
    "ad_prepare": "请稍候——小梨开始准备 id{target_short_id} 的谱面文件啦！",
    "ad_error": "小梨在处理谱面文件时遇到了问题，请联系监护人确认喔qwq",
    "ad_private_success": "登登~请查收谱面 {song_name}！",
    "ad_group_success": "小梨已经将 {song_name} 的adx谱面传到群里啦！",
    "ad_tg_success": "wu~小梨已经将 {song_name} 的谱面发来啦！",
    # mai_info
    "mai_info_no_shortid": "请提供正确的乐曲 ID 哦qwq",
    "mai_info_no_maidata": "没有找到 id{short_id} 的乐曲数据qwq",
    # mai_what_song (mws)
    "mws_found_no_results": "没有找到包含「{keyword}」的乐曲数据qwq",
    "mws_found_one": "猜你想找：{shortid}. {title}",
    "mws_found_multiple": "小梨找到了 {count} 首乐曲，请查看是否有你的期待w",
    "mws_found_multiple_more": "小梨翻到了好多歌……呜哇，{count}首（）",
    "mws_found_too_many": "太多了啦！缩小一下搜索范围吧qwq",
    # mai_alias (alias)
    "alias_added_successfully": "成功为 {shortid} 添加别名【{alias}】！",
    "alias_already_exists": "这个别名似乎已经存在了捏~",
    "alias_deletion_not_supported": "目前还不能自助删除别名喔~",
    # b50
    "b50_all_not_supported": "混合成绩图还在开发中，暂时无法使用哦qwq",
    "b50_no_target": "小梨没找到合适的查询目标……？请联系监护人确认",
    "b50_drawing": "小梨正在绘制 b50 图片，请稍候……",
    "b50_other_updated_drawing": "小梨发现查询对象的水鱼数据有更新，已经为TA更新到了最新！正在尝试绘制 b50 图片，请稍候……",
    "b50_no_jp_data": "你还没有日服数据！可以通过 lyra-sync 上传成绩后再试哦！",

    # sytb
    "sy_syncing": "小梨正在尝试从水鱼查分器获取你的最新成绩数据！",
    "sy_no_updates": "检查过啦！小梨记录的成绩数据已经是最新的啦。",
    "platform_not_supported": "意外错误(Platform Not Supported)，请联系监护人确认喔qwq",
    # Exception Tip
    "error_invalid_user_id": "无法解析 str 格式的 user_id: {raw_uid}",
    "error_user_not_found": "未找到绑定的 QQ 账号，请先使用 link 功能绑定 QQ 号",
    "error_unexpected": "不支持的平台类型",
    "error": "小梨遇到了意外的错误，请联系监护人确认喔qwq",
}

# --- tool functions ---

def reply(key: str, **kwargs) -> str:
    """快捷回复及格式化函数"""
    text_or_list = _REPLY_DICT.get(key, None)
    if text_or_list is None:
        text_or_list = _REPLY_DICT.get("error", "未知错误")
    if isinstance(text_or_list, list):
        text = random.choice(text_or_list)
    else:
        text = text_or_list
    return text.format(**kwargs)

async def build_msg(matcher: Matcher, event: Event, msg_segments: list[tuple[str, Any]], tag: Literal['send', 'finish'] = 'send') -> None:
    """根据事件类型构建并发送消息对象"""
    
    if isinstance(event, OneBotV11Event):
        onebotv11_msg = OneBotV11Message()
        for type_, content in msg_segments:
            if type_ == "text":
                onebotv11_msg += OneBotV11MessageSegment.text(content)
            elif type_ == "image":
                onebotv11_msg += OneBotV11MessageSegment.image(content)
            elif type_ == "at":
                # QQ 端如果传入了元组 (username, user_id)，只取 user_id
                uid = content[1] if isinstance(content, tuple) else content
                onebotv11_msg += OneBotV11MessageSegment.at(uid) + ' '
            else:
                continue
                
        if not onebotv11_msg:
            return
        func = matcher.send if tag == 'send' else matcher.finish
        await func(onebotv11_msg)

    elif isinstance(event, TGEvent):
        tg_msg = TGMessage()
        for type_, content in msg_segments:
            if type_ == "text":
                tg_msg += TGMessageEntity.text(content)
            elif type_ == "image":
                tg_msg += TGMessageFile.photo(content)
            elif type_ == "at" and isinstance(content, tuple) and len(content) == 2:
                username, tg_user_id = content
                tg_msg += TGMessageEntity.text_link(f"{username}", f"tg://user?id={tg_user_id}") + ' '
            else:
                continue
                
        if not tg_msg:
            return
        func = matcher.send if tag == 'send' else matcher.finish
        await func(tg_msg)

def get_args(args_text: str) -> tuple[int | None, SERVER_TAG | Literal['ALL'] | None]:
    """服务器数据 args 拆分"""
    target_user_id, target_server = None, None
    if args_text:
        for arg in args_text.split(' '):
            if arg.isdigit() and not target_user_id:
                # 解析纯数字 QQ 号
                target_user_id = int(arg)
            if arg.upper() in ['JP', 'CN', 'ALL'] and not target_server:
                # 解析服务器字符串
                target_server = cast(SERVER_TAG | Literal['ALL'], arg.upper())
            if arg in ['全服'] and not target_server:
                target_server = 'ALL'
            if arg in ['日服', '日'] and not target_server:
                target_server = 'JP'
            if arg in ['国服', '国'] and not target_server:
                target_server = 'CN'
    return target_user_id, target_server

async def _build_sy_records_hash(records: list[dict[str, Any]]) -> str:
    """为水鱼 records 生成稳定 MD5 指纹。"""
    # dict 稳定序列化排序
    _stable_json_dumps = lambda data: orjson.dumps(data, option=orjson.OPT_SORT_KEYS)

    normalized_records = sorted(records, key=lambda item: _stable_json_dumps(item))
    payload = _stable_json_dumps(normalized_records)
    return hashlib.md5(payload).hexdigest()


# --- 准业务逻辑 ---

async def get_maiuser(event: Event, user_id: int | None = None) -> utils.MaiUser:
    """根据数据获取 MaiUser 对象"""
    if user_id is None:
        # 从 event 中获取
        raw_uid: str = event.get_user_id()
        try:
            user_id = int(raw_uid)
        except ValueError as e:
            # user_id 为 str 格式
            raise ValueError(reply("error_invalid_user_id", raw_uid=raw_uid)) from e

    if isinstance(event, OneBotV11Event):
        mu = await services.get_or_create_user_by_id(user_id)
    elif isinstance(event, TGEvent):
        mu = await services.get_user_by_telegram_id(user_id)
        if mu is None:
            raise NoLinkQQError(reply("error_user_not_found"))
    else:
        # platform event
        raise ValueError(reply("error_unexpected"))

    if not mu.username:
        qq = mu.user_id
        # 获取水鱼用户名并更新数据库
        data = cast(dict, await network.sy_dev_player_records(qq=qq, developer_token=DEVELOPER_TOKEN))
        username = data.get("nickname", "maimai")
        await services.set_username(qq, username)
        mu.username = username
    
    return mu.to_data()

async def get_maidata_with_ach(short_id: int, target_server: SERVER_TAG, user_id: int) -> Optional[tuple[utils.MaiData, SERVER_TAG]]:
    """获取乐曲数据并处理服务器回退逻辑"""
    mdt = await services.get_mdt_by_id(short_id, user_id)
    if not mdt:
        return None
        
    maidata = mdt.to_data(include_achs=True)
    # 核心回退逻辑：如果没有国服版本，强制回退到日服展示
    actual_server = target_server if maidata.version_cn is not None else "JP"
    
    # MaiData, 实际使用的服务器标签
    return maidata, actual_server

# --- Json Parser ---

async def onebotv11_read_json(bot: OneBotV11Bot, file_info: dict, file_id: str) -> Optional[Any]:
    """NapCat OneBotV11 JSON 文件解析"""
    file_base64 = file_info.get("base64")
    file_path_str = file_info.get("file")
    file_url = file_info.get("url")

    # 策略 1: Base64
    if file_base64:
        try:
            b64_data = file_base64.split(",")[1] if "," in file_base64 else file_base64
            return orjson.loads(base64.b64decode(b64_data))
        except Exception:
            logger.debug("Base64 解析失败，尝试下一策略")

    # 策略 2: 本地路径
    if file_path_str:
        file_path = Path(file_path_str)
        if file_path.exists():
            try:
                async with aiofiles.open(file_path, "rb") as f:
                    return orjson.loads(await f.read())
            except Exception as e:
                logger.debug(f"本地读取失败: {e}，尝试下一策略")

    # 策略 3: URL 下载
    if file_url and file_url.startswith("http"):
        try:
            return await network.request_json(file_url)
        except Exception as e:
            logger.debug(f"URL 请求失败: {e}，尝试下一策略")

    # 策略 4: NapCat 流式接管
    if file_id:
        try:
            async with NapCatStreamFile(bot, file_id) as stream_path:
                async with aiofiles.open(stream_path, "rb") as f:
                    return orjson.loads(await f.read())
        except Exception as e:
            logger.debug(f"流式接管失败: {e}")

    return None

async def tg_read_json(bot: TGBot, file_id: str) -> Optional[Any]:
    """Telegram JSON 文件解析"""
    try:
        tg_file_info = await bot.get_file(file_id=file_id)
        if tg_file_info.file_path:
            token = bot.bot_config.token  
            file_url = f"https://api.telegram.org/file/bot{token}/{tg_file_info.file_path}"
            return await network.request_json(file_url)
    except Exception as e:
        logger.error(f"Telegram 远程文件解析失败: {e}")
    return None


# =================================
# 业务逻辑
# =================================

# --- link ---

@link.handle()
async def link_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: link"""
    action, args_text = groups
    global link_cache, link_hash_index

    # 预先的遍历过期检查
    current_time = int(time.time())
    expired_hashes = []
    for uid, (h, exp) in list(link_cache.items()):
        if current_time > exp:
            expired_hashes.append(h)
            del link_cache[uid]
    
    for h in expired_hashes:
        if h in link_hash_index:
            del link_hash_index[h]
    
    # 查询分支
    if action == "查询":
        await matcher.finish(reply("link_query_disabled"))
        return
    
    # 获取/绑定分支
    elif action in ("获取", "绑定"):
        # 检查是否为 Onebot (QQ) 平台
        if not isinstance(event, OneBotV11Event):
            await matcher.finish(reply("link_only_qq"))
            return
        
        # 生成随机 hash 并设置五分钟到期
        import secrets
        hash_value = secrets.token_hex(8)
        expiration_time = int(time.time()) + 300
        
        # 存储到缓存中
        user_id = int(event.get_user_id())
        _ = await services.get_or_create_user_by_id(user_id)
        link_cache[user_id] = (hash_value, expiration_time)
        link_hash_index[hash_value] = user_id
        
        # 发送提示文案和绑定指令
        await matcher.send(reply("link_tip"))
        await matcher.finish(f"link {hash_value}")
        return
    
    # 解除/解绑分支
    elif action in ("解除", "解绑"):
        if isinstance(event, OneBotV11Event):
            # QQ 端解绑全部
            user_id = int(event.get_user_id())
            await services.remove_telegram_id(user_id)
            await matcher.finish(reply("link_unlink_success"))
            return
        elif isinstance(event, TGEvent):
            # TG 端解绑当前账号
            telegram_id = int(event.get_user_id())
            mu = await services.get_user_by_telegram_id(telegram_id)
            if mu:
                await services.remove_telegram_id(mu.user_id)
            await matcher.finish(reply("link_unlink_success"))
            return
        await matcher.finish(reply("link_not_platform"))
    
    # 验证分支（action为空）
    else:
        if not args_text:
            await matcher.finish(reply("link_invalid_hash"))
            return
        
        provided_hash = args_text.strip()
        
        # 通过反向索引直接查找
        if provided_hash not in link_hash_index:
            await matcher.finish(reply("link_not_found"))
            return
        
        user_id = link_hash_index[provided_hash]
        _, expiration_time = link_cache[user_id]
        
        # 验证成功，执行绑定逻辑
        if isinstance(event, OneBotV11Event):
            # 但 OneBotV11 不需要绑定 qq
            await matcher.finish(reply("link_onebot_no_bind"))
            return
        elif isinstance(event, TGEvent):
            await services.set_telegram_id(user_id, telegram_id=int(event.get_user_id()))
            
            # 清理缓存
            del link_cache[user_id]
            del link_hash_index[provided_hash]
            await matcher.finish(reply("link_success"))
            return
        
        # 非支持平台（理论上不会到达）
        await matcher.finish(reply("link_not_platform"))
        return

# --- adx_download ---

async def _get_adx_folder(bot: OneBotV11Bot, group_id: int) -> Optional[str]:
    """确保群内存在谱面文件夹，不存在则创建。返回 folder_id，失败返回 None"""
    ADX_FOLDER_NAME = "maib-adx"

    try:
        group_folder = await bot_services.get_group_root_files(bot, group_id)
    except Exception as e:
        logger.error(f"获取群文件夹失败: {e}")
        return None

    folder_id = None
    for folder in group_folder.get("folders", []):
        if folder.get("folder_name") == ADX_FOLDER_NAME:
            folder_id = folder.get("folder_id")
            break
            
    if not folder_id:
        try:
            created = await bot_services.create_group_file_folder(bot, group_id, ADX_FOLDER_NAME)
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return None
        folder_id = created.get("groupItem", {}).get("folderInfo", {}).get("folderId")
        
    return folder_id

async def _cleanup_expired_group_files(bot: OneBotV11Bot, group_id: int, folder_id: str):
    """清理指定文件夹下超过 72 小时的文件"""
    FILE_EXPIRE_SECONDS = 72 * 3600  # 72 小时
    
    files_info = await bot_services.get_group_files_by_folder(bot, group_id, folder_id)
    if isinstance(files_info, Exception):
        logger.error(f"获取群文件失败: {files_info}")
        return

    files = files_info.get("files", [])
    # 按照 modify_time 排序，从旧到新
    files.sort(key=lambda x: x.get("modify_time", 0))
    
    now = time.time()
    for file in files:
        modify_time = file.get("modify_time", 0)
        if now - modify_time > FILE_EXPIRE_SECONDS:
            try:
                f_id = file.get("file_id")
                await bot.call_api("delete_group_file", group_id=str(group_id), file_id=str(f_id))
                logger.info(f"已删除过期文件: {file.get('file_name')}")
            except Exception as e:
                logger.error(f"删除过期文件失败: {e}")
        else:
            # 由于已排序，遇到未过期的文件即可停止
            break

@adx_download.handle()
async def adx_download_handled(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()): 
    """处理命令: 下载谱面11568"""
    raw_short_id, archive_type = groups
    archive_type = archive_type.strip().lower()
    target_short_id: Optional[int] = int(raw_short_id) if raw_short_id.isdigit() else None

    if target_short_id is None:
        # 未显式指定 ID，尝试从回复消息中提取
        if isinstance(event, OneBotV11Event):
            if reply_msg := getattr(event, "reply", None):
                replied_text = str(reply_msg.message)
                match = re.search(r"(\d+)", replied_text)
                if match:
                    target_short_id = int(match.group(1))
                    logger.debug(f"从 OneBotV11 回复消息中提取到 short_id: {target_short_id}")
        elif isinstance(event, TGEvent):
            # 从 Telegram 回复中提取 short_id
            if reply_to_message := getattr(event, "reply_to_message", None):
                replied_text = str(getattr(reply_to_message, "text", "")) or str(getattr(reply_to_message, "caption", ""))
                match = re.search(r"(\d+)", replied_text)
                if match:
                    target_short_id = int(match.group(1))
                    logger.debug(f"从 TG 回复消息中提取到 short_id: {target_short_id}")

    if target_short_id is None:
        # 仍然未找到 ID，视为误触
        # **大家当做无事发生**
        return
    elif not (0 < target_short_id < 999999):
        await matcher.finish(reply("ad_bad_id"))
        return

    # 获取 MaiData
    mdt: Optional[models.MaiData] = await services.get_mdt_by_id(target_short_id)
    if not mdt:
        await matcher.finish(reply("ad_no_maidata", short_id=target_short_id))
        return
    chart_file_path = get_plugin_data_dir() / mdt.zip_path
    if not chart_file_path.exists():
        await matcher.finish(reply("ad_no_chart_file", short_id=target_short_id))
        return

    # 开始着手上传
    await matcher.send(reply("ad_prepare", target_short_id=target_short_id))
    
    file_ext = "zip" if "zip" in archive_type else "adx"
    file_name = f"{target_short_id}.{file_ext}"
    title = mdt.title

    if isinstance(event, OneBotV11Event) and isinstance(bot, OneBotV11Bot):
        # OneBotV11
        if isinstance(event, OneBotV11GroupMessageEvent):
            # 群消息
            group_id = event.group_id
            folder_id = await _get_adx_folder(bot, group_id)
            if not folder_id:
                await matcher.finish(reply("ad_error"))
                return
            try:
                result = await bot_services.update_group_file(bot, group_id, chart_file_path, file_name=file_name, folder_id=folder_id)
            except Exception as e:
                logger.error(f"上传失败: {e}")
                await matcher.finish(reply("ad_error"))
                return
            else:
                if result.get("file_id", None) is None:
                    await matcher.finish(reply("ad_error"))
                    return
            await matcher.send(reply("ad_group_success", song_name=title))
            # 清理逻辑
            await _cleanup_expired_group_files(bot, group_id, folder_id)
            
        elif isinstance(event, OneBotV11PrivateMessageEvent):
            # 私聊消息
            user_id = event.get_user_id()
            try:
                _ = await bot_services.upload_private_file(bot, user_id, chart_file_path, file_name=file_name)
            except Exception as e:
                logger.error(f"上传失败: {e}")
                await matcher.finish(reply("ad_error"))
                return
            await matcher.finish(reply("ad_private_success", song_name=title))
            
        else:
            # 其他类型消息，理论上不应触发该命令
            await matcher.finish(reply("ad_error"))
            return
    elif isinstance(event, TGEvent) and isinstance(bot, TGBot):
        session_id = event.get_session_id()
        chat_id = int(session_id.split("_")[-1])

        if mdt.tg_file_id_cache and file_ext == "adx":
            # tg 缓存只考虑 .adx 文件，zip 不常用因此不缓存
            # 未来可能考虑数据库增加adx和zip的双重缓存
            logger.debug(f"命中 Telegram file_id 缓存，正在触发秒传: {mdt.tg_file_id_cache}")
            try:
                # 缓存命中，尝试直接发送文件
                await bot.send_document(
                    chat_id=chat_id,
                    document=mdt.tg_file_id_cache
                )
                await matcher.send(reply("ad_private_success", song_name=title))
                return
            except Exception as e:
                # 极少情况下，TG 端的 file_id 可能会失效，需要重新上传
                logger.warning(f"缓存的 file_id 失效，将尝试重新上传: {e}")

        # 文件上传逻辑
        try:
            # 读取本地文件字节流
            if not chart_file_path.exists():
                await matcher.send(reply("ad_no_chart_file", short_id=target_short_id))
                return
                
            bytes_data = chart_file_path.read_bytes()
            tg_msg_obj = await bot.send_document(
                chat_id=chat_id,
                document=(file_name, bytes_data)
            )
            
            # 回写缓存
            new_file_id = None
            if tg_msg_obj and hasattr(tg_msg_obj, "document") and tg_msg_obj.document and file_ext == "adx":
                new_file_id = tg_msg_obj.document.file_id
                logger.debug(f"成功获取 file_id: {new_file_id}，正在写入缓存...")
                await services.update_mdt_tg_file_id(target_short_id, new_file_id)

            await matcher.send(reply("ad_tg_success", song_name=title))
            return
        except Exception as e:
            logger.error(f"Telegram 谱面文件上传失败: {e}")
            await matcher.finish(reply("ad_error"))
            return

    # 兜底逻辑
    await matcher.finish(reply("ad_error"))
    return

# --- mai_info ---

@mai_info.handle()
async def mai_info_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: id11451 / info11451"""
    _, short_id, args = groups
    # shortid 判断
    if not short_id.isdigit():
        await matcher.finish(reply("mai_info_no_shortid"))
        return
    shortid = int(short_id)

    try:
        maiuser = await get_maiuser(event)
        qq = int(maiuser.user_id)
        default_server = maiuser.default_server
    except NoLinkQQError as e:
        # 未绑定 QQ
        maiuser = None
        qq = None
        default_server = 'JP'  # 没有绑定 QQ 的用户默认展示日服数据
    except ValueError as e:
        await matcher.finish(str(e))
        return
    
    _, server = get_args(args)
    
    server = server if (server != 'ALL' and server is not None) else default_server  # 暂不支持 ALL
    # 查询乐曲信息
    if (mdt := await services.get_mdt_by_id(shortid, qq)) is None:
        await matcher.finish(reply("mai_info_no_maidata", short_id=shortid))
        return
    maidata = mdt.to_data(include_achs=True)
    s = server if maidata.version_cn is not None else "JP"  # 如果乐曲没有国服版本，则展示日服数据
    
    info_box = image_gen.draw_info_box(maidata, s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
    info_box_bytes = image_gen.get_image_bytes(info_box)
    
    payload = [
        ("text", f"{mdt.shortid}. {mdt.title}"),
        ("image", info_box_bytes)
    ]
    if qq is None:
        payload.append(("text", reply("link_get_more_info")))
    await build_msg(matcher, event, payload, tag='finish')

@mai_what_song.handle()
async def mai_what_song_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxx是什么歌"""
    keyword, all_tag = groups
    blur_search = bool(all_tag and all_tag.strip() in ['?', '？'])
    keyword = keyword.strip(' ')

    try:
        maiuser = await get_maiuser(event)
        qq = int(maiuser.user_id)
        server = maiuser.default_server
    except NoLinkQQError as e:
        # 未绑定 QQ
        maiuser = None
        qq = None
        server = 'JP'  # 没有绑定 QQ 的用户默认展示日服数据
    except ValueError as e:
        await matcher.finish(str(e))
        return

    try:
        # 搜索歌曲
        search_func = services.get_mdt_by_name_blur if blur_search else services.get_mdt_by_name_smart
        mdt_list = list(await search_func(keyword, achs_userid=qq))
    except ValueError as exc:
        await matcher.finish(str(exc))
        return
    
    # 过滤宴会场 (shortid >= 100000)
    # mdt_list = [mdt for mdt in mdt_list if mdt.shortid < 100000]
    if not mdt_list:
        await matcher.finish(reply("mws_found_no_results", keyword=keyword))
        return

    def generate_single_info_box(mdt) -> bytes:
        """生成单首乐曲的 info box 图片字节"""
        maidata = mdt.to_data(include_achs=True)
        s = server if maidata.version_cn is not None else "JP"
        info_box = image_gen.draw_info_box(maidata, server=s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
        return image_gen.get_image_bytes(info_box)

    # 输出结果
    payload = []
    
    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        payload.append(("text", reply("mws_found_one", shortid=mdt.shortid, title=mdt.title)))
        payload.append(("image", generate_single_info_box(mdt)))

    elif len(mdt_list) <= 4:
        payload.append(("text", reply("mws_found_multiple", count=len(mdt_list))))
        for mdt in mdt_list:
            payload.append(("image", generate_single_info_box(mdt)))

    elif len(mdt_list) <= 40:
        # 结果大于 4 首，采用简要列表图承载
        # TODO 采用类似于 b50 样式的可视化列表图（默认显示对应的最高难度）
        img = image_gen.simple_maidata_box([mdt.to_data() for mdt in mdt_list])
        img_bytes = image_gen.get_image_bytes(img)
        payload.append(("text", reply("mws_found_multiple_more", count=len(mdt_list))))
        payload.append(("image", img_bytes))

    else:
        await matcher.finish(reply("mws_found_too_many"))
        return

    # 4. 统一发送消息
    await build_msg(matcher, event, payload, tag='finish')

# --- mai_alias ---

@mai_alias.handle()
async def mai_alias_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: 添加别名 id11451 xxx / 删除别名 id11451 xxx"""
    action, shortid, alias = groups
    try:
        short_id = int(shortid)
        mdt: Optional[services.MaiData] = await services.get_mdt_by_id(short_id)
        if not mdt:
            raise ValueError
    except (ValueError, TypeError):
        await matcher.finish(reply("mai_info_no_shortid"))
        return
    
    try:
        maiuser = await get_maiuser(event)
    except ValueError as e:
        await matcher.finish(str(e))
        return

    qq = maiuser.user_id
    if isinstance(event, OneBotV11GroupMessageEvent):
        group_id = event.group_id
    elif isinstance(event, TGEvent):
        group_id = -3  # 标记：来自于 Telegram
    else:
        group_id = None

    if action == "添加":
        # 添加别名
        new_alias = await services.add_mdt_alias(short_id, alias, qq, group_id)
        if new_alias:
            await matcher.finish(reply("alias_added_successfully", shortid=shortid, alias=alias))
        else:
            await matcher.finish(reply("alias_already_exists"))
    else:
        await matcher.finish(reply("alias_deletion_not_supported"))

# --- ra_calc ---

@ra_calc.handle()
async def ra_calc_handled(matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: ra 13.2 100.1000"""
    info, rate = groups
    level: float = 0

    # 先解析 rate
    try:
        achievement = float(rate)
    except (ValueError, TypeError):
        achievement = RATE_ALIAS_MAP.get(rate.lower(), -100)

    # 1. 尝试以定数形式解析
    try:
        level = float(info)
    except (ValueError, TypeError):
        pass

    # 2. 判断定数是否越界，越界则解析为纯数字 id
    if level > 20:
        level = 0  # 大于 20 则一定不为定数，驳回上述解析
        try:
            shortid = int(info)
            mai = await services.get_mdt_by_id(shortid)
        except (ValueError, TypeError):
            mai = None
        if mai and mai.charts:
            level = mai.charts[-1].lv  # 取最高难度的定数

    # 3. 尝试以 id11451/info11451/id114514紫 形式解析
    if level == 0:
        # 通过正则提取 id
        match = re.search(r'\d+', info)
        diff_info = re.search('[绿黄红紫白]', info)
        if match and any([
            'id' in info.lower(),
            'info' in info.lower(),
            diff_info,
        ]):
            level_str = match.group(0)
            try:
                shortid = int(level_str)
                mai = await services.get_mdt_by_id(shortid)
            except (ValueError, TypeError):
                mai = None
            if mai:
                charts = mai.charts
                s = diff_info.group(0) if diff_info else ''
                diff = utils.parse_status(s, DIFFS_MAP)
                if diff:
                    # 指定了难度颜色，尝试匹配
                    for c in charts:
                        if c.difficulty == diff:
                            level = c.lv
                            break
                level = level if level else charts[-1].lv

    # 4. 尝试解析 歌名/别名
    if level == 0:
        pass  # todo: 未实现 歌名/别名解析

    # 解析结束
    if level == 0:
        await matcher.finish("小梨无法解析你提供的定数或歌曲信息喔TT")
        return

    # 调用 MaiChart 计算 DX Rating
    chart = MaiChart(shortid=0, difficulty=0, lv=level)
    chart.set_ach(MaiChartAch(shortid=0, difficulty=0, server="JP", achievement=achievement))
    ra = chart.get_dxrating()

    msg = f"小梨算出来咯！\n定数{level}*{achievement:.4f}% -> Rating: {ra}"
    if achievement >= 100.5:
        msg += "\n该 ra 不考虑 AP 的额外分数哦！"
    await matcher.finish(msg)

# --- sytb ---

async def get_sy_and_upload(user_id: int) -> MaiChartAchDiffReport:
    # 获取水鱼数据
    data = await network.sy_dev_player_records(qq=user_id, developer_token=DEVELOPER_TOKEN)
    records = data.pop('records', []) if data else []

    # records 稳定哈希一致时，直接短路跳过上传流程
    sy_hash = await _build_sy_records_hash(records)
    last_sy_hash = await services.get_last_sy_hash(user_id)
    if last_sy_hash == sy_hash:
        return MaiChartAchDiffReport()

    achs = utils.get_sy_records(records) if data else None
    # 批量上传到数据库
    if data is None or achs is None:
        return MaiChartAchDiffReport()

    report: MaiChartAchDiffReport = await services.upload_achievements_batch(user_id, achs)

    await services.set_last_sy_hash(user_id, sy_hash)
    return report

@sytb.handle()
async def sytb_handled(event: Event, matcher: Matcher):
    """处理命令: sytb (水鱼同步)"""
    try:
        user_id = int(event.get_user_id())
        maiuser: utils.MaiUser = await get_maiuser(event, user_id=user_id)
    except Exception as e:
        await matcher.finish(str(e))
        return

    # 更新水鱼数据并生成差异报告
    report = await get_sy_and_upload(maiuser.user_id)
    payload: list = [
        ("at", (maiuser.username, user_id)),
    ]

    if report.has_changes:
        await matcher.send(reply("sy_syncing"))
        summary_text, diff_img = build_diff_report(report)
        
        payload.append(("text", f"{summary_text}\n"))
        if diff_img:
            payload.append(("image", image_gen.get_image_bytes(diff_img)))
    else:
        payload.append(("text", reply("sy_no_updates")))

    await build_msg(matcher, event, payload, tag='finish')

# --- b50 ---

@b50.handle()
async def b50_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxxb50/xxxkkb xxx"""
    # 低内存模式，短路拦截
    if LOW_MEMORY_MODE:
        if LOW_MEMORY_TIP:
            await matcher.finish(LOW_MEMORY_TIP)
        return

    _, args_text = groups
    args_text = args_text.strip()
    sender_user_id = int(event.get_user_id())

    # 解析命令参数
    parsed_uid, target_server = get_args(args_text)
    server: SERVER_TAG = target_server if (target_server and target_server != 'ALL') else 'CN'

    if target_server == 'ALL':
        await matcher.finish(reply("b50_all_not_supported"))
        return

    # 解析用户
    at_qq = None
    parsed_qq = None
    sender_qq = None
    sender_username = "maimai"

    if isinstance(event, OneBotV11Event):
        parsed_qq = parsed_uid if parsed_uid else None
        sender_qq = sender_user_id
        for segment in event.get_message():
            if segment.type == "at":
                at_qq = int(segment.data["qq"])
                break

    elif isinstance(event, TGEvent):
        async def get_qq_from_tg_uid(tg_uid: int) -> Optional[int]:
            if tg_uid is None:
                return None
            mu = await services.get_user_by_telegram_id(tg_uid)
            return int(mu.user_id) if mu else None
        
        # parsed_qq = await get_qq_from_tg_uid(parsed_uid) if parsed_uid else None
        parsed_qq = None  # Telegram 目前不支持文本参数解析 QQ，预留接口但暂不启用
        sender_qq = await get_qq_from_tg_uid(sender_user_id)
        
        if from_ := getattr(event, "from_", None):
            sender_username = from_.username or from_.first_name or "maimai"
            
        # 预留给 TG 适配：从 entities 中提取 text_link 或 mention 的 user_id
        # at_uid = ...
        # at_username = ...
        at_qq = None  # Telegram 暂不支持 at
        pass

    # 确定最终被查询人 (优先级：at 目标 > 文本传参 > 发送者自己)
    target_qq = at_qq or parsed_qq or sender_qq
    is_querying_self = target_qq == sender_qq
    if target_qq is None:
        logger.warning(f"未能解析出目标 QQ，无法继续执行 b50 命令。平台：{type(event)}")
        await matcher.finish(reply("b50_no_target"))
        return
    try:
        target_maiuser = (await services.get_or_create_user_by_id(target_qq)).to_data()
    except ValueError as e:
        await matcher.finish(str(e))
        return

    # 获取 QQ 头像
    avatar_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={target_qq}&spec=100"
    avatar = await network.request_image(avatar_url)

    payload: list[tuple[str, Any]] = [("at", (sender_username, sender_user_id)), ("text", reply("b50_drawing"))]
    # extra. 查询内容含国服，强制刷新水鱼数据
    if server in ['CN', 'ALL']:
        try:
            report = await get_sy_and_upload(target_qq)
            if report.has_changes:
                # 有变化，考虑查询者是否在查询自己，展示不同的报告细节
                if is_querying_self:
                    summary_text, diff_img = build_diff_report(report)
                    sync_payload: list[tuple[str, Any]] = [
                        ("text", f"已同步水鱼数据！以下是水鱼数据的同步详情：\n\n{summary_text}")
                    ]
                    if diff_img:
                        sync_payload.append(("image", image_gen.get_image_bytes(diff_img)))
                    await build_msg(matcher, event, sync_payload, tag='send')
                    await build_msg(matcher, event, payload, tag='send')
                else:
                    # 查询他人：简化提示
                    payload[1] = ("text", reply("b50_other_updated_drawing"))
                    await build_msg(matcher, event, payload, tag='send')
            else:
                await build_msg(matcher, event, payload, tag='send')
        except Exception as e:
            logger.warning(f"强制刷新水鱼数据失败: {e}")
        
        # 由于进行了更新，刷新 MaiUser 数据
        target_maiuser = (await services.get_or_create_user_by_id(target_qq)).to_data()
    else:
        await build_msg(matcher, event, payload, tag='send')


    # 确定版本并获取 achs 数据
    ver_jp, ver_cn = utils.get_current_versions()
    current_version = ver_cn if server == 'CN' else ver_jp  # 目前不兼容 ALL 混合模式
    cut_version = services.get_cut_version(current_version)
    
    b35_achs, b15_achs = await services.get_mdts_for_b50(target_qq, server, cut_version)

    # 清洗谱面数据，构建绘图数据结构
    def _build_entries(achs: list[models.MaiChartAch]) -> list[tuple[utils.MaiData, int]]:
        entries = []
        for ach in achs:
            chart = ach.chart
            if not chart or not chart.maidata:
                continue
            maidata = chart.maidata.to_data()
            maidata.set_chart_ach(chart.difficulty, ach.to_data())
            entries.append((maidata, chart.difficulty))
        return entries

    b35_entries = _build_entries(list(b35_achs))
    b15_entries = _build_entries(list(b15_achs))

    if server == 'JP' and not (b35_entries or b15_entries):
        await build_msg(matcher, event, [("text", reply("b50_no_jp_data"))], tag='send')

    # 绘制 b50
    dxrating = target_maiuser.cn_dxrating if server == 'CN' else target_maiuser.jp_dxrating
    update_time = target_maiuser.get_formated_time(server)

    img = image_gen.draw_b50(
        b35_entries, b15_entries,
        current_version=current_version,
        server=server,
        user_name=target_maiuser.username,
        user_avatar=avatar,
        dxrating=dxrating,
        update_time=update_time,
        cn_level=1 if server == 'CN' else 0
    )
    img_bytes = image_gen.get_image_bytes(img)
    
    final_payload = [
        ("at", (sender_username, sender_user_id)),
        ("image", img_bytes)
    ]
    await build_msg(matcher, event, final_payload, tag='finish')


# TODO TG适配
@file_receiver.handle()
async def file_receiver_handled(bot: Bot, event: Event, matcher: Matcher):
    
    file_name: str = ""
    file_data: Optional[Any] = None

    # ---- 跨平台解析 JSON 数据 ----
    if isinstance(event, OneBotV11PrivateMessageEvent) and isinstance(bot, OneBotV11Bot):
        try:
            onebotv11_file_seg = event.get_message()["file"][0]
            onebotv11_file_id = cast(str, onebotv11_file_seg.data.get("file_id"))
            file_name = onebotv11_file_seg.data.get("file", "")
        except (KeyError, IndexError):
            return

        if not file_name.endswith(".json"):
            return

        file_info = await bot.get_file(file_id=onebotv11_file_id)
        file_data = await onebotv11_read_json(bot, file_info, onebotv11_file_id)

    elif isinstance(event, TGPrivateMessageEvent) and isinstance(bot, TGBot):
        tg_msg = event.telegram_model.message
        if not (tg_msg and tg_msg.document):
            return

        file_name = tg_msg.document.file_name or ""
        if not file_name.endswith(".json"):
            return

        file_data = await tg_read_json(bot, tg_msg.document.file_id)
        
        
    
    else:
        # 群消息或其他类型等消息，不做解析，静默退出
        return
    
    # 校验 file_name 和 file_data
    
    # 1. 数据必须是列表
    if not isinstance(file_data, list):
        return
    # 2. 列表不能为空
    if len(file_data) == 0:
        return
    # 3. 列表中必须包含 sheetId 字段
    if "sheetId" not in file_data[0]:
        return
    # 4. sheetId 中必须包含 __dxrt__ 字样
    if "__dxrt__" not in file_data[0].get("sheetId", ""):
        return

    # 落到数据解析
    await matcher.send("检查到 lyra-maimai 数据导出！正在识别曲目并记录成绩...")
    
    maiuser = await get_maiuser(event)
    user_id = maiuser.user_id
    
    ach_list = []
    title_type_cache: dict[tuple[str, str], int | None] = {}
    unmatched_titles: list[str] = []
    invalid_diff_items: list[str] = []
    parse_failed_items: list[str] = []

    def append_unique(items: list[str], value: str):
        value = value.strip()
        if value and value not in items:
            items.append(value)
    
    for record in file_data:
        try:
            title = str(record.get("title", "")).strip() or "Unknown"
            record_type = str(record.get("type", "sd")).lower() # 'sd' 或 'dx'
            
            if (title, record_type) not in title_type_cache:
                song_list = await services.get_mdt_by_title(title)
                if len(song_list) == 0:
                    title_type_cache[(title, record_type)] = None
                    logger.warning(f"无法找到曲目: {title}")
                    append_unique(unmatched_titles, title)
                    continue
                elif len(song_list) == 1:
                    title_type_cache[(title, record_type)] = song_list[0].shortid
                else:
                    filtered = []
                    if record_type == "dx":
                        filtered = [s for s in song_list if 100000 > s.shortid >= 10000]
                    elif record_type in ("sd", "std"):
                        filtered = [s for s in song_list if s.shortid < 10000]

                    if len(filtered) == 1:
                        title_type_cache[(title, record_type)] = filtered[0].shortid
                    else:
                        title_type_cache[(title, record_type)] = None
                        logger.warning(f"无法找到曲目: {title}，type: {record_type}")
                        append_unique(unmatched_titles, f"{title}[{record_type.upper()}]")
                        continue
 
            # 提取其他字段
            difficulty = DIFFS_MAP.get(record.get("diff", "").lower(), -1)
            if difficulty < 0:
                append_unique(invalid_diff_items, f"{title}[{record.get('diff', '?')}]")
                continue

            shortid = title_type_cache[(title, record_type)]
            if shortid is not None:
                ach_obj = MaiChartAch(
                    shortid=shortid,
                    difficulty=difficulty,
                    server=record.get("server", "JP"),
                    achievement=float(record.get("achievement", 0)),
                    dxscore=int(record.get("dxscore", 0)),
                    combo=DF_FC_MAP.get(record.get("combo", "").lower(), 0),
                    sync=DF_FS_MAP.get(record.get("sync", "").lower(), 0),
                    user_id=user_id
                )
                ach_list.append(ach_obj)

        except Exception as e:
            logger.warning(f"记录处理失败: {e}")
            if isinstance(record, dict):
                rec_title = str(record.get("title", "")).strip() or "(无标题)"
                append_unique(parse_failed_items, rec_title)
            continue

    if not ach_list:
        from .report import MaiChartAchDiffReport
        report = MaiChartAchDiffReport()
    else:
        try:
            report = await services.upload_achievements_batch(user_id, ach_list)
        except Exception as e:
            logger.error(f"数据库写入崩溃: {e}")
            await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")
            return

    # 将清洗循环中抓出来的脏数据塞入 report 对象中，实现全量漏报统计
    for title in unmatched_titles:
        report.no_data_song.append((0, title, -1))
    for title_diff in invalid_diff_items:
        report.other_error_song.append({"type": "invalid_diff", "msg": title_diff})
    for title_failed in parse_failed_items:
        report.other_error_song.append({"type": "parse_failed", "msg": title_failed})

    summary_text, diff_img = build_diff_report(
        report,
        file_count=len(file_data),
        parsed_count=len(ach_list)
    )

    # 构造跨平台兼容的统一消息负载
    payload: list[tuple[str, Any]] = [("text", summary_text)]
    if diff_img:
        payload.append(("image", image_gen.get_image_bytes(diff_img)))

    await build_msg(matcher, event, payload, tag='finish')

@get_sync_code.handle()
async def _(matcher: Matcher):
    await matcher.finish("lyra-sync 服务器尚未开放，请等待 API 开放后再试一下~")
