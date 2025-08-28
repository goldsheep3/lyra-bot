import re
from typing import List, Tuple

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event

# 表格数据，完成率从高到低排序
RATE_FACTOR_TABLE: List[Tuple[float, float]] = [
    (100.5000, 0.224),
    (100.4999, 0.222),
    (100.0000, 0.216),
    (99.9999, 0.214),
    (99.5000, 0.211),
    (99.0000, 0.208),
    (98.9999, 0.206),
    (98.0000, 0.203),
    (97.0000, 0.200),
    (96.9999, 0.176),
    (94.0000, 0.168),
    (90.0000, 0.152),
    (80.0000, 0.136),
    (79.9999, 0.128),
    (75.0000, 0.120),
    (70.0000, 0.112),
    (60.0000, 0.096),
    (50.0000, 0.080),
    (40.0000, 0.064),
    (30.0000, 0.048),
    (20.0000, 0.032),
    (10.0000, 0.016),
]

# 完成率别名映射表
rate_alias_map = {
    "鸟加": 100.5,
    "鸟家": 100.5,
    "sss+": 100.5,
    "3s+": 100.5,
    "鸟": 100.0,
    "sss": 100.0,
    "3s": 100.0,
    "ss+": 99.5,
    "2s+": 99.5,
    "ss": 99.0,
    "2s": 99.0,
    "s+": 98.0,
    "s": 97.0,
    "aaa": 94.0,
    "3a": 94.0,
    "aa": 90.0,
    "2a": 90.0,
    "a": 80.0,
    "bbb": 75.0,
    "3b": 75.0,
    "bb": 70.0,
    "2b": 70.0,
    "b": 60.0,
    "c": 50.0,
    "d": 0.0,
}


async def calculate_score(event: Event, matcher):
    """捕获消息，计算 dx rating"""

    msg = str(event.get_message())
    logger.info(f"收到消息: {msg}")

    match = re.search(r"ra\s+(\S+)(?:\s+(\S+))?", msg)
    if match:
        # 判断是否为 help 命令
        if match.group(1).lower() == "help":
            help_text = (
                "使用方法：\n"
                "ra <难度> <完成率>\n"
                "例如：ra 13.2 100.1000\n"
                "计算给定难度和完成率的得分。"
            )
            await matcher.finish(help_text)
        # 判断是否有两个参数
        elif match.group(2) is None:
            await matcher.finish("这样的数字小梨算不出来的啊（\nError: 参数不完整")
        else:
            # 提取难度和完成率
            try:
                difficulty = float(match.group(1))
                rate_str = match.group(2)
                try:
                    rate = float(rate_str)
                except ValueError:
                    # 尝试用别名映射
                    rate = rate_alias_map.get(rate_str.lower())
                    if rate is None:
                        await matcher.finish(f"这样的数字小梨算不出来的啊qwq\nError: 完成率参数不支持")
                        return None
            except ValueError:
                await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: 难度和完成率必须是数字或支持的文本别名")
                return None
            logger.info(f"提取到难度: {difficulty}, 完成率: {rate}")
            # 计算
            factor = 0.0
            for threshold, f in RATE_FACTOR_TABLE:
                if rate >= threshold:
                    factor = f
                    break
            # 若完成率低于表最低值，因子为0
            if rate < RATE_FACTOR_TABLE[-1][0]:
                factor = 0.0
            dxrating = int(difficulty * rate * factor)
            # 格式化完成率为四位小数
            rate_fmt = f"{rate:.4f}"
            await matcher.finish(f'小梨算出来咯！\n定数{difficulty}*{rate_fmt}% -> Rating: {dxrating}')
    return None