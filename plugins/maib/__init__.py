from nonebot import on_regex
from nonebot.plugin import PluginMetadata

from .adx_download import handle_download

# from .config import Config

__plugin_meta__ = PluginMetadata(
    name="lyra-maib",
    description="一个QQ群的 舞萌DX 功能机器人。",
    usage="使用 help 查询使用方法",
    # config=Config,
)

# config = get_plugin_config(Config)


adx_download = on_regex(r"下载谱面\s*([0-9]+)", priority=5)

@adx_download.handle()
async def _(bot, event, matcher):
    """处理命令: 下载谱面11568"""
    await handle_download(bot, event, matcher)
