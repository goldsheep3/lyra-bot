import io, re, orjson, aiofiles
from pathlib import Path
from typing import Optional, List

from . import services, image_gen, network, bot_services
from .utils import MaiData, MaiChart, MaiChartAch, parse_status, MaiB50Manager, get_current_versions
from .constants import *

from nonebot import logger, on_regex, on_message
from nonebot.rule import Rule
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, MessageEvent, PrivateMessageEvent


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
mai_info = on_regex(r"^(id|info)(\d+)", priority=10, block=True)
# 查询乐曲信息 (是什么歌)
mai_what_song = on_regex(r"^(\S+?)是什么歌([?？]?)$", priority=10, block=True)
# 设置乐曲别名
alias_setting = on_regex(r'^(添加|删除)别名\s+(?:id)?(\d+)\s+([^\s]+)$', priority=5, block=True)
# 列表查询（完成表/进度/列表）
scorelist = on_regex(r'^(.*?)\s*(完成表|进度|列表)$', priority=5, block=True)
# b50 查询
b50 = on_regex(r'^([a-z0-9+]*?)(b50|kkb)\s*(.*)$', priority=1, block=True)
# ra 计算
ra_calc = on_regex(r"^ra\s+(\S+)?\s+(\S+)", priority=5, block=True)
# 上传 JSON 配置数据
file_receiver = on_message(priority=25, rule=is_private_file())


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
    mdt = await services.get_song_by_id(short_id)
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


async def get_song_image(mdt: services.MaiData, user_id: str | int) -> bytes:
    """提取的共用查歌并生成图片的逻辑"""
    user_id = str(user_id)
    maidata: MaiData = mdt.to_data()
    server = "CN" if maidata.version_cn else "JP"
    if maidata.version_cn is not None:
        # 通过 QQ 获取用户绑定的信息
        record_list = await network.sy_dev_player_record(maidata.shortid, qq=user_id, developer_token=DEVELOPER_TOKEN)
        if record_list:
            maidata.parse_sy_player_record(record_list)  # 若水鱼有数据则进行填入
    # 构建回复图片
    output = io.BytesIO()
    img = image_gen.DrawInfo(maidata, server=server, cn_level=1 if maidata.version_cn else 0).get_image()
    img.save(output, format="jpeg")
    return output.getvalue()


@mai_info.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: id11451 / info11451"""
    _, shortid = groups
    user_id = event.get_user_id()  # 意图通过QQ查询乐曲数据
    try:
        short_id = int(shortid)
    except (ValueError, TypeError):
        return
    # 查询数据库获取曲目数据
    mdt: Optional[services.MaiData] = await services.get_song_by_id(short_id)
    if not mdt:
        await matcher.finish(f"没有找到 id{short_id} 的乐曲数据qwq")
        return
    img_bytes = await get_song_image(mdt, user_id)
    await matcher.finish(Message(f"{mdt.shortid}. {mdt.title}") + MessageSegment.image(img_bytes))


@mai_what_song.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxx是什么歌"""
    keyword, all_tag = groups
    user_id = event.get_user_id()  # 意图通过QQ查询乐曲数据
    mdt_list: List[services.MaiData] = list((
        await services.get_song_by_name_smart(keyword) if not all_tag else
        await services.get_song_by_name_blur(keyword)
    ))  # 不带问号为智能搜索，带问号进行强制搜索
    mdt_list = [mdt for mdt in mdt_list if mdt.shortid < 100000]  # 忽略宴会场
    if not mdt_list:
        await matcher.finish(f"没有找到包含「{keyword}」的乐曲数据qwq")
        return
    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        msg = Message(f"找到了乐曲 {mdt.shortid}. {mdt.title}")
    elif len(mdt_list) > 4:
        await matcher.send(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下是否有你的目标！")
        # 未来 b50 提上日程后，希望可以以 b50_box 承载曲目信息
        img = image_gen.simple_list([mdt.to_data() for mdt in mdt_list])
        output = io.BytesIO()
        img.save(output, format="jpeg")
        img_bytes = output.getvalue()
        await matcher.finish(MessageSegment.image(img_bytes))
        return
    else:
        msg = Message(f"找到了 {len(mdt_list)} 首相应的乐曲！请查看以下乐曲！")
    
    imgs = []
    for mdt in mdt_list:
        img_bytes = await get_song_image(mdt, user_id)
        imgs.append(MessageSegment.image(img_bytes))
    await matcher.finish(msg + Message().join(imgs))


@alias_setting.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: 添加别名 id11451 xxx / 删除别名 id11451 xxx"""
    action, shortid, alias = groups
    try:
        short_id = int(shortid)
        mdt: Optional[services.MaiData] = await services.get_song_by_id(short_id)
        if not mdt:
            raise ValueError
    except (ValueError, TypeError):
        await matcher.finish("请提供正确的乐曲 ID 哦qwq")
        return

    group_id = getattr(event, "group_id", None)
    group_id = int(group_id) if group_id else None

    if action == "添加":
        # 添加别名
        new_alias = await services.add_alias(short_id, alias, short_id, group_id)
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
        shortid = int(level)
        mai = await services.get_song_by_id(shortid)
        level = mai.charts[-1].lv if mai else 0  # 取最高难度的定数

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
                mai = await services.get_song_by_id(shortid)
            except (ValueError, TypeError):
                mai = None
            if mai:
                charts = mai.charts
                s = diff_info.group(1) if diff_info else''
                diff = parse_status(s, DIFFS_MAP)
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
    if achievement > 100.5:
        msg += "\n该 ra 不考虑 AP 的额外分数哦！"
    await matcher.finish(msg)


@b50.handle()
async def _(event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: xxxb50/xxxkkb xxx"""
    _keyword, _, extra = groups
    user_id, server = None, None
    extra: str = extra.strip()
    if extra:
        extra_list = extra.split(' ')
        for item in extra_list:
            if (not user_id) and item.isdigit():
                user_id = int(item)  # 其次解析纯数字 QQ 号
            if (not server) and item.lower() in ['jp', 'cn', 'all']:
                server = item.upper()  # 解析服务器信息
        for segment in event.get_message():
            if segment.type == "at":
                user_id = int(segment.data["qq"])  # 优先解析 @ 的用户信息
                break
    user_id = user_id or int(event.get_user_id())  # 最后默认使用发送者的 QQ 号
    server = server or 'ALL'
    
    
    # 当前：解析水鱼读取 b50
    # TODO: 修改为同步到数据库并可选查询
    sy_b50_data = await network.sy_query_player(qq=user_id)
    if not sy_b50_data:
        await matcher.finish("没有找到你的水鱼数据哦qwq")
        return
    sy_b50_records = sy_b50_data.get('records', [])
    sy_b50_records = sy_b50_records or sum(sy_b50_data.get('charts', {'': []}).values(), [])
    music_dict = dict()
    maidata_list = []
    for record in sy_b50_records:
        if shortid := record.get('song_id'):
            l = music_dict.get(shortid, [])
            l.append(record)
            music_dict[shortid] = l
    for shortid, records in music_dict.items():
        mdt = await services.get_song_by_id(shortid)
        if mdt:
            maidata = mdt.to_data()
            maidata.parse_sy_player_record(records)  # 填入水鱼数据
            for record in records:
                # 构造数据-难度元组
                diff = record.get('level_index', 3) + 2
                maidata_list.append((maidata, diff))
    if not maidata_list:
        await matcher.finish("没有找到可用于绘制的谱面记录哦qwq")
        return
    await matcher.send("小梨绘制中……")
    manager = MaiB50Manager(current_version=get_current_versions()[1], server='CN')
    manager.add_entries(maidata_list)
    img = image_gen.DrawB50Boxex(manager, sy_b50_data.get('nickname', ''), cn_level=1).get_image()
    output = io.BytesIO()
    img.save(output, format="jpeg")
    img_bytes = output.getvalue()
    await matcher.finish(MessageSegment.image(img_bytes))
    


@file_receiver.handle()
async def _(bot: Bot, event: PrivateMessageEvent, matcher: Matcher):
    # 1. 获取文件基础信息
    file_seg = event.get_message()["file"][0]
    file_id = file_seg.data.get("file_id")
    file_name = file_seg.data.get("file", "")
    
    if not file_name.endswith(".json"):
        await matcher.finish("请发送 .json 格式的文件。")
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
    if isinstance(data, list) and len(data) > 0 and "sheetId" not in data[0]:
        return

    await matcher.send("检查到数据导出！正在识别曲目并记录成绩...")

    user_id = int(event.get_user_id())
    ach_list = []
    title_cache = {}  # 缓存标题查询结果
    
    # 3. 解析并修正 SD/DX ID
    for record in data:
        try:
            title = record.get("title", "")
            record_type = str(record.get("type", "sd")).lower() # 'sd' 或 'dx'
            
            if title not in title_cache:
                songs = await services.get_song_by_name(title)
                if not songs:
                    title_cache[title] = None
                title_cache[title] = songs[0].shortid if songs else None

            base_id = title_cache[title]
            if base_id is None:
                logger.warning(f"无法找到曲目: {title}")
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
            if difficulty < 0: continue

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
            continue

    # 4. 批量上传
    if ach_list:
        try:
            await services.upload_achievements_batch(user_id, ach_list)
        except Exception as e:
            logger.error(f"数据库写入崩溃: {e}")
            await matcher.finish("同步到数据库时出错了……请联系监护人确认情况哦qwq")
        await matcher.finish(f"成功导入 {len(ach_list)} 条成绩！")
    else:
        import time
        await matcher.finish(f"已解析，但似乎没有有效的成绩诶qwq\n当前的时间为：{time.strftime('%Y-%m-%d %H:%M:%S')}，请截图发送给监护人确认情况。\n果咩纳塞qwq")
