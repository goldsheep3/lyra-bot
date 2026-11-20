from typing import Sequence

from .._refactoring import _id_remapper as _idmap


async def get_pending_mappings() -> Sequence[tuple[int, int]]:
    """返回所有待处理的 shortid 映射。"""
    return await _idmap.get_pending_mappings()


async def resolve_mapping(original_id: int, mapped_id: int):
    """执行一条 shortid 映射迁移。

    Args:
        original_id: 待迁移的原始 shortid。
        mapped_id: 原始 shortid 应映射到的目标 shortid。
    """
    return await _idmap.resolve_id_mapping(original_id, mapped_id)
