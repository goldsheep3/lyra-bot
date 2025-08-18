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


async def calculate_score(event: Event, matcher):
    """捕获消息，下载谱面文件并上传至群文件"""

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
                rate = float(match.group(2))
            except ValueError:
                await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: 难度和完成率必须是数字")
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
            score = int(difficulty * rate * factor)
            await matcher.finish(f'定数 {difficulty} 的完成率 {rate} 对应的ra为 {score}')
    return None