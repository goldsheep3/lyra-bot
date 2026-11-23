import hashlib
from pathlib import Path
from typing import Optional, Any, cast
from datetime import datetime, timedelta

import aiofiles
import orjson

from nonebot import logger, on_message, on_regex
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Bot, Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Bot as OneBotV11Bot,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,)

from nonebot.adapters.telegram import Bot as TGBot
from nonebot.adapters.telegram.event import PrivateMessageEvent as TGPrivateMessageEvent

from .. import config, utils, services, image_gen, network
from ..utils.report import MaiChartAchDiffReport, build_diff_report
from ..utils.sync import build_legacy_lyra_ach_list, build_lyra_records_v3, parse_lyra_maisync_data
from . import Reply, reply, rule_is_private
from .message import build_msg
from .context import get_or_create_maiuser

sytb = on_regex(r'^sytb$', priority=5, block=True)

file_receiver = on_message(priority=25, rule=rule_is_private, block=False)

get_sync_code = on_regex(r"^获取同步码$", priority=5, block=True)


async def onebot_v11_read_file(bot: OneBotV11Bot, file_id: str) -> Optional[bytes]:
    """NapCat OneBotV11 文件解析"""
    file_info = await bot.get_file(file_id=file_id)
    file_path_str = file_info.get("file")
    
    # 策略 1: 本地路径
    if file_path_str:
        file_path = Path(file_path_str)
        if file_path.exists():
            try:
                async with aiofiles.open(file_path, "rb") as f:
                    return await f.read()
            except Exception as e:
                logger.debug(f"本地读取失败: {e}，尝试 stream 接管")
        else:
            logger.debug("本地文件路径不存在，尝试 stream 接管")

    # 策略 2: NapCat 流式接管
    if file_id:
        try:
            async with utils.OneBotV11FileAPI.download_file_stream_to_temp_file(bot, file_id) as stream_path:
                async with aiofiles.open(stream_path, "rb") as f:
                    return await f.read()
        except Exception as e:
            logger.debug(f"流式接管失败: {e}")

    return None

async def onebotv11_read_json(bot: OneBotV11Bot, file_id_or_bytes: str | bytes) -> Optional[Any]:
    """NapCat OneBotV11 JSON 文件解析"""
    
    file_bytes = await onebot_v11_read_file(bot, file_id_or_bytes) if isinstance(file_id_or_bytes, str) else file_id_or_bytes
    if file_bytes is not None:
        try:
            return orjson.loads(file_bytes)
        except Exception as e:
            logger.debug(f"JSON 解析失败: {e}")
            return None
    return None

async def tg_read_file(bot: TGBot, file_id: str) -> Optional[bytes]:
    """Telegram 文件解析为原始字节。"""
    try:
        tg_file_info = await bot.get_file(file_id=file_id)
        if tg_file_info.file_path:
            token = bot.bot_config.token
            file_url = f"https://api.telegram.org/file/bot{token}/{tg_file_info.file_path}"
            return await network.request_bytes(file_url)
    except Exception as e:
        logger.error(f"Telegram 远程文件解析失败: {e}")
    return None


async def tg_read_json(bot: TGBot, file_id: str) -> Optional[Any]:
    """Telegram JSON 文件解析"""
    file_bytes = await tg_read_file(bot, file_id)
    if file_bytes is not None:
        try:
            return orjson.loads(file_bytes)
        except Exception as e:
            logger.debug(f"Telegram JSON 解析失败: {e}")
    return None

async def _build_sy_records_hash(records: list[dict[str, Any]]) -> str:
    """为水鱼 records 生成稳定 MD5 指纹。"""
    # dict 稳定序列化排序
    _stable_json_dumps = lambda data: orjson.dumps(data, option=orjson.OPT_SORT_KEYS)

    normalized_records = sorted(records, key=lambda item: _stable_json_dumps(item))
    payload = _stable_json_dumps(normalized_records)
    return hashlib.md5(payload).hexdigest()


# --- CN 更新线路---

async def get_sy_and_upload(user_id: int) -> MaiChartAchDiffReport:
    # 获取水鱼数据
    data = await network.DivingFish.dev_player_records(qq=user_id)
    records = data.pop('records', []) if data else []

    # records 稳定哈希一致时，直接短路跳过上传流程
    sy_hash = await _build_sy_records_hash(records)
    is_new = await services.achievement.is_diving_fish_source_current(qq=user_id, hash=sy_hash)
    if is_new:
        return MaiChartAchDiffReport()

    achs = utils.sync.get_sy_records(records) if data else None
    # 批量上传到数据库
    if data is None or achs is None:
        return MaiChartAchDiffReport()

    return await services.achievement.update_achievements(qq=user_id, ach_list=achs, diving_fish_hash=sy_hash)



async def check_sync_cn(*, qq: int, ignore_cache_expire: bool = False) -> MaiChartAchDiffReport | None:
    # 1. 统一获取 MaiUser 对象
    maiuser = await services.user.get_or_create_from_qq(qq)
    
    # 2. 缓存有效性检查
    if not ignore_cache_expire:
        cache_ttl = timedelta(hours=config.DATA_PROVIDER_CACHE_EXPIRATION)
        # 兼容 naive/aware 时间戳：cn_update_at 在 PostgreSQL(timestamptz) 下是 aware、
        # 在 SQLite 下是 naive，直接与 datetime.now() 相减会因类型不一致抛 TypeError，
        # 故按 last_update 是否带时区选取同类型的 now。
        last_update = maiuser.cn_update_time
        now = datetime.now(last_update.tzinfo) if last_update.tzinfo is not None else datetime.now()
        if now - last_update < cache_ttl:
            # 缓存未过期，直接返回
            return None
    
    # 3. 执行同步并获取差异报告
    report = await get_sy_and_upload(qq)
    
    return report


@sytb.handle()
async def sytb_handled(event: Event, matcher: Matcher, reply: Reply = reply):
    """处理命令: sytb (水鱼同步)"""
    user_id = int(event.get_user_id())
    maiuser = await get_or_create_maiuser(event, target_id=user_id)
    if maiuser.user_id is None:
        await matcher.finish(await reply("link.get_more_info"))
        return

    # 更新水鱼数据并生成差异报告
    report = await get_sy_and_upload(maiuser.user_id)
    payload: list = [
        ("at", (maiuser.username, user_id)),
    ]

    if report.has_changes:
        await matcher.send(await reply("sync.sy.syncing"))
        summary_text, diff_img = build_diff_report(report)
        
        payload.append(("text", f"{summary_text}\n"))
        if diff_img:
            payload.append(("image", image_gen.get_image_bytes(diff_img)))
    else:
        payload.append(("text", await reply("sync.sy.no_update")))

    await build_msg(matcher, event, payload, tag='finish')


@get_sync_code.handle()
async def get_sync_code_handled(event: Event, matcher: Matcher, reply: Reply = reply):
    maiuser = await get_or_create_maiuser(event)
    if maiuser.user_id is None:
        await matcher.finish(await reply("link.get_more_info"))
        return

    issue = await services.websync.create_pairing_code(qq=maiuser.user_id)
    expires_text = issue.expires_at.strftime("%Y-%m-%d %H:%M:%S")
    await matcher.finish(
        "在线同步配对码如下，5 分钟内仅可使用一次。\n"
        "重新获取同步码会立即使旧 token 失效。\n\n"
        f"{issue.code}\n\n"
        f"过期时间：{expires_text}"
    )


# --- JP 更新线路 ---

@file_receiver.handle()
async def file_receiver_handled(bot: Bot, event: Event, matcher: Matcher, reply: Reply = reply):
    file_name: str = ""
    file_version: Optional[str] = None
    file_data: Optional[Any] = None

    if isinstance(event, OneBotV11PrivateMessageEvent) and isinstance(bot, OneBotV11Bot):
        # OneBotV11 文件消息解析
        try:
            onebotv11_file_seg = event.get_message()["file"][0]
            onebotv11_file_id = cast(str, onebotv11_file_seg.data.get("file_id"))
            file_name = onebotv11_file_seg.data.get("file", "")
        except (KeyError, IndexError):
            return

        if file_name.endswith(".json"):
            file_data = await onebotv11_read_json(bot, file_id_or_bytes=onebotv11_file_id)
        else:
            file_bytes = await onebot_v11_read_file(bot, onebotv11_file_id)
            if file_bytes is not None:
                try:
                    file_data, file_version = parse_lyra_maisync_data(file_bytes)
                except Exception as e:
                    logger.debug(f"lyra-maisync 数据解析失败: {e}")
                    return

    elif isinstance(event, TGPrivateMessageEvent) and isinstance(bot, TGBot):
        # Telegram 文件消息解析
        tg_msg = event.telegram_model.message
        if not (tg_msg and tg_msg.document):
            return
        file_name = tg_msg.document.file_name or ""

        if file_name.endswith(".json"):
            file_data = await tg_read_json(bot, tg_msg.document.file_id)
        else:
            file_bytes = await tg_read_file(bot, tg_msg.document.file_id)
            if file_bytes is not None:
                try:
                    file_data, file_version = parse_lyra_maisync_data(file_bytes)
                except Exception as e:
                    logger.debug(f"Telegram lyra-maisync 数据解析失败: {e}")
                    return

    else:
        return  # 静默退出未被捕获的其他情况

    maiuser = await get_or_create_maiuser(event)
    user_id = maiuser.user_id
    file_version = file_version or "v0.2.3"  # dxrating.net 兼容脚本的默认版本号

    if not isinstance(file_data, list) or len(file_data) == 0:
        return

    if file_version == "v0.2.3":
        # v0.2.3 / dxrating.net 兼容脚本的导入逻辑，检查 sheetId 字段
        if "sheetId" not in file_data[0]:
            return
        if "__dxrt__" not in file_data[0].get("sheetId", ""):
            return

        await matcher.send("lyra-maisync v0.2.3 脚本数据导入中~请稍等片刻~")

        title_type_cache: dict[tuple[str, str], tuple[Optional[int], str]] = {}

        async def resolve_shortid(title: str, record_type: str) -> tuple[Optional[int], str]:
            key = (title, record_type)
            if key in title_type_cache:
                return title_type_cache[key]

            song_list = await services.catalog.search_maidata(
                title,
                mode="title",
            )
            if len(song_list) == 0:
                logger.warning(f"无法找到曲目: {title}")
                result = (None, title)
            elif len(song_list) == 1:
                result = (song_list[0].shortid, title)
            else:
                filtered = []
                if record_type == "dx":
                    filtered = [s for s in song_list if 100000 > s.shortid >= 10000]
                elif record_type in ("sd", "std"):
                    filtered = [s for s in song_list if s.shortid < 10000]

                if len(filtered) == 1:
                    result = (filtered[0].shortid, title)
                else:
                    logger.warning(f"无法找到曲目: {title}，type: {record_type}")
                    result = (None, f"{title}[{record_type.upper()}]")

            title_type_cache[key] = result
            return result

        legacy_result = await build_legacy_lyra_ach_list(
            file_data,
            user_id=user_id,
            resolve_shortid=resolve_shortid,
        )

        if not legacy_result.ach_list:
            report = MaiChartAchDiffReport()
        else:
            try:
                report = await services.achievement.update_achievements(qq=user_id, ach_list=legacy_result.ach_list)
            except Exception as e:
                logger.error(f"数据库写入崩溃: {e}")
                await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")
                return

        for title in legacy_result.unmatched_titles:
            report.no_data_song.append((0, title, -1))
        for title_diff in legacy_result.invalid_diff_items:
            report.other_error_song.append({"type": "invalid_diff", "msg": title_diff})
        for title_failed in legacy_result.parse_failed_items:
            report.other_error_song.append({"type": "parse_failed", "msg": title_failed})

        summary_text, diff_img = build_diff_report(
            report,
            file_count=len(file_data),
            parsed_count=len(legacy_result.ach_list),
        )

        payload: list[tuple[str, Any]] = [("text", summary_text)]
        if diff_img:
            payload.append(("image", image_gen.get_image_bytes(diff_img)))

        await build_msg(matcher, event, payload, tag='finish')
        return

    if file_version.startswith("v0.3."):
        # v0.3.0 / *.json.gz.b64 版本的导入逻辑
        await matcher.send("lyra-maisync3 脚本数据导入中~请稍等片刻~")

        parsed_result = build_lyra_records_v3(file_data, user_id=user_id)

        try:
            report = await services.record.ingest_records(parsed_result.records, qq=user_id)
        except Exception as e:
            logger.error(f"成绩记录入库失败: {e}")
            await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")
            return

        for title_diff in parsed_result.invalid_diff_items:
            report.other_error_song.append({"type": "invalid_diff", "msg": title_diff})
        for title_failed in parsed_result.parse_failed_items:
            report.other_error_song.append({"type": "parse_failed", "msg": title_failed})

        summary_text, diff_img = build_diff_report(
            report,
            file_count=len(file_data),
            parsed_count=len(parsed_result.records),
        )

        payload: list[tuple[str, Any]] = [("text", summary_text)]
        if diff_img:
            payload.append(("image", image_gen.get_image_bytes(diff_img)))

        await build_msg(matcher, event, payload, tag='finish')
        return
