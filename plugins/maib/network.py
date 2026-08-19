"""network.py 网络请求核心模块"""
import asyncio
import httpx
import orjson
from pathlib import Path
from typing import Optional, Any, Literal
from dataclasses import dataclass

from nonebot import logger, get_driver


__all__ = [
    "DivingFish",
    "MaichartConverts",
    "Lxns",
    "YuzuChaN",

    "get_qq_avatar",
]


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


# --- url endpoints ---

_ENDPOINTS = {
    "diving_fish": "https://www.diving-fish.com/api/maimaidxprober",
    "maichart_raw": "https://raw.githubusercontent.com",
    "maichart_proxy": "https://gh-proxy.org/https://raw.githubusercontent.com",
    "lxns": "https://maimai.lxns.net/api/v0/maimai",
    "yuzuchan": "https://www.yuzuchan.moe/api/maimaidx",
}


# --- key require function ---

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

async def request_image(url: str, method: str = "GET", **kwargs) -> Optional[bytes]:
    """请求并获取图片二进制数据，失败时返回 None"""
    response = await _request(url, method=method, **kwargs)
    if response:
        return response.content
    return None


# --- functions ---

@dataclass
class MusicData:
    data: list
    updated: bool
    

class DivingFish:
    @staticmethod
    async def music_data(plugin_data_dir: Path, max_retries: int = 3) -> MusicData:
        """`~/music_data`"""
        
        data_cache_path = plugin_data_dir / "music_data.json"
        etag_cache_path = plugin_data_dir / "music_data.etag"
        
        etag = etag_cache_path.read_text(encoding="utf-8").strip() if etag_cache_path.exists() else None
        headers = {"If-None-Match": etag} if etag else {}
        try:
            response = await _request(
                url=_ENDPOINTS["diving_fish"] + "/music_data",
                project_name="diving-fish*/music_data",
                headers=headers,
                retries=max_retries,
            )
            if response is None:
                raise httpx.RequestError("No response received")
        except httpx.RequestError as e:
            logger.error(f"Network error, returning cached data if available. Error: {e}")
            if data_cache_path.exists():
                try:
                    data = orjson.loads(data_cache_path.read_bytes())
                    return MusicData(data=data, updated=False)
                except Exception as e:
                    logger.error(f"Failed to load cached data: {e}")
            return MusicData(data=[], updated=False)
        
        # etag 命中，直接读取本地缓存
        if etag and response.status_code == 304:
            if data_cache_path.exists():
                try:
                    data = orjson.loads(data_cache_path.read_bytes())
                    return MusicData(data=data, updated=False)
                except Exception as e:
                    logger.warning("Local cache corrupted, clearing ETag and retrying.")
                    logger.debug(f"Error: {e}")
                    # 清除缓存，重新下载
                    etag_cache_path.unlink(missing_ok=True)
                    return await DivingFish.music_data(plugin_data_dir, max_retries=max_retries)

        # 获得了新数据
        if response.status_code == 200:
            data = []
            try:
                data = response.json()
                new_etag = response.headers.get("etag", "")
                # 保存新数据和 ETag
                plugin_data_dir.mkdir(parents=True, exist_ok=True)
                data_cache_path.write_bytes(orjson.dumps(data))
                if new_etag:
                    etag_cache_path.write_text(new_etag, encoding="utf-8")
                return MusicData(data=data, updated=True)
            except Exception as e:
                logger.error(f"Failed to parse or save new data: {e}")
                return MusicData(data=data, updated=True)
        
        # 其他状态码，尝试读取本地缓存
        if data_cache_path.exists():
            try:
                data = orjson.loads(data_cache_path.read_bytes())
                return MusicData(data=data, updated=False)
            except Exception as e:
                logger.error(f"Failed to load cached data: {e}")
        return MusicData(data=[], updated=False)

    @staticmethod
    async def chart_stats():
        """`~/chart_stats`"""
        return await request_json(
            _ENDPOINTS["diving_fish"] + "/chart_stats",
            project_name="diving-fish*/chart_stats"
        )

    @staticmethod
    async def query_player(qq: int | str, b50: bool = True):
        """`~/query/player`"""
        return await request_json(
            _ENDPOINTS["diving_fish"] + "/query/player",
            method="POST",
            json={"qq": str(qq), "b50": b50},
            project_name="diving-fish*/query/player"
        )

    @staticmethod
    async def dev_player_records(qq: int | str, developer_token: Optional[str] = None):
        """`~/dev/player/records`"""
        return await request_json(
            _ENDPOINTS["diving_fish"] + f"/dev/player/records?qq={str(qq)}", 
            project_name="diving-fish*/dev/player/records",
            developer_token=developer_token
    )

    @staticmethod
    async def dev_player_record(shortid: int | str | list[int | str], qq: int | str,
                                developer_token: Optional[str] = None) -> Optional[list]:
        """`~/dev/player/record`"""
        music_id = str(shortid) if isinstance(shortid, (int, str)) else [str(id) for id in shortid]
        result = await request_json(
            _ENDPOINTS["diving_fish"] + "/dev/player/record",
            method="POST",
            json={"qq": str(qq), "music_id": music_id},
            project_name="diving-fish*/dev/player/record",
            developer_token=developer_token
        )
        if result and len(result) == 1:
            return next(iter(result.values()))
        return None
    

class MaichartConverts:
    @staticmethod
    async def maichart_index() -> dict[str, str] | None:
        """`index.json`"""
        MAICHART_INDEX_URL = "/Neskol/Maichart-Converts/refs/heads/master/index.json"
        # 尝试直连
        res = await request_json(_ENDPOINTS["maichart_raw"] + MAICHART_INDEX_URL, project_name="maichart*/index.json")
        if not res:
            # 尝试代理
            res = await request_json(_ENDPOINTS["maichart_proxy"] + MAICHART_INDEX_URL, project_name="maichart_proxy*/index.json")
        return res or {}


class Lxns:
    @staticmethod
    async def lx_alias_list() -> dict | None:
        """`~/alias/list`"""
        return await request_json(
            _ENDPOINTS["lxns"] + "/alias/list", 
            project_name="lxns*/alias/list"
        )


class YuzuChaN:
    @staticmethod
    async def yuzuchan_alias_list() -> dict | None:
        """`~/maimaidxalias`"""
        return await request_json(
            _ENDPOINTS["yuzuchan"] + "/maimaidxalias",
            project_name="yuzuchan*/maimaidxalias"
        )


# --- 工具函数 ---

async def get_qq_avatar(qq: str | int, spec: Literal[1, 2, 3, 4, 5, 40, 100, 640] = 100) -> Optional[bytes]:
    avatar_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={qq}&spec={spec}"
    avatar = await request_image(avatar_url)
    return avatar