"""utils/file_api.py 文件 API 封装"""
import base64
import hashlib
import math
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from loguru import logger
from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot

from ..napcat_stream import NapCatStreamFile


__all__ = [
    "OneBotV11FileAPI",
]

DEFAULT_STREAM_CHUNK_SIZE = 256 * 1024
DEFAULT_STREAM_FILE_RETENTION = 30 * 1000


class OneBotV11FileAPI:
    """OneBot V11 文件 API 封装"""

    @staticmethod
    @asynccontextmanager
    async def download_file_stream_to_temp_file(
        bot: OneBotV11Bot,
        file_id: str,
        timeout: float = 30.0,
    ) -> AsyncIterator[Path]:
        """使用 NapCat stream 下载文件到临时文件。"""
        async with NapCatStreamFile(bot, file_id, timeout=timeout) as stream_path:
            yield stream_path

    @staticmethod
    async def clean_stream_temp_file(bot: OneBotV11Bot, **kwargs) -> dict:
        """清理 NapCat stream 临时文件。"""
        return await bot.call_api("clean_stream_temp_file", **kwargs)

    @staticmethod
    async def _file_sha256(file_path: Path, chunk_size: int) -> str:
        hasher = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as file_obj:
            while True:
                chunk = await file_obj.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    async def upload_file_stream(
        bot: OneBotV11Bot,
        file_path: Path,
        *,
        chunk_size: int = DEFAULT_STREAM_CHUNK_SIZE,
        file_retention: int = DEFAULT_STREAM_FILE_RETENTION,
        stream_id: str | None = None,
        filename: str | None = None,
    ) -> str:
        """通过 NapCat stream 上传本地文件，并返回 NapCat 侧可用的临时文件路径。"""
        file_path = file_path.resolve()
        file_size = file_path.stat().st_size
        total_chunks = max(1, math.ceil(file_size / chunk_size))
        stream_id = stream_id or str(uuid.uuid4())
        filename = filename or file_path.name
        expected_sha256 = await OneBotV11FileAPI._file_sha256(file_path, chunk_size)

        async with aiofiles.open(file_path, "rb") as file_obj:
            for chunk_index in range(total_chunks):
                chunk = await file_obj.read(chunk_size)
                params = {
                    "stream_id": stream_id,
                    "chunk_data": base64.b64encode(chunk).decode("utf-8"),
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "file_size": file_size,
                    "expected_sha256": expected_sha256,
                    "filename": filename,
                    "file_retention": file_retention,
                }
                await bot.call_api("upload_file_stream", **params)

        result = await bot.call_api(
            "upload_file_stream",
            stream_id=stream_id,
            is_complete=True,
        )
        if not isinstance(result, dict) or result.get("status") != "file_complete":
            raise RuntimeError(f"NapCat stream upload failed: {result}")

        uploaded_file_path = result.get("file_path")
        if not uploaded_file_path:
            raise RuntimeError(f"NapCat stream upload returned no file_path: {result}")

        return str(uploaded_file_path)

    @staticmethod
    async def _resolve_upload_file_path(
        bot: OneBotV11Bot,
        file_path: Path,
        *,
        file_name: str,
        use_stream: bool,
        stream_chunk_size: int,
        stream_file_retention: int,
    ) -> str:
        if not use_stream:
            return file_path.resolve().as_posix()

        try:
            return await OneBotV11FileAPI.upload_file_stream(
                bot,
                file_path,
                chunk_size=stream_chunk_size,
                file_retention=stream_file_retention,
                filename=file_name,
            )
        except Exception as e:
            logger.debug(f"NapCat stream upload failed, fallback to local upload path: {e}")
            return file_path.resolve().as_posix()

    @staticmethod
    async def get_group_root_files(bot: OneBotV11Bot, group_id: str | int, **kwargs) -> dict:
        """获取群根目录文件列表"""
        return await bot.call_api(
            "get_group_root_files",
            group_id=str(group_id),
            **kwargs
        )

    @staticmethod
    async def create_group_file_folder(bot: OneBotV11Bot, group_id: str | int, folder_name: str, **kwargs) -> dict:
        """创建群文件夹"""
        return await bot.call_api(
            "create_group_file_folder",
            group_id=str(group_id),
            folder_name=folder_name,
            **kwargs
        )

    @staticmethod
    async def get_group_files_by_folder(bot: OneBotV11Bot, group_id: str | int, folder_id: str | int, **kwargs) -> dict:
        """获取群文件夹内的文件列表"""
        return await bot.call_api(
            "get_group_files_by_folder",
            group_id=str(group_id),
            folder_id=str(folder_id),
            **kwargs
        )

    @staticmethod
    async def update_group_file(bot: OneBotV11Bot, group_id: str | int, file_path: Path, **kwargs) -> dict:
        """上传群文件"""
        file_name = kwargs.pop("file_name", file_path.name)
        use_stream = kwargs.pop("use_stream", True)
        stream_chunk_size = kwargs.pop("stream_chunk_size", DEFAULT_STREAM_CHUNK_SIZE)
        stream_file_retention = kwargs.pop("stream_file_retention", DEFAULT_STREAM_FILE_RETENTION)
        upload_file_path = await OneBotV11FileAPI._resolve_upload_file_path(
            bot,
            file_path,
            file_name=file_name,
            use_stream=use_stream,
            stream_chunk_size=stream_chunk_size,
            stream_file_retention=stream_file_retention,
        )
        return await bot.call_api(
            "upload_group_file",
            group_id=str(group_id),
            file=upload_file_path,
            name=file_name,
            **kwargs
        )

    @staticmethod
    async def upload_private_file(bot: OneBotV11Bot, user_id: str | int, file_path: Path, **kwargs) -> dict:
        """上传私聊文件"""
        file_name = kwargs.pop("file_name", file_path.name)
        use_stream = kwargs.pop("use_stream", True)
        stream_chunk_size = kwargs.pop("stream_chunk_size", DEFAULT_STREAM_CHUNK_SIZE)
        stream_file_retention = kwargs.pop("stream_file_retention", DEFAULT_STREAM_FILE_RETENTION)
        upload_file_path = await OneBotV11FileAPI._resolve_upload_file_path(
            bot,
            file_path,
            file_name=file_name,
            use_stream=use_stream,
            stream_chunk_size=stream_chunk_size,
            stream_file_retention=stream_file_retention,
        )
        return await bot.call_api(
            "upload_private_file",
            user_id=str(user_id),
            file=upload_file_path,
            name=file_name,
            **kwargs
        )
