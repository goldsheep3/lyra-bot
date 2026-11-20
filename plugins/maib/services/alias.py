from ._refactoring import alias as _alias


async def add_alias(shortid: int, alias: str, *, qq: int) -> _alias.AliasAddStatus:
    """添加曲目别名。

    Args:
        shortid: 要添加别名的乐曲 shortid。
        alias: 要添加的别名。
        qq: 创建该别名的用户 QQ 号。
    """
    return await _alias.add_alias(shortid, alias, qq=qq)


async def remove_alias(shortid: int, alias: str, *, qq: int) -> _alias.AliasRemoveStatus:
    """删除曲目别名。

    Args:
        shortid: 别名所属乐曲的 shortid。
        alias: 要删除的别名。
        qq: 请求删除的用户 QQ 号；仅允许删除本人创建的别名。
    """
    return await _alias.remove_alias(shortid, alias, qq=qq)
