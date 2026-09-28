"""
image_gen.components.cabinet
谱面（机台）类型组件

> Standard / Deluxe
"""
from typing import Optional
from PIL import Image, ImageDraw
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ..color import TRANSPARENT
from ..style import CABINET_TYPE, get_cabinet_style
from .base import TextDrawStyle, Drawer
from .capsule import Capsule


class CabinetBadge:
    """SD/DX 机台徽章组件"""
    
    # 最终图片输出尺寸
    width: float = 20
    height: float = 5
    outline: float = 0.6

    @classmethod
    def size(cls) -> tuple[float, float]:
        return cls.width, cls.height

    dx_font_size: float = 3.2
    sd_font_size: float = 3.6
    sd_font_size_cn: float = 3.0

    @classmethod
    @lru_cache(maxsize=4)
    def _cabinet_badge2(cls, cabinet: CABINET_TYPE, ms: MS = MS(), is_cn: bool = False) -> Image.Image:
        style = get_cabinet_style(cabinet, is_cn)
        img = Image.new('RGBA', ms.xy(*cls.size()), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        if cabinet == 'DX':
            font_size_mpx = cls.dx_font_size
        else:
            font_size_mpx = cls.sd_font_size_cn if is_cn else cls.sd_font_size
        font = FontManager.font(FontCode.MiSans_Heavy, ms.x(font_size_mpx))
        drawer.capsule(0, 0, *cls.size(), fill=style.fill,
                        outline=style.outline, outline_width=cls.outline)
        char_width = ms.rev(round(font.getlength(style.content))) / len(style.content)
        start_x = 10 - (char_width * (len(style.content) - 1) / 2)
        current_x = start_x
        center_y = 2.5
        
        colors: tuple[str, ...] = style.text
        for index, char in enumerate(style.content):
            tds = TextDrawStyle(fill=colors[index % len(colors)], anchor='mm', font=font)
            drawer.text(current_x, center_y, text=char, tds=tds)
            current_x += char_width

        return img

    @classmethod
    @lru_cache(maxsize=4)
    def _cabinet_badge(cls, cabinet: CABINET_TYPE, ms: MS = MS(), is_cn: bool = False) -> Image.Image:
        style = get_cabinet_style(cabinet, is_cn)
        img = Image.new('RGBA', ms.xy(21, 6), "#FFFFFF00")
        drawer = Drawer(img, ms=ms)
        if cabinet == 'DX':
            font_size_mpx = 3.2
        else:
            font_size_mpx = 3.6 if is_cn else 3.0
        font = FontManager.font(FontCode.MiSans_Heavy, ms.x(font_size_mpx))
        drawer.capsule(0.5, 0.5, 20, 5, fill=style.fill,
                        outline=style.outline, outline_width=0.5)
        char_width = ms.rev(round(font.getlength(style.content))) / len(style.content)
        start_x = 10.5 - (char_width * (len(style.content) - 1) / 2)
        current_x = start_x
        center_y = 3
        
        colors: tuple[str, ...] = style.text
        for index, char in enumerate(style.content):
            tds = TextDrawStyle(fill=colors[index % len(colors)], anchor='mm', font=font)
            drawer.text(current_x, center_y, text=char, tds=tds)
            current_x += char_width

        return img

    @classmethod
    def cabinet_sd_badge(cls, ms: MS = MS(), is_cn: bool = False) -> Image.Image:
        """绘制 SD 机台徽章"""
        return cls._cabinet_badge(cabinet='SD', ms=ms, is_cn=is_cn).copy()

    @classmethod
    def cabinet_dx_badge(cls, ms: MS = MS(), is_cn: bool = False) -> Image.Image:
        """绘制 DX 机台徽章"""
        return cls._cabinet_badge(cabinet='DX', ms=ms, is_cn=is_cn).copy()

    @classmethod
    def cabinet_badge(cls, cabinet: CABINET_TYPE, *, ms: MS = MS(),
                      is_cn: Optional[bool] = None, ui_code: UICode = UICode.JP) -> Image.Image:
        """绘制 SD/DX 机台徽章"""
        is_cn = ui_code.is_cn if is_cn is None else is_cn
        return cls.cabinet_dx_badge(ms=ms, is_cn=is_cn) if cabinet == 'DX' else cls.cabinet_sd_badge(ms=ms, is_cn=is_cn)

    @classmethod
    def cabinet_badge2(cls, cabinet: CABINET_TYPE, *, ms: MS = MS(),
                       is_cn: Optional[bool] = None, ui_code: UICode = UICode.JP) -> Image.Image:
        """绘制 SD/DX 机台徽章"""
        is_cn = ui_code.is_cn if is_cn is None else is_cn
        
        return cls._cabinet_badge2(cabinet='DX', ms=ms, is_cn=is_cn) if cabinet == 'DX' else cls._cabinet_badge2(cabinet='SD', ms=ms, is_cn=is_cn)