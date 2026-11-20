from typing import Sequence

from ..utils.report import MaiChartAchDiffReport
from ..utils.sync import LyraRecordV3
from ._refactoring import _record, _sync


async def ingest_records(records: Sequence[LyraRecordV3], *, qq: int) -> MaiChartAchDiffReport:
    """批量上传 LyraRecordV3 成绩记录并返回报告。

    Args:
        records: 待导入的原始游玩记录。
        qq: 记录所属用户的 QQ 号。
    """
    record_keys, unmatched_items = await _record.add_record_batch(qq, records)
    ach_list = await _record.get_record_achs(qq, list(record_keys))
    report = await _sync.upd_ach_batch(qq, ach_list) if ach_list else MaiChartAchDiffReport()
    for title, difficulty in unmatched_items:
        report.no_data_song.append((0, title, difficulty))
    return report
