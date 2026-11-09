import asyncio
import httpx
from typing import Optional, Any

from nonebot import logger, get_driver


_client: Optional[httpx.AsyncClient] = None

def _get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=20.0, 
            follow_redirects=True
        )
    return _client


driver = get_driver()

@driver.on_startup
async def _():
    _get_http_client()
    logger.info("HTTPX Client 已初始化")

@driver.on_shutdown
async def _():
    global _client
    if _client:
        await _client.aclose()
        logger.info("HTTPX Client 已关闭")


async def _request(url: str, method: str = "GET", developer_token: Optional[str] = None, **kwargs) -> Optional[httpx.Response]:
    """通用异步请求核心"""
    retries = kwargs.pop("retries", 1)
    project_name = kwargs.pop("project_name", "Network")
    delay = kwargs.pop("delay", 1.0)
    header = kwargs.get("headers", {})
    if developer_token:
        header["Developer-Token"] = developer_token
        kwargs["headers"] = header
    
    client = _get_http_client()
    response = None
    for i in range(retries):
        try:
            response = await client.request(method=method, url=url, **kwargs)
            if response.status_code == 304:
                return response
            response.raise_for_status()
            return response
        except Exception as e:
            if i < retries - 1:
                logger.warning(f"[{project_name}] 尝试 {i+1} 失败: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[{project_name}] 最终请求失败: {url} | Error: {e}")
    return response


# --- tool functions ---

async def request_json(url: str, method: str = "GET", **kwargs) -> Optional[Any]:
    """请求并解析 JSON，失败时返回 None"""
    if not url:
        return
    response = await _request(url, method=method, **kwargs)
    if response:
        try:
            return response.json()
        except Exception as e:
            logger.error(f"JSON 解析失败: {url} | Error: {e}")
    return None

async def request_bytes(url: str, method: str = "GET", **kwargs) -> Optional[bytes]:
    """请求并获取图片二进制数据，失败时返回 None"""
    response = await _request(url, method=method, **kwargs)
    if response:
        return response.content
    return None
