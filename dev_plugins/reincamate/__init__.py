from nonebot import get_plugin_config, on_startswith
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent

# from .config import Config
from .reinc_cn import ReincamateCN

__plugin_meta__ = PluginMetadata(
    name="自助投胎",
    description="一个QQ群的自助投胎小游戏插件。",
    usage="发送'投胎中国'即可参与",
    # config=Config,
)

# config = get_plugin_config(Config)


# 创建命令触发器
reinc_cn = on_startswith("投胎中国", rule=to_me(), priority=2, block=True)


@reinc_cn.handle()
async def rebirth_handler(matcher: Matcher, event: MessageEvent):
    rcn = ReincamateCN(event)
    await matcher.finish(rcn.reincamate())
