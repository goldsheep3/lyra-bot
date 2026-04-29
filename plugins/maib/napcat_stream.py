import asyncio
import base64
import contextvars
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from nonebot.adapters.onebot.store import ResultStore
from nonebot.adapters.onebot.v11 import Adapter, Bot


_HOOK_INSTALLED = False
_CURRENT_STREAM: contextvars.ContextVar["NapCatStreamFile | None"] = contextvars.ContextVar(
    "maib_current_stream",
    default=None,
)
_ACTIVE_STREAMS: dict[int, "NapCatStreamFile"] = {}

_original_json_to_event = Adapter.json_to_event.__func__
_original_get_seq = ResultStore.get_seq


def _decode_stream_payload(payload: Any) -> bytes:
    if payload is None:
        return b""
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        raw = payload.split(",", 1)[1] if "," in payload else payload
        try:
            return base64.b64decode(raw)
        except Exception:
            return payload.encode("utf-8")
    if isinstance(payload, dict):
        for key in ("data", "content", "chunk_data", "body"):
            if key in payload:
                return _decode_stream_payload(payload[key])
    return str(payload).encode("utf-8")


def _extract_echo(result: dict[str, Any]) -> Optional[int]:
    echo = result.get("echo")
    if isinstance(echo, int):
        return echo
    if isinstance(echo, str) and echo.isdecimal():
        return int(echo)
    return None


def _stream_kind(result: dict[str, Any]) -> tuple[Optional[str], bytes, Optional[str]]:
    payload = result.get("data")
    if not isinstance(payload, dict):
        return None, b"", None

    packet_type = str(payload.get("type", "")).lower()
    if packet_type == "stream":
        return "chunk", _decode_stream_payload(payload.get("data")), None
    if packet_type == "response":
        return "done", b"", None
    if packet_type == "error":
        message = payload.get("message") or result.get("message") or "NapCat stream error"
        return "error", b"", str(message)
    return None, b"", None


def _patched_get_seq(self: ResultStore) -> int:
    seq = _original_get_seq(self)
    stream = _CURRENT_STREAM.get()
    if stream is not None:
        stream.bind_seq(seq)
    return seq


def _patched_json_to_event(cls, json_data: Any):
    if isinstance(json_data, dict) and "post_type" not in json_data:
        seq = _extract_echo(json_data)
        if seq is not None:
            stream = _ACTIVE_STREAMS.get(seq)
            if stream is not None:
                kind, chunk, message = _stream_kind(json_data)
                if kind == "chunk":
                    stream.on_chunk(chunk)
                    return None
                if kind == "done":
                    stream.on_done()
                elif kind == "error":
                    stream.on_error(message or "NapCat stream error")

    return _original_json_to_event(cls, json_data)


def install_hook() -> None:
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return

    setattr(ResultStore, 'get_seq', _patched_get_seq)
    setattr(Adapter, 'json_to_event', _patched_json_to_event)
    _HOOK_INSTALLED = True
    logger.info("NapCat stream hook installed")


class NapCatStreamFile:
    def __init__(self, bot: Bot, file_id: str, timeout: float = 30.0):
        self.bot = bot
        self.file_id = file_id
        self.timeout = timeout
        self._seq: Optional[int] = None
        self._buffer = bytearray()
        self._done = asyncio.Event()
        self._error: Optional[str] = None
        self.path: Optional[Path] = None

    def bind_seq(self, seq: int) -> None:
        self._seq = seq
        _ACTIVE_STREAMS[seq] = self

    def on_chunk(self, chunk: bytes) -> None:
        if chunk:
            self._buffer.extend(chunk)

    def on_done(self) -> None:
        self._done.set()

    def on_error(self, message: str) -> None:
        self._error = message
        self._done.set()

    async def open(self) -> Path:
        install_hook()

        token = _CURRENT_STREAM.set(self)
        try:
            await asyncio.wait_for(
                self.bot.call_api("download_file_stream", file_id=self.file_id),
                timeout=self.timeout,
            )
            if self._error:
                raise RuntimeError(self._error)

            fd, path_str = tempfile.mkstemp(suffix=".json")
            self.path = Path(path_str)
            with os.fdopen(fd, "wb") as file_obj:
                file_obj.write(self._buffer)
            return self.path
        finally:
            _CURRENT_STREAM.reset(token)
            if self._seq is not None:
                _ACTIVE_STREAMS.pop(self._seq, None)

    async def __aenter__(self) -> Path:
        return await self.open()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._buffer.clear()
        self._done.clear()
        if self.path and self.path.exists():
            try:
                self.path.unlink()
            except Exception:
                pass
