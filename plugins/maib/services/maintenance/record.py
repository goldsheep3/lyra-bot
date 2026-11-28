from .._refactoring import _record, _sync
from ...utils.models import Server


async def backfill_and_rebuild_achievements() -> None:
    """回填历史记录的乐曲 ID，并重建受影响用户的成绩。"""
    affected_by_user = await _record.backfill_record_shortids()
    for qq, record_keys in affected_by_user.items():
        ach_list = await _record.get_record_achs(qq, list(record_keys))
        if ach_list:
            for ach in ach_list:
                if ach.server == Server.JP:
                    await _sync.set_mca(ach, server=Server.JP)
                    break
            for ach in ach_list:
                if ach.server == Server.CN:
                    await _sync.set_mca(ach, server=Server.CN)
                    break
