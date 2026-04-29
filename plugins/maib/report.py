from collections.abc import Sequence
from typing import Any

from PIL import Image

from . import image_gen
from .constants import DF_FC_DICT, DF_FS_DICT


# 从 DF_FC_DICT 和 DF_FS_DICT 构建标签字典（取第一个元素并 upper）
_COMBO_LABELS = {code: value[0].upper() for code, value in DF_FC_DICT.items()}
_COMBO_LABELS[0] = "None"

_SYNC_LABELS = {code: value[0].upper() for code, value in DF_FS_DICT.items()}
_SYNC_LABELS[0] = "None"


def _format_achievement_report_value(value: Any, *, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except Exception:
        return str(value)


def _format_change_label(code: Any, mapping: dict[int, str]) -> str:
    try:
        return mapping.get(int(code), str(code))
    except Exception:
        return str(code)


def _format_change_log_lines(change_log: dict[str, Any]) -> list[str]:
    song = change_log.get("song") or {}
    new_payload = change_log.get("new") or {}
    old_payload = change_log.get("old")

    shortid = song.get("shortid", "?")
    title = song.get("title", "")
    difficulty_text = song.get("difficulty_text") or song.get("difficulty", "")

    lines = [f"{shortid}. {title}({difficulty_text})"]

    if old_payload is None:
        lines.extend([
            f"Achievement: {_format_achievement_report_value(new_payload.get('achievement', ''))}",
            f"DX Score: {new_payload.get('dxscore', '')}",
            f"Combo: {_format_change_label(new_payload.get('combo'), _COMBO_LABELS)}",
            f"Sync: {_format_change_label(new_payload.get('sync'), _SYNC_LABELS)}",
        ])
    else:
        lines.extend([
            f"Achievement: {_format_achievement_report_value(old_payload.get('achievement', ''))} -> {_format_achievement_report_value(new_payload.get('achievement', ''))}",
            f"DX Score: {old_payload.get('dxscore', '')} -> {new_payload.get('dxscore', '')}",
            f"Combo: {_format_change_label(old_payload.get('combo'), _COMBO_LABELS)} -> {_format_change_label(new_payload.get('combo'), _COMBO_LABELS)}",
            f"Sync: {_format_change_label(old_payload.get('sync'), _SYNC_LABELS)} -> {_format_change_label(new_payload.get('sync'), _SYNC_LABELS)}",
        ])

    return lines


def _split_change_diffs(data_diffs: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    diff_insert: list[dict[str, Any]] = []
    diff_update: list[dict[str, Any]] = []
    for data_diff in data_diffs:
        action = data_diff.get("action")
        if action == "insert":
            diff_insert.append(data_diff)
        elif action == "update":
            diff_update.append(data_diff)
    return diff_insert, diff_update


def _build_detail_text(data_diffs: Sequence[dict[str, Any]]) -> str | None:
    if not data_diffs:
        return None

    diff_insert, diff_update = _split_change_diffs(data_diffs)
    if not diff_insert and not diff_update:
        return None

    detail_lines: list[str] = ["发现成绩更新！"]

    if diff_insert:
        detail_lines.append("")
        detail_lines.append("新增成绩数据：")
        for change_log in diff_insert:
            detail_lines.extend(_format_change_log_lines(change_log))

    if diff_update:
        detail_lines.append("")
        detail_lines.append("更新了已有成绩：")
        for change_log in diff_update:
            detail_lines.extend(_format_change_log_lines(change_log))

    return "\n".join(detail_lines)


def _build_summary_text(
    data_diffs: Sequence[dict[str, Any]],
    summary_lines: Sequence[str] | None = None,
) -> str:
    if summary_lines is not None:
        return "\n".join(summary_lines)

    diff_insert, diff_update = _split_change_diffs(data_diffs)
    return "\n".join([
        "发现成绩更新！",
        f"- 新增成绩数：{len(diff_insert)}",
        f"- 更新成绩数：{len(diff_update)}",
        f"- 实际变更数：{len(data_diffs)}",
    ])


def build_achievements_report(
    data_diffs: Sequence[dict[str, Any]],
    *,
    summary_lines: Sequence[str] | None = None,
) -> tuple[str, Image.Image | None]:
    """把结构化成绩变更转成可发送的摘要和明细图。"""
    if not data_diffs:
        return "", None

    summary_text = _build_summary_text(data_diffs, summary_lines=summary_lines)
    detail_text = _build_detail_text(data_diffs)
    detail_image = image_gen.simple_list(detail_text) if detail_text else None
    return summary_text, detail_image


def build_import_report(
    data_diffs: Sequence[dict[str, Any]] | None,
    *,
    file_count: int = 0,
    parsed_count: int = 0,
    unmatched_titles: Sequence[str] | None = None,
    invalid_diff_items: Sequence[str] | None = None,
    parse_failed_items: Sequence[str] | None = None,
) -> tuple[str, str, Image.Image | None]:
    """为 JSON 导入生成完整报告（摘要、警告、明细图）。

    Args:
        data_diffs: 成绩变更结构化数据，为空时表示没有可入库的有效成绩。
        file_count: 文件中的原始记录总数。
        parsed_count: 成功解析的成绩数。
        unmatched_titles: 曲库未匹配的曲名列表。
        invalid_diff_items: 难度字段无法识别的项目列表。
        parse_failed_items: 解析失败的项目列表。

    Returns:
        (summary_text, warning_text, detail_image)
    """

    def _format_preview(items: Sequence[str], limit: int = 12) -> str:
        if not items:
            return ""
        items_list = list(items)
        show = items_list[:limit]
        if len(items_list) > limit:
            return f"{'、'.join(show)} 等 {len(items_list)} 项"
        return "、".join(show)

    # 构建摘要
    summary_lines: list[str] = ["导入完成，以下为实际入库结果："]
    summary_lines.append(f"- 文件记录总数：{file_count}")
    summary_lines.append(f"- 可识别成绩数：{parsed_count}")

    if data_diffs:
        insert_count = sum(1 for item in data_diffs if item.get("action") == "insert")
        update_count = sum(1 for item in data_diffs if item.get("action") == "update")
        changed_count = len(data_diffs)
        unchanged_count = max(0, parsed_count - changed_count)

        summary_lines.append(
            f"- 实际入库变更：{changed_count}（新增 {insert_count} / 更新 {update_count}）"
        )
        if unchanged_count > 0:
            summary_lines.append(f"- 未写入（已有更优或相同成绩）：{unchanged_count}")
    else:
        summary_lines.append("- 实际入库变更：0")

    summary_text = "\n".join(summary_lines)

    # 构建警告
    warning_lines: list[str] = []
    if unmatched_titles:
        warning_lines.append(
            f"- 曲库尚未匹配（数据库未更新）：{_format_preview(unmatched_titles)}"
        )
    if invalid_diff_items:
        warning_lines.append(
            f"- 难度字段无法识别：{_format_preview(invalid_diff_items)}"
        )
    if parse_failed_items:
        warning_lines.append(
            f"- 记录解析异常：{_format_preview(parse_failed_items)}"
        )

    warning_text = ""
    if warning_lines:
        warning_text = "\n\n以下数据未入库（正常情况）：\n" + "\n".join(warning_lines)

    # 构建明细图
    detail_image: Image.Image | None = None
    if data_diffs:
        detail_text = _build_detail_text(data_diffs)
        detail_image = image_gen.simple_list(detail_text) if detail_text else None

    return summary_text, warning_text, detail_image
