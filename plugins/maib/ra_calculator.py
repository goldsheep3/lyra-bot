import re
import httpx
from typing import List, Tuple, Optional

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


async def fetch_chart_level(chart_id: int, is_dx: bool, color_index: Optional[int]) -> Optional[Tuple[float, str, int]]:
    """
    调用 maimai.lxns.net API 获取谱面定数。
    :param chart_id: 谱面 id
    :param is_dx: 是否为 dx 谱面
    :param color_index: 难度颜色索引（0-4），若为 None 自动识别白谱或紫谱
    :return: (定数, 歌名, 难度颜色索引) 或 None
    """
    url = f"https://maimai.lxns.net/api/v0/maimai/song/{chart_id}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"谱面 API 请求失败: {e}")
        return None
    difficulties = data.get("difficulties", {})
    if not isinstance(difficulties, dict):
        logger.error("API difficulties 字段格式异常")
        return None
    diff_list = difficulties.get("dx" if is_dx else "standard", [])
    if not diff_list:
        logger.error("API 返回无对应类型难度")
        return None
    # 选定颜色
    if color_index is not None:
        for d in diff_list:
            if d.get("difficulty") == color_index:
                return float(d.get("level_value", 0)), data.get("title", "Unknown Song Name"), color_index
        logger.error("未找到指定颜色难度")
        return -2.0, "", -1
    # 自动识别：优先白谱（4），否则紫谱（3），不会出现其他情况
    for idx in [4, 3]:
        for d in diff_list:
            if d.get("difficulty") == idx:
                return float(d.get("level_value", 0)), data.get("title", "Unknown Song Name"), idx
    logger.error("未找到白谱或紫谱难度")
    return None


async def calculate_score(event: Event, matcher):
    """捕获消息，计算 dx rating"""

    msg = str(event.get_message())
    logger.info(f"收到消息: {msg}")

    title = None
    is_dx = False
    chart_color_idx = None
    rate_str = None
    difficulty = None

    # 支持 ra <难度> <完成率> 和 ra id10240[颜色] <完成率>
    # 颜色支持：绿黄红紫白，可选
    match = re.search(
        r"ra\s+(?:(id\d+)([绿黄红紫白])?|(\d+(?:\.\d+)?))\s+(\S+)", msg
    )
    if match:
        # 判断是否为 help 命令
        if (
            (match.group(1) and match.group(1).lower() == "help")
            or (match.group(3) and match.group(3).lower() == "help")
        ):
            help_text = (
                "小梨提醒你：ra命令可以计算给定难度和完成率的得分。\n"
                "使用方法：\n"
                "ra <难度> <完成率>\n"
                "ra id<谱面id>[颜色] <完成率>\n"
                "例如：ra 13.2 100.1000 或 ra id10240红 100.5\n"
                "颜色支持：绿黄红紫白，若无颜色默认取最高难度(白, 其次为紫)"
            )
            await matcher.finish(help_text)
        else:
            # 判断是否需要处理歌曲获取id
            if match.group(1):
                chart_id_raw = int(match.group(1)[2:])
                chart_color = match.group(2) if match.group(2) else ""
                rate_str = match.group(4)
                # id 合法性判断
                if chart_id_raw >= 100000:
                    await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: 不支持宴谱")
                    return None
                elif 20000 <= chart_id_raw < 100000:
                    await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: id格式错误")
                    return None
                elif 10000 <= chart_id_raw < 20000:
                    chart_id = chart_id_raw % 10000
                    is_dx = True
                elif 1 <= chart_id_raw < 10000:
                    chart_id = chart_id_raw
                    is_dx = False
                else:
                    await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: id范围错误")
                    return None
                color_map = {"绿": 0, "黄": 1, "红": 2, "紫": 3, "白": 4}
                color_index = color_map.get(chart_color) if chart_color else None
                try:
                    rate = float(rate_str)
                except ValueError:
                    rate = rate_alias_map.get(rate_str.lower())
                    if rate is None:
                        await matcher.finish(f"这样的数字小梨算不出来的啊qwq\nError: 完成率参数不支持")
                        return None
                # 获取定数、歌名、实际难度颜色
                result = await fetch_chart_level(chart_id, is_dx, color_index)
                if result is None:
                    await matcher.finish("这样的数字小梨算不出来的啊qwq\nError: 谱面定数获取失败，请联系管理员查看后台")
                    return None
                elif result[0] == -2.0:
                    # 谱面错误
                    await matcher.finish(f"😡小梨生气了！这首歌根本就没有{chart_color}谱！")
                difficulty, title, chart_color_idx = result
                logger.info(f"API获取定数: {difficulty}, 完成率: {rate}, 难度颜色: {chart_color_idx}")
            else:
                try:
                    difficulty = float(match.group(3))
                    rate_str = match.group(4)
                except ValueError:
                    await matcher.finish(
                        "这样的数字小梨算不出来的啊qwq\nError: 难度和完成率必须是数字或支持的文本别名"
                    )
                    return None

    try:
        rate = float(rate_str)
    except ValueError:
        rate = rate_alias_map.get(rate_str.lower())
        if rate is None:
            await matcher.finish(
                f"这样的数字小梨算不出来的啊qwq\nError: 完成率参数不支持"
            )
            return None
    logger.info(f"提取到难度: {difficulty}, 完成率: {rate}")
    factor = 0.0
    for threshold, f in RATE_FACTOR_TABLE:
        if rate >= threshold:
            factor = f
            break
    dxrating = int(difficulty * rate * factor)
    rate_fmt = f"{rate:.4f}"
    # 返回时带有title和实际识别到的谱面颜色
    color_names = ["绿", "黄", "红", "紫", "白"]
    if title and chart_color_idx is not None:
        await matcher.finish((
            f"小梨算出来[{'DX' if is_dx else 'SD'}]{title} 的{color_names[chart_color_idx]}谱数据咯！\n"
            f"定数{difficulty}*{rate_fmt}% -> Rating: {dxrating}"
        ))
    await matcher.finish((
        "小梨算出来咯！\n"
        f"定数{difficulty}*{rate_fmt}% -> Rating: {dxrating}"
    ))
    return None
