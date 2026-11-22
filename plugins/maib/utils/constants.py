from datetime import datetime, timezone
from pathlib import Path

from .enums import Server


__all__ = [
    "DEFAULT_DATETIME",
    "ASSETS_PATH",
    "LEGACY_DEFAULT_PROVIDER_BY_SERVER",
    "DEFAULT_PROVIDER",
]


# 默认时区常量（时间戳=0的时刻）
DEFAULT_DATETIME = datetime(1970, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

# 插件本体路径
PLUGIN_BASE_PATH = Path(__file__).parent.parent
# 插件资源路径
ASSETS_PATH = PLUGIN_BASE_PATH / "assets"


# 各服务器历史默认成绩来源；成绩入库缺省 provider 时按此兜底
LEGACY_DEFAULT_PROVIDER_BY_SERVER: dict[Server, str] = {
    Server.JP: "lyrasync-oto",
    Server.CN: "diving-fish",
}

# 无法确定来源时的兜底值（与 ORM 列默认保持一致）
DEFAULT_PROVIDER = "unknown"
