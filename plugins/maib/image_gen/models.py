"""
image_gen 绘图模块的内部数据模型
- 难度信息 (Difficulty)
- 达成率颜色 (Achievement)
- 评价信息 (Combo, Sync)
"""

from enum import Enum
from typing import Iterator, Optional, Any
from dataclasses import dataclass


# ========================================
# 基础颜色常量
# ========================================

COLOR_DXSCORE_GN = '#0A5'
COLOR_DXSCORE_OR = '#C72'
COLOR_DXSCORE_GD = '#ED4'
COLOR_THEME = '#64d2ce'
NO_COLOR = '#FFFFFF00'  # 完全透明

COLOR_UTAGE_TAG_BG = '#236'
COLOR_UTAGE_TAG_FRAME = '#BEF'
COLOR_BUDDY_TAG_BG = '#411'
COLOR_BUDDY_TAG_FRAME = '#FEA'


# ========================================
# 难度定义
# ========================================

@dataclass(frozen=True)
class Diff:
    """难度信息数据类"""
    code: int
    text_title: str
    text_title_cn: str
    bg: str
    frame: str
    text: str
    deep: str
    title_bg: str
    _level_text: Optional[str] = None

    @property
    def level_text(self) -> str:
        return self._level_text if self._level_text else self.text


class Difficulty(Enum):
    """难度枚举"""
    NONE = Diff(0, "N/A", "N/A", bg='#FFF', frame='#FFF', text='#FFF', deep='#FFF', title_bg='#FFF')
    EASY = Diff(1, "EASY", "简单", bg='#FFF', frame='#FFF', text='#FFF', deep='#FFF', title_bg='#FFF')
    BASIC = Diff(2, "BASIC", "基础", bg='#7E6', frame='#053', text='#FFF', deep='#8D5', title_bg='#2B5')
    ADVANCED = Diff(3, "ADVANCED", "高级", bg='#FD3', frame='#B41', text='#FFF', deep='#FB1', title_bg='#F92')
    EXPERT = Diff(4, "EXPERT", "专家", bg='#F88', frame='#C23', text='#FFF', deep='#F9A', title_bg='#F46')
    MASTER = Diff(5, "MASTER", "大师", bg='#C7F', frame='#618', text='#FFF', deep='#B3D', title_bg='#94E')
    REMASTER = Diff(6, "Re:MASTER", "宗师", bg='#EDE', frame='#82D', text='#D5F', deep='#FFF', title_bg='#B6F', _level_text='#FFF')
    UTAGE = Diff(7, "U·TA·GE", "宴·会·场", bg='#E6E', frame='#D0B', text='#FFF', deep='#F6F', title_bg='#F4F')

    @classmethod
    def get(cls, code: int) -> Diff:
        """根据难度代码获取难度信息"""
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value


# ========================================
# 达成率相关定义
# ========================================

@dataclass(frozen=True)
class AchColor:
    """达成率颜色信息"""
    fill: str
    stroke: str
    shadow: str


class Achievement(Enum):
    """达成率评级"""
    S = AchColor(fill='#F93', stroke='#C00', shadow='#EB5')
    A = AchColor(fill='#D77', stroke='#834', shadow='#B77')
    B = AchColor(fill='#3AD', stroke='#239', shadow='#58B')

    @classmethod
    def get_by_percent(cls, percent: float) -> AchColor:
        """根据达成率百分比获取颜色"""
        if percent >= 97:
            return cls.S.value
        if percent >= 80:
            return cls.A.value
        return cls.B.value


# ========================================
# 评价定义 (FC/FS/Sync)
# ========================================

@dataclass(frozen=True)
class EvaluateColor:
    """评价颜色信息"""
    fill: str
    shadow: str


_EVAL_GN = EvaluateColor(fill='#7D5', shadow='#162')  # FC / FC+
_EVAL_GD = EvaluateColor(fill='#FE2', shadow='#A02')  # AP / AP+ / FDX / FDX+
_EVAL_BE = EvaluateColor(fill='#6DF', shadow='#038')  # FS / FS+
_EVAL_DB = EvaluateColor(fill='#038', shadow='#FFF')  # SYNC PLAY


@dataclass(frozen=True)
class EvalInfo:
    """评价信息数据类"""
    code: int
    color: EvaluateColor
    full_name: str
    short_name: str
    cn_name: str

    def __iter__(self) -> Iterator[Any]:
        # 使 EvalInfo 可以直接解包为 (color, full_name, short_name, cn_name)
        return iter((self.color, self.full_name, self.short_name, self.cn_name))


class Combo(Enum):
    """Combo 类型 (FC, AP 等)"""
    NONE    = EvalInfo(0, _EVAL_GN, '', '', '')
    FC      = EvalInfo(1, _EVAL_GN, 'FULL COMBO', 'FC', '全连击')
    FC_PLUS = EvalInfo(2, _EVAL_GN, 'FULL COMBO +', 'FC+', '全连击+')
    AP      = EvalInfo(3, _EVAL_GD, 'ALL PERFECT', 'AP', '完美无缺')
    AP_PLUS = EvalInfo(4, _EVAL_GD, 'ALL PERFECT +', 'AP+', '完美无缺+')

    @classmethod
    def get(cls, code: int) -> EvalInfo:
        """根据代码获取组合评价"""
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value


class Sync(Enum):
    """Sync 类型 (FS, FDX 等)"""
    NONE     = EvalInfo(0, _EVAL_DB, '', '', '')
    SYNC     = EvalInfo(1, _EVAL_DB, 'SYNC PLAY', 'SYNC', '同步游玩')
    FS       = EvalInfo(2, _EVAL_BE, 'FULL SYNC', 'FS', '全完同步')  # 原文如此
    FS_PLUS  = EvalInfo(3, _EVAL_BE, 'FULL SYNC +', 'FS+', '全完同步+')  # 原文如此
    FDX      = EvalInfo(4, _EVAL_GD, 'FULL SYNC DX', 'FDX', '完全同步DX')
    FDX_PLUS = EvalInfo(5, _EVAL_GD, 'FULL SYNC DX +', 'FDX+', '完全同步DX+')

    @classmethod
    def get(cls, code: int) -> EvalInfo:
        """根据代码获取同步评价"""
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value
