import re

import maimai_py

from nonebot import on_regex
from nonebot.exception import FinishedException
from nonebot.plugin import PluginMetadata
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event

from .adx_download import handle_download
from .ra_calculator import calculate_rating, fetch_chart_level
from .utils import init_difficulty_from_text

__plugin_meta__ = PluginMetadata(
    name="lyra-maib",
    description="一个QQ群的 舞萌DX 功能机器人。",
    usage="使用 help 查询使用方法",
    # config=Config,
)


# maimai_py 初始化
maipy = maimai_py.MaimaiClient()


adx_download = on_regex(r"下载谱面\s*([0-9]+)", priority=5)

@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher):
    """处理命令: 下载谱面11568"""
    short_id = int(re.search(r"下载谱面\s*([0-9]+)", str(event.get_message())).group())
    await handle_download(bot, event, matcher, short_id)


ra_calculators = [
    on_regex(r"^ra\s+help", priority=5, block=True),  # 帮助命令
    on_regex(r"^ra\s+(\d+(?:\.\d+)?)\s+(\S+)", priority=4, block=True),  # 定数直接计算
    on_regex(r"^ra\s+id(\d+)([绿黄红紫白])\s+(\S+)", priority=3, block=True),  # id(加颜色)计算
]

@ra_calculators[1].handle()
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
    match = re.search(r"^ra\s+id(\d+)([绿黄红紫白])\s+(\S+)", msg)  # id加颜色计算
    if not match: return
    song_info = await fetch_chart_level(maipy, int(match.group(1)), init_difficulty_from_text(match.group(2)))
    if song_info:
        await calculate_rating(matcher, song_info['level'], match.group(2), song_info)
    else:
        await matcher.finish(f"小梨找不到这个谱面qwq\n请确认谱面的id和难度。")
