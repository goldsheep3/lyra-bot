import io
import re
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

try:
    from nonebot import require, logger, on_regex, get_plugin_config
    from nonebot.plugin import PluginMetadata
    from nonebot.params import RegexGroup
    from nonebot.internal.matcher import Matcher
    from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment

    # noinspection PyPep8Naming N812
    from . import db_utils as MaidataManager
    from .diving_fish import dev_player_record
    from .utils import rate_alias_map, MaiData, MaiChart, MaiChartAch, parse_status, DIFFS_MAP, MusicDataManager

    require("nonebot_plugin_localstore")
    require("nonebot_plugin_datastore")
    from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir


    class Config(BaseModel):
        DIVING_FISH_DEVELOPER_TOKEN: Optional[str]


    __plugin_meta__ = PluginMetadata(
        name="lyra-maib",
        description="一个QQ群的 舞萌DX 功能机器人。",
        usage="使用 help 查询使用方法",
        config=Config,
    )

    cfg = get_plugin_config(Config)
    DEVELOPER_TOKEN = cfg.DIVING_FISH_DEVELOPER_TOKEN

except (ImportError, ValueError, RuntimeError):
    pass


# =================================
# ADX 谱面下载
# =================================

adx_download = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)


@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: 下载谱面11568"""

    raw_short_id, archive_type = groups
    archive_type = archive_type.strip().lower()
    short_id = int(raw_short_id) if raw_short_id.isdigit() else 0

    if short_id <= 0:
        # 只有在没有显式输入 ID 的情况下才尝试从回复提取
        if hasattr(event, "reply") and event.reply:
            replied_text = str(event.reply.message)
            match = re.search(r"(\d+)", replied_text)
            if match:
                short_id = int(match.group(1))
                logger.debug(f"从回复消息中提取到 short_id: {short_id}")

        # 仍然未找到 ID，视为误触
        # **大家当做无事发生**
        if short_id <= 0:
            return

    # 获取谱面信息
    mdt = await MaidataManager.get_song_by_id(short_id)  # 不转换为 utils.MaiData，直接使用数据库对象中才包含的 zip_path
    chart_file_path = Path(mdt.zip_path) if mdt else None

    if not chart_file_path or not chart_file_path.exists():
        logger.warning(f"谱面 id {short_id} 不存在")
        await matcher.finish("小梨没有找到这个谱面！可能还没被收录，请联系监护人确认喔qwq")
        return

    await matcher.send(f"请稍候——小梨开始准备 id {short_id} 的谱面文件啦！")

    # 4. 上传逻辑
    file_ext = "zip" if "zip" in archive_type else "adx"
    file_name = f"{short_id}.{file_ext}"
    song_name = getattr(mdt, 'title', f"id {short_id}")

    group_id = getattr(event, "group_id", None)
    if group_id:
        try:
            await bot.call_api(
                "upload_group_file",
                group_id=group_id,
                file=chart_file_path.resolve().as_posix(),
                name=file_name
            )
        except Exception as e:
            logger.error(f"上传失败: {e}")
            await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.finish(f"小梨已经帮你把 {song_name} 的谱面传到群里啦！")
    else:
        user_id = event.get_user_id()
        try:
            await bot.call_api(
                "upload_private_file",
                user_id=user_id,
                file=chart_file_path.resolve().as_posix(),
                name=file_name
            )
        except Exception as e:
            logger.error(f"上传失败: {e}")
            await matcher.finish("小梨上传谱面时遇到了问题，请联系监护人确认喔qwq")
            return
        await matcher.finish(f"登登~请查收 {song_name} 谱面！")


# =================================
# 查歌
# =================================

mai_info = on_regex(r"^(id|info)(\d+)", priority=10, block=True)  # `id11451`,`info11451`


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
    mdt: MaidataManager.MaiData = await MaidataManager.get_song_by_id(short_id)
    if not mdt:
        await matcher.finish(f"没有找到 id{short_id} 的乐曲数据qwq")
        return
    maidata: MaiData = mdt.to_data()
    song_in_cn = await MusicDataManager.contains_id(short_id, get_plugin_cache_dir())
    if song_in_cn:
        # 通过 QQ 获取用户绑定的信息
        record_list = await dev_player_record(maidata.shortid, qq=user_id, developer_token=DEVELOPER_TOKEN)
        maidata.from_diving_fish_json(record_list)  # 若水鱼有数据则进行填入
    # 构建回复图片
    from .img import info_board
    img = info_board(maidata, cn=True if maidata.version_cn else False)
    output = io.BytesIO()
    img.save(output, format="jpeg")
    img_bytes = output.getvalue()
    # 发送消息：`11951. サイエンス [Image]`
    # 考虑支持回复自动下载
    await matcher.finish(Message(f"{maidata.shortid}. {maidata.title}") + MessageSegment.image(img_bytes))


# =================================
# Rating 计算
# =================================

ra_calc = on_regex(r"^ra\s+(\S+)?\s+(\S+)", priority=5, block=True)


@ra_calc.handle()
async def _(matcher: Matcher, groups: tuple = RegexGroup()):
    """处理命令: ra 13.2 100.1000"""
    info, rate = groups
    level: float = 0

    # 先解析 rate
    try:
        achievement = float(rate)
    except (ValueError, TypeError):
        achievement = rate_alias_map.get(rate.lower())

    # 1. 尝试以定数形式解析
    try:
        level = float(info)
    except (ValueError, TypeError):
        pass

    # 2. 判断定数是否越界，越界则解析为纯数字 id
    if level > 20:
        level = 0  # 大于 20 则一定不为定数，驳回上述解析
        shortid = int(level)
        mai = await MaidataManager.get_song_by_id(shortid)
        if mai:
            charts = mai.charts
            charts.sort(key=lambda c: c.chart_number)
            level = charts[-1].lv  # 取最高难度的定数

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
                mai = await MaidataManager.get_song_by_id(shortid)
            except (ValueError, TypeError):
                mai = None
            if mai:
                charts = mai.charts
                diff = parse_status(diff_info.group(1), DIFFS_MAP)
                if diff:
                    # 指定了难度颜色，尝试匹配
                    for c in charts:
                        if c.chart_number == diff:
                            level = c.lv
                            break
                if not level:
                    # 取最高难度
                    charts.sort(key=lambda c: c.chart_number)
                    level = charts[-1].lv  # 取最高难度的定数

    # 4. 尝试解析 歌名/别名
    if level == 0:
        pass  # todo: 未实现 歌名/别名解析

    # 解析结束
    if level == 0:
        await matcher.finish("小梨无法解析你提供的定数或歌曲信息喔TT")
        return

    # 调用 MaiChart 计算 DX Rating
    ra = MaiChart(difficulty=0, lv=level, ach=MaiChartAch(achievement=achievement)).get_dxrating()

    await matcher.finish("小梨算出来咯！\n"
                         f"定数{level}*{achievement:.4f}% -> Rating: {ra}")
