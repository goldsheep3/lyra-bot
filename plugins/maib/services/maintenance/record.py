from .._refactoring import _record, _sync


async def backfill_and_rebuild_achievements() -> None:
    """回填历史记录的乐曲 ID，并重建受影响用户的成绩。"""
    affected_by_user = await _record.backfill_record_shortids()
    for qq, record_keys in affected_by_user.items():
        ach_list = await _record.get_record_achs(qq, list(record_keys))
        if ach_list:
            await _sync.upd_ach_batch(qq, ach_list)
