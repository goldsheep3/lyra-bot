from typing import List, Tuple
from pathlib import Path

from .utils import MaiChart, MaiChartAch, DF_FC_MAP, DF_FS_MAP
from .db_utils import get_shortids_by_version, get_song_by_id
from .json_manager import UserDataManager


async def maib50_calc(cache_path: Path, user_id: int, current_version: int, developer_token: str,
                      cn: bool = True) -> Tuple[List[MaiChart], List[MaiChart]]:
    """通过版本筛选查询用户成绩数据，返回 b50 列表组"""
    user_datas, _ = await UserDataManager.get_user_data(user_id, cache_path, developer_token)
    if user_datas:
        records = user_datas.get("records", [])
        version = current_version - 1 if 24 < current_version < 2000 else current_version
        version_map = await get_shortids_by_version(version, cn=cn, r=1)
        b35 = []
        b15 = []
        for record in records:
            b_count = 15 if record["shortid"] in version_map else 35
            b_list = b15 if b_count == 15 else b35
            if len(b_list) == 0 or b_list[-1]["ra"] < record["ra"]:
                b_list.append(record)
                b_list.sort(key=lambda x: x["ra"], reverse=True)
                if len(b_list) > b_count:
                    b_list.pop()
        b35_charts = []
        b15_charts = []
        for b_list, b_target_list in zip([b35, b15], [b35_charts, b15_charts]):
            for record in b_list:
                shortid = record["shortid"]
                difficulty = record["level_index"]+2
                
                dxscore_max = 0
                mdt = await get_song_by_id(shortid)
                if mdt:
                    charts = mdt.get_charts()
                    target_chart = next((c for c in charts if c.difficulty == difficulty), None)
                    if target_chart:
                        dxscore_max = (
                            target_chart.note_count_tap +
                            target_chart.note_count_hold +
                            target_chart.note_count_slide +
                            target_chart.note_count_touch +
                            target_chart.note_count_break
                        ) * 3
 
                chart = MaiChart(
                    shortid=shortid,
                    difficulty=difficulty,
                    lv=record["ds"],
                    ach=MaiChartAch(
                        achievement=record["achievements"],
                        dxscore=record["dxScore"],
                        dxscore_max=dxscore_max,
                        combo=DF_FC_MAP.get(record["combo"]),
                        sync=DF_FS_MAP.get(record["sync"]),
                        )
                )
                b_target_list.append(chart)
        return b35_charts, b15_charts
    return [], []
