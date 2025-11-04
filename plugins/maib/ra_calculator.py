from typing import Tuple, Dict, Optional

from nonebot import logger
from nonebot.internal.matcher import Matcher

from .utils import DifficultyVariant, RATE_FACTOR_TABLE, DIFFICULTY_MAP, init_difficulty


# 完成率别名映射
rate_alias: Dict[float, Tuple[str]] = {
    101.0000: ("ap+", "理论"),
    100.7500: ("ap",),
    100.5000: ("鸟加", "鸟家", "sss+", "3s+"),
    100.0000: ("鸟", "鸟s", "sss", "3s"),
     99.5000: ("ss+", "2s+"),
     99.0000: ("ss", "2s"),
     98.0000: ("s+", "1s+"),
     97.0000: ("s", "1s"),
     94.0000: ("鸟a", "aaa", "3a"),
     90.0000: ("aa", "2a"),
     80.0000: ("a", "1a"),
     75.0000: ("鸟b", "bbb", "3b"),
     70.0000: ("bb", "2b"),
     60.0000: ("b", "1b"),
     50.0000: ("c", "1c"),
      0.0000: ("d", "1d"),
}
rate_alias_map: Dict[str, float] = {}
for rate_value, aliases in rate_alias.items():
    for alias in aliases:
        rate_alias_map[alias.lower()] = rate_value


async def fetch_chart_level(maipy, short_id: int, difficult: Optional[DifficultyVariant] = None) -> Optional[dict]:
    """调用 maipy 获取谱面及定数信息"""
    difficulty_tag = short_id // 10000  # 0->SD, 1->DX, 其余在 ra 计算中无效
    if difficulty_tag > 1 or difficulty_tag < 0: return None
    chart_tag: str = "SD" if difficulty_tag == 0 else "DX"
    maipy_id: int = short_id % 10000

    # maipy 获取阶段
    try:
        songs = await maipy.songs()
        song = await songs.by_id(maipy_id)
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
        rate = rate_alias_map.get(rate_str.lower())
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
