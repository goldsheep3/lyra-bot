import re
import zipfile
import tempfile
from pathlib import Path

import maimai_py

from nonebot import require, logger, on_regex
from nonebot.plugin import PluginMetadata
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event

from .ra_calculator import calculate_rating, fetch_chart_level
from .utils import init_difficulty_from_text

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir


__plugin_meta__ = PluginMetadata(
    name="lyra-maib",
    description="一个QQ群的 舞萌DX 功能机器人。",
    usage="使用 help 查询使用方法",
    # config=Config,
)


# maimai_py 初始化
maipy = maimai_py.MaimaiClient()

# =================================
# ADX 谱面下载
# =================================

adx_download = on_regex(r"下载谱面\s*([0-9]+)", priority=5)


@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher):
    """处理命令: 下载谱面11568"""
    short_id = int(matcher.state["_matched"].group(1))
    group_id = event.group_id if hasattr(event, "group_id") else None
    logger.debug(f"group_id: {group_id}")
    if not group_id:
        logger.debug("未检测到group_id，非群聊环境")
        await matcher.finish("现在小梨只能把谱面传到群文件喔qwq")
        return

    data_dir_path = get_plugin_data_dir() / "charts"
    chart_file_path = data_dir_path / f"{short_id}.zip"
    logger.info(f"获取文件 {str(chart_file_path)}")
    if not chart_file_path.exists():
        logger.warning(f"谱面: id{str(short_id)} 不存在。")
        await matcher.finish("小梨没有找到这个谱面！可能这张谱面未被收录，请联系小梨的监护人确认谱面存在及收录情况qwq")
        return

    # 解压并读取maidata.txt第一行
    logger.info("开始解压zip文件")
    maidata_title = None
    with tempfile.TemporaryDirectory(dir=get_plugin_cache_dir()) as tmp_dir:
        with zipfile.ZipFile(chart_file_path, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)
        maidata_path = Path(tmp_dir) / "maidata.txt"
        if maidata_path.exists():
            logger.info("找到 maidata.txt，开始读取标题")
            with maidata_path.open("r", encoding="utf-8", errors="ignore") as f:
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
    await bot.call_api(
        "upload_group_file",
        group_id=group_id,
        file=chart_file_path.as_posix(),
        name=f"{short_id}.zip"
    )
    logger.success(f"{short_id}.zip 上传成功")
    finish_message = f"{maidata_title}(id{short_id})" if maidata_title else f"id{short_id}"
    await matcher.finish(f"小梨已经帮你把 {finish_message} 的谱面传到群里啦！")

# =================================
# Rating 计算
# =================================

ra_calculators = [
    on_regex(r"^ra\s+help", priority=5, block=True),  # 帮助命令
    on_regex(r"^ra\s+(\d+(?:\.\d+)?)\s+(\S+)", priority=4, block=True),  # 定数直接计算
    on_regex(r"^ra\s+id(\d+)([绿黄红紫白])?\s+(\S+)", priority=3, block=True),  # id(加颜色)计算
]


@ra_calculators[0].handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: ra help"""
    msg = str(event.get_message())
    if re.search(r"^ra\s+help", msg):
        await matcher.finish((
            "小梨提醒你：ra命令可以计算给定难度和完成率的得分。\n"
            "使用方法：\n"
            "ra <难度> <完成率>\n"
            "ra id<谱面id>[颜色] <完成率>\n"
            "例如：ra 13.2 100.1000 或 ra id10240红 100.5\n"
            "颜色支持：绿/黄/红/紫/白，无颜色默认取最高难度"
        ))


@ra_calculators[1].handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: ra 13.2 100.1000 或 ra 13.2 鸟加 或 ra help"""
    msg = str(event.get_message())
    match = re.search(r"^ra\s+(\d+(?:\.\d+)?)\s+(\S+)", msg)  # 定数直接计算
    if not match: return
    await calculate_rating(matcher, float(match.group(1)), match.group(2))


@ra_calculators[2].handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: ra id10240红 100.5 或 ra id10240红 鸟加 或 ra help"""
    msg = str(event.get_message())
    match = re.search(r"^ra\s+id(\d+)([绿黄红紫白])?\s+(\S+)", msg)  # id加颜色计算
    if not match: return
    difficulty = init_difficulty_from_text(match.group(2)) if match.group(2) else None
    song_info = await fetch_chart_level(maipy, int(match.group(1)), difficulty)
    if song_info:
        await calculate_rating(matcher, song_info['level'], match.group(3), song_info)
    else:
        await matcher.finish(f"小梨找不到这个谱面qwq\n请确认谱面的id和难度。")
