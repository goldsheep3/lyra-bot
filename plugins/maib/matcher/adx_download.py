import asyncio
import re
import time
from typing import Any, Optional
from pathlib import Path

from nonebot import logger, on_regex, on_notice
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Bot as OneBotV11Bot,
                                         Event as OneBotV11Event,
                                         MessageEvent as OneBotV11MessageEvent,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,
                                         GroupUploadNoticeEvent as OneBotV11GroupUploadNoticeEvent)
from nonebot.adapters.onebot.v11.exception import NetworkError

from nonebot.adapters.telegram import Bot as TGBot, Event as TGEvent
from nonebot.adapters.telegram.event import MessageEvent as TGMessageEvent

from nonebot_plugin_localstore import get_plugin_data_dir

from . import rule_is_group, rule_is_self
from .. import services
from ..utils import file_api
from . import Reply, reply


def rule_is_group_upload_notice(event: Event) -> bool:
    return isinstance(event, OneBotV11GroupUploadNoticeEvent)


# 下载谱面
adx_download = on_regex(r"^下载[铺谱]面\s*(?:[iI][dD])?\s*(\d+)\s*(.*)$", priority=10, block=True)
adx_download_en = on_regex(r"^download\s*(?:[iI][dD])?\s*(\d+)\s*(.*)$", priority=10, block=True)
# 群文件上传 notice，用于处理 upload_group_file 超时但实际成功的场景
group_upload_notice = on_notice(priority=1, block=False, rule=(rule_is_group and rule_is_self and rule_is_group_upload_notice))


GROUP_UPLOAD_NOTICE_TIMEOUT: float = 90.0
_GROUP_UPLOAD_WAITERS: dict[tuple[int, str, int], list[asyncio.Future[dict[str, Any]]]] = {}
FILE_EXPIRE_SECONDS = 72 * 3600  # 72 小时
ADX_FOLDER_NAME = "maib-adx"



@group_upload_notice.handle()
async def group_upload_notice_handled(event: OneBotV11GroupUploadNoticeEvent):
    """处理群文件上传 notice，唤醒等待的 future"""
    file_name: str = event.file.name
    file_size: int = event.file.size
    qq_group: int = event.group_id

    if not file_name or file_size is None:
        return

    key = (qq_group, file_name, file_size)
    waiters = _GROUP_UPLOAD_WAITERS.pop(key, [])
    
    for future in waiters:
        if not future.done():
            future.set_result(event.file.dict())


async def _cleanup_expired_group_files(bot: OneBotV11Bot, qq_group: int, folder: str):
    """清理指定文件夹下超过 72 小时的文件"""    
    files_info = await file_api.OneBotV11FileAPI.get_group_files_by_folder(bot, qq_group, folder)
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
                await bot.call_api("delete_group_file", group_id=str(qq_group), file_id=str(f_id))
                logger.info(f"已删除过期文件: {file.get('file_name')}")
            except Exception as e:
                logger.error(f"删除过期文件失败: {e}")
        else:
            # 由于已排序，遇到未过期的文件即可停止
            break


async def _get_or_create_adx_folder(bot: OneBotV11Bot, qq_group: int) -> Optional[str]:
    """获取或创建 ADX_FOLDER_NAME 文件夹"""
    try:
        root_folder = await file_api.OneBotV11FileAPI.get_group_root_files(bot, qq_group)
        for fd in root_folder.get("folders", []):
            if fd.get("folder_name") == ADX_FOLDER_NAME:
                return fd["folder_id"]

        # 未找到文件夹，尝试创建
        created = await file_api.OneBotV11FileAPI.create_group_file_folder(bot, qq_group, ADX_FOLDER_NAME)
        return created.get("groupItem", {}).get("folderInfo", {}).get("folderId")

    except Exception as e:
        logger.error(f"群文件夹获取失败: {type(e).__module__}.{type(e).__qualname__}: {e}")
        return None


async def onebot_v11_group_upload(
    bot: OneBotV11Bot,
    qq_group: int,
    file_name: str,
    file_path: Path,
    file_size: int,
    folder: Optional[str] = None
) -> Optional[Exception]:
    """处理 OneBotV11 群文件上传请求"""
    # 尝试查找或创建 ADX_FOLDER_NAME 文件夹    
    # 锁定等待
    lock_key = (qq_group, file_name, file_size)
    lock_future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
    _GROUP_UPLOAD_WAITERS.setdefault(lock_key, []).append(lock_future)

    # 尝试上传文件
    try:
        result = await file_api.OneBotV11FileAPI.update_group_file(
            bot=bot, group_id=qq_group, file_path=file_path, file_name=file_name, folder_id=folder, use_stream=True
        )

    except NetworkError as e:
        logger.info(f"群文件上传 API 超时，等待 group_upload notice 确认结果")
        try:
            notice_file = await asyncio.wait_for(asyncio.shield(lock_future), timeout=GROUP_UPLOAD_NOTICE_TIMEOUT)
            result = {"file_id": notice_file.get("id") or notice_file.get("file_id"), "file": notice_file}
        except asyncio.TimeoutError:
            # 确认超时
            return e

    except Exception as e:
        return e

    finally:
        # 清理锁定等待
        if waiters := _GROUP_UPLOAD_WAITERS.get(lock_key):
            try:
                waiters.remove(lock_future)
            except ValueError:
                pass
        else:
            _GROUP_UPLOAD_WAITERS.pop(lock_key, None)
    
    if result.get("file_id", None) is None:
        return Exception("未获取到 file_id")

    # 文件夹清理逻辑
    if folder:
        await _cleanup_expired_group_files(bot, qq_group, folder)
    return None


async def telegram_upload(
    bot: TGBot,
    chat_id: int,
    shortid: int,
    file_name: str,
    file_path: Path,
) -> Optional[Exception]:
    """处理 Telegram 文件上传请求"""
    if not file_path.exists():
        return IOError(f"文件不存在: {file_path}")

    file_bytes = file_path.read_bytes()
    try:
        tg_msg_obj = await bot.send_document(
            chat_id=chat_id,
            document=(file_name, file_bytes)
        )
    except Exception as e:
        return e

    # 回写缓存
    file_id = None
    if tg_msg_obj.document and file_name.endswith(".adx"):
        file_id = tg_msg_obj.document.file_id
        await services.upd_mdt_tg_fileid(shortid, file_id)
    return None

@adx_download.handle()
@adx_download_en.handle()
async def adx_download_handled(
    bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup(), reply: Reply = reply): 
    """处理命令: 下载谱面11568"""
    # 硬编码拦截：OneBotV11 私聊暂时不支持谱面下载
    if isinstance(event, OneBotV11PrivateMessageEvent):
        await matcher.finish("由于部分原因，暂停私聊谱面发送，请通过支持的群聊或加入 672460250 下载谱面~")
        return

    raw_short_id, archive_type = groups
    archive_type = archive_type.strip().lower()
    target_short_id: Optional[int] = int(raw_short_id)

    if target_short_id is None:
        # 未显式指定 ID，尝试从回复消息中提取
        replied_text = None
        if isinstance(event, OneBotV11MessageEvent):
            if reply_msg := event.reply:
                replied_text = reply_msg.message.extract_plain_text()
        elif isinstance(event, TGMessageEvent):
            if reply_msg := event.reply_to_message:
                replied_text = reply_msg.message.extract_plain_text()

        if replied_text:
            if match := re.search(r"(\d+)", replied_text):
                target_short_id = int(match.group(1))

    if target_short_id is None:
        # 仍然未找到 ID，视为误触
        # **大家当做无事发生**
        return

    if not (0 < target_short_id < 999999):
        # ID 不合法
        await matcher.finish(await reply("ad.bad_id"))
        return

    # 获取 MaiData
    mdt: Optional[services.MaiData] = await services.get_mdt.id(target_short_id)
    if not mdt:
        await matcher.finish(await reply("ad.no_maidata", short_id=target_short_id))
        return
    chart_file_path = get_plugin_data_dir() / mdt.zip_path
    if not chart_file_path.exists():
        await matcher.finish(await reply("ad.no_chart_file", short_id=target_short_id))
        return

    # 开始着手上传
    await matcher.send(await reply("ad.prepare", target_short_id=target_short_id))
    
    file_ext = "zip" if "zip" in archive_type else "adx"
    file_name = f"{target_short_id}.{file_ext}"
    title = mdt.title

    if isinstance(event, OneBotV11MessageEvent) and isinstance(bot, OneBotV11Bot):
        # OneBotV11
        if isinstance(event, OneBotV11GroupMessageEvent):
            # 群消息
            folder = await _get_or_create_adx_folder(bot, event.group_id)
            e = await onebot_v11_group_upload(
                bot=bot,
                qq_group=event.group_id,
                file_name=file_name,
                file_path=chart_file_path,
                file_size=chart_file_path.stat().st_size,
                folder=folder,
            )
            if e is not None:
                logger.error(f"OneBotV11 群聊上传失败: [{type(e).__module__}.{type(e).__qualname__}] {e}")
                await matcher.finish(await reply("ad.error"))
                return
            if not folder:
                await matcher.finish(await reply("ad.warn.no_folder", folder_name=ADX_FOLDER_NAME, song_name=title))
            else:
                await matcher.finish(await reply("ad.success.qq_group", song_name=title))
            
        elif isinstance(event, OneBotV11PrivateMessageEvent):
            # 私聊消息
            try:
                await file_api.OneBotV11FileAPI.upload_private_file(
                    bot,
                    event.get_user_id(),
                    chart_file_path,
                    file_name=file_name,
                    use_stream=True,
                )
            except Exception as e:
                logger.error(f"OneBotV11 私聊上传失败: [{type(e).__module__}.{type(e).__qualname__}] {e}")
                await matcher.finish(await reply("ad.error"))
                return
            await matcher.finish(await reply("ad.success.qq_private", song_name=title))

    elif isinstance(event, TGMessageEvent) and isinstance(bot, TGBot):
        session_id = event.get_session_id()
        chat_id = int(session_id.split("_")[-1])

        if mdt.tg_file_id_cache and file_ext == "adx":
            # tg 缓存只考虑 .adx 文件，zip 不常用因此不缓存
            # 未来可能考虑数据库增加adx和zip的双重缓存
            try:
                # 缓存命中，尝试直接发送文件
                await bot.send_document(
                    chat_id=chat_id,
                    document=mdt.tg_file_id_cache
                )
                logger.info(f"Telegram file_id 缓存命中，已触发秒传: {mdt.tg_file_id_cache}")
                await matcher.finish(await reply("ad.success.tg", song_name=title))
                return
            except Exception as e:
                # 极少情况下，TG 端的 file_id 可能会失效，需要重新上传
                logger.warning(f"Telegram 缓存失效: [{type(e).__module__}.{type(e).__qualname__}] {e}")
        
        # 触发 TG 普通上传逻辑
        e = await telegram_upload(
            bot=bot,
            chat_id=chat_id,
            shortid=target_short_id,
            file_name=file_name,
            file_path=chart_file_path
        )
        if e is not None:
            logger.error(f"Telegram 上传失败: [{type(e).__module__}.{type(e).__qualname__}] {e}")
            await matcher.finish(await reply("ad.error"))
            return
        await matcher.finish(await reply("ad.success.tg", song_name=title))
