"""utils/calculator.py DXRating 和 DXScore 计算模块"""


__all__ = [
    "get_ap_bonus_value",
    "get_dxrating",
    "get_dxscore_max",
    "get_dxscore_star_count",
]


# rate_factor_table: rating 计算因子
_RATE_FACTOR_TABLE: list[tuple[float, float]] = [
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


def get_ap_bonus_value(version: int) -> int:
    """根据版本获取 AP 奖励分数"""
    if version >= 2000:
        return 0
    if version >= 25:  # CiRCLE 追加 ap 1 奖励分
        return 1
    if version >= 0:
        return 0
    raise ValueError(f"Invalid version: {version}")


def get_dxrating(achievement: float, level: float, ap_bonus: int = 0, combo: int = 0) -> int:
    """根据成就率和定数计算 DX Rating"""
    factor = next((f for t, f in _RATE_FACTOR_TABLE if achievement >= t), 0.0)
    ach = 100.5 if achievement >= 100.5 else achievement
    ra = int(level * ach * factor)
    # AP 奖励分：只有实际达成 AP(combo>=3) 时才加
    if ap_bonus > 0 and combo >= 3:
        ra += ap_bonus
    return ra


def get_dxscore_max(note_count: int) -> int:
    """根据 Note 数量计算 DX 分数上限"""
    return note_count * 3


def get_dxscore_star_count(dxscore: int, dxscore_max: int) -> int:
    """根据 DX 分数计算星数"""
    if dxscore_max < dxscore or dxscore_max <= 0 or dxscore <= 0:
        return 0
    percent = dxscore / dxscore_max * 100
    thresholds = [85, 90, 93, 95, 97, 100]
    for i, t in enumerate(thresholds):
        if percent < t:
            return i
    return 5
