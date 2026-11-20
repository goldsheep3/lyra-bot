from .._refactoring import alias as _alias


async def sync_aliases(data: list[tuple[int, str]], *, create_qq: int) -> None:
    """同步别名库数据。

    Args:
        data: ``(shortid, alias)`` 形式的别名数据。
        create_qq: 写入别名时使用的创建者 QQ 号。
    """
    return await _alias.add_ma_batch(data=data, create_qq=create_qq)
