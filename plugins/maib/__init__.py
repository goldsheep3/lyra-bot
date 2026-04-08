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
        LYRA_FETCH_SKIP: bool = False

    __plugin_meta__ = PluginMetadata(
        name="lyra-maib",
        description="一个QQ群的 舞萌DX 功能机器人。",
        usage="",
        config=Config,
    )

    if get_plugin_config(Config).LYRA_FETCH_SKIP is False:
        # 仅在未跳过 fetch 的情况下才导入 fetch 模块
        # 用于 DEBUG 调试，节约启动时间
        from . import fetch 

    from . import matcher, models, utils
    matcher.DEVELOPER_TOKEN = get_plugin_config(Config).DIVING_FISH_DEVELOPER_TOKEN
