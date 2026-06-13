from dataclasses import dataclass
from typing import Optional

from .constants import SERVER_TAG, DIFFS_DICT, DF_FC_DICT, DF_FS_DICT
from .utils import MaiChartAch
from .image_gen import Image, simple_list


def _format_label(code: int, mapping: dict[int, tuple[str, ...]], index: int = 0) -> str:
    try:
        return mapping.get(code, (str(code),))[index]
    except Exception:
        return str(code)


@dataclass
class MaiChartAchDiff:
    """成绩变更信息"""
    shortid: int
    title: str
    difficulty: int
    server: SERVER_TAG
    new_ach: MaiChartAch
    old_ach: Optional[MaiChartAch] = None

@dataclass
class MaiChartAchDiffReport:
    """成绩变更报告"""

    updated_song: list[MaiChartAchDiff]
    new_song: list[MaiChartAchDiff]
    no_data_song: list[tuple[int, str, int]]  # (曲目 ID, 曲目名, 难度) 列表，表示没有数据的谱面
    other_error_song: list[dict]

    @property
    def has_changes(self) -> bool:
        """是否存在实际入库的变更"""
        return len(self.updated_song) + len(self.new_song) > 0

def _format_diff_lines(diff: MaiChartAchDiff) -> str:
    """格式化单条变更明细"""
    new = diff.new_ach
    old = diff.old_ach
    old_dxscore = old.dxscore if old else 0

    infos = [
        f"{diff.shortid}. {diff.title}【{_format_label(diff.difficulty, DIFFS_DICT, 1)}】",
        '  ',
        "0.0000%(   )(    )",  # index = 2
        '->',
        f"{new.achievement:.4f}%({_format_label(new.combo, DF_FC_DICT,)})({_format_label(new.sync, DF_FS_DICT)})",
        ' | ',
        f"DXSCORE: {old_dxscore}->{new.dxscore}"
    ]
    
    if old is not None:
        # 替换成实际旧值
        infos[2] = f"{old.achievement:.4f}%({_format_label(old.combo, DF_FC_DICT)})({_format_label(old.sync, DF_FS_DICT)})"
    
    return ''.join(infos)

def build_diff_report(
    report: MaiChartAchDiffReport, 
    *, 
    file_count: int = 0, 
    parsed_count: int = 0
) -> tuple[str, Image.Image | None]:
    """成绩更新报告生成入口"""

    # 快速确定：无变更直接结束
    if report.has_changes:
        lines = [
            "发现成绩数据更新！",
            f"· 记录解析成功: {parsed_count}/{file_count}",
            f"· 实际变更: {len(report.new_song) + len(report.updated_song)}",
            f"· 其中新歌/更新: {len(report.new_song)} / {len(report.updated_song)}"
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
    
    # 图片生成
    detail_lines = ["乐曲成绩变更详情:"]
    if report.new_song:
        detail_lines.append("\n【新增成绩】")
        for diff in report.new_song:
            detail_lines.append(_format_diff_lines(diff))
    if report.updated_song:
        detail_lines.append("\n【更新成绩】")
        for diff in report.updated_song:
            detail_lines.append(_format_diff_lines(diff))
            
    detail_text = "\n".join(detail_lines)
    detail_image = simple_list(detail_text) if report.has_changes else None

    return final_text, detail_image
