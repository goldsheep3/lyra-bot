"""
image_gen.components.level
等级标签组件

> LV 13.8+ / ...
"""
from typing import Literal
from PIL import Image
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ..style import _DIFFICULTY_TYPE, get_difficulty_style
from .base import TextDrawStyle, Drawer


_LEVEL_DECIMAL_TYPE = Literal['display', 'ignore', 'question_mask']


class LevelBadge:
    """等级标签组件""" 
    
    @classmethod
    @lru_cache(maxsize=64)
    def _level_badge(cls, integer: str, fractional: str, difficulty: _DIFFICULTY_TYPE,
                     display_plus_mask: bool = False, display_fractional: _LEVEL_DECIMAL_TYPE = 'display',
                     ms: MS = MS(), is_cn_all: bool = False) -> Image.Image:
        style = get_difficulty_style(difficulty, is_cn_all=is_cn_all)
        height = 6
        
        # 确定输出文本
        level_text = style.level
        if is_cn_all:
            level_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2.2))
        else:
            level_font = FontManager.font(FontCode.JBMono_Bold, size=ms.x(2.8))
        int_text = integer
        int_font = FontManager.font(FontCode.JBMono_Bold, size=ms.x(5))
        if display_fractional == 'display':
            frac_text = f".{fractional}"
        elif display_fractional == 'question_mask':
            frac_text = ".?"
        else:
            frac_text = ""
        frac_font = FontManager.font(FontCode.JBMono_Bold, size=ms.x(3.8))
        plus_mask_text = "+" if display_plus_mask else ""
        plus_mask_font = FontManager.font(FontCode.JBMono_Bold, size=ms.x(2.8))

        # 计算文本宽度
        level_bbox = level_font.getbbox(level_text, anchor='ls', stroke_width=0.4)
        int_bbox = int_font.getbbox(int_text, anchor='ls', stroke_width=0.4)
        frac_bbox = frac_font.getbbox(frac_text if len(frac_text) >= 2 else '00', anchor='ls', stroke_width=0.4)
        # plus_mask_bbox = plus_mask_font.getbbox(plus_mask_text, anchor='ls', stroke_width=0.4)  # 暂时用不到

        level_w = ms.rev(round(level_bbox[2] - level_bbox[0]))
        int_w = ms.rev(round(int_bbox[2] - int_bbox[0]))
        frac_w = ms.rev(round(frac_bbox[2] - frac_bbox[0]))
        width = level_w + 1 + int_w + frac_w + 1 + 1

        shadow_width = 0.6

        # 绘制
        img = Image.new('RGBA', ms.xy(width, height+1), '#FFFFFF00')
        drawer = Drawer(img, ms=ms)
        def lv_tds(font):
            return TextDrawStyle(fill=style.level_text, anchor='ls', font=font,
                                  shadow_width=shadow_width, shadow=style.frame)
        
        drawer.text(0.5, height, text=level_text, tds=lv_tds(level_font))
        drawer.text(level_w + 2, height, text=int_text, tds=lv_tds(int_font))
        if frac_text:
            drawer.text(level_w + 2 + int_w, height, text=frac_text, tds=lv_tds(frac_font))
        if plus_mask_text:
            drawer.text(level_w + 2 + int_w, height - 5, text=plus_mask_text, tds=TextDrawStyle(
                fill=style.level_text, anchor='lt', font=plus_mask_font, shadow_width=shadow_width, shadow=style.frame
            ))
        return img

    @classmethod
    def _level(cls, level: float, difficulty: _DIFFICULTY_TYPE,
               display_plus_mask: bool = False, display_frac: _LEVEL_DECIMAL_TYPE = 'display',
               ms: MS = MS(), is_cn_all: bool = False) -> Image.Image:
        integer = int(level)
        fractional = round((level - integer) * 10)
        return cls._level_badge(str(integer), str(fractional), difficulty, display_plus_mask, display_frac, ms, is_cn_all)

    @classmethod
    def level(cls, level: float, difficulty: _DIFFICULTY_TYPE,
              display_plus_mask: bool = False, display_frac: _LEVEL_DECIMAL_TYPE = 'display',
              ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """渲染等级标签"""
        return cls._level(level, difficulty, display_plus_mask=display_plus_mask, display_frac=display_frac,
                          ms=ms, is_cn_all=ui_code.is_cn_all).copy()
