from datetime import datetime
from pathlib import Path


def save_fortune_history(
        history_path: Path, today: datetime, group_id: int, user_id: int, sub_titles: list[str], logger) -> None:
    date_str = today.strftime('%Y%m%d')
    sub_fortunes_str = ";".join(sub_titles)
    new_line = f"{date_str},{group_id},{user_id},{sub_fortunes_str}\n"

    # 若文件不存在则写入表头
    if not history_path.exists():
        with open(history_path, 'w', encoding='utf-8') as f:
            f.write("date,group_id,user_id,sub_fortunes\n")

    # 倒序逐行读取并检查
    duplicate_found = False
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines[1:]):  # 跳过表头
                line = line.rstrip('\n')
                if line == new_line.rstrip('\n'):
                    duplicate_found = True
                    break
                # 检查 date 字段，过日直接中断
                line_date = line.split(',', 1)[0]
                if line_date != date_str:
                    break
    except Exception as e:
        logger.error(f"读取运势历史文件时发生错误。{e}")
        return

    # 没有重复则写入
    if not duplicate_found:
        with open(history_path, 'a', encoding='utf-8') as f:
            f.write(new_line)
            