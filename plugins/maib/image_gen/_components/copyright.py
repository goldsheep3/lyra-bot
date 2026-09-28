"""
image_gen.components.copyright
底栏组件
"""
from PIL import Image
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ..color import THEME_CYAN, THEME_DARK
from ...utils import get_git_head_hash
from .base import TextDrawStyle, Drawer


class CopyrightBadge:
    """版权信息栏组件"""

    @classmethod
    def size(cls, width: float, content: str, ms: MS = MS()) -> tuple[float, float, float]:
        """计算版权信息栏的尺寸"""
        raw_size = 5.0
        test_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(raw_size))
        tx1, ty1, tx2, ty2 = test_font.getbbox(content)
        raw_width, raw_height = int(tx2 - tx1 + 1), int(ty2 - ty1 + 1)
        w_h_ratio = raw_width / raw_height
        h_size_radio = raw_height / raw_size
        
        # 计算目标尺寸
        w = width * 0.8
        h = w / w_h_ratio
        size = ms.x(h / h_size_radio) * 0.8
        height = h / 0.8
        
        return width, height, size

    @classmethod
    @lru_cache(maxsize=3)
    def _copyright_bar(cls, width: float, content: str, ms: MS = MS()) -> Image.Image:
        _, height, size = cls.size(width, content, ms=ms)
        
        font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(size))
        img = Image.new('RGBA', ms.xy(width, height), THEME_DARK)

        drawer = Drawer(img, ms=ms)
        drawer.text(width / 2, height / 2, text=content,
                    tds=TextDrawStyle(fill=THEME_CYAN, anchor='mm', font=font))

        return img

    @classmethod
    def _copyright(cls, width_mpx: float, ms: MS = MS()) -> Image.Image:
        content = "    ".join([
            "Generate by LyraBot",
            "Dev by GoldSheep3 (and his Bakamai⑨'s Members)",
            "Version: " + (get_git_head_hash() or "Unknown"),
            "Background Artist by @银色山雾",
        ])
        return cls._copyright_bar(width_mpx, content, ms=ms).copy()

    @classmethod
    def copyright(cls, width_px: int, ms: MS = MS()) -> Image.Image:
        """绘制版权信息栏"""
        width_mpx = ms.x(width_px)
        return cls._copyright(width_mpx, ms=ms)

    @classmethod
    def copyright_mpx(cls, width_mpx: float, ms: MS = MS()) -> Image.Image:
        """绘制版权信息栏"""
        return cls._copyright(width_mpx, ms=ms)