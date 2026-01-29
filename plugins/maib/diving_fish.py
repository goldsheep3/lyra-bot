import httpx
from typing import Optional, Dict, List

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
        headers: Optional[dict] = None,
        import_token: Optional[str] = None,
        developer_token: Optional[str] = None,
        method: str = "GET"):
    """封装的 httpx 请求函数"""

    if _client is None or _client.is_closed:
        raise RuntimeError("HTTPX Client 尚未初始化或已关闭")

    if import_token:
        headers["Import-Token"] = import_token
    if developer_token:
        headers["Developer-Token"] = developer_token

    try:
        response = await _client.request(
            method=method,
            url=url,
            headers=headers if headers else {})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        logger.error(f"API请求失败: {e}")
        return None


async def get_record(shortid: int, qq: int | str, developer_token: str) -> Optional[List[Dict]]:
    headers = {
        "music_id": str(shortid),
        "qq": str(qq)
    }

    result = await _make_request(
        url=BASE_API_URL + "/dev/player/record",
        headers=headers,
        developer_token=developer_token
        )
    
    return result
