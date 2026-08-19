"""LyraBot Plugin: maib - MaimaiDX 相关功能插件"""
from pydantic import BaseModel


class Config(BaseModel):
    # Low Memory Mode: 低内存模式，会阻止 B50 等大型图片合成
    LOW_MEMORY_MODE: bool = False
    # Low Memory Tip: 低内存模式下的提示信息，设置为 None 显示默认提示，设置为 "" 则不显示提示
    LOW_MEMORY_TIP: str | None = None
    # Diving-Fish Developer Token: 水鱼开发者 token，若不设置则无法使用水鱼的查分服务
    DIVING_FISH_DEVELOPER_TOKEN: str | None = None
    # Cache Expiration: 缓存过期时间，单位为小时，默认 72 小时
    # 替代 [LYRA_FETCH_SKIP]
    CACHE_EXPIRATION: int = 72
    # Max Blur Search Results: 模糊搜索最大允许结果数，超过会提示缩小搜索范围
    # 有效范围: >= 5，不在范围内会被设定为默认值（40）
    MAX_BLUR_SEARCH_RESULTS: int = 40

try:
        
    from nonebot import require, get_driver, get_plugin_config
    from nonebot.plugin import PluginMetadata
    
    try:
        get_driver()
    except ValueError:
        raise RuntimeError
    else:
        # 在 __init__.py 中预导入，便于在其他文件直接 import
        require("nonebot_plugin_localstore")
        require("nonebot_plugin_datastore")

    __plugin_meta__ = PluginMetadata(
        name="nonebot-plugin-performai",
        description="查询、操作和管理 MaimaiDX 相关数据",
        usage="使用 /help maib 查看详细帮助",
        type="application", 
        homepage="https://github.com/goldsheep3/lyra-bot/tree/main/plugins/maib",
        config=Config,
        supported_adapters={
            "~onebot.v11",
            "~telegram",
        },
    )

    # --- config fix ---
    config = get_plugin_config(Config)
    if config.MAX_BLUR_SEARCH_RESULTS < 5:
        config.MAX_BLUR_SEARCH_RESULTS = 40


    from . import matcher, services, utils, plugin_help, fetch, napcat_stream, webapi

    # 注入 hook 以支持 stream 获取文件
    napcat_stream.install_hook()

except (RuntimeError, ImportError):
    from loguru import logger
    logger.warning("插件 maib 未被加载，可能是调试阶段")
