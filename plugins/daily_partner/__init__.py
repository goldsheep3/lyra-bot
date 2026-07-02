from pydantic import BaseModel
from nonebot.plugin import PluginMetadata

from nonebot import require, get_plugin_config
# require("nonebot_plugin_i18n")

class Config(BaseModel):
    MAX_SWAP_COUNT: int = 3  # 每个用户每天换老婆的最大次数
    HOPE_SUCCESS_RATE: float = 0.5  # 愿望单成功率，0.5 表示 50% 的概率抽中愿望单标记目标
    ACTIVE_DAYS: int = 7  # 活跃成员的时间阈值，单位为天，表示在过去多少天内发过言的成员才算活跃

__plugin_meta__ = PluginMetadata(
    name="daily_partner",
    description="支持「一夫一妻制」的今日老婆插件",
    usage="发送「jrlp」开始体验，发送「help jrlp」查看帮助",
    config=Config,
)

config = get_plugin_config(Config)

# 导入以启用 Matcher
from . import matcher, plugin_help
