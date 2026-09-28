"""
image_gen.components.difficulty
难度标签组件

> MASTER / Re:MASTER / ...
"""
from typing import Optional
from PIL import Image, ImageFont
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ..tools import limit_text
from ..style import DIFFICULTY_TYPE, get_difficulty_style, DifficultyStyle
from .base import TextDrawStyle, Drawer


class DifficultyBadge:
    """难度标签组件"""

    font_size = 4.8
    sub_font_size = 3.3

    @classmethod
    def tds(cls, style: DifficultyStyle, font: ImageFont.FreeTypeFont, sub: bool = False, scale: float = 1) -> TextDrawStyle:
        anchor = 'ld' if sub else 'lm'
        return TextDrawStyle(
            fill=style.text, anchor=anchor, font=font,
            shadow_width=0.8 * scale, shadow=style.deep,
            shadow2_width=0.8 * scale, shadow2=style.frame, shadow2_offset=0.7 * scale
        )

    @classmethod
    def _difficulty_badge(cls, difficulty: DIFFICULTY_TYPE, ms: MS = MS(), is_cn_all: bool = False,
                          text: Optional[str] = None, sub_text: Optional[str] = None, limit: Optional[float] = None) -> Image.Image:
        # limit 限制宽度为 px 而非 mpx，mpx 传入前需要 ms.rev() 转换；仅在手动输入 text 时生效
        style = get_difficulty_style(difficulty)

        # 确定输出文本
        if text is None:
            text = style.title_jp
            sub_text = style.title_cn if is_cn_all else None
        elif limit is not None:
            text = limit_text(text, FontManager.font(FontCode.MiSans_Heavy, ms.x(cls.font_size)), limit)
            sub_text = None
        # else: text = text, sub_text = sub_text

        # 确定输出宽度
        font = FontManager.font(FontCode.MiSans_Heavy, ms.x(cls.font_size))
        text_bbox = font.getbbox(text, anchor='lm', stroke_width=ms.x(0.8))
        text_w, text_h = ms.rev(round(text_bbox[2] - text_bbox[0])), ms.rev(round(text_bbox[3] - text_bbox[1]))
        if sub_text is not None:
            sub_font = FontManager.font(FontCode.MiSans_Heavy, ms.x(cls.sub_font_size))
            sub_bbox = sub_font.getbbox(sub_text, anchor='lm', stroke_width=ms.x(0.8))
            sub_w = ms.rev(round(sub_bbox[2] - sub_bbox[0]))
        else:
            sub_font, sub_w = None, 0
        shadow2_offset = 0.7
        width, height = text_w + sub_w, text_h + shadow2_offset
        
        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        drawer = Drawer(img, ms=ms)
        
        # 绘制文本
        tds = cls.tds(style, font, sub=False)
        drawer.text(1, height / 2, text, tds=tds)
        if sub_text is not None and sub_font is not None:
            sub_tds = cls.tds(style, sub_font, sub=True)
            drawer.text(text_w + 1, height, sub_text, tds=sub_tds)

        return img

    @classmethod
    @lru_cache(maxsize=8)
    def _difficulty(cls, difficulty: DIFFICULTY_TYPE, ms: MS = MS(), is_cn_all: bool = False) -> Image.Image:
        # 只有预设难度才会缓存，手动输入文本的情况不缓存
        return cls._difficulty_badge(difficulty, ms=ms, is_cn_all=is_cn_all).copy()

    @classmethod
    def difficulty(cls, difficulty: DIFFICULTY_TYPE, ms: MS = MS(), is_cn_all: Optional[bool] = None, ui_code: UICode = UICode.JP) -> Image.Image:
        """渲染难度标签"""
        is_cn_all = ui_code.is_cn_all if is_cn_all is None else is_cn_all
        return cls._difficulty(difficulty, ms=ms, is_cn_all=is_cn_all)

    @classmethod
    def draw_text(cls, difficulty: DIFFICULTY_TYPE, text: str, sub_text: Optional[str] = None,
                  ms: MS = MS()) -> Image.Image:
        """渲染难度标签（自定义文本）"""
        return cls._difficulty_badge(difficulty, ms=ms, text=text, sub_text=sub_text)

    @classmethod
    def draw_text_with_limit(cls, difficulty: DIFFICULTY_TYPE, text: Optional[str] = None,
                             limit: Optional[float] = None, ms: MS = MS()) -> Image.Image:
        """渲染难度标签（自定义文本）"""
        return cls._difficulty_badge(difficulty, ms=ms, text=text, limit=limit)
