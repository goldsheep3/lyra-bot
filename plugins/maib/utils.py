from typing import Dict, List, Tuple, Optional, Literal
from enum import IntEnum


# 完成率对应的评分因子表
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


DIFFICULTY_MAP: Dict[DifficultyVariant, str] = {
    ChartDifficulty.EASY: "蓝",
    ChartDifficulty.BASIC: "绿",
    ChartDifficulty.ADVANCED: "黄",
    ChartDifficulty.EXPERT: "红",
    ChartDifficulty.MASTER: "紫",
    ChartDifficulty.Re_MASTER: "白"
}


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

_old_versions = [
    'maimai', 'maimai_PLUS','GreeN', 'GreeN_PLUS',
    'ORANGE', 'ORANGE_PLUS', 'PiNK', 'PiNK_PLUS',
    'MURASAKi', 'MURASAKi_PLUS', 'MiLK', 'MiLK_PLUS', 'FiNALE',
]
_versions = [
    'でらっくす', 'でらっくす_PLUS', 'Splash', 'Splash_PLUS',
    'UNiVERSE', 'UNiVERSE_PLUS', 'FESTiVAL', 'FESTiVAL_PLUS',
    'BUDDiES', 'BUDDiES_PLUS', 'PRiSM', 'PRiSM_PLUS',
    'CiRCLE',
]
_versions_cn = [
    '舞萌DX', '舞萌DX_2021',
    '舞萌DX_2022', '舞萌DX_2023',
    '舞萌DX_2024', '舞萌DX_2025',
]

Version = IntEnum('Version', [(v, i) for i, v in enumerate(_old_versions + _versions)])
VersionCN = IntEnum('VersionCN', [(v, i) for i, v in enumerate(_old_versions + _versions_cn)])


COMBO = Literal['FC', 'FC+', 'AP', 'AP+']
SYNC = Literal['SyncPlay', 'FS', 'FS+', 'FDX', 'FDX+']
REGION_VERSION = Literal['JP', 'INTL', 'INTL(USA)', 'CN']


class MusicInfo:

    name: str
    short_id: int
    dx_chart: bool
    score: float
    difficulty: DifficultyVariant
    level: float
    version: int
    region_version: REGION_VERSION
    combo: Optional[COMBO] = None
    sync: Optional[SYNC] = None
    dx_score: Tuple[int, int] = 0, 0  # (当前 DX Score, 最高 DX Score)
    dx_score_star_count: int = 0
    dxrating: int = 0

    def __init__(self, name: str, short_id: int, dx_chart: bool, score: float, difficulty: DifficultyVariant,
                 level: float, version: int, region_version: REGION_VERSION, combo: Optional[COMBO] = 0,
                 sync: Optional[SYNC] = 0, dx_score: int | Tuple[int, int] = 0) -> None:
        # 初始化属性
        self.name = name
        self.short_id = short_id
        self.dx_chart = dx_chart
        self.score = score
        self.difficulty = difficulty
        self.level = level
        self.version = version
        self.region_version = region_version
        self.combo = combo
        self.sync = sync
        if isinstance(dx_score, int):
            self.dx_score = (dx_score, dx_score)
        elif isinstance(dx_score, tuple):
            if dx_score[1] < dx_score[0]:
                raise ValueError("dx_score max must be greater than or equal to dx_score")
        else: raise ValueError("dx_score must be int or Tuple[int, int]")

        self.get_dx_rating()
        self.get_dx_score_star_count()

    def get_dx_rating(self) -> int:
        """计算 DX Rating"""
        # 使用 next() 找到第一个满足条件的因子
        factor = next(
            (f for threshold, f in RATE_FACTOR_TABLE if self.score >= threshold),
            0.0  # 默认值
        )
        self.dxrating = int(self.level * self.score * factor)
        # CiRCLE 版本 AP 曲目额外奖励
        if all([
            self.version >= {
                'JP': Version.CiRCLE,  # 默认
                'INTL': Version.CiRCLE,
                'INTL(USA)': Version.CiRCLE,
                'CN': 1000  # 目前不确定`舞萌DX_2026`是否实施该算法
            }.get(self.region_version, Version.CiRCLE),
            self.combo in ['AP', 'AP+']  # 获得额外 1 分需要至少 All Perfect
        ]):
            self.dxrating += 1
        return self.dxrating

    def get_dx_score_star_count(self) -> int:
        """计算 DX Score 星数"""
        dx_score = self.dx_score[0] / self.dx_score[1]
        self.dx_score_star_count = next((i for i, s in enumerate([85, 90, 93, 95, 97, 100]) if dx_score <= s), 5)
        return self.dx_score_star_count


def _ra_calculate(level: float, score: float) -> int:
    return MusicInfo(
        name="", short_id=-1, dx_chart=True,difficulty=ChartDifficulty.MASTER,
        score=score, level=level, version=0, region_version='JP'
    ).dxrating


class GenB50Info:

    b35_music_infos: List[MusicInfo] = []
    b15_music_infos: List[MusicInfo] = []
    version: int
    region_version: REGION_VERSION = 'JP'
    name: str = ""

    ra: int = 0
    b35_ra: int = 0
    b15_ra: int = 0
    friend_rank: str = "B5"
    rank: str = "初心者"

    def __init__(self, name: str, version: int, region_version: REGION_VERSION = 'JP',
                 friend_battle_rank: Optional[str] = None, rank: Optional[str] = None) -> None:
        # 初始化属性
        self.name = name
        self.version = version
        self.region_version = region_version
        self.friend_rank = friend_battle_rank if friend_battle_rank else "B5"
        self.rank = rank if rank else "初心者"

    def add_music_info(self, music_info: MusicInfo) -> int:
        """尝试将曲目加入 B50 计算中，并返回当前总 DX Rating"""
        # 确定曲目属于 b15 还是 b35 部分
        b15_double_ver = self.version >= {
            'JP': Version.CiRCLE,  # 默认
            'INTL': Version.CiRCLE,
            'INTL(USA)': Version.CiRCLE,
            'CN': 1000  # 目前不确定`舞萌DX_2026`是否实施该算法
        }.get(self.region_version, Version.CiRCLE)
        b15_line = self.version - 1 if b15_double_ver else self.version

        if music_info.version >= b15_line:
            # b15
            if len(self.b15_music_infos) < 15:
                self.b15_music_infos.append(music_info)
            else:
                # 替换最低
                self.b15_music_infos.sort(key=lambda x: x.dxrating)  # 按分数排序，确定最低分数曲目
                min_ra: int = self.b15_music_infos[-1].get_dx_rating()  # type: ignore
                if music_info.get_dx_rating() > min_ra:
                    self.b15_music_infos[-1] = music_info  # type: ignore
            self.b15_music_infos.sort(key=lambda x: x.dxrating)  # 再次按分数排序
        else:
            # b35
            if len(self.b35_music_infos) < 35:
                self.b35_music_infos.append(music_info)
            else:
                # 替换最低
                self.b35_music_infos.sort(key=lambda x: x.dxrating)  # 按分数排序，确定最低分数曲目
                min_ra: int = self.b35_music_infos[-1].get_dx_rating()  # type: ignore
                if music_info.get_dx_rating() > min_ra:
                    self.b35_music_infos[-1] = music_info  # type: ignore
            self.b35_music_infos.sort(key=lambda x: x.dxrating)  # 再次按分数排序
        # 重新计算总 DX Rating
        self.b35_ra = sum(music.get_dx_rating() for music in self.b35_music_infos)
        self.b15_ra = sum(music.get_dx_rating() for music in self.b15_music_infos)
        self.ra = self.b35_ra + self.b15_ra
        return self.ra
