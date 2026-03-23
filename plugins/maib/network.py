import asyncio
import httpx
import orjson
from pathlib import Path
from typing import Optional, Any
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
async def _request(url: str, method: str = "GET", developer_token: Optional[str] = None, **kwargs) -> Optional[httpx.Response]:
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
            if response.status_code == 304:
                return response
            response.raise_for_status()
        except Exception as e:
            if i < retries - 1:
                logger.warning(f"[{project_name}] 尝试 {i+1} 失败: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[{project_name}] 最终请求失败: {url} | Error: {e}")
    return response

async def request_json(url: str, method: str = "GET", developer_token: Optional[str] = None, **kwargs) -> Optional[Any]:
    """请求并解析 JSON，失败时返回 None"""
    response = await _request(url, method=method, developer_token=developer_token, **kwargs)
    if response:
        try:
            return response.json()
        except Exception as e:
            logger.error(f"JSON 解析失败: {url} | Error: {e}")
    return None

async def request_image(url: str, method: str = "GET", developer_token: Optional[str] = None, **kwargs) -> Optional[bytes]:
    """请求并获取图片二进制数据，失败时返回 None"""
    response = await _request(url, method=method, developer_token=developer_token, **kwargs)
    if response:
        return response.content
    return None


# --- 4. 具体接口实现 ---

async def sy_music_data(etag: str | None = None) -> tuple[str | None, list | None]:
    """获取公开乐曲数据"""
    headers = {"If-None-Match": etag} if etag else {}
    response = await _request(ENDPOINTS["diving_fish"] + "/music_data", project_name="diving-fish*/music_data", headers=headers)
    if response is None:
        return None, None
    if response.status_code == 304:
        return etag, None
    if response.status_code == 200:
        try:
            data = response.json()
            new_etag = response.headers.get("etag", "")  # 强制保留引号
            return new_etag, data
        except Exception as e:
            logger.error(f"解析水鱼数据失败: {e}")
    return None, None

async def sy_music_data_from_file(dir_path: Path, max_retries: int = 3) -> list | None:
    """获取公开乐曲数据"""
    data_path = dir_path / "music_data.json"
    etag_path = dir_path / "music_data.etag"
    
    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        
        # 1. 获取本地 ETag
        current_etag = None
        if etag_path.exists() and data_path.exists():
            current_etag = etag_path.read_text(encoding="utf-8").strip()

        # 2. 请求网络数据
        new_etag, remote_data = await sy_music_data(etag=current_etag)

        # 3. 处理新数据（远程更新）
        if remote_data:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                data_path.write_bytes(orjson.dumps(remote_data))
                if new_etag:
                    etag_path.write_text(new_etag, encoding="utf-8")
            except Exception as e:
                logger.error(f"保存数据失败: {e}")
            # 无论保存成功与否，该数据都可用
            return remote_data

        # 4. 处理缓存数据（ETag 命中）
        if new_etag and not remote_data:
            if data_path.exists():
                try:
                    return orjson.loads(data_path.read_bytes())
                except Exception as e:
                    logger.warning(f"本地缓存损坏，清除 ETag 并重试: {e}")
                    etag_path.unlink(missing_ok=True)
                    continue # 触发下一次循环，重新下载
            else:
                # 理论上不应到达这里（有 ETag 没数据），清除 ETag 重试
                etag_path.unlink(missing_ok=True)
                continue

        # 5. 异常降级：如果 ETag 为 None 或其他未知情况
        # 尝试读取本地现有数据作为最后的保障
        if data_path.exists():
            try:
                return orjson.loads(data_path.read_bytes())
            except:
                pass
        
        break # 无效状态，跳出循环
    return None


async def sy_chart_stats():
    """获取公开乐曲统计数据"""
    return await request_json(
        ENDPOINTS["diving_fish"] + "/chart_stats",
        project_name="diving-fish*/chart_stats"
    )

async def sy_dev_player_records(qq: int | str, developer_token: Optional[str] = None):
    """获取完整成绩信息"""
    return await request_json(
        ENDPOINTS["diving_fish"] + f"/dev/player/records?qq={str(qq)}", 
        project_name="diving-fish*/dev/player/records",
        developer_token=developer_token
    )

async def sy_query_player(qq: int | str, b50: bool = True):
    """查询 B50 / B40"""
    return await request_json(
        ENDPOINTS["diving_fish"] + "/query/player",
        method="POST",
        json={"qq": str(qq), "b50": b50},
        project_name="diving-fish*/query/player"
    )

async def sy_dev_player_record(shortid: int | str | list[int | str], qq: int | str,
                               developer_token: Optional[str] = None) -> Optional[list]:
    """获取用户单曲成绩信息"""
    music_id = str(shortid) if isinstance(shortid, (int, str)) else [str(id) for id in shortid]
    result = await request_json(
        ENDPOINTS["diving_fish"] + "/dev/player/record",
        method="POST",
        json={"qq": str(qq), "music_id": music_id},
        project_name="diving-fish*/dev/player/record",
        developer_token=developer_token
    )
    if result and len(result) == 1:
        return next(iter(result.values()))
    return None
    

# 水鱼之外的：

async def maichart_index() -> dict[str, str] | None:
    """获取谱面索引 (带 Fallback 机制)"""
    MAICHART_INDEX_URL = "/Neskol/Maichart-Converts/refs/heads/master/index.json"
    # 尝试直连
    res = await request_json(ENDPOINTS["maichart_raw"] + MAICHART_INDEX_URL, project_name="maichart*/index.json")
    if not res:
        # 尝试代理
        res = await request_json(ENDPOINTS["maichart_proxy"] + MAICHART_INDEX_URL, project_name="maichart_proxy*/index.json")
    return res or {}

async def lx_alias_list() -> dict | None:
    """获取落雪别名库"""
    return await request_json(
        ENDPOINTS["lxns"] + "/alias/list", 
        project_name="lxns*/alias/list"
    )

async def yuzuchan_alias_list() -> dict | None:
    """获取 YuzuChaN 别名库"""
    return await request_json(
        ENDPOINTS["yuzuchan"] + "/maimaidxalias",
        project_name="yuzuchan*/maimaidxalias"
    )
