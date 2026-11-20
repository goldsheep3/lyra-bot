from typing import Literal, Optional, Sequence

from ..utils.enums import ServerScope
from ..utils.models import MaiData
from ._refactoring import catalog as _catalog


async def get_maidata(shortid: int, *, qq: Optional[int] = None, server: ServerScope = ServerScope.CN, provider: Optional[str] = None) -> Optional[MaiData]:
    """获取乐曲信息。

    Args:
        shortid: 乐曲 shortid。
        qq: 可选的 QQ 号；提供时会加载该用户的成绩。
        server: 加载成绩时使用的服务器范围。
        provider: 可选的成绩数据提供方。
    """
    return await _catalog.get_maidata(shortid, qq=qq, server=server, provider=provider)


async def search_maidata(keyword: str, *, qq: Optional[int] = None, server: ServerScope = ServerScope.CN, provider: Optional[str] = None, mode: Literal["smart", "title", "name", "blur"] = "smart") -> Sequence[MaiData]:
    """搜索乐曲信息。

    Args:
        keyword: 用于匹配曲名或别名的关键词。
        qq: 可选的 QQ 号；提供时会加载该用户的成绩。
        server: 加载成绩时使用的服务器范围。
        provider: 可选的成绩数据提供方。
        mode: 搜索模式，可为智能、曲名、别名或模糊搜索。
    """
    return await _catalog.search_maidata(keyword, qq=qq, server=server, provider=provider, mode=mode)
