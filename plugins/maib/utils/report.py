"""utils/report.py 成绩变更报告生成模块"""
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from ..utils.map import Difficulties, Combos, Syncs
from .enums import Server
from .models import MaiChartAch
from .calculator import get_dxscore_star_count



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
    server: Server
    new_ach: MaiChartAch
    old_ach: Optional[MaiChartAch] = None

    @property
    def message(self) -> str:
        """生成单条成绩变更的文本描述"""
        # Line 1
        text = (
            f"{self.shortid}. "
            f'{(self.title[:20] + chr(46)*3) if len(self.title) > 20 else self.title} '
            f"{Difficulties.text_cn_short(self.difficulty) or str(self.difficulty)}\n"
        )
        # Line 2
        text += ' '*4
        # Line 2 - old achievement
        if self.old_ach is None:
            text += "0.0000%(    )(    )"
        else:
            ach_old = f"{self.old_ach.achievement:.4f}%"
            combo_old = Combos.text_short(self.old_ach.combo, default=str(self.old_ach.combo))
            sync_old = Syncs.text_short(self.old_ach.sync, default=str(self.old_ach.sync))
            text += (
                f"{ach_old:>8}"
                f"({combo_old:>4})"
                f"({sync_old:>4})"
            )
        text += "  ->  "
        # Line 2 - new achievement
        ach_new = f"{self.new_ach.achievement:.4f}%"
        combo_new = Combos.text_short(self.new_ach.combo, default=str(self.new_ach.combo))
        sync_new = Syncs.text_short(self.new_ach.sync, default=str(self.new_ach.sync))
        text += (
            f"{ach_new:>8}"
            f"({combo_new:>4})"
            f"({sync_new:>4})"
        )
        text += "  |  "
        # Line 2 - dxscore
        text += (
            "DXSCORE: "
            f"{self.old_ach.dxscore if self.old_ach is not None else 0}"
            f"(✦{get_dxscore_star_count(self.old_ach.dxscore, self.old_ach.dxscore_max) if self.old_ach is not None else 0})"
            "  ->  "
            f"{self.new_ach.dxscore}"
            f"(✦{get_dxscore_star_count(self.new_ach.dxscore, self.new_ach.dxscore_max)})"
        )
        
        return text


@dataclass
class MaiChartAchDiffReport:
    """成绩变更报告（单次）"""

    maib: str = "maimaiDX"
    server: Server = Server.JP
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



def diff_message_lite(shortid: int, title: str, difficulty: int, reason: str) -> str:
    difficulty_text = Difficulties.text_cn_short(difficulty) or str(difficulty)
    return f"{shortid}. {title}    {difficulty_text} \n    {reason}"


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
        new_count = len(report.new_song)
        update_count = len(report.updated_song) + new_count
        text = (
            f"乐曲成绩数据更新~\n"
            f"记录解析: {parsed_count}/{file_count}, "
            f"更新{update_count}(新增{new_count}), "
        )
    elif report.no_data_song or report.other_error_song:
        text = (
            f"乐曲数据没有发生变化喔~\n"
            f"记录解析: {parsed_count}/{file_count}, "
        )
    else:
        enable_image = False
        text = "乐曲数据没有发生变化喔~"

    if report.no_data_song:
        text += f"曲库未匹配或无数据: {len(report.no_data_song)}, "
    if report.other_error_song:
        text += f"记录解析异常: {len(report.other_error_song)}, "
    
    text = text.rstrip(", ")
    
    if not enable_image:
        return text, None

    # 图片生成
    detail_lines = [f"{report.maib} [{report.server}] 乐曲成绩变更详情:"]
    if report.new_song:
        detail_lines.append("\n【NEW / 新增成绩】")
        for diff in report.new_song:
            detail_lines.append(diff.message)
    if report.updated_song:
        detail_lines.append("\n【UPDATE / 更新成绩】")
        for diff in report.updated_song:
            detail_lines.append(diff.message)
    if report.no_data_song:
        detail_lines.append("\n【NONE / 无数据曲目】")
        for song_id, title, difficulty in report.no_data_song:
            detail_lines.append(diff_message_lite(song_id, title, difficulty, "曲库中无该数据 (会在未来曲库更新后生效)"))
    if report.other_error_song:
        detail_lines.append("\n【ERROR / 解析异常曲目】")
        for error in report.other_error_song:
            song_id = error.get("song_id", "?????")
            title = error.get("title", "Unknown Music")
            difficulty = error.get("difficulty", "??????")
            detail_lines.append(diff_message_lite(song_id, title, difficulty, "曲目解析异常 (可能是部分宴谱或其他异常数据)"))

    detail_text = "\n".join(detail_lines)
    if report.has_changes:
        from ..image_gen import draw_simple_board, FontManager, FontCode

        detail_image = draw_simple_board(detail_text, font=FontManager.font(FontCode.SmileySans, size=16))
    else:
        detail_image = None

    return text, detail_image

