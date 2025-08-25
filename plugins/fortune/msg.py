from datetime import datetime

from .desc import MAIN_FORTUNE_DESC, SUB_FORTUNE_TITLES
from .core import _get_daily_seed


def build_fortune_message(
        main_title: str,
        user_id: int,
        date: datetime,
        sub_fortunes: list[str],
) -> str:
    date_str = date.strftime("%Y%m%d")
    # 用主运势和 user_id+date 再次生成 seed，分配唯一描述
    desc_seed = _get_daily_seed(user_id, f"{date_str}_{main_title}")
    desc_list = MAIN_FORTUNE_DESC.get(main_title, [""])
    desc_idx = desc_seed % len(desc_list)
    main_desc = desc_list[desc_idx]

    lines = [
        f"小梨来啦！你今天的运势是：【{main_title}】！",
        main_desc,
        "",
        "今日你的特别运势是："
        ]
    for i in range(0, len(SUB_FORTUNE_TITLES), 2):
        left = f"{SUB_FORTUNE_TITLES[i]}  {sub_fortunes[i]}"
        if i + 1 < len(SUB_FORTUNE_TITLES):
            right = f"{SUB_FORTUNE_TITLES[i+1]}  {sub_fortunes[i+1]}"
        else:
            right = ""
        lines.append(f"{left}{'  |  ' if right else ''}{right}")
    lines.append("")
    lines.append("无论运势如何，小梨都在陪着你呢！")

    return "\n".join(lines)