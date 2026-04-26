import io
import bisect
import re
import time
from pathlib import Path
from typing import Optional, List, cast
from dataclasses import dataclass

import aiofiles
import orjson

from . import utils, services, image_gen, bot_services, network
from .utils import MaiChart, MaiChartAch
from .constants import *

from nonebot import logger, on_regex, on_message
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent, PrivateMessageEvent


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
    if not chart_file_path or not chart_file_path.exists():
        logger.warning(f"谱面 id {short_id} 不存在")
        await matcher.finish("小梨没有找到这个谱面！可能还没被收录，请联系监护人确认喔qwq")
        return

    await matcher.send(f"请稍候——小梨开始准备 id {short_id} 的谱面文件啦！")

    # 4. 上传逻辑
    file_ext = "zip" if "zip" in archive_type else "adx"
    file_name = f"{short_id}.{file_ext}"
    song_name = mdt.title

    group_id = getattr(event, "group_id", None)
    
    if group_id:
        result = await bot_services.update_group_file(bot, group_id, chart_file_path, file_name=file_name)
        if result:
            logger.error(f"上传失败: {result}")
            await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.finish(f"小梨已经帮你把 {song_name} 的谱面传到群里啦！")
    else:
        user_id = event.get_user_id()
        result = await bot_services.upload_private_file(bot, user_id, chart_file_path, file_name=file_name)
        if result:
            logger.error(f"上传失败: {result}")
            await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.finish(f"登登~请查收 {song_name} 谱面！")


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
    
    info_box = image_gen.draw_info_box(maidata, server, maiuser=maiuser, cn_level=1 if server == 'CN' else 0)
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
        info_box = image_gen.draw_info_box(maidata, server=server, maiuser=maiuser, cn_level=1 if server == 'CN' else 0)
        info_box_bytes = image_gen.get_image_bytes(info_box)
        await matcher.finish(Message(f"找到了乐曲 {mdt.shortid}. {mdt.title}") + MessageSegment.image(info_box_bytes))
    
    elif len(mdt_list) > 4:
        # TODO 以 b50_box 承载曲目信息
        img = image_gen.simple_maidata_box([mdt.to_data() for mdt in mdt_list])
        img_bytes = image_gen.get_image_bytes(img)
        await matcher.finish(
            Message(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下是否有你的目标！") + MessageSegment.image(img_bytes))
        return

    else:
        img_bytes_list = []
        for mdt in mdt_list:
            maidata = mdt.to_data(include_achs=True)
            info_box = image_gen.draw_info_box(maidata, server=server, maiuser=maiuser, cn_level=1 if server == 'CN' else 0)
            img_bytes_list.append(image_gen.get_image_bytes(info_box))
        await matcher.finish(Message(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下乐曲！") + Message().join(img_bytes_list))


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


def build_achievements_diff_image(data_diffs: list[dict]) -> image_gen.Image.Image | None:
    """将成绩变更列表渲染为图片，便于直接发送给用户。"""
    if not data_diffs:
        return None

    diff_update, diff_insert = [], []
    for data_diff in data_diffs:
        action = data_diff.get('action')
        if action == 'update':
            diff_update.append(data_diff)
        elif action == 'insert':
            diff_insert.append(data_diff)

    def get_log_text_items(log_items: list[dict]) -> list[str]:
        return [
            services.change_log_to_text(item)
            for item in log_items
            if isinstance(item.get('lines'), list) and item.get('lines')
        ]

    if (not diff_insert) and (not diff_update):
        return None

    data_diff_text = '\n'.join([
        '发现成绩更新！\n',
        '新增成绩数据：',
        *get_log_text_items(diff_insert),
        '\n更新了已有成绩：',
        *get_log_text_items(diff_update)
    ])
    return image_gen.simple_list(data_diff_text)


async def get_sy_and_upload(user_id: int) -> image_gen.Image.Image | None:
    # 获取水鱼数据
    data = await network.sy_dev_player_records(qq=user_id, developer_token=DEVELOPER_TOKEN)
    records = data.get('records', []) if data else []
    achs = utils.get_sy_records(records) if data else None
    # 批量上传到数据库
    if not achs:
        return None
    data_diffs = await services.upload_achievements_batch(user_id, achs)
    if not data_diffs:
        return None

    return build_achievements_diff_image(data_diffs)


@sync_sy.handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: sytb"""
    user_id = int(event.get_user_id())
    diff_img = await get_sy_and_upload(user_id)
    if diff_img:
        output = io.BytesIO()
        diff_img.save(output, format="jpeg")
        img_bytes = output.getvalue()
        await matcher.finish(MessageSegment.image(img_bytes))
    else:
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
    user_id, group_id = int(event.get_user_id()), getattr(event, "group_id", None)
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
    if group_id:
        user_info = await bot.get_group_member_info(group_id=group_id, user_id=target_user_id)
        target_name = user_info.get("card") or user_info.get("nickname") or str(target_user_id)
    else:
        target_name = str(target_user_id)
    avatar = await network.request_image(f"http://q2.qlogo.cn/headimg_dl?dst_uin={target_user_id}&spec=100")
    server: SERVER_TAG | Literal['ALL'] = cast(SERVER_TAG | Literal['ALL'], target_server or 'CN')
    
    # 同步水鱼数据
    if server in ['CN', 'ALL']:
        diff_img = await get_sy_and_upload(target_user_id)
        if diff_img:
            if target_user_id == user_id:
                # 如果查询目标是自己，同步数据给予提示
                output = io.BytesIO()
                diff_img.save(output, format="jpeg")
                img_bytes = output.getvalue()
                await matcher.send(MessageSegment.image(img_bytes))
            else:
                # 如果查询目标是他人，不直接展示差异图，改为提示已同步
                await matcher.send(f"已同步水鱼数据，正在查询 {target_name} 的 B50 数据……")

    ver_jp, ver_cn = utils.get_current_versions()
    if server == 'ALL':
        await matcher.finish("暂时还不支持全服查询qwq")
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
    update_time = target_maiuser.get_update_time(server)

    # 记录生成开始时间
    generate_start_time = time.time()
    img = image_gen.draw_b50(b35_entries, b15_entries,
                             current_version=current_version,
                             server=server,
                             user_name=target_name,
                             user_avatar=avatar,
                             dxrating=dxrating,
                             update_time=update_time)

    output = io.BytesIO()
    img.save(output, format="jpeg")
    img_bytes = output.getvalue()
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
    # 1. 获取文件基础信息
    file_seg = event.get_message()["file"][0]
    file_id = file_seg.data.get("file_id")
    file_name = file_seg.data.get("file", "")
    
    if not file_name.endswith(".json"):
        return

    # 获取文件下载/路径信息
    file_info = await bot.get_file(file_id=file_id)
    url = file_info.get("url", "")
    raw_path = file_info.get("file")
    local_path = Path(raw_path) if raw_path else None
    
    data = None

    # --- 策略 1: 优先从本地路径读取 (解决 NapCat 路径报错) ---
    if local_path and local_path.exists():
        try:
            async with aiofiles.open(local_path, "rb") as f:
                content = await f.read()
                data = orjson.loads(content)
            logger.info(f"成功从本地路径读取文件: {local_path}")
        except Exception as e:
            logger.warning(f"本地读取失败，尝试网络下载: {e}")

    # --- 策略 2: 降级走网络请求 ---
    if not data and url:
        if url.startswith("http"):
            try:
                data = await network.request_json(url)
            except Exception as e:
                logger.error(f"网络请求失败: {e}")
        else:
            logger.error(f"URL 协议错误: {url}")

    if not data:
        await matcher.finish("读取或解析文件失败，请重试。")

    # 2. 校验数据格式
    if not all([
        isinstance(data, list),  # 数据必须是列表
        len(data) > 0,  # 列表不能为空
        "sheetId" in data[0],  # 必须包含 sheetId 字段
        '__dxrt__' in data[0].get("sheetId")  # sheetId 中必须包含 __dxrt__ 字样
    ]):
        # 格式不正确，静默失败（可能是其他插件识别的文件，不进行失败提醒）
        return

     # 3. 解析
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

    def format_preview(items: list[str], limit: int = 12) -> str:
        if not items:
            return ""
        show = items[:limit]
        if len(items) > limit:
            return f"{'、'.join(show)} 等 {len(items)} 项"
        return '、'.join(show)
    
    for record in data:
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

    # 4. 批量上传
    if ach_list:
        try:
            data_diffs = await services.upload_achievements_batch(user_id, ach_list)
        except Exception as e:
            logger.error(f"数据库写入崩溃: {e}")
            await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")

        insert_count = sum(1 for item in data_diffs if item.get("action") == "insert")
        update_count = sum(1 for item in data_diffs if item.get("action") == "update")
        changed_count = len(data_diffs)
        unchanged_count = max(0, len(ach_list) - changed_count)

        summary_lines = [
            "导入完成，以下为实际入库结果：",
            f"- 文件记录总数：{len(data)}",
            f"- 可识别成绩数：{len(ach_list)}",
            f"- 实际入库变更：{changed_count}（新增 {insert_count} / 更新 {update_count}）",
        ]

        if unchanged_count > 0:
            summary_lines.append(f"- 未写入（已有更优或相同成绩）：{unchanged_count}")

        warning_lines = []
        if unmatched_titles:
            warning_lines.append(
                f"- 曲库尚未匹配（数据库未更新）：{format_preview(unmatched_titles)}"
            )
        if invalid_diff_items:
            warning_lines.append(
                f"- 难度字段无法识别：{format_preview(invalid_diff_items)}"
            )
        if parse_failed_items:
            warning_lines.append(
                f"- 记录解析异常：{format_preview(parse_failed_items)}"
            )

        summary_text = "\n".join(summary_lines)
        warning_text = ""
        if warning_lines:
            warning_text = "\n\n以下数据未入库（正常情况）：\n" + "\n".join(warning_lines)

        diff_img = build_achievements_diff_image(data_diffs)
        if diff_img:
            output = io.BytesIO()
            diff_img.save(output, format="jpeg")
            img_bytes = output.getvalue()
            await matcher.finish(Message([
                MessageSegment.text(
                    f"{summary_text}\n\n以下是本次成绩变更明细：\n"
                ),
                MessageSegment.image(img_bytes),
                MessageSegment.text(warning_text),
            ]))

        await matcher.finish(f"{summary_text}{warning_text}")
    else:
        warning_lines = []
        if unmatched_titles:
            warning_lines.append(
                f"- 曲库尚未匹配（数据库未更新）：{format_preview(unmatched_titles)}"
            )
        if invalid_diff_items:
            warning_lines.append(
                f"- 难度字段无法识别：{format_preview(invalid_diff_items)}"
            )
        if parse_failed_items:
            warning_lines.append(
                f"- 记录解析异常：{format_preview(parse_failed_items)}"
            )

        msg = "已解析，但没有可入库的有效成绩。"
        if warning_lines:
            msg += "\n\n以下数据未入库（正常情况）：\n" + "\n".join(warning_lines)
        await matcher.finish(msg)


@get_code.handle()
async def _(matcher: Matcher):
    await matcher.finish("lyra-sync 服务器尚未开放，请等待 API 开放后再试一下~")

