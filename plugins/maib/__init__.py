"""LyraBot Plugin: maib - MaimaiDX 相关功能插件"""
from pydantic import BaseModel
from nonebot.plugin import PluginMetadata


class Config(BaseModel):
    # Low Memory Mode: 低内存模式，会阻止 B50 等大型图片合成
    LOW_MEMORY_MODE: bool = False
    # Low Memory Tip: 低内存模式下的提示信息，设置为 None 显示默认提示，设置为 "" 则不显示提示
    LOW_MEMORY_TIP: str | None = None
    # Chart Data Directory: 谱面数据目录，默认使用插件数据目录下的 "data" 子目录
    CHART_DATA_DIR: str | None = None
    # Diving-Fish OAuth 凭据
    DIVING_FISH_DEVELOPER_TOKEN: str | None = None
    DIVING_FISH_CLIENT_ID: str | None = None
    DIVING_FISH_CLIENT_SECRET: str | None = None
    # Lxns OAuth 凭据
    LXNS_CLIENT_ID: str | None = None
    LXNS_CLIENT_SECRET: str | None = None
    # Data Provider Cache Expiration: 在线数据源缓存过期时间，单位为小时，默认 24 小时
    DATA_PROVIDER_CACHE_EXPIRATION: float = 24
    # Max Blur Search Results: 模糊搜索最大允许结果数，超过会提示缩小搜索范围
    # 有效范围: >= 5，不在范围内会被设定为默认值（40）
    MAX_BLUR_SEARCH_RESULTS: int = 40
    # MCP Bearer Token: 独立于在线同步 token；为空时不挂载 MCP 服务
    MAIB_MCP_API_TOKEN: str | None = None


__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-pfmai",
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


try:
    from nonebot import require, get_driver, get_plugin_config
    get_driver()
    
    # 在 __init__.py 中预导入，便于在其他文件直接 import
    require("nonebot_plugin_localstore")
    require("nonebot_plugin_datastore")
    require("nonebot_plugin_locales")

    # --- config fix ---
    config = get_plugin_config(Config)
    if config.MAX_BLUR_SEARCH_RESULTS < 5:
        config.MAX_BLUR_SEARCH_RESULTS = 40
    
    from . import matcher, services, utils, fetch, napcat_stream, webapi
    # 注入 hook 以支持 stream 获取文件
    napcat_stream.install_hook()

except Exception as e:
    import os
    if os.getenv("MAIB_IMAGE_GEN_DEBUG") == "1":
        from loguru import logger
        logger.warning(f"插件 maib 导入失败，可能是正在调试 image_gen 模块。如果并非调试过程，请关注错误原因。错误信息: {e}")
    else:
        raise  # 非调试，重新抛出
