"""webapi.py maib 在线同步 HTTP 接口"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from nonebot import get_app, logger

from . import services
from .utils.sync import build_lyra_records_v3, parse_lyra_maisync_data


router = APIRouter(tags=["maib-sync"])


class PairRequest(BaseModel):
    code: str
    device_id: str
    device_name: Optional[str] = None


class UploadRequest(BaseModel):
    payload: str


class _MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


_rate_limiter = _MemoryRateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _extract_bearer_token(authorization: Optional[str]) -> str:
    header_value = str(authorization or "").strip()
    if not header_value.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    token = header_value[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")
    return token


def _raise_pair_error(exc: Exception) -> None:
    if isinstance(exc, services.PairingCodeError):
        detail = str(exc) if str(exc) else (exc.args[0] if exc.args else "pairing_code_error")
        if detail in {"invalid_code", "expired_code", "used_code", "revoked_code", "empty_code"}:
            raise HTTPException(status_code=401, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    raise HTTPException(status_code=400, detail="pairing_failed")


async def _process_uploaded_payload(user_id: int, payload: str) -> None:
    """在响应已返回后解析上传数据、写入记录并刷新派生成绩。"""
    try:
        file_data, file_version = parse_lyra_maisync_data(payload.encode("utf-8"))
        if not isinstance(file_data, list) or len(file_data) == 0:
            raise ValueError("empty_payload")
        if not file_version.startswith("v0.3."):
            raise ValueError(f"unsupported_version:{file_version}")

        parsed_result = build_lyra_records_v3(file_data, user_id=user_id)
        record_keys, unmatched_items = await services.add_record_batch(user_id, parsed_result.records)
        ach_list = await services.get_record_achs(user_id, list(record_keys))
        if ach_list:
            await services.upd_ach_batch(user_id, ach_list)
        logger.info(
            "maib 在线同步后台处理完成: user_id=%s, received=%s, parsed=%s, affected=%s, unmatched=%s",
            user_id,
            len(file_data),
            len(parsed_result.records),
            len(record_keys),
            len(unmatched_items),
        )
    except Exception:
        logger.exception("maib 在线同步后台处理失败: user_id=%s", user_id)


@router.post("/api/pair")
async def pair_device(payload: PairRequest, request: Request) -> dict[str, str]:
    client_ip = _client_ip(request)
    if not _rate_limiter.check(f"pair:ip:{client_ip}", limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="too_many_requests")
    if not _rate_limiter.check(f"pair:code:{payload.code}", limit=6, window_seconds=300):
        raise HTTPException(status_code=429, detail="too_many_requests")

    try:
        _user_id, access_token = await services.exchange_pairing_code(
            payload.code,
            device_id=payload.device_id,
            device_name=payload.device_name,
        )
    except Exception as exc:
        _raise_pair_error(exc)
        return {}

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post("/api/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_records(
    payload: UploadRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, object]:
    access_token = _extract_bearer_token(authorization)
    try:
        user_id = await services.authenticate_access_token(access_token)
    except services.AccessTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc) or "invalid_token") from exc

    background_tasks.add_task(_process_uploaded_payload, user_id, payload.payload)

    return {
        "ok": True,
        "processing": True,
    }


_app = get_app()
if not any(m.cls is CORSMiddleware for m in _app.user_middleware):
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://u.otogame.net"],
        allow_credentials=False,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["authorization", "content-type"],
    )

if not any(getattr(route, "path", None) == "/api/pair" for route in _app.router.routes):
    _app.include_router(router)
    logger.info("maib 在线同步 Web API 已挂载: /api/pair, /api/upload")
