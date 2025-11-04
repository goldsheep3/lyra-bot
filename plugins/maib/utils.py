from typing import List, Tuple, Literal, Dict


# Rating 因子速查表
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

DIFFICULTY_MAP: Dict[int, str] = {1: "蓝", 2: "绿", 3: "黄", 4: "红", 5: "紫", 6: "白"}

# 封装 maipy 和 simai 的难度数值
class DifficultyVariant:
    def __init__(self, num: int):
        self.simai = num
        self.maipy = num - 2

class ChartDifficulty:
    # 主要采用 simai 规则的数值表示
    EASY = DifficultyVariant(1)
    BASIC = DifficultyVariant(2)
    ADVANCED = DifficultyVariant(3)
    EXPERT = DifficultyVariant(4)
    MASTER = DifficultyVariant(5)
    Re_MASTER = DifficultyVariant(6)

    EAZ = EASY
    BAS = BASIC
    ADV = ADVANCED
    EXP = EXPERT
    MAS = MASTER
    ReM = Re_MASTER

def init_difficulty(level: int, variant: Literal['simai', 'maipy'] = 'simai') -> DifficultyVariant:
    """根据数值初始化 ChartDifficulty"""
    index = level - 1 if variant == 'simai' else level + 1  # 0=EASY
    return [
        ChartDifficulty.EASY,
        ChartDifficulty.BASIC,
        ChartDifficulty.ADVANCED,
        ChartDifficulty.EXPERT,
        ChartDifficulty.MASTER,
        ChartDifficulty.Re_MASTER,
    ][index]

def init_difficulty_from_text(name: str) -> DifficultyVariant:
    """根据字符串初始化 ChartDifficulty"""
    name = name.lower()
    mapping = {
        "蓝": ChartDifficulty.EASY,
        "绿": ChartDifficulty.BASIC,
        "黄": ChartDifficulty.ADVANCED,
        "红": ChartDifficulty.EXPERT,
        "紫": ChartDifficulty.MASTER,
        "白": ChartDifficulty.Re_MASTER,
    }
    return mapping.get(name, ChartDifficulty.MASTER)  # 默认返回 MASTER