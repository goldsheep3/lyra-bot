import re

from .cmd_query import cmd_query
from .cmd_update import cmd_update, cmd_adjust


async def radar(event):
    # 定义正则，捕获命令主体和操作部分
    pattern = re.compile(
        r"^[.。 ]\s*([^\s\d]+)\s*("       # 命令主体
        r"几|"                           # 2.1 查询
        r"([1-9]?\d)|"                   # 2.2 直接数字
        r"\+\s*([1-9]?\d)|"              # 2.3 增加
        r"-\s*([1-9]?\d)"                # 2.4 减少
        r")"
    )
    m = pattern.match(str(event.message))
    if not m:
        return None
    group_id = event.group_id
    sender_name = event.sender.card

    jt_code = m.group(1)  # 命令主体
    op = m.group(2)       # 操作部分（几/数字/+数字/-数字）

    # 分配处理逻辑
    if op == "几":
        # 查询
        result = await cmd_query(group_id, jt_code)
    elif m.group(3):
        # 直接数字修改
        card_number = int(m.group(3))
        result = await cmd_update(group_id, jt_code, card_number, sender_name)
    elif m.group(4):
        # 增加
        card_number_adjust = int(m.group(4))
        result = await cmd_adjust(group_id, jt_code, card_number_adjust, sender_name)
    elif m.group(5):
        # 减少
        card_number_adjust = -int(m.group(5))
        result = await cmd_adjust(group_id, jt_code, card_number_adjust, sender_name)
    else:
        return None

    return result
