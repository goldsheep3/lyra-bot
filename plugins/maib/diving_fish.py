import httpx
from nonebot import get_driver, logger
from typing import Optional, Dict, List

# 水鱼 maimaiDX 查分器 API 基础 URL
BASE_API_URL = "https://www.diving-fish.com/api/maimaidxprober"

# 初始化和自动关闭 httpx Client
driver = get_driver()
_client: Optional[httpx.AsyncClient] = None


@driver.on_startup
async def init_http_client():
    global _client
    # 在这里可以配置全局超时、连接池等参数
    _client = httpx.AsyncClient(timeout=10.0)
    logger.info("✅ HTTPX Client 已初始化")


@driver.on_shutdown
async def close_http_client():
    global _client
    if _client:
        await _client.aclose()
        logger.info("🛑 HTTPX Client 已关闭")


async def _make_request(
        url: str,
        headers: dict = {},
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
            headers=headers)
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
