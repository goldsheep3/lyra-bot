from ._refactoring import mcp_sql as _mcp_sql

ReadOnlySqlError = _mcp_sql.ReadOnlySqlError


async def sql_query(sql: str):
    """执行受限的只读 SQL 查询。

    Args:
        sql: 待验证并执行的 SQL 语句。
    """
    return await _mcp_sql.sql_query(sql)
