import httpx
import orjson
from pathlib import Path
from typing import Optional, TypedDict
from datetime import datetime

from nonebot import logger


from .tool import _request, request_json
from .. import config


AUTH_URL = "https://auth.diving-fish.com/"
BASE_URL = "https://www.diving-fish.com/api/maimaidxprober"

# {aid: (access_token, expires_at)}
_ACCESS_CACHE: dict[str, tuple[str, datetime]] = {}

    
class MusicData(TypedDict):
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
                url=BASE_URL + "/music_data",
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
            BASE_URL + "/chart_stats",
            project_name="diving-fish*/chart_stats"
        )

    @staticmethod
    async def query_player(qq: int | str, b50: bool = True):
        """`~/query/player`"""
        return await request_json(
            BASE_URL + "/query/player",
            method="POST",
            json={"qq": str(qq), "b50": b50},
            project_name="diving-fish*/query/player"
        )

    @staticmethod
    async def dev_player_records(qq: int | str):
        """`~/dev/player/records`"""
        return await request_json(
            BASE_URL + f"/dev/player/records?qq={str(qq)}", 
            project_name="diving-fish*/dev/player/records",
            developer_token=config.DIVING_FISH_DEVELOPER_TOKEN
    )

    @staticmethod
    async def dev_player_record(shortid: int | str | list[int | str], qq: int | str) -> Optional[list]:
        """`~/dev/player/record`"""
        music_id = str(shortid) if isinstance(shortid, (int, str)) else [str(id) for id in shortid]
        result = await request_json(
            BASE_URL + "/dev/player/record",
            method="POST",
            json={"qq": str(qq), "music_id": music_id},
            project_name="diving-fish*/dev/player/record",
            developer_token=config.DIVING_FISH_DEVELOPER_TOKEN
        )
        if result and len(result) == 1:
            return next(iter(result.values()))
        return None
