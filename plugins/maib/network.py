import asyncio
import httpx
from typing import Optional, Any, Union
from loguru import logger

try:
    from nonebot import get_driver
    driver = get_driver()

    # NoneBot 模式下的生命周期管理
    @driver.on_startup
    async def _():
        get_http_client()
        logger.info("HTTPX Client 已初始化")

    @driver.on_shutdown
    async def _():
        global _client
        if _client:
            await _client.aclose()
            logger.info("HTTPX Client 已关闭")
except (ImportError, ValueError):
    pass

# --- 1. 统一 URL 配置表 ---
ENDPOINTS = {
    "diving_fish": "https://www.diving-fish.com/api/maimaidxprober",
    "maichart_raw": "https://raw.githubusercontent.com",
    "maichart_proxy": "https://gh-proxy.org/https://raw.githubusercontent.com",
    "lxns": "https://maimai.lxns.net/api/v0/maimai",
    "yuzuchan": "https://www.yuzuchan.moe/api/maimaidx",
}

# --- 2. 全局客户端单例 ---
_client: Optional[httpx.AsyncClient] = None

def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=20.0, 
            follow_redirects=True
        )
    return _client

# --- 3. 核心请求引擎 ---
async def _request(url: str, method: str = "GET", developer_token: Optional[str] = None, **kwargs) -> Optional[Any]:
    """
    通用异步请求核心。
    kwargs 可包含: json, params, headers, retries, project_name 等
    """
    retries = kwargs.pop("retries", 1)
    project_name = kwargs.pop("project_name", "Network")
    delay = kwargs.pop("delay", 1.0)
    header = kwargs.get("headers", {})
    if developer_token:
        header["Developer-Token"] = developer_token
        kwargs["headers"] = header
    
    client = get_http_client()
    for i in range(retries):
        try:
            response = await client.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if i < retries - 1:
                logger.warning(f"[{project_name}] 尝试 {i+1} 失败: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[{project_name}] 最终请求失败: {url} | Error: {e}")
    return None

# --- 4. 具体接口实现 ---

async def sy_music_data():
    """获取公开乐曲数据"""
    return await _request(ENDPOINTS["diving_fish"] + "/music_data", project_name="diving-fish*/music_data")

async def sy_query_player(qq: Union[int, str], b50: bool = True):
    """查询 B50 / B40"""
    return await _request(
        ENDPOINTS["diving_fish"] + "/query/player",
        method="POST",
        json={"qq": str(qq), "b50": b50},
        project_name="diving-fish*/query/player"
    )

async def sy_dev_player_records(qq: Union[int, str], developer_token: Optional[str] = None):
    """获取完整成绩信息"""
    return await _request(
        ENDPOINTS["diving_fish"] + f"/dev/player/records?qq={str(qq)}", 
        project_name="diving-fish*/dev/player/records",
        developer_token=developer_token
    )

async def sy_dev_player_record(shortid: int | str | list[int | str], qq: int | str,
                            developer_token: Optional[str] = None):
    """获取用户单曲成绩信息"""
    music_id = str(shortid) if isinstance(shortid, (int, str)) else [str(id) for id in shortid]
    return await _request(
        ENDPOINTS["diving_fish"] + "/dev/player/record", 
        json={"qq": str(qq), "music_id": music_id},
        project_name="diving-fish*/dev/player/record",
        developer_token=developer_token
    )

# 水鱼之外的：

async def maichart_index():
    """获取谱面索引 (带 Fallback 机制)"""
    MAICHART_INDEX_URL = "/Neskol/Maichart-Converts/refs/heads/master/index.json"
    # 尝试直连
    res = await _request(ENDPOINTS["maichart_raw"] + MAICHART_INDEX_URL, project_name="maichart*/index.json")
    if not res:
        # 尝试代理
        res = await _request(ENDPOINTS["maichart_proxy"] + MAICHART_INDEX_URL, project_name="maichart_proxy*/index.json")
    return res or {}

async def lx_alias_list():
    """获取落雪别名库"""
    return await _request(
        ENDPOINTS["lxns"] + "/alias/list", 
        project_name="lxns*/alias/list"
    )
async def yuzuchan_alias_list():
    """获取 YuzuChaN 别名库"""
    return await _request(
        ENDPOINTS["yuzuchan"] + "/maimaidxalias",
        project_name="yuzuchan*/maimaidxalias"
    )
