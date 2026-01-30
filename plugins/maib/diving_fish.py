import httpx
from typing import Optional, Dict, List, Any

from .utils import MaiChartAch

try:
    from nonebot import get_driver, logger
    driver = get_driver()
except (ImportError, ValueError):
    driver = None
    from loguru import logger

# 全局 httpx AsyncClient 实例
_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """获取或初始化全局 AsyncClient"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    return _client


# --- NoneBot 模式下的生命周期管理 ---
if driver:
    @driver.on_startup
    async def _():
        get_http_client()
        logger.info("✅ NoneBot 模式：HTTPX Client 已初始化")

    @driver.on_shutdown
    async def _():
        global _client
        if _client:
            await _client.aclose()
            logger.info("🛑 NoneBot 模式：HTTPX Client 已关闭")

# 水鱼 maimaiDX 查分器 API 基础 URL
BASE_API_URL = "https://www.diving-fish.com/api/maimaidxprober"


async def _make_request(
        url: str,
        method: str = "GET",
        json_data: Optional[dict] = None,   # 新增：用于 POST 的 JSON 数据
        params: Optional[dict] = None,      # 新增：用于 GET 的查询参数
        import_token: Optional[str] = None,
        developer_token: Optional[str] = None):
    """封装的 httpx 请求函数"""

    client = get_http_client()  # 确保 client 已初始化

    headers = {}
    if import_token:
        headers["Import-Token"] = import_token
    if developer_token:
        headers["Developer-Token"] = developer_token

    try:
        response = await client.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        # 增加更详细的错误输出，方便调试
        error_msg = f"API请求失败: {e}"
        if hasattr(e, "response") and e.response:
            error_msg += f" | 响应内容: {e.response.text}"
        logger.error(error_msg)
        return None


async def get_record(shortid: int, qq: int | str, developer_token: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """获取用户的单曲成绩信息"""
    # 核心修改：参数放入 body
    data_body = {
        "music_id": str(shortid),
        "qq": str(qq)
    }

    result = await _make_request(
        method="POST",  # 必须是 POST
        url=f"{BASE_API_URL}/dev/player/record",
        json_data=data_body,
        developer_token=developer_token
    )

    return result
