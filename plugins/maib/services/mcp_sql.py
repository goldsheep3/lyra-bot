from datetime import date, datetime, time
from typing import Any, Mapping

from nonebot import logger
from sqlalchemy import text
from sqlglot import exp, parse

from nonebot_plugin_datastore import create_session as get_session


DEFAULT_LIMIT = 50                      # 默认的查询结果行数限制
MAX_LIMIT = 200                         # 查询结果行数的最大限制
POSTGRES_STATEMENT_TIMEOUT_MS = 5_000   # PostgreSQL 查询超时设置（毫秒）

_BLOCKED_FUNCTIONS = {                  # 禁止调用的 SQL 函数列表
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "pg_logdir_ls", "pg_read_server_files", "dblink", "lo_import", "set_config",
}

_TABLE_NAMES = {                        # MaiData/MaiChart 表的规范化名称映射
    "maidata": "maib_maidatas",
    "maib_maidatas": "maib_maidatas",
    "maichart": "maib_maicharts",
    "maib_maicharts": "maib_maicharts",
}


class ReadOnlySqlError(ValueError):
    """用户传入的 SQL 不在 MCP 允许的只读子集内。"""


def normalize_readonly_sql(sql: str) -> tuple[str, int]:
    """验证并规范化一条仅查询 MaiData/MaiChart 的 SELECT SQL。"""
    if not sql or not sql.strip():
        raise ReadOnlySqlError("SQL 不能为空")

    try:
        statements = [statement for statement in parse(sql) if statement is not None]
    except Exception as exc:
        raise ReadOnlySqlError("SQL 语法无效") from exc

    if len(statements) != 1:
        raise ReadOnlySqlError("仅支持一条 SQL 语句")

    statement = statements[0]
    read_query_types = (exp.Select, exp.Union, exp.Intersect, exp.Except)
    if not isinstance(statement, read_query_types):
        raise ReadOnlySqlError("仅支持 SELECT 查询及其集合运算")

    mutating_node_names = (
        "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter",
        "TruncateTable", "Command", "Transaction", "Grant", "Revoke", "Into",
    )
    mutating_node_types = tuple(
        node_type for name in mutating_node_names
        if (node_type := getattr(exp, name, None)) is not None
    )
    if mutating_node_types and any(
        statement.find(node_type) is not None for node_type in mutating_node_types
    ):
        raise ReadOnlySqlError("查询中不能包含写入、定义或事务控制语句")

    for function in statement.find_all(exp.Func):
        if function.name.lower() in _BLOCKED_FUNCTIONS:
            raise ReadOnlySqlError(f"不允许调用函数: {function.name}")

    with_clause = statement.args.get("with_")
    cte_names = {
        cte.alias_or_name.lower()
        for cte in (with_clause.expressions if with_clause else [])
        if cte.alias_or_name
    }

    tables = list(statement.find_all(exp.Table))
    if not tables:
        raise ReadOnlySqlError("查询必须引用 MaiData 或 MaiChart")

    for table in tables:
        if table.args.get("db") is not None or table.args.get("catalog") is not None:
            raise ReadOnlySqlError("不支持数据库或 schema 限定符")
        table_name = table.name.lower()
        if table_name in cte_names:
            continue
        canonical_name = _TABLE_NAMES.get(table_name)
        if canonical_name is None:
            raise ReadOnlySqlError("仅支持 MaiData 和 MaiChart 两个表")
        table.set("this", exp.to_identifier(canonical_name))

    limit = statement.args.get("limit")
    applied_limit = DEFAULT_LIMIT if limit is None else 0
    if limit is None:
        statement.limit(DEFAULT_LIMIT)
    else:
        limit_expression = limit.expression
        if not isinstance(limit_expression, exp.Literal) or not limit_expression.is_int:
            raise ReadOnlySqlError("LIMIT 必须是整数")
        if not (0 <= int(limit_expression.this) <= MAX_LIMIT):
            limit.set("expression", exp.Literal.number(MAX_LIMIT))
    return statement.sql(), applied_limit


def _json_safe(value: Any) -> Any:
    """将值转换为 JSON 可序列化的形式。"""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


# ====== Public API ======

__all__ = [
    "ReadOnlySqlError",     # [异常] 不在允许范围内的 SQL
    "sql_query",            # [函数] 执行受限的只读 SQL 查询
]

async def sql_query(sql: str):
    """执行受限的只读 SQL 查询。

    Args:
        sql: 待验证并执行的 SQL 语句。
    """
    normalized_sql, applied_limit = normalize_readonly_sql(sql)
    async with get_session() as session:
        try:
            if session.get_bind().dialect.name == "postgresql":
                await session.execute(
                    text(f"SET LOCAL statement_timeout = '{POSTGRES_STATEMENT_TIMEOUT_MS}ms'")
                )
            result = await session.execute(text(normalized_sql))
        except Exception:
            logger.exception(f"[mcp_sql.sql_query] SQL failed sql={normalized_sql!r}")
            raise

        columns = list(result.keys())
        rows = [
            {key: _json_safe(value) for key, value in row._mapping.items()}
            for row in result
        ]
        return {
            "sql": normalized_sql,
            "default_limit_applied": bool(applied_limit),
            "max_limit": MAX_LIMIT,
            "columns": columns,
            "rows": rows,
        }
