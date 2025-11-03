import re
import maimai_py

from nonebot import require, on_regex
from nonebot.plugin import PluginMetadata
from nonebot.internal.matcher import Matcher
from nonebot.adapters.onebot.v11 import Bot, Event

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_cache_dir as get_cache_dir

from .adx_download import handle_download
from .ra_calculator import calculate_score


__plugin_meta__ = PluginMetadata(
    name="lyra-maib",
    description="一个QQ群的 舞萌DX 功能机器人。",
    usage="使用 help 查询使用方法",
    # config=Config,
)


# maimai_py 初始化
maip = maimai_py.MaimaiClient()


adx_download = on_regex(r"下载谱面\s*([0-9]+)", priority=5)

@adx_download.handle()
async def _(bot: Bot, event: Event, matcher: Matcher):
    """处理命令: 下载谱面11568"""
    short_id = int(re.search(r"下载谱面\s*([0-9]+)", str(event.get_message())).group())
    await handle_download(bot, event, matcher, short_id)


ra_calculator = on_regex(r"ra\s+(?:(id\d+)([绿黄红紫白])?|(\d+(?:\.\d+)?))\s+(\S+)", priority=5)

@ra_calculator.handle()
async def _(event: Event, matcher: Matcher):
    """处理命令: ra 13.2 100.1000 或 ra 13.2 鸟加 或 ra help"""
    await calculate_score(event, matcher)
