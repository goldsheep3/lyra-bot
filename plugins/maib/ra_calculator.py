from typing import Tuple, Dict, Optional

from nonebot import logger
from nonebot.internal.matcher import Matcher

from .utils import DifficultyVariant, RATE_FACTOR_TABLE, DIFFICULTY_MAP, init_difficulty


RATE_ALIAS_MAP: Dict[str, float] = {
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
}  # 完成率别名映射表


async def fetch_chart_level(maipy, short_id: int, difficult: Optional[DifficultyVariant] = None) -> Optional[dict]:
    """调用 maipy 获取谱面及定数信息"""
    difficulty_tag = short_id // 10000  # 0->SD, 1->DX, 其余在 ra 计算中无效
    if difficulty_tag > 1 or difficulty_tag < 0: return None
    chart_tag: str = "SD" if difficulty_tag == 0 else "DX"
    maipy_id: int = short_id % 10000

    # maipy 获取阶段
    try:
        song = await maipy.songs().by_id(maipy_id)
        charts = song.difficulties.sd if chart_tag == "SD" else song.difficulties.dx
        difficult: DifficultyVariant = difficult if difficult else init_difficulty(len(charts) - 1, variant='maipy')
        chart = charts[difficult.maipy]
        return {
            "title": song.title,
            "difficult": difficult,
            "chart": chart_tag,
            "level": chart.level_value
        }
    except IndexError:
        logger.warning(f"ra 计算：谱面 {short_id} 不存在对应难度的谱面数据")
    except Exception as ex:
        logger.warning(f"ra 计算：获取谱面 {short_id} 数据时发生错误。{ex}")
    return None


def _calculate(level: float, rate_str: str) -> Optional[Tuple[int, float]]:
    """根据定数和完成率字符串计算 Rating"""
    try:
        rate = float(rate_str)
    except ValueError:
        rate = RATE_ALIAS_MAP.get(rate_str.lower())
        if rate is None:
            return None
    factor = 0.0
    for rate_standard, factor in RATE_FACTOR_TABLE:
        if rate >= rate_standard:
            factor = factor
            break
    d = int(level * rate * factor)
    return d, rate


async def calculate_rating(matcher: Matcher, level: float, rate_str: str, song_info: Optional[dict] = None)-> None:
    """计算并回复 Rating"""
    result = _calculate(level, rate_str)
    if result is None:
        await matcher.finish(f"小梨看不懂这个完成率qwq")
        return

    song_text = "" if not song_info else \
        f"[{song_info['chart']}]{song_info['title']} {DIFFICULTY_MAP[song_info['difficult'].simai]}谱的数据"

    await matcher.finish(f"小梨算出来{song_text}咯！\n定数{level}*{result[1]:.4f}% -> Rating: {result[0]}")
