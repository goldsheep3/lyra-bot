from typing import Optional
from PIL import Image
from functools import lru_cache

from ..color import TRANSPARENT
from ..utils import MS
from .base import Drawer, TextDrawStyle


class Capsule:
    
    @classmethod
    @lru_cache(maxsize=16)
    def _capsule(cls, width: float, height: float, fill: str,
                 *, outline: Optional[str] = None, outline_width = 1,
                 ms: MS = MS()) -> Image.Image:
        """绘制胶囊形状"""
        img = Image.new('RGBA', ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        drawer.capsule(0, 0, width, height, fill=fill, outline=outline, outline_width=outline_width)
        return img

    @classmethod
    def _mm_text(cls, drawer: Drawer, x: float, y: float, text: str, tds: TextDrawStyle):
        """绘制文本（强制修改为 mm 锚点）"""
        if tds.anchor != 'mm':
            tds = TextDrawStyle(
                font=tds.font, anchor='mm', margin=tds.margin, limit=tds.limit,
                fill=tds.fill, stroke=tds.stroke, stroke_width=tds.stroke_width,
                shadow=tds.shadow, shadow_width=tds.shadow_width,
                shadow2=tds.shadow2, shadow2_width=tds.shadow2_width,
                shadow2_offset=tds.shadow2_offset
            )
        drawer.text(x, y, text=text, tds=tds)

    @classmethod
    def _capsule_with_text(cls, width: float, height: float, fill: str, text: str,
                           *, tds: TextDrawStyle, outline: Optional[str] = None, outline_width = 1,
                           ms: MS = MS()) -> Image.Image:
        """绘制带文本的胶囊形状"""
        img = cls._capsule(width, height, fill=fill, outline=outline, outline_width=outline_width, ms=ms).copy()
        drawer = Drawer(img, ms=ms)
        x, y = width / 2, height / 2
        if outline is not None and outline_width > 0:
            x, y = x + outline_width, y + outline_width
        cls._mm_text(drawer, x, y, text, tds)
        return img

    @classmethod
    def capsule(cls, width: float, height: float, fill: str, text: str = '',
                *, tds: Optional[TextDrawStyle] = None, outline: Optional[str] = None, outline_width = 1,
                ms: MS = MS()) -> Image.Image:
        """绘制胶囊形状"""
        if text and tds is not None:
            return cls._capsule_with_text(width, height, fill, text, tds=tds, outline=outline, outline_width=outline_width, ms=ms)
        else:
            return cls._capsule(width, height, fill=fill, outline=outline, outline_width=outline_width, ms=ms).copy()
