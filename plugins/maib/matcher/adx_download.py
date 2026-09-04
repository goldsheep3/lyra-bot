import asyncio
import re
import time
from typing import Any, Optional

from nonebot import logger, on_regex, on_notice
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Bot as OneBotV11Bot,
                                         Event as OneBotV11Event,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,
                                         GroupUploadNoticeEvent as OneBotV11GroupUploadNoticeEvent)

from nonebot.adapters.telegram import (Bot as TGBot,
                                       Event as TGEvent,)

from nonebot_plugin_localstore import get_plugin_data_dir

from . import rule_is_group, rule_is_self
from .. import services
from ..utils import file_api
from . import i18n_data, i18n, reply


# 下载谱面
adx_download = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)
# 群文件上传 notice，用于处理 upload_group_file 超时但实际成功的场景
group_upload_notice = on_notice(priority=1, block=False, rule=(rule_is_group and rule_is_self))


GROUP_UPLOAD_NOTICE_TIMEOUT: float = 90.0
_GROUP_UPLOAD_WAITERS: dict[tuple[int, str, int], list[asyncio.Future[dict[str, Any]]]] = {}


def _group_upload_waiter_key(group_id: int | str, file_name: str, file_size: int) -> tuple[int, str, int]:
    return int(group_id), file_name, int(file_size)


def _register_group_upload_waiter(
    group_id: int | str,
    file_name: str,
    file_size: int,
) -> tuple[tuple[int, str, int], asyncio.Future[dict[str, Any]]]:
    key = _group_upload_waiter_key(group_id, file_name, file_size)
    future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
    _GROUP_UPLOAD_WAITERS.setdefault(key, []).append(future)
    return key, future


def _remove_group_upload_waiter(key: tuple[int, str, int], future: asyncio.Future[dict[str, Any]]) -> None:
    waiters = _GROUP_UPLOAD_WAITERS.get(key)
    if not waiters:
        return
    try:
        waiters.remove(future)
    except ValueError:
        pass
    if not waiters:
        _GROUP_UPLOAD_WAITERS.pop(key, None)


def _is_call_api_timeout(exc: Exception, api_name: str) -> bool:
    message = str(exc).lower()
    return api_name in message and "timeout" in message


async def _wait_group_upload_notice(
    future: asyncio.Future[dict[str, Any]],
    timeout: float = GROUP_UPLOAD_NOTICE_TIMEOUT,
) -> Optional[dict[str, Any]]:
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
    except asyncio.TimeoutError:
        return None


@group_upload_notice.handle()
async def group_upload_notice_handled(event: OneBotV11GroupUploadNoticeEvent):
    file_name = event.file.name
    file_size = event.file.size
    group_id = event.group_id

    if not file_name or file_size is None:
        return

    key = _group_upload_waiter_key(group_id, file_name, int(file_size))
    waiters = _GROUP_UPLOAD_WAITERS.pop(key, [])
    
    for future in waiters:
        if not future.done():
            future.set_result(event.file.dict())


async def _get_adx_folder(bot: OneBotV11Bot, group_id: int) -> Optional[str]:
    """确保群内存在谱面文件夹，不存在则创建。返回 folder_id，失败返回 None"""
    ADX_FOLDER_NAME = "maib-adx"

    try:
        group_folder = await file_api.OneBotV11FileAPI.get_group_root_files(bot, group_id)
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
            created = await file_api.OneBotV11FileAPI.create_group_file_folder(bot, group_id, ADX_FOLDER_NAME)
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return None
        folder_id = created.get("groupItem", {}).get("folderInfo", {}).get("folderId")
        
    return folder_id

async def _cleanup_expired_group_files(bot: OneBotV11Bot, group_id: int, folder_id: str):
    """清理指定文件夹下超过 72 小时的文件"""
    FILE_EXPIRE_SECONDS = 72 * 3600  # 72 小时
    
    files_info = await file_api.OneBotV11FileAPI.get_group_files_by_folder(bot, group_id, folder_id)
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
async def adx_download_handled(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n): 
    """处理命令: 下载谱面11568"""
    i18n_data.set(_i18n)

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
        await matcher.finish(reply("ad.bad_id"))
        return

    # 获取 MaiData
    mdt: Optional[services.MaiData] = await services.get_mdt.id(target_short_id)
    if not mdt:
        await matcher.finish(reply("ad.no_maidata", short_id=target_short_id))
        return
    chart_file_path = get_plugin_data_dir() / mdt.zip_path
    if not chart_file_path.exists():
        await matcher.finish(reply("ad.no_chart_file", short_id=target_short_id))
        return

    # 开始着手上传
    await matcher.send(reply("ad.prepare", target_short_id=target_short_id))
    
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
                await matcher.finish(reply("ad.error"))
                return
            waiter_key, upload_notice_future = _register_group_upload_waiter(
                group_id,
                file_name,
                chart_file_path.stat().st_size,
            )
            try:
                result = await file_api.OneBotV11FileAPI.update_group_file(
                    bot,
                    group_id,
                    chart_file_path,
                    file_name=file_name,
                    folder_id=folder_id,
                    use_stream=True,
                )
            except Exception as e:
                logger.warning(f"上传异常类型: {type(e).__module__}.{type(e).__qualname__}: {e}")
                if not _is_call_api_timeout(e, "upload_group_file"):
                    logger.error(f"上传失败: {e}")
                    await matcher.finish(reply("ad.error"))
                    return

                logger.warning(f"群文件上传 API 超时，等待 group_upload notice 确认结果: {e}")
                notice_file = await _wait_group_upload_notice(upload_notice_future)
                if notice_file is None:
                    logger.error(f"上传失败: {e}")
                    await matcher.finish(reply("ad.error"))
                    return
                result = {"file_id": notice_file.get("id") or notice_file.get("file_id"), "file": notice_file}
            finally:
                _remove_group_upload_waiter(waiter_key, upload_notice_future)

            if result.get("file_id", None) is None:
                await matcher.finish(reply("ad.error"))
                return
            await matcher.send(reply("ad.success.qq_group", song_name=title))
            # 清理逻辑
            await _cleanup_expired_group_files(bot, group_id, folder_id)
            return
            
        elif isinstance(event, OneBotV11PrivateMessageEvent):
            # 私聊消息
            user_id = event.get_user_id()
            try:
                _ = await file_api.OneBotV11FileAPI.upload_private_file(
                    bot,
                    user_id,
                    chart_file_path,
                    file_name=file_name,
                    use_stream=True,
                )
            except Exception as e:
                logger.error(f"上传失败: {e}")
                await matcher.finish(reply("ad.error"))
                return
            else:
                await matcher.finish(reply("ad.success.qq_private", song_name=title))
                return
            
        else:
            # 其他类型消息，理论上不应触发该命令
            await matcher.finish(reply("ad.error"))
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
                await matcher.finish(reply("ad.success.tg", song_name=title))
                return
            except Exception as e:
                # 极少情况下，TG 端的 file_id 可能会失效，需要重新上传
                logger.warning(f"缓存的 file_id 失效，将尝试重新上传: {e}")

        # 文件上传逻辑
        try:
            # 读取本地文件字节流
            if not chart_file_path.exists():
                await matcher.send(reply("ad.no_chart_file", short_id=target_short_id))
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
                await services.upd_mdt_tg_fileid(target_short_id, new_file_id)

            await matcher.finish(reply("ad.success.tg", song_name=title))
            return
        except Exception as e:
            logger.error(f"Telegram 谱面文件上传失败: {e}")
            await matcher.finish(reply("ad.error"))
            return

    logger.warning(f"未处理的事件类型: {type(event)} 或 bot 类型: {type(bot)}")
    return  # 兜底 return
