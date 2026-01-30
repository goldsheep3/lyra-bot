import io
import re
import zipfile
import tempfile
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

try:
    from nonebot import require, logger, on_regex, get_plugin_config
    from nonebot.plugin import PluginMetadata
    from nonebot.params import RegexGroup
    from nonebot.internal.matcher import Matcher
    from nonebot.adapters.onebot.v11 import Bot, Event, MessageSegment

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

adx_download = on_regex(r"下载[铺谱]面\s*(?:id\s*)?(\d+)(?:\s*(zip|z))?$", priority=5)


@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher):
    """处理命令: 下载谱面11568"""
    short_id, archive_type = matcher.state["_matched"].groups()
    short_id = int(short_id)
    group_id = event.group_id if hasattr(event, "group_id") else None
    logger.debug(f"group_id: {group_id}")
    if not group_id:
        logger.debug("未检测到group_id，非群聊环境")
        await matcher.finish("现在小梨只能把谱面传到群文件喔qwq")
        return

    i = 0
    chart_file_path = None
    while i < 3:
        data_dir_path = get_plugin_data_dir() / f"charts{i if i > 0 else ""}"
        chart_file_path = data_dir_path / f"{short_id}.zip"
        logger.info(f"获取文件 {str(chart_file_path)}")
        if chart_file_path.exists():
            break
        i += 1
    if not chart_file_path.exists():
        logger.warning(f"谱面: id{str(short_id)} 不存在。")
        await matcher.finish("小梨没有找到这个谱面！可能这张谱面未被收录，请联系小梨的监护人确认谱面存在及收录情况qwq")
        return
    await matcher.send(f"请稍候——小梨开始准备id{short_id}的谱面文件啦！")

    # 解压并读取maidata.txt第一行
    logger.info("开始解压zip文件")
    maidata_title = None
    with tempfile.TemporaryDirectory(dir=get_plugin_cache_dir()) as tmp_dir:
        with zipfile.ZipFile(chart_file_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)
        maidata_path = Path(tmp_dir) / "maidata.txt"
        if maidata_path.exists():
            logger.info("找到 maidata.txt，开始读取标题")
            with maidata_path.open('r', encoding="utf-8", errors="ignore") as f:
                for line in f:
                    title_match = re.search(r"&title=(.*)", line)
                    if title_match:
                        maidata_title = title_match.group(1).strip()
                        logger.info(f"成功读取谱面标题: {maidata_title}")
                        break
        else:
            logger.error("谱面中未找到 maidata.txt ?!")
    if not maidata_title:
        logger.error(f"读取谱面标题失败，maidata.txt 内容异常。对应谱面：id{short_id} -> {str(chart_file_path)}")
        await matcher.finish("小梨下载到的谱面好像有问题……请求助小梨的监护人qwq")
        return

    # 上传到QQ群文件
    logger.info(f"{short_id}.zip 开始上传群文件")
    file_type = "zip" if archive_type else "adx"
    await bot.call_api(
        "upload_group_file",
        group_id=group_id,
        file=chart_file_path.as_posix(),
        name=f"{short_id}.{file_type}"
    )
    logger.success(f"{short_id}.zip 上传成功")
    finish_message = f"{maidata_title}(id{short_id})" if maidata_title else f"id{short_id}"
    await matcher.finish(f"小梨已经帮你把 {finish_message} 的谱面传到群里啦！")


# =================================
# 查歌
# =================================

mai_info = on_regex(r"^(id|info)(\d+)", priority=10, block=True)  # `id11451`,`info11451`


@mai_info.handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: id11451 / info11451"""
    matched = matcher.state["_matched"]
    _, shortid = matched.groups()
    user_id = event.get_user_id()  # 意图通过QQ查询乐曲数据
    try:
        short_id = int(shortid)
    except (ValueError, TypeError):
        return
    # 查询数据库获取曲目数据
    maidata: MaidataManager.MaiData = await MaidataManager.get_song_by_id(short_id)
    if not maidata:
        await matcher.finish(f"没有找到 id{short_id} 的乐曲数据qwq")
        return
    maidata_data: MaiData = maidata.to_data()
    song_in_cn = await MusicDataManager.contains_id(short_id, get_plugin_cache_dir())
    if song_in_cn:
        # 通过 QQ 获取用户绑定的信息
        record_list = await dev_player_record(maidata_data.shortid, qq=user_id, developer_token=DEVELOPER_TOKEN)
        maidata_data.from_diving_fish_json(record_list)  # 若水鱼有数据则进行填入
    # 构建回复消息
    from .img import info_board
    img = info_board(maidata_data, cn=True if maidata_data.version_cn else False)
    output = io.BytesIO()
    img.save(output, format="jpeg")
    img_bytes = output.getvalue()
    await matcher.finish(
        MessageSegment.image(img_bytes)
    )


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
