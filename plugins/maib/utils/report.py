"""utils/report.py 成绩变更报告生成模块"""
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from ..constants import server, DIFFICULTY_MAP as DiffMap, COMBO_MAP as ComboMap, SYNC_MAP as SyncMap
from .models import MaiChartAch


__all__ = [
    "MaiChartAchDiff",
    "MaiChartAchDiffReport",
    "build_diff_report"
]


@dataclass
class MaiChartAchDiff:
    """成绩变更信息（单条）"""
    shortid: int
    title: str
    difficulty: int
    server: server
    new_ach: MaiChartAch
    old_ach: Optional[MaiChartAch] = None

    def get_diff_text(self) -> str:
        """获取变更文本"""
        new = self.new_ach
        old = self.old_ach
        old_dxscore = old.dxscore if old else 0

        infos = [
            f"{self.shortid}. {self.title}【{DiffMap.label(self.difficulty) or str(self.difficulty)}】",
            '  ',
            "0.0000%(   )(    )",  # index = 2
            '->',
            f"{new.achievement:.4f}%({ComboMap.label(new.combo) or str(new.combo)})({SyncMap.label(new.sync) or str(new.sync)})"
            ' | ',
            f"DXSCORE: {old_dxscore}->{new.dxscore}"
        ]
        
        if old is not None:
            # 替换成实际旧值
            infos[2] = f"{old.achievement:.4f}%({ComboMap.label(old.combo) or str(old.combo)})({SyncMap.label(old.sync) or str(old.sync)})"
        
        return ''.join(infos)


@dataclass
class MaiChartAchDiffReport:
    """成绩变更报告（单次）"""

    no_update_song_count: int = 0
    updated_song: list[MaiChartAchDiff] = field(default_factory=list)
    new_song: list[MaiChartAchDiff] = field(default_factory=list)
    no_data_song: list[tuple[int, str, int]] = field(default_factory=list)  # (曲目 ID, 曲目名, 难度) 列表，表示没有数据的谱面
    other_error_song: list[dict] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """是否存在实际入库的变更"""
        return len(self.updated_song) + len(self.new_song) > 0

    @property
    def total_song_count(self) -> int:
        """总曲目数"""
        return self.no_update_song_count + len(self.updated_song) + len(self.new_song) + len(self.no_data_song) + len(self.other_error_song)


def build_diff_report(
    report: MaiChartAchDiffReport, 
    *, 
    file_count: int = 0, 
    parsed_count: int = 0,
    enable_image: bool = True
) -> tuple[str, Image.Image | None]:
    """成绩更新报告生成入口"""

    # 快速确定：无变更直接结束
    if report.has_changes:
        success_rate = parsed_count / file_count if file_count > 0 else 0
        update_count = len(report.updated_song) + len(report.new_song)
        update_rate = update_count / parsed_count if parsed_count > 0 else 0
        lines = [
            "乐曲成绩数据更新~",
            f"· 解析了{file_count}条记录，其中成功{parsed_count}条，成功率{success_rate:.2%}",
            f"· 记录更新{len(report.updated_song)}条，新增{len(report.new_song)}条，共计{update_count}条，更新率{update_rate:.2%}",
            ]
    elif report.no_data_song or report.other_error_song:
        lines = [
            "乐曲数据没有发生变化喔~",
            f"· 记录解析成功: {parsed_count}/{file_count}"
        ]
    else:
        return "乐曲数据没有发生变化喔~", None

    if report.no_data_song:
        lines.append(f"· 曲库未匹配或无数据: {len(report.no_data_song)}")
    if report.other_error_song:
        lines.append(f"· 记录解析异常: {len(report.other_error_song)}")
    
    final_text = "\n".join(lines)
    
    if not enable_image:
        return final_text, None

    # 图片生成
    detail_lines = ["乐曲成绩变更详情:"]
    if report.new_song:
        detail_lines.append("\n【新增成绩】")
        for diff in report.new_song:
            detail_lines.append(diff.get_diff_text())
    if report.updated_song:
        detail_lines.append("\n【更新成绩】")
        for diff in report.updated_song:
            detail_lines.append(diff.get_diff_text())
    if report.no_data_song:
        detail_lines.append("\n【无数据曲目】")
        for song_id, title, diff in report.no_data_song:
            detail_lines.append(f"{song_id}. {title}【{DiffMap.label(diff) or str(diff)}】")
    if report.other_error_song:
        detail_lines.append("\n【解析异常曲目】")
        for error in report.other_error_song:
            song_id = error.get("song_id", "?????")
            title = error.get("title", "Unknown Music")
            diff = error.get("difficulty", "??????")
            detail_lines.append(f"{song_id}. {title}【{DiffMap.label(diff) or str(diff)}】 - 解析异常")
            
    detail_text = "\n".join(detail_lines)
    if report.has_changes:
        from ..image_gen import simple_list

        detail_image = simple_list(detail_text)
    else:
        detail_image = None

    return final_text, detail_image
