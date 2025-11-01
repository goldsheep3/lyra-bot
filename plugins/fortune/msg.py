from datetime import datetime
from typing import Dict, Tuple, Optional

from .core import get_text_index


def is_ascii(c: str) -> bool: return ord(c) < 128


def calc_display_length(s: str) -> int: return sum(1 if is_ascii(c) else 3 for c in s)


def format_fortune_lines(sub_fortunes: list[tuple[str, str]]) -> str:
    def format_text(t: tuple[str, str], w: int) -> str:
        text = f"{t[0]}{t[1]}"
        p = w - calc_display_length(text)
        return f"{t[0]}{' ' * p}{t[1]}"

    if not sub_fortunes: return ""
    # 步骤一：拆分为左/右两列
    left_entries, right_entries = [], []
    for idx, entry in enumerate(sub_fortunes):
        if idx % 2 == 0:
            left_entries.append(entry)
        else:
            right_entries.append(entry)

    # 补齐右列长度与左列一致
    while len(right_entries) < len(left_entries):
        right_entries.append(("", ""))

    # 步骤二：分别计算最大宽度+1（至少有一个空格隔开）
    left_width = max(calc_display_length(e[0]) + calc_display_length(e[1]) for e in left_entries) + 1
    right_width = max(calc_display_length(e[0]) + calc_display_length(e[1]) for e in right_entries) + 1

    # 步骤三：格式化内容，补齐空格
    lines = []
    for left, right in zip(left_entries, right_entries):
        left_formatted = format_text(left, left_width)
        if any(right): # 若右列非空
            right_formatted = format_text(right, right_width)
            lines.append(f"{left_formatted} | {right_formatted}")
        else: # 若右列空
            lines.append(f"{left_formatted}")

    return "\n".join(lines)


def get_main_desc(main_fortune_desc, main_title:str, user_id: str, date: datetime) -> str:
    desc_list = main_fortune_desc.get(main_title, [""])
    main_desc = desc_list[get_text_index(user_id, date, len(desc_list))]
    return main_desc


def build_fortune_message(
        main_title: str,
        sub_fortunes: list[tuple[str, str]],
        main_desc: Optional[str] = None,
        main_fortune_desc: Optional[Dict[str, Tuple[str, ...]]] = None,
) -> str:
    if not main_desc and main_fortune_desc is not None:
        main_desc = get_main_desc(main_fortune_desc, main_title, "", datetime.now())
    elif not any((main_desc, main_fortune_desc)): return ""

    lines = f"""
小梨来啦！你今天的运势是：【{main_title}】！
{main_desc}

今日你的特别运势：
{format_fortune_lines(sub_fortunes)}

无论运势如何，小梨都在陪着你呢！
"""

    return lines.strip()