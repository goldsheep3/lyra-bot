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
        LOW_MEMORY_MODE: bool = False  # 低内存模式，会阻止 B50 等大型图片合成
        LOW_MEMORY_TIP: str | None = None
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

    from . import matcher, models, utils, plugin_help
    # 将配置项传递给 matcher 模块
    cfg = get_plugin_config(Config)
    matcher.LOW_MEMORY_MODE = cfg.LOW_MEMORY_MODE
    matcher.LOW_MEMORY_TIP = cfg.LOW_MEMORY_TIP
    matcher.DEVELOPER_TOKEN = cfg.DIVING_FISH_DEVELOPER_TOKEN
