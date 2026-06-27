"""
徽章与标签组件
- LevelBadge: 等级标签
- DifficultyBadge: 难度标签
- DrawBadge: 谱面类型徽章
"""

from typing import Literal, Optional
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from ..models import Diff
from ..utils import MS, _MS_DEFAULT
from ..resources import FontManager, FontCode
from .base import TextStyle, BaseDrawer


class LevelBadge:
    """等级标签组件"""
    
    def __init__(self, level: float, diff: Diff, plus: bool = False, 
                 ignore_decimal: bool = False, cn_level: Literal[0, 1, 2] = 0):
        self.level = level
        self.diff = diff
        self.plus = plus
        self.ignore_decimal = ignore_decimal
        self.cn_level = cn_level

    def render(self, draw: ImageDraw.ImageDraw, font_manager: FontManager, ms: MS, x: float, y: float):
        """渲染等级标签"""
        f = f"{str(int(self.level // 1)).replace('0', 'O'):>2}"
        d = str(round(self.level % 1 * 10)).replace('0', 'O')

        # 等级 `LV`
        if self.cn_level == 2:
            draw.text(ms.xy(x - 1, y), text="等级", fill=self.diff.frame, anchor='ls',
                     font=font_manager.font(FontCode.MiSans_Demibold, size=ms.x(3)),
                     stroke_width=ms.x(0.5), stroke_fill=self.diff.frame)
            draw.text(ms.xy(x - 1, y), text="等级", fill=self.diff.level_text, anchor='ls',
                     font=font_manager.font(FontCode.MiSans_Demibold, size=ms.x(3)))
        else:
            draw.text(ms.xy(x, y), text="LV", fill=self.diff.frame, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(4)),
                     stroke_width=ms.x(0.5), stroke_fill=self.diff.frame)
            draw.text(ms.xy(x, y), text="LV", fill=self.diff.level_text, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(4)))
        
        # 等级 `xx.x`
        draw.text(ms.xy(x + 6, y), text=f, fill=self.diff.frame, anchor='ls',
                 font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(6)),
                 stroke_width=ms.x(0.5), stroke_fill=self.diff.frame)
        draw.text(ms.xy(x + 6, y), text=f, fill=self.diff.level_text, anchor='ls',
                 font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(6)))
        
        if not self.ignore_decimal:
            draw.text(ms.xy(x + 13, y), text="." + d, fill=self.diff.frame, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(5)),
                     stroke_width=ms.x(0.5), stroke_fill=self.diff.frame)
            draw.text(ms.xy(x + 13, y), text="." + d, fill=self.diff.level_text, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(5)))
        
        # 等级 `+`
        if self.plus:
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=self.diff.frame, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(3.5)),
                     stroke_width=ms.x(0.5), stroke_fill=self.diff.frame)
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=self.diff.level_text, anchor='ls',
                     font=font_manager.font(FontCode.JBMono_Bold, size=ms.x(3.5)))


class DifficultyBadge:
    """难度标签组件"""
    
    def __init__(self, diff: Diff, custom_text: Optional[str] = None, 
                 limit_width: float = -1, ms: MS = _MS_DEFAULT, 
                 cn_level: Literal[0, 1, 2] = 0, font_manager: Optional[FontManager] = None):
        self.diff = diff
        self.custom_text = custom_text
        self.limit_width = limit_width
        self.ms = ms
        self.cn_level = cn_level
        self.font_manager = font_manager

    @lru_cache(maxsize=10)
    def _get_diff_text_image(self, diff: Diff, text: Optional[str] = None, 
                            limit_width: float = -1, ms: MS = _MS_DEFAULT, 
                            cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """生成难度文本图片（缓存版）"""
        from ..utils import limit_text
        
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ...constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        font = font_manager.font(FontCode.MiSans_Heavy, ms.x(4.8))
        if text:
            text = limit_text(text, font, limit_width) if limit_width > 0 else text
            display_text = text
        else:
            display_text = diff.text_title

        x1, y1, x2, y2 = font.getbbox(display_text, anchor='lm', stroke_width=ms.x(0.8))
        if cn_level == 2 and not text:
            cn_font = font_manager.font(FontCode.MiSans_Heavy, ms.x(3.3))
            cn_x1, _cn_y1, cn_x2, _cn_y2 = cn_font.getbbox(diff.text_title_cn, anchor='lm', stroke_width=ms.x(0.8))
            cn_width = ms.rev(cn_x2 - cn_x1)
        else:
            cn_width = 0
        
        width = (ms.rev(x2 - x1) + cn_width) * 1.2
        height = ms.rev(y2 - y1) * 1.2

        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        draw = ImageDraw.Draw(img)
        drawer = BaseDrawer(img, draw, ms)
        
        style = TextStyle(fill=diff.text, anchor='lm', font=font, 
                         shadow_width=0.8, shadow_color=diff.deep,
                         shadow2_width=0.8, shadow2_color=diff.frame, shadow2_offset=0.7)
        drawer.text(1, height / 2, display_text, style)
        
        if cn_width:
            style_cn = TextStyle(fill=diff.text, anchor='ld', 
                               font=font_manager.font(FontCode.MiSans_Heavy, ms.x(3.3)),
                               shadow_width=0.8, shadow_color=diff.deep,
                               shadow2_width=0.8, shadow2_color=diff.frame, shadow2_offset=0.7)
            drawer.text(ms.rev(x2 - x1) * 1.1, ms.rev(y2 - y1) * 1.1, 
                       diff.text_title_cn, style_cn)

        return img

    def render(self) -> Image.Image:
        """渲染难度标签"""
        return self._get_diff_text_image(self.diff, self.custom_text, 
                                        self.limit_width, self.ms, self.cn_level)


class DrawBadge:
    """谱面类型徽章组件 (标准/DX)"""
    
    def __init__(self, is_cabinet_dx: bool, ms: MS = _MS_DEFAULT, 
                 cn_level: Literal[0, 1, 2] = 0, font_manager: Optional[FontManager] = None):
        self.is_cabinet_dx = is_cabinet_dx
        self.ms = ms
        self.cn_level = cn_level
        self.font_manager = font_manager

    @lru_cache(maxsize=4)
    def _render_sd_badge(self, ms: MS, cn_level: Literal[0, 1, 2]) -> Image.Image:
        """渲染标准谱面徽章"""
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        draw = ImageDraw.Draw(img)
        drawer = BaseDrawer(img, draw, ms)

        COLOR_SD = '#4AF'
        drawer.rounded_rect(0, 0, 20, 5, fill=COLOR_SD, radius=5)
        
        offset = 0.6 if cn_level else 0
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ...constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        font = font_manager.font(FontCode.MiSans_Heavy, ms.x(3 + offset))
        text = "标 准" if cn_level else "スタンダード"
        style = TextStyle(fill='#FFF', anchor='mm', font=font)
        drawer.text(10, 2.5, text, style)
        return img

    @lru_cache(maxsize=4)
    def _render_dx_badge(self, ms: MS, cn_level: Literal[0, 1, 2]) -> Image.Image:
        """渲染 DX 谱面徽章"""
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        draw = ImageDraw.Draw(img)
        drawer = BaseDrawer(img, draw, ms)

        COLOR_DX = ('#FF7711', '#FFFFFF')
        COLOR_DELUXE = ('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6', '#2299EE')

        drawer.rounded_rect(0, 0, 20, 5, fill='#FFF', radius=5,
                          outline=COLOR_DX[1] if cn_level else COLOR_DELUXE[-1], width=0.5)
        
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ...constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        if cn_level:
            text = "DX"
            style = TextStyle(fill=COLOR_DX[0], anchor='mm', 
                            font=font_manager.font(FontCode.MiSans_Heavy, ms.x(4.1)))
            drawer.text(10, 2.5, text, style)
        else:
            font = font_manager.font(FontCode.MiSans_Heavy, ms.x(3.2))
            text = "でらっくす"
            total_text_width = ms.rev(font.getlength(text))
            start_x = 10 - (total_text_width / 2)
            current_x = start_x
            center_y = 2.5
            for char, color in zip(text, COLOR_DELUXE):
                style = TextStyle(fill=color, anchor='lm', font=font)
                drawer.text(current_x, center_y, char, style)
                char_width = ms.rev(font.getlength(char))
                current_x += char_width
        return img

    def render(self) -> Image.Image:
        """渲染徽章"""
        if self.is_cabinet_dx:
            return self._render_dx_badge(self.ms, self.cn_level)
        else:
            return self._render_sd_badge(self.ms, self.cn_level)
