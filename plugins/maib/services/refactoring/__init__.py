"""正在收拢边界的新 services API。

这些模块稳定后会移动到 :mod:`plugins.maib.services` 顶层。
"""

from . import aime, alias, b50, catalog, mcp_sql, link, user

__all__ = ["aime", "alias", "b50", "catalog", "mcp_sql", "link", "user"]
