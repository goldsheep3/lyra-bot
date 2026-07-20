import hashlib
from pathlib import Path
from typing import Optional, Any, cast

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

from .. import config, utils, services, image_gen, network, sync
from ..utils.report import MaiChartAchDiffReport, build_diff_report
from ..utils import MaiChartAch
from ..constants import DIFFICULTY_MAP, COMBO_MAP, SYNC_MAP
from . import i18n_data, i18n, reply, rule_is_private
from .context import get_maiuser
from .message import build_msg

sytb = on_regex(r'^sytb$', priority=5, block=True)

file_receiver = on_message(priority=25, rule=rule_is_private)

get_sync_code = on_regex(r"^获取同步码$", priority=5, block=True)


# --- Json Parser ---

async def onebotv11_read_json(bot: OneBotV11Bot, file_info: dict, file_id: str) -> Optional[Any]:
    """NapCat OneBotV11 JSON 文件解析"""
    file_path_str = file_info.get("file")

    # 策略 1: 本地路径
    if file_path_str:
        file_path = Path(file_path_str)
        if file_path.exists():
            try:
                async with aiofiles.open(file_path, "rb") as f:
                    return orjson.loads(await f.read())
            except Exception as e:
                logger.debug(f"本地读取失败: {e}，尝试 stream 接管")
        else:
            logger.debug("本地文件路径不存在，尝试 stream 接管")

    # 策略 2: NapCat 流式接管
    if file_id:
        try:
            async with utils.OneBotV11FileAPI.download_file_stream_to_temp_file(bot, file_id) as stream_path:
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

async def _build_sy_records_hash(records: list[dict[str, Any]]) -> str:
    """为水鱼 records 生成稳定 MD5 指纹。"""
    # dict 稳定序列化排序
    _stable_json_dumps = lambda data: orjson.dumps(data, option=orjson.OPT_SORT_KEYS)

    normalized_records = sorted(records, key=lambda item: _stable_json_dumps(item))
    payload = _stable_json_dumps(normalized_records)
    return hashlib.md5(payload).hexdigest()

# --- sytb ---

async def get_sy_and_upload(user_id: int) -> MaiChartAchDiffReport:
    # 获取水鱼数据
    data = await network.DivingFish.dev_player_records(qq=user_id, developer_token=config.DIVING_FISH_DEVELOPER_TOKEN)
    records = data.pop('records', []) if data else []

    # records 稳定哈希一致时，直接短路跳过上传流程
    sy_hash = await _build_sy_records_hash(records)
    last_sy_hash = await services.get_last_sy_hash(user_id)
    if last_sy_hash == sy_hash:
        return MaiChartAchDiffReport()

    achs = sync.get_sy_records(records) if data else None
    # 批量上传到数据库
    if data is None or achs is None:
        return MaiChartAchDiffReport()

    report: MaiChartAchDiffReport = await services.upd_ach_batch(user_id, achs)

    await services.set_last_sy_hash(user_id, sy_hash)
    return report

@sytb.handle()
async def sytb_handled(event: Event, matcher: Matcher, _i18n = i18n):
    """处理命令: sytb (水鱼同步)"""
    i18n_data.set(_i18n)

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
        await matcher.send(reply("sync.sy.syncing"))
        summary_text, diff_img = build_diff_report(report)
        
        payload.append(("text", f"{summary_text}\n"))
        if diff_img:
            payload.append(("image", image_gen.get_image_bytes(diff_img)))
    else:
        payload.append(("text", reply("sync.sy.no_update")))

    await build_msg(matcher, event, payload, tag='finish')


@file_receiver.handle()
async def file_receiver_handled(bot: Bot, event: Event, matcher: Matcher, _i18n = i18n):
    i18n_data.set(_i18n)
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
                song_list = await services.get_mdt.title(title, way='title')
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
            difficulty = DIFFICULTY_MAP.key(record.get("diff", "").lower()) or -1
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
                    combo=COMBO_MAP.key(record.get("combo", "").lower()) or 0,
                    sync=SYNC_MAP.key(record.get("sync", "").lower()) or 0,
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
        report = MaiChartAchDiffReport()
    else:
        try:
            report = await services.upd_ach_batch(user_id, ach_list)
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
async def _(matcher: Matcher, _i18n = i18n):
    i18n_data.set(_i18n)
    await matcher.finish("lyra-sync 服务器尚未开放，请等待 API 开放后再试一下~")
