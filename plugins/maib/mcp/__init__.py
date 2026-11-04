"""面向 maib 公开曲目数据的、独立认证 MCP 服务。"""
from __future__ import annotations

from hmac import compare_digest
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .. import services
from .sql import ReadOnlySqlError, execute_readonly_sql


class _BearerTokenMiddleware(BaseHTTPMiddleware):
    """保护整个 MCP ASGI 应用，避免与 maib 在线同步 token 共用凭据。"""

    def __init__(self, app: Any, *, api_token: str) -> None:
        super().__init__(app)
        self._api_token = api_token

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or not compare_digest(token, self._api_token):
            return JSONResponse(
                {"error": "unauthorized", "detail": "需要有效的 MCP Bearer Token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


def _serialize_song(song: services.MaiData) -> dict[str, Any]:
    return {
        "shortid": song.shortid,
        "title": song.title,
        "artist": song.artist,
        "bpm": song.bpm,
        "genre": song.genre,
        "cabinet": song.cabinet,
        "version": song.version,
        "version_cn": song.version_cn,
        "is_utage": song.is_utage,
        "utage_tag": song.utage_tag,
        "buddy": song.buddy,
        "aliases": [alias.alias for alias in song.aliases],
        "charts": [
            {
                "id": chart.id,
                "difficulty": chart.difficulty,
                "lv": chart.lv,
                "lv_cn": chart.lv_cn,
                "lv_synh": chart.lv_synh,
                "designer": chart.des,
                "internal_notes": chart.inote,
                "notes": chart.notes,
                "dxscore_max": chart.dxscore_max,
            }
            for chart in sorted(song.charts, key=lambda chart: chart.difficulty)
        ],
    }


server = MCPServer(
    name="maib",
    title="maib MaimaiDX 数据服务",
    description="查询 maimai DX 曲目和谱面数据。所有工具均只读。",
)


@server.tool(
    description="按曲名或别名搜索 maimai DX 曲目。smart 会先精确匹配，再模糊匹配。",
)
async def search_song(
    keyword: str,
    mode: Literal["smart", "title", "name", "blur"] = "smart",
) -> list[dict[str, Any]]:
    songs = await services.get_mdt.title(keyword, way=mode)
    return [_serialize_song(song) for song in songs]


@server.tool(description="通过 maib shortid 获取一首 maimai DX 曲目的完整资料和所有谱面。")
async def get_song(shortid: int) -> dict[str, Any] | None:
    song = await services.get_mdt.id(shortid)
    return _serialize_song(song) if song is not None else None


@server.tool(
    description=(
        "执行一条只读 SELECT。仅可查询 MaiData 与 MaiChart（或实际表名 "
        "maib_maidatas、maib_maicharts），支持 CTE、子查询与集合运算，"
        "但不支持任何写入、定义或事务控制语句。"
        "未显式指定 LIMIT 时自动追加 LIMIT 50；显式 LIMIT 最大为 200。"
    ),
)
async def query_maib_sql(sql: str) -> dict[str, Any]:
    try:
        async with services.get_session() as session:
            return await execute_readonly_sql(session, sql)
    except ReadOnlySqlError as exc:
        return {"error": "invalid_sql", "detail": str(exc)}


def create_mcp_app(api_token: str) -> Any:
    """创建由独立静态 Bearer Token 保护的 Streamable HTTP MCP ASGI 应用。"""
    if not api_token.strip():
        raise ValueError("MAIB_MCP_API_TOKEN 不能为空")
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )
    app.add_middleware(_BearerTokenMiddleware, api_token=api_token)
    return app
