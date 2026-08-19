"""
image_gen.style
图像风格定义与获取
"""
from typing import Literal
from ..utils.enums import UICode
from ..utils.type import Achievement
from ..utils.calculator import get_dxscore_star_count
from ..utils.map import (
    GenreID, GenreInfo, Genres,
    ComboID, ComboInfo, Combos,
    SyncID, SyncInfo, Syncs,
    AchievementRateInfo, AchievementMap,
    DifficultyID, DifficultyInfo, Difficulties,
)
from .color import (
    THEME_CYAN, WHITE, BLACK, TRANSPARENT, HALF_TRANSPARENT,
    GENRE_STYLE, COMBO_STYLE, SYNC_STYLE, RATE_STYLE, DIFFICULTY_STYLE,
    CABINET_STYLE, DXSCORE_STYLE, DXSCORE_TEXT_COLOR,
)
from .models import GenreStyle, EvaluateStyle, RateStyle, RateFrameStyle, DifficultyStyle, CabinetStyle, DXScoreStyle


_GENRE_TYPE = GenreID | GenreInfo

def get_genre_style(genre: _GENRE_TYPE, ui_code: UICode) -> GenreStyle:
    """获取流派风格信息"""
    _info = genre if isinstance(genre, GenreInfo) else Genres.get(genre)
    if _info is None:
        return GenreStyle(content="N/A", fill=THEME_CYAN, shadow=TRANSPARENT)
    gid: GenreID = _info.id
    ginfo: GenreInfo = _info
    
    # content
    if ui_code.is_jp:
        content = ginfo.jp
    elif ui_code.is_cn:
        content = ginfo.cn
    else:
        content = ginfo.intl

    # fill
    colors = GENRE_STYLE.get(gid)
    if colors is None:
        fill = THEME_CYAN
        sub_fill = TRANSPARENT
    else:
        fill = colors.main
        sub_fill = colors.sub if colors.sub else TRANSPARENT

    return GenreStyle(
        content=content,
        fill=fill,
        sub_fill=sub_fill,
        shadow=WHITE,
    )


_COMBO_TYPE = ComboID | ComboInfo

def get_combo_style(combo: _COMBO_TYPE, short: bool = False, is_cn_all: bool = False) -> EvaluateStyle:
    """获取连击评价风格信息"""
    _info = combo if isinstance(combo, ComboInfo) else Combos.get(combo)
    if _info is None:
        return EvaluateStyle(content="N/A", fill=THEME_CYAN, stroke=TRANSPARENT, shadow=TRANSPARENT)
    cid: ComboID = _info.id
    cinfo: ComboInfo = _info

    # content
    if is_cn_all:
        content = cinfo.cn
    else:
        if short:
            content = cinfo.short
        else:
            content = cinfo.full

    # fill
    colors = COMBO_STYLE.get(cid)
    if colors is None:
        fill = THEME_CYAN
        stroke = TRANSPARENT
        shadow = TRANSPARENT
    else:
        fill = colors.fill
        stroke = colors.stroke
        shadow = colors.shadow

    return EvaluateStyle(
        content=content,
        fill=fill,
        stroke=stroke,
        shadow=shadow,
    )


_SYNC_TYPE = SyncID | SyncInfo

def get_sync_style(sync: _SYNC_TYPE, short: bool = False, is_cn_all: bool = False) -> EvaluateStyle:
    """获取同步评价风格信息"""
    _info = sync if isinstance(sync, SyncInfo) else Syncs.get(sync)
    if _info is None:
        return EvaluateStyle(content="N/A", fill=THEME_CYAN, stroke=TRANSPARENT, shadow=TRANSPARENT)
    sid: SyncID = _info.id
    sinfo: SyncInfo = _info

    # content
    if is_cn_all:
        content = sinfo.cn
    else:
        if short:
            content = sinfo.short
        else:
            content = sinfo.full

    # fill
    colors = SYNC_STYLE.get(sid)
    if colors is None:
        fill = THEME_CYAN
        stroke = TRANSPARENT
        shadow = TRANSPARENT
    else:
        fill = colors.fill
        stroke = colors.stroke
        shadow = colors.shadow

    return EvaluateStyle(
        content=content,
        fill=fill,
        stroke=stroke,
        shadow=shadow,
    )


_DIFFICULTY_TYPE = DifficultyID | DifficultyInfo

def get_difficulty_style(difficulty: _DIFFICULTY_TYPE, is_cn_all: bool = False) -> DifficultyStyle:
    """获取难度风格信息"""
    level = '等级' if is_cn_all else 'LV'
    
    _info = difficulty if isinstance(difficulty, DifficultyInfo) else Difficulties.get(difficulty)
    if _info is None:
        return DifficultyStyle(
            id=0,
            title_jp="UNKNOWN",
            title_cn="未知",
            level= level,
            bg=DIFFICULTY_STYLE[0].bg,
            frame=DIFFICULTY_STYLE[0].frame,
            text=DIFFICULTY_STYLE[0].text,
            deep=DIFFICULTY_STYLE[0].deep,
            title_bg=DIFFICULTY_STYLE[0].title_bg,
            level_text=DIFFICULTY_STYLE[0].level_text,
        )
    did: DifficultyID = _info.id
    dinfo: DifficultyInfo = _info
    
    colors = DIFFICULTY_STYLE.get(did, DIFFICULTY_STYLE[0])
    return DifficultyStyle(
        id=did,
        title_jp=dinfo.jp,
        title_cn=dinfo.cn,
        level=level,
        bg=colors.bg,
        frame=colors.frame,
        text=colors.text,
        deep=colors.deep,
        title_bg=colors.title_bg,
        level_text=colors.level_text,
    )


_RATE_TYPE = AchievementRateInfo | Achievement

def get_rate_style(achievement: Achievement | float, buddy: bool = False) -> RateStyle:
    """获取达成率风格信息"""
    # buddy = True 的情况下，Achievement int 按照输入 202.0000% 的原值处理
    if isinstance(achievement, Achievement):
        achievement_value = achievement
        info = AchievementMap.get(int(achievement / 2) if buddy else achievement)
    else:  # isinstance(achievement, float):
        # legacy support / int 会先被 Achievement 捕获，剩下的就是 float 了（
        achievement_value = int(achievement * 10000)
        info = AchievementMap.get(int(achievement_value / 2) if buddy else achievement_value)

    rate = AchievementMap.rate(info)
    
    # content
    content = f"{achievement_value/10000:.4f}%"
    
    # fill / stroke
    colors = RATE_STYLE[rate]
    fill = colors.fill
    stroke = colors.stroke
    shadow = colors.shadow

    return RateStyle(
        content=content,
        fill=fill,
        stroke=stroke,
        shadow=shadow,
    )

def get_rate_frame_style(difficulty: _DIFFICULTY_TYPE, is_cn_all: bool = False) -> RateFrameStyle:
    """获取达成率框架风格信息"""
    diff_style = get_difficulty_style(difficulty, is_cn_all=is_cn_all)
    content = "达成率" if is_cn_all else "ACHIEVEMENT"
    return RateFrameStyle(
        content=content,
        fill=diff_style.frame,
        bg_fill=HALF_TRANSPARENT,
    )


_CABINET_TYPE = Literal['SD', 'DX']

def get_cabinet_style(cabinet: _CABINET_TYPE, is_cn: bool) -> CabinetStyle:
    """获取谱面类型标记风格信息"""
    if cabinet == 'SD':
        content = "标 准" if is_cn else "スタンダード"
        tag = 'SD'
    elif cabinet == 'DX':
        content = "DX" if is_cn else "でらっくす"
        tag = 'DX_CN' if is_cn else 'DX'
    else:
        content = "N/A"
        tag = ''
    colors = CABINET_STYLE.get(tag)
    if colors is None:
        return CabinetStyle(
            content=content,
            fill=WHITE,
            outline=THEME_CYAN,
            text=(THEME_CYAN,),
        )
    return CabinetStyle(
        content=content,
        fill=colors.fill,
        outline=colors.outline,
        text=colors.text,
    )


def get_dxscore_style(dxscore: int, max_dxscore: int, is_jp: bool = True, is_cn: bool = False) -> DXScoreStyle:
    """获取 DX 分数风格信息"""
    # title
    if is_jp:
        title = "でらっくスコア"
    elif is_cn:
        title = "DX分数"
    else:
        title = "DXSCORE"
    
    # content
    content = f"{dxscore} / {max_dxscore}"
    
    # star
    star_count = get_dxscore_star_count(dxscore, max_dxscore)
    star_color = DXSCORE_STYLE.get(star_count, DXSCORE_STYLE[0])

    return DXScoreStyle(
        title=title,
        title_fill=DXSCORE_TEXT_COLOR,
        bg_fill=BLACK,
        content=content,
        fill=HALF_TRANSPARENT,
        star=' '.join(['✦'] * star_count) if star_count > 0 else None,
        star_fill=star_color,
    )
    

def get_note_designer_text(is_cn_all: bool = False) -> str:
    """获取谱面设计师文本"""
    return "谱师: " if is_cn_all else "NOTE DESIGNER: "