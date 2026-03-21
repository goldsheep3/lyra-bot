# ==============================================================
# lyra-maib
# 支持 MaimaiDX 的数据插件
# ==============================================================

try:
    from nonebot import get_driver
    driver = get_driver()
except ValueError:
    pass
else:
    from pydantic import BaseModel
    from nonebot import get_plugin_config
    from nonebot.plugin import PluginMetadata
    
    class Config(BaseModel):
        DIVING_FISH_DEVELOPER_TOKEN: str | None = None

    __plugin_meta__ = PluginMetadata(
        name="lyra-maib",
        description="一个QQ群的 舞萌DX 功能机器人。",
        usage="",
        config=Config,
    )

    from . import matcher, models, utils, fetch 
    matcher.DEVELOPER_TOKEN = get_plugin_config(Config).DIVING_FISH_DEVELOPER_TOKEN
