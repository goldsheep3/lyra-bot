"""
image_gen.color
绘图颜色表
"""
from ..utils.map import GenreID, DifficultyID, ComboID, SyncID
from .models import GenreColors, DifficultyColors, RateColors, EvaluateColors, CabinetColors

__all__ = [
    # 常用颜色常量
    "THEME_CYAN", "THEME_DARK", "WHITE", "BLACK", "TRANSPARENT", "HALF_TRANSPARENT",
    # 流派 / Genre 颜色主题
    "GENRE_STYLE",
    # 难度 / Difficulty 颜色主题
    "DIFFICULTY_STYLE",
    "DIFFICULTY_UTAGE_TAG_BG", "DIFFICULTY_UTAGE_TAG_FRAME",
    "DIFFICULTY_BUDDY_TAG_BG", "DIFFICULTY_BUDDY_TAG_FRAME",
    # DX 分数 / DXScore 颜色主题
    "DXSCORE_TEXT_COLOR", "DXSCORE_STYLE",
    # 评级 / Rate 颜色主题
    "RATE_STYLE",
    # 连击-同步 / Combo-Sync 颜色主题
    "COMBO_STYLE", "SYNC_STYLE",
]


# --------------------------------
# 常用颜色常量
# --------------------------------

# 插件主题色
THEME_CYAN = '#64D2CE'
# 深色主题色
THEME_DARK = '#313D7C'
# 白色常量
WHITE = '#FFFFFF'
# 黑色常量
BLACK = '#000000'
# 灰色常量
GRAY = '#CCCCCC'
# 透明色常量
TRANSPARENT = '#FFFFFF00'
# 半透明常量
HALF_TRANSPARENT = '#FFFFFF88'

# --------------------------------
# 流派 / Genre 颜色主题
# --------------------------------

GENRE_STYLE: dict[GenreID, GenreColors] = {
    # POPS&ANIME
    0: GenreColors(main='#FF972A'),
    # niconico&VOCALOID™
    1: GenreColors(main='#02C8D3'),
    # 東方Project
    2: GenreColors(main='#AD59EE'),
    # GAME&VARIETY
    3: GenreColors(main='#4BE070'),
    # maimai
    4: GenreColors(main='#F64849'),
    # ONGEKI&CHUNITHM
    5: GenreColors(main='#3584FE', sub='#FFD82A'),
    # UTAGE
    6: GenreColors(main='#DC39B8'),
}


# --------------------------------
# 难度 / Difficulty 颜色主题
# --------------------------------

DIFFICULTY_STYLE: dict[DifficultyID, DifficultyColors] = {
    # 未知 Unknown
    0: DifficultyColors(bg="#9B9B9B", frame="#555555", text=WHITE, deep="#7F7F7F", title_bg="#717171", level_text=WHITE),
    # 简单 Easy (占位，暂时无蓝色色卡且 DX 已经没有 Easy 难度)
    1: DifficultyColors(bg=WHITE, frame=WHITE, text=WHITE, deep=WHITE, title_bg=WHITE, level_text=WHITE),
    # 基础 Basic
    2: DifficultyColors(bg='#77EE66', frame='#005533', text=WHITE, deep='#88DD55', title_bg='#22BB55', level_text=WHITE),
    # 高级 Advanced
    3: DifficultyColors(bg='#FFDD33', frame='#BB4411', text=WHITE, deep='#FFBB11', title_bg='#FF9922', level_text=WHITE),
    # 专家 Expert
    4: DifficultyColors(bg='#FF8888', frame='#CC2233', text=WHITE, deep='#FF99AA', title_bg='#FF4466', level_text=WHITE),
    # 大师 Master
    5: DifficultyColors(bg='#CC77FF', frame='#661188', text=WHITE, deep='#BB33DD', title_bg='#9944EE', level_text=WHITE),
    # 宗师 Re:MASTER
    6: DifficultyColors(bg='#EEEDEE', frame='#8822DD', text='#DD55FF', deep='#FFFFFF', title_bg='#BB66FF', level_text=WHITE),
    # 宴会场 U·TA·GE
    7: DifficultyColors(bg='#EE66EE', frame='#DD00BB', text=WHITE, deep='#FF66FF', title_bg='#FF44FF', level_text=WHITE),
}

DIFFICULTY_UTAGE_TAG_BG    = '#223366'  # 标签背景
DIFFICULTY_UTAGE_TAG_FRAME = '#BBEEFF'  # 标签边框
DIFFICULTY_BUDDY_TAG_BG    = '#441111'  # buddy 标签背景
DIFFICULTY_BUDDY_TAG_FRAME = '#FFEEAA'  # buddy 标签边框


# --------------------------------
# DX 分数 / DXScore 颜色主题
# --------------------------------

# 适用于 DX 分数为 1~2✦ 的星星颜色，和 DX 分数文本的显示颜色
_DXSCORE_GREEN = "#00AA55"
# 适用于 DX 分数为 3~4✦ 的星星颜色
_DXSCORE_ORANGE = "#CC7722"
# 适用于 DX 分数为 5✦ 的星星颜色
_DXSCORE_GOLD = "#EEAA44"

DXSCORE_TEXT_COLOR = _DXSCORE_GREEN
DXSCORE_STYLE: dict[int, str] = {
    0: TRANSPARENT,
    1: _DXSCORE_GREEN,
    2: _DXSCORE_GREEN,
    3: _DXSCORE_ORANGE,
    4: _DXSCORE_ORANGE,
    5: _DXSCORE_GOLD,
}


# --------------------------------
# 评级 / Rate 颜色主题
# --------------------------------

RATE_STYLE: dict[str, RateColors] = {
    # S
    'S': RateColors(fill='#FF9933', stroke='#CC0000', shadow='#EEBB55'),
    # A
    'A': RateColors(fill='#DD7777', stroke='#883344', shadow='#BB7777'),
    # B
    'B': RateColors(fill='#33AADD', stroke='#223399', shadow='#5588BB'),
}


# --------------------------------
# 连击-同步 / Combo-Sync 颜色主题
# --------------------------------

# FC / FC+
_EVAL_GREEN_FILL   = '#77DD55'
_EVAL_GREEN_SHADOW = '#116622'
# AP / AP+ / FDX / FDX+
_EVAL_GOLD_FILL    = '#FFEE22'
_EVAL_GOLD_SHADOW  = '#AA0022'
# FS / FS+
_EVAL_BLUE_FILL    = '#66DDFF'
_EVAL_BLUE_SHADOW  = '#003388'
# SYNC PLAY
_EVAL_WHITE_FILL   = '#003388'
_EVAL_WHITE_SHADOW = '#FFFFFF'

_N = EvaluateColors(fill=TRANSPARENT, stroke=TRANSPARENT, shadow=TRANSPARENT)
_GN = EvaluateColors(fill=_EVAL_GREEN_FILL, stroke=_EVAL_GREEN_SHADOW, shadow=_EVAL_GREEN_SHADOW)
_GD = EvaluateColors(fill=_EVAL_GOLD_FILL, stroke=_EVAL_GOLD_SHADOW, shadow=_EVAL_GOLD_SHADOW)
_BE = EvaluateColors(fill=_EVAL_BLUE_FILL, stroke=_EVAL_BLUE_SHADOW, shadow=_EVAL_BLUE_SHADOW)
_W = EvaluateColors(fill=_EVAL_WHITE_FILL, stroke=_EVAL_WHITE_SHADOW, shadow=_EVAL_WHITE_SHADOW)

COMBO_STYLE: dict[ComboID, EvaluateColors] = {0: _N, 1: _GN, 2: _GN, 3: _GD, 4: _GD}
SYNC_STYLE: dict[SyncID, EvaluateColors] = {0: _N, 1: _W, 2: _BE, 3: _BE, 4: _GD, 5: _GD}


# --------------------------------
# 谱面类型 (SD/DX) / Cabinet 颜色主题
# --------------------------------

CABINET_STYLE: dict[str, CabinetColors] = {
    'SD': CabinetColors(fill='#44AAFF', outline=TRANSPARENT, text=('#FFFFFF',)),
    'DX': CabinetColors(fill='#FFFFFF', outline='#2299EE', text=('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6')),
    'DX_CN': CabinetColors(fill='#FFFFFF', outline=TRANSPARENT, text=('#FF7711',)),
}
