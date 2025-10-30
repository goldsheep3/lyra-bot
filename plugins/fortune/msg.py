from datetime import datetime
from typing import Dict, Tuple, Optional

from .core import get_text_index


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

    lines = [
        f"小梨来啦！你今天的运势是：【{main_title}】！",
        main_desc,
        "",
        "今日你的特别运势："
    ]
    for i in range(0, len(sub_fortunes), 2):
        left = f"{sub_fortunes[i][0]}  {sub_fortunes[i][1]}"
        if i + 1 < len(sub_fortunes):
            right = f"{sub_fortunes[i+1][0]}  {sub_fortunes[i+1][1]}"
        else:
            right = ""
        lines.append(f"{left}{'  |  ' if right else ''}{right}")
    lines.append("")
    lines.append("无论运势如何，小梨都在陪着你呢！")

    return "\n".join(lines)