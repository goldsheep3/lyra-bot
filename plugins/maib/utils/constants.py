from datetime import datetime, timezone
from pathlib import Path


__all__ = [
    "DEFAULT_DATETIME",
    "ASSETS_PATH",
]


# 默认时区常量（时间戳=0的时刻）
DEFAULT_DATETIME = datetime(1970, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

# 插件本体路径
PLUGIN_BASE_PATH = Path(__file__).parent.parent
# 插件资源路径
ASSETS_PATH = PLUGIN_BASE_PATH / "assets"
