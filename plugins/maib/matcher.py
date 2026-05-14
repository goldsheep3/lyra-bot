import base64
import hashlib
import re
import time
from pathlib import Path
from typing import Optional, List, Any, cast

import aiofiles
import orjson
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import utils, services, image_gen, bot_services, network
from .napcat_stream import NapCatStreamFile
from .report import build_achievements_report, build_import_report
from .utils import MaiChart, MaiChartAch
from .models import MaiChartAch as MaiChartAchModel
from .constants import *
from .bot_registry import PluginRegistry

from nonebot import logger, on_regex, on_message
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed


LOW_MEMORY_MODE: bool = False  # 低内存模式，会阻止 B50 等大型图片合成
LOW_MEMORY_TIP: str | None = None
DEVELOPER_TOKEN: Optional[str] = None


# --- rule ---

# 规则：必须是私聊事件，且消息段中包含 file
def is_private_file():
    async def _check(event: MessageEvent) -> bool:
        return isinstance(event, PrivateMessageEvent) and \
               any(seg.type == "file" for seg in event.get_message())
    return Rule(_check)

# --- matcher ---

# 下载谱面
adx_download = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (id / info)
mai_info = on_regex(r"^(id|info)(\d+)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (是什么歌)
mai_what_song = on_regex(r"^(.+?)是什么歌([?？]?)$", priority=10, block=True)
# 设置乐曲别名
alias_setting = on_regex(r'^(添加|删除)别名\s+(?:id)?(\d+)\s+([^\s]+)$', priority=5, block=True)
# 列表查询（完成表/进度/列表）
scorelist = on_regex(r'^(.*?)\s*(完成表|进度|列表)$', priority=5, block=True)
# 同步水鱼数据
sync_sy = on_regex(r'^sytb$', priority=5, block=True)
# b50 查询
b50 = on_regex(r'^(b50|kkb)\s*(.*)$', priority=1, block=True)
# ra 计算
ra_calc = on_regex(r"^ra\s+(\S+)?\s+(\S+)", priority=5, block=True)
# 上传 JSON 配置数据
file_receiver = on_message(priority=25, rule=is_private_file())
# 获取 code
get_code = on_regex(r"^获取code$", priority=5, block=True, rule=is_private_file())

# --- tool functions ---

def to_int(val):
    try:
        return int(val)
    except Exception:
        return None

def get_args(args_text: str) -> tuple[int | None, SERVER_TAG | Literal['ALL'] | None]:
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


async def _finish_with_optional_image(matcher: Matcher, text: str, image_bytes: bytes, *, fallback_text: str | None = None):
    try:
        await matcher.finish(Message([
            MessageSegment.text(text),
            MessageSegment.image(image_bytes),
        ]))
    except ActionFailed as exc:
        logger.warning(f"图片发送失败，已降级为纯文本: {exc}")
        await matcher.finish(fallback_text or text)


def _stable_json_dumps(data: Any) -> bytes:
    """稳定序列化：固定 key 顺序并去除空白，避免顺序差异导致 hash 变化。"""
    return orjson.dumps(data, option=orjson.OPT_SORT_KEYS)


def _build_sy_records_hash(records: list[dict[str, Any]]) -> str:
    """为水鱼 records 生成稳定 MD5 指纹。"""
    normalized_records = sorted(records, key=lambda item: _stable_json_dumps(item))
    payload = _stable_json_dumps(normalized_records)
    return hashlib.md5(payload).hexdigest()


# =================================
# 业务逻辑
# =================================

@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()): 
    """处理命令: 下载谱面11568"""

    raw_short_id, archive_type = groups
    archive_type = archive_type.strip().lower()
    short_id = int(raw_short_id) if raw_short_id.isdigit() else -1

    if short_id <= 0:
        # 只有在没有显式输入 ID 的情况下才尝试从回复提取
        if reply := getattr(event, "reply", None):
            replied_text = str(reply.message)
            match = re.search(r"(\d+)", replied_text)
            if match:
                short_id = int(match.group(1))
                logger.debug(f"从回复消息中提取到 short_id: {short_id}")

        # 仍然未找到 ID，视为误触
        # **大家当做无事发生**
        if short_id <= 0:
            return

    # 获取谱面信息
    mdt = await services.get_mdt_by_id(short_id)
    if not mdt:
        await matcher.finish("小梨没有找到这个谱面！可能还没被收录，请联系监护人确认喔qwq")
        return

    chart_file_path = Path(mdt.zip_path)
    if not chart_file_path.is_absolute():
        chart_file_path = PluginRegistry.get_data_dir() / chart_file_path
    if not chart_file_path or not chart_file_path.exists():
        logger.warning(f"谱面 id {short_id} 不存在: {chart_file_path}")
        await matcher.finish("小梨没有找到这个谱面！可能还没被收录，请联系监护人确认喔qwq")
        return

    await matcher.send(f"请稍候——小梨开始准备 id {short_id} 的谱面文件啦！")

    # 4. 上传逻辑
    file_ext = "zip" if "zip" in archive_type else "adx"
    file_name = f"{short_id}.{file_ext}"
    song_name = mdt.title

    group_id = getattr(event, "group_id", None)
    
    if not group_id:
        user_id = event.get_user_id()
        result = await bot_services.upload_private_file(bot, user_id, chart_file_path, file_name=file_name)
        if isinstance(result, Exception) or result.get("file_id", None) is None:
            logger.error(f"上传失败: {result}")
            await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.finish(f"登登~请查收 {song_name} 谱面！")
    else:
        group_folder = await bot_services.get_group_root_files(bot, group_id)
        if isinstance(group_folder, Exception):
            await matcher.send("出现了意外问题，上传失败了qwq")
            logger.error(f"获取群文件夹失败: {group_folder}")
            return
        folder_id = None
        for folder in group_folder.get("folders", []):
            if folder.get("folder_name") == "maib-adx":
                folder_id = folder.get("folder_id")
                break
        if not folder_id:
            # 没有找到 maib-adx 文件夹，尝试创建
            created = await bot_services.create_group_file_folder(bot, group_id, "maib-adx")
            if isinstance(created, Exception):
                logger.error(f"创建文件夹失败: {created}")
                await matcher.send("出现了意外问题，上传失败了qwq")
                return
            folder_id = created.get("groupItem", {}).get("folderInfo", {}).get("folderId")

        result = await bot_services.update_group_file(bot, group_id, chart_file_path, file_name=file_name, folder_id=folder_id)
        if isinstance(result, Exception) or result.get("file_id", None) is None:
            logger.error(f"上传失败: {result}")
            await matcher.send("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.send(f"小梨已经帮你把 {song_name} 的谱面传到群里啦！")
        
        # 群文件：旧文件检查机制
        # 1. `get_group_root_files` 检查 `maib-adx` 文件夹是否存在
        # 2. 获取 `maib-adx` 文件夹内的文件，根据时间排序，超过 72 小时的文件视为过期文件，进行删除
        files = await bot_services.get_group_files_by_folder(bot, group_id, folder_id)
        if isinstance(files, Exception):
            logger.error(f"获取群文件失败: {files}")
            return
        files = files.get("files", [])
        # 按照 modify_time 排序，删除超过 72 小时的文件
        files.sort(key=lambda x: x.get("modify_time", 0))
        now = time.time()
        for file in files:
            modify_time = file.get("modify_time", 0)
            if now - modify_time > 72 * 3600:
                try:
                    file_id = file.get("file_id")
                    await bot.call_api("delete_group_file", group_id=str(group_id), file_id=str(file_id))
                    logger.info(f"已删除过期文件: {file.get('file_name')}")
                except Exception as e:
                    logger.error(f"删除过期文件失败: {e}")
            else:
                # 文件未过期，后续文件更不需要检查，直接结束逻辑
                break
        logger.info(f"删除过期文件完成")
        return

async def get_username(event, bot, user_id: int | None = None) -> str:
    resolved_name = ""
    group_id = getattr(event, "group_id", None)
    user_id = user_id or int(event.get_user_id())

    if group_id:
        try:
            member_info = await bot.get_group_member_info(group_id=int(group_id), user_id=user_id)
            resolved_name = str(member_info.get("card") or member_info.get("nickname") or "").strip()
        except Exception:
            pass

    if not resolved_name:
        try:
            user_info = await bot.get_stranger_info(user_id=user_id)
            resolved_name = str(user_info.get("nickname") or "").strip()
        except Exception:
            pass

    return resolved_name



@mai_info.handle()
async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: id11451 / info11451"""
    _, short_id, args = groups
    user_id = int(event.get_user_id())
    maiuser = await services.get_or_set_user_by_id(user_id)
    if not maiuser.username:
        maiuser.username = await get_username(event, bot)
    _, server = get_args(args)
    # 暂不支持 ALL
    server = server if (server != 'ALL' and server is not None) else maiuser.default_server
    # 2 days 水鱼过期检查
    if server == 'CN' and (time.time() - maiuser.get_update_time(server=server) > 2 * 24 * 3600):
        pass
        # await matcher.send(Message(
        #     f"检测到国服数据过期，已同步最新的国服数据：") + MessageSegment.image(diff_bytes)
        # )
    
    # shortid 判断
    if (shortid := to_int(short_id)) is None:
        await matcher.finish("请提供正确的乐曲 ID 哦qwq")
        return
    # 查询乐曲信息
    if (mdt := await services.get_mdt_by_id(shortid, user_id)) is None:
        await matcher.finish(f"没有找到 id{shortid} 的乐曲数据qwq")
        return
    maidata = mdt.to_data(include_achs=True)
    s = server if maidata.version_cn is not None else "JP"  # 如果乐曲没有国服版本，则展示日服数据
    
    info_box = image_gen.draw_info_box(maidata, s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
    info_box_bytes = image_gen.get_image_bytes(info_box)
    
    await matcher.finish(Message(f"{mdt.shortid}. {mdt.title}") + MessageSegment.image(info_box_bytes))


@mai_what_song.handle()
async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxx是什么歌"""
    keyword, all_tag = groups
    blur_search = bool(all_tag and all_tag.strip() in ['?', '？'])
    keyword = keyword.strip(' ')
    user_id = int(event.get_user_id())
    maiuser = await services.get_or_set_user_by_id(user_id)
    if not maiuser.username:
        maiuser.username = await get_username(event, bot)
    server = maiuser.default_server

    # 不带问号为智能搜索，带问号进行强制搜索
    try:
        mdt_list: List[services.MaiData] = list((
            await services.get_mdt_by_name_blur(keyword, achs_userid=user_id) if blur_search else
            await services.get_mdt_by_name_smart(keyword, achs_userid=user_id)))
    except ValueError as exc:
        await matcher.finish(str(exc))
        return
    mdt_list = [mdt for mdt in mdt_list if mdt.shortid < 100000]  # 忽略宴会场
    if not mdt_list:
        await matcher.finish(f"没有找到包含「{keyword}」的乐曲数据qwq")
        return

    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        maidata = mdt.to_data(include_achs=True)
        s = server if maidata.version_cn is not None else "JP"  # 如果乐曲没有国服版本，则展示日服数据
        info_box = image_gen.draw_info_box(maidata, server=s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
        info_box_bytes = image_gen.get_image_bytes(info_box)
        await matcher.finish(Message([
            MessageSegment.text(f"找到了乐曲 {mdt.shortid}. {mdt.title}"),
            MessageSegment.image(info_box_bytes)
        ]))

    elif len(mdt_list) <= 4:
        segments = [MessageSegment.text(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下乐曲！")]
        for mdt in mdt_list:
            maidata = mdt.to_data(include_achs=True)
            s = server if maidata.version_cn is not None else "JP"
            info_box = image_gen.draw_info_box(maidata, server=s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
            img_bytes = image_gen.get_image_bytes(info_box)
            segments.append(MessageSegment.image(img_bytes))
        await matcher.finish(Message(segments))

    else:
        # TODO 以 b50_box 承载曲目信息
        img = image_gen.simple_maidata_box([mdt.to_data() for mdt in mdt_list])
        img_bytes = image_gen.get_image_bytes(img)
        await matcher.finish(Message([
            MessageSegment.text(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下是否有你的目标！"),
            MessageSegment.image(img_bytes)
        ]))
        return


@alias_setting.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: 添加别名 id11451 xxx / 删除别名 id11451 xxx"""
    action, shortid, alias = groups
    try:
        short_id = int(shortid)
        mdt: Optional[services.MaiData] = await services.get_mdt_by_id(short_id)
        if not mdt:
            raise ValueError
    except (ValueError, TypeError):
        await matcher.finish("请提供正确的乐曲 ID 哦qwq")
        return

    user_id = int(event.get_user_id())
    group_id = getattr(event, "group_id", None)
    group_id = int(group_id) if group_id else None

    if action == "添加":
        # 添加别名
        new_alias = await services.add_mdt_alias(short_id, alias, user_id, group_id)
        if new_alias:
            await matcher.finish(f"成功为 {shortid} 添加别名【{alias}】！")
        else:
            await matcher.finish("这个别名似乎已经存在了捏~")
    else:
        await matcher.finish("还不支持自主删除别名喔，请联系监护人处理~")


@ra_calc.handle()
async def _(matcher: Matcher, groups: tuple = RegexGroup()):
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


async def get_sy_and_upload(user_id: int) -> list[dict] | None:
    # 获取水鱼数据
    data = await network.sy_dev_player_records(qq=user_id, developer_token=DEVELOPER_TOKEN)
    records = data.get('records', []) if data else []

    # records 稳定哈希一致时，直接短路跳过上传流程
    sy_hash = _build_sy_records_hash(records)
    last_sy_hash = await services.get_last_sy_hash(user_id)
    if last_sy_hash == sy_hash:
        return None

    achs = utils.get_sy_records(records) if data else None
    # 批量上传到数据库
    if data is None or achs is None:
        return None

    data_diffs = await services.upload_achievements_batch(user_id, achs)
    await services.set_last_sy_hash(user_id, sy_hash)
    if not data_diffs:
        return None

    return data_diffs


@sync_sy.handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: sytb"""
    user_id = int(event.get_user_id())
    data_diffs = await get_sy_and_upload(user_id)
    if data_diffs:
        await matcher.send("正在进行水鱼数据同步")
        summary_text, diff_img = build_achievements_report(data_diffs)
        if diff_img:
            img_bytes = image_gen.get_image_bytes(diff_img)
            await matcher.finish(Message([
                MessageSegment.text(f"{summary_text}\n"),
                MessageSegment.image(img_bytes),
            ]))
        else:
            await matcher.finish(summary_text)
        return

    await matcher.finish("已完成水鱼同步，似乎没有数据更新~")


@b50.handle()
async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxxb50/xxxkkb xxx"""
    # Low Memory Block
    if LOW_MEMORY_MODE:
        if LOW_MEMORY_TIP:
            await matcher.finish(LOW_MEMORY_TIP)
        return
    _, args_text = groups
    user_id = int(event.get_user_id())
    target_user_id, target_server = None, None
    args_text: str = args_text.strip()
    if args_text:
        args = args_text.split(' ')
        for arg in args:
            if (not target_user_id) and arg.isdigit():
                target_user_id = int(arg)  # 其次解析纯数字 QQ 号
            if (not target_server) and arg.lower() in ['jp', 'cn', 'all']:
                target_server = arg.upper()  # 解析服务器信息
            if (not target_server) and arg in ['日服', '日']:
                target_server = 'JP'
            if (not target_server) and arg in ['国服', '国']:
                target_server = 'CN'
        for segment in event.get_message():
            if segment.type == "at":
                target_user_id = int(segment.data["qq"])  # 优先解析 @ 的用户信息
                break
    target_user_id = target_user_id or user_id  # 最后默认使用发送者的 QQ 号
    avatar = await network.request_image(f"http://q2.qlogo.cn/headimg_dl?dst_uin={target_user_id}&spec=100")
    server: SERVER_TAG | Literal['ALL'] = cast(SERVER_TAG | Literal['ALL'], target_server or 'CN')
    
    # 同步水鱼数据
    if server in ['CN', 'ALL']:
        data_diffs = await get_sy_and_upload(target_user_id)
        if data_diffs:
            if target_user_id == user_id:
                # 如果查询目标是自己，同步数据给予提示
                await matcher.send("发现数据更新，正在进行水鱼数据同步，稍等喵~\n由于当前代码质量偏低，更新速度可能较慢，请耐心等待（")
                summary_text, diff_img = build_achievements_report(data_diffs)
                if diff_img:
                    img_bytes = image_gen.get_image_bytes(diff_img)
                    await matcher.send(Message([
                        MessageSegment.text(f"{summary_text}\n"),
                        MessageSegment.image(img_bytes),
                        MessageSegment.text("\n水鱼数据同步完成！开始生成 B50 图片~"),
                    ]))
                else:
                    await matcher.send(Message([
                        MessageSegment.text(f"{summary_text}\n"),
                        MessageSegment.text("\n水鱼数据同步完成！开始生成 B50 图片~"),
                    ]))
            else:
                # 如果查询目标是他人，不直接展示差异图，改为提示已同步
                await matcher.send("已经同步TA的水鱼数据，开始生成 B50 图片~")
        else:
            await matcher.send("B50 图片生成中，请稍等~")

    ver_jp, ver_cn = utils.get_current_versions()
    if server == 'ALL':
        await matcher.finish("暂时还不支持全服查询qwq")
        return
    current_version = ver_cn if server == 'CN' else ver_jp

    target_maiuser = await services.get_or_set_user_by_id(target_user_id)
    if not target_maiuser.username:
        target_maiuser.username = await get_username(event, bot, user_id=target_user_id)
    cut_version = services.get_cut_version(server)
    b35_achs, b15_achs = await services.get_mdts_for_b50(target_user_id, server, cut_version)

    def _build_entries(achs: list[services.MaiChartAch] | tuple[services.MaiChartAch, ...]):
        entries: list[tuple[utils.MaiData, int]] = []
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
        # 提醒通过 lyra-sync 上传 JP 数据
        await matcher.send("你还没有日服数据！可以通过 lyra-sync 上传成绩后再试哦！")

    dxrating = target_maiuser.cn_dxrating if server == 'CN' else target_maiuser.jp_dxrating
    update_time = target_maiuser.get_formated_time(server)

    # 记录生成开始时间
    generate_start_time = time.time()
    img = image_gen.draw_b50(b35_entries, b15_entries,
                             current_version=current_version,
                             server=server,
                             user_name=target_maiuser.username,
                             user_avatar=avatar,
                             dxrating=dxrating,
                             update_time=update_time,
                             cn_level=1 if server == 'CN' else 0)

    img_bytes = image_gen.get_image_bytes(img)
    # 计算生成耗时
    generate_time = time.time() - generate_start_time
    logger.info(f"B50 生成耗时: {generate_time:.2f}秒")
    
    await matcher.finish(Message([
        MessageSegment.at(event.get_user_id()),
        MessageSegment.text(f" \nB50 生成时间: {generate_time:.2f}秒\n"),
        MessageSegment.image(img_bytes),
    ]))


@file_receiver.handle()
async def _(bot: Bot, event: PrivateMessageEvent, matcher: Matcher):

    # 获取文件
    file_seg = event.get_message()["file"][0]
    file_id = file_seg.data.get("file_id")
    file_name = file_seg.data.get("file", "")
    if not file_name.endswith(".json"):
        return

    file_info = await bot.get_file(file_id=file_id)
    file_path = Path(file_info.get("file", "")) if file_info.get("file") else None
    file_url = file_info.get("url", None)
    file_base64 = file_info.get("base64", None)
    
    file_data = None
    # 1. base64 直接读取
    if file_base64:
        try:
            if "," in file_base64:
                file_base64 = file_base64.split(",")[1]
            content = base64.b64decode(file_base64)
            file_data = orjson.loads(content)
        except:
            logger.warning("base64 解码失败，尝试其他方式读取文件")
    # 2. 本地路径读取
    if not file_data and file_path and file_path.exists():
        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
                file_data = orjson.loads(content)
            logger.info(f"成功从本地路径读取文件: {file_path}")
        except Exception as e:
            logger.warning(f"本地读取失败，尝试其他方式读取文件: {e}")
    # 3. URL 下载读取
    if not file_data and file_url:
        if file_url.startswith("http"):
            try:
                file_data = await network.request_json(file_url)
            except Exception as e:
                logger.error(f"网络请求失败: {e}")
        else:
            logger.warning(f"URL 协议错误: {file_url}")
    # 4. NapCat 流式接管
    if not file_data and file_id:
        try:
            async with NapCatStreamFile(bot, file_id) as stream_path:
                async with aiofiles.open(stream_path, "rb") as f:
                    content = await f.read()
                file_data = orjson.loads(content)
            logger.info(f"成功从 NapCat 流式接管读取文件: {file_id}")
        except Exception as e:
            logger.warning(f"流式接管失败: {e}")
    # E. 失败
    if not file_data:
        await matcher.finish("读取或解析文件失败，请重试。")

    # 校验数据格式
    if not all([
        isinstance(file_data, list),  # 数据必须是列表
        len(file_data) > 0,  # 列表不能为空
        "sheetId" in file_data[0],  # 必须包含 sheetId 字段
        '__dxrt__' in file_data[0].get("sheetId")  # sheetId 中必须包含 __dxrt__ 字样
    ]):
        # 格式不正确，静默失败（可能是其他插件识别的文件，不进行失败提醒）
        return

    # 落到数据解析
    await matcher.send("检查到 lyra-maimai 数据导出！正在识别曲目并记录成绩...")
    user_id = int(event.get_user_id())
    ach_list = []
    title_cache = {}  # 缓存标题查询结果
    unmatched_titles: list[str] = []
    invalid_diff_items: list[str] = []
    parse_failed_items: list[str] = []

    def append_unique(items: list[str], value: str):
        value = value.strip()
        if value and value not in items:
            items.append(value)
    
    for record in file_data:
        try:
            title = str(record.get("title", "")).strip() or "(无标题)"
            record_type = str(record.get("type", "sd")).lower() # 'sd' 或 'dx'
            
            if title not in title_cache:
                song = await services.get_mdt_by_title(title)
                if not song:
                    title_cache[title] = None
                title_cache[title] = song.shortid if song else None

            base_id = title_cache[title]
            if base_id is None:
                logger.warning(f"无法找到曲目: {title}")
                append_unique(unmatched_titles, title)
                continue

            # --- 关键：SD/DX ID 偏移逻辑 ---
            if record_type == "dx":
                # DX 曲目：如果是基础 ID (<10000)，则补足 10000
                shortid = base_id + 10000 if base_id < 10000 else base_id
            else:
                # SD 曲目：如果是偏移 ID (>=10000)，则剔除 10000
                shortid = base_id - 10000 if base_id >= 10000 else base_id

            # 提取其他字段
            difficulty = DIFFS_MAP.get(record.get("diff", "").lower(), -1)
            if difficulty < 0:
                append_unique(invalid_diff_items, f"{title}[{record.get('diff', '?')}]")
                continue

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
            logger.warning(f"单条记录处理失败: {e}")
            if isinstance(record, dict):
                rec_title = str(record.get("title", "")).strip() or "(无标题)"
                append_unique(parse_failed_items, rec_title)
            continue

    # 4. 批量上传与报告生成
    data_diffs: list[dict] | None = None
    if ach_list:
        try:
            data_diffs = await services.upload_achievements_batch(user_id, ach_list)
        except Exception as e:
            logger.error(f"数据库写入崩溃: {e}")
            await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")
            return

    # TODO 造成过 Exception: nonebot.adapters.onebot.v11.exception.ActionFailed
    # ActionFailed(status='failed', retcode=1200, data=None, message='EventChecker Failed: NTEvent serviceAndMethod:NodeIKernelMsgService/sendMsg ListenerName:NodeIKernelMsgListener/onMsgInfoListUpdate EventRet:\n{\n    "result": -1,\n    "errMsg": "rich media transfer failed"\n}\n', wording='EventChecker Failed: NTEvent serviceAndMethod:NodeIKernelMsgService/sendMsg ListenerName:NodeIKernelMsgListener/onMsgInfoListUpdate EventRet:\n{\n    "result": -1,\n    "errMsg": "rich media transfer failed"\n}\n', echo='9', stream='normal-action')
    summary_text, warning_text, detail_img = build_import_report(
        data_diffs,
        file_count=len(file_data),
        parsed_count=len(ach_list),
        unmatched_titles=unmatched_titles,
        invalid_diff_items=invalid_diff_items,
        parse_failed_items=parse_failed_items,
    )

    if detail_img:
        img_bytes = image_gen.get_image_bytes(detail_img)
        await _finish_with_optional_image(
            matcher,
            f"{summary_text}\n\n以下是本次成绩变更明细：\n{warning_text}",
            img_bytes,
            fallback_text=f"{summary_text}{warning_text}",
        )

    await matcher.finish(f"{summary_text}{warning_text}")


@get_code.handle()
async def _(matcher: Matcher):
    await matcher.finish("lyra-sync 服务器尚未开放，请等待 API 开放后再试一下~")


# === TEMP ===

# 仅用于最近 DXRating 明显错误问题的修复尝试
temp_refresh = on_regex(r'sudo refresh', priority=100, block=True, temp=True)

@temp_refresh.handle()
async def _(matcher: Matcher):
    await matcher.send("开始全量重算 DXRating，请稍等喵~")

    jp_current_version, cn_current_version = utils.get_current_versions()
    current_version_by_server: dict[SERVER_TAG, int] = {
        "JP": jp_current_version,
        "CN": cn_current_version,
    }

    affected_user_ids: dict[SERVER_TAG, set[int]] = {
        "JP": set(),
        "CN": set(),
    }
    total_count = 0

    async with PluginRegistry.get_session() as session:
        statement = select(MaiChartAchModel).options(selectinload(MaiChartAchModel.chart))
        result = await session.execute(statement)
        achs = result.scalars().all()

        if not achs:
            await matcher.finish("没有找到任何 MaiChartAch 记录，已跳过重算。")
            return

        for ach in achs:
            
            chart = ach.chart
            if not chart:
                continue

            maichart = chart.to_data()
            ach_data = ach.to_data()
            ach_data.user_id = ach.user_id or 0
            maichart.set_ach(ach_data)

            current_version = current_version_by_server[ach.server]
            ap_bonus = 1 if 2000 > current_version >= 25 else 0
            ach.dxrating = maichart.get_dxrating(server=ach.server, ap_bonus=ap_bonus, user_id=ach.user_id)

            if ach.user_id is not None:
                affected_user_ids[ach.server].add(ach.user_id)
            total_count += 1

        for server in ("JP", "CN"):
            if affected_user_ids[server]:
                await services.refresh_user_dxrating_cache_batch(
                    user_ids=list(affected_user_ids[server]),
                    server=server,
                    session=session,
                )

        await session.commit()

    await matcher.finish(
        f"全量重算完成，共处理 {total_count} 条 MaiChartAch 记录，"
        f"已刷新 {len(affected_user_ids['JP']) + len(affected_user_ids['CN'])} 个用户缓存。"
    )
    
