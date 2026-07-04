"""sync/ 数据同步、缓存与查分器适配模块"""
from datetime import datetime
from typing import Optional

from ..constants import ASIA_SHANGHAI, COMBO_MAP, SYNC_MAP
from ..utils.models import MaiChartAch, MaiData


# Cache: link 绑定临时存储
link_cache: dict[int, tuple[str, int]] = {
    # user_id: (link_hash, expiration_timestamp)
}
link_hash_index: dict[str, int] = {
    # hash -> user_id
}


def _parse_single_sy_record(record: dict) -> Optional[MaiChartAch]:
    """将单条原始 record 字典解析为 MaiChartAch 对象，若无效则返回 None"""
    shortid = record.get("song_id")
    level_idx = record.get("level_index")
    if not shortid or level_idx is None:
        return None

    return MaiChartAch(
        shortid=shortid,
        difficulty=level_idx + 2,
        server="CN",
        achievement=record.get("achievements", 0.0),
        dxscore=record.get("dxScore", 0),
        combo=COMBO_MAP.key(record.get("fc", "").lower()) or 0,
        sync=SYNC_MAP.key(record.get("fs", "").lower()) or 0,
        update_time=datetime.now(ASIA_SHANGHAI)
    )

def parse_sy_player_record(maidata: MaiData, records: list) -> MaiData:
    """解析水鱼玩家记录并更新到 MaiData 对象中"""
    for record in records:
        if record.get("song_id") != maidata.shortid:
            continue
            
        ach = _parse_single_sy_record(record)
        if ach and (chart := maidata.get_chart(ach.difficulty)):
            chart.set_ach(ach)
    
    return maidata        

def get_sy_records(records: list[dict]) -> list[MaiChartAch]:
    """解析水鱼记录为成就对象"""
    return [
        ach for record in records 
        if (ach := _parse_single_sy_record(record)) is not None
    ]
