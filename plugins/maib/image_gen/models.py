"""
image_gen.models
色彩与风格模型
"""
from dataclasses import dataclass
from typing import Optional

from ..utils.map import DifficultyID


# --------------------------------
# 颜色模型
# --------------------------------

@dataclass(frozen=True)
class GenreColors:
    """流派颜色信息"""
    main: str
    sub: Optional[str] = None


@dataclass(frozen=True)
class DifficultyColors:
    """难度颜色信息"""
    bg: str
    frame: str
    text: str
    deep: str
    title_bg: str
    level_text: str


@dataclass(frozen=True)
class RateColors:
    """达成率颜色信息"""
    fill: str
    stroke: str
    shadow: str


@dataclass(frozen=True)
class EvaluateColors:
    """评价颜色信息"""
    fill: str
    stroke: str
    shadow: str


@dataclass(frozen=True)
class CabinetColors:
    """谱面类型徽章颜色信息"""
    fill: str
    outline: str
    text: tuple[str, ...]
    

# --------------------------------
# 风格模型
# --------------------------------

@dataclass(frozen=True)
class GenreStyle:
    """流派"""
    content: str
    fill: str
    shadow: str
    sub_fill: str  # 中二/音击 分两行绘制特有


@dataclass(frozen=True)
class EvaluateStyle:
    """Combo / Sync"""
    content: str
    fill: str
    stroke: str
    shadow: str


@dataclass(frozen=True)
class RateStyle:
    """达成率"""
    content: str
    fill: str
    stroke: str
    shadow: str


@dataclass(frozen=True)
class RateFrameStyle:
    """达成率框架"""
    content: str
    fill: str
    bg_fill: Optional[str] = None


@dataclass(frozen=True)
class DifficultyStyle:
    """难度"""
    id: DifficultyID
    title_jp: str
    title_cn: str
    level: str
    bg: str
    frame: str
    text: str
    deep: str
    title_bg: str
    level_text: str


@dataclass(frozen=True)
class CabinetStyle:
    """SD/DX"""
    content: str
    fill: str
    outline: str
    text: tuple[str, ...]


@dataclass(frozen=True)
class DXScoreStyle:
    """DX 分数"""
    title: str
    title_fill: str
    bg_fill: str
    content: str
    fill: str
    star: str
    star_fill: str
