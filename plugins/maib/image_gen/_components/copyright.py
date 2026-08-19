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
    @lru_cache(maxsize=3)
    def _copyright_bar(cls, width_px: int, content: str, ms: MS = MS()) -> Image.Image:
        width = ms.rev(width_px)
        # 测量字体大小合适尺寸
        base_size = 5.0
        test_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(base_size))
        tx1, ty1, tx2, ty2 = test_font.getbbox(content)
        raw_width, raw_height = int(tx2 - tx1 + 1), int(ty2 - ty1 + 1)
        target_content_width = width * 0.9  # 预留左右各 5% 的空白边距
        # 缩放系数 = 目标 / 原始
        ratio = min(target_content_width / raw_width, 1.0)
        final_size = max(base_size * ratio, 1.2)
        height = round(max((raw_height * ratio) * 1.4, ms.x(6)))  # 预留上下各 20% 的空白边距
        font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(final_size))
        
        # 实际渲染
        img = Image.new('RGBA', (width_px, ms.x(height)), THEME_DARK)
        drawer = Drawer(img, ms=ms)
        drawer.text(width / 2, height / 2, text=content,
                    tds=TextDrawStyle(fill=THEME_CYAN, anchor='mm', font=font))

        return img

    @classmethod
    def _copyright(cls, width_px: int, ms: MS = MS()) -> Image.Image:
        content = "  ,  ".join([
            "Generate by LyraBot",
            "Dev by GoldSheep3 (and his Bakamai⑨'s Members)",
            "Version: " + (get_git_head_hash() or "Unknown"),
            "Background Artist by @银色山雾",
        ])
        return cls._copyright_bar(width_px, content, ms=ms).copy()

    @classmethod
    def copyright(cls, width_px: int, ms: MS = MS()) -> Image.Image:
        """绘制版权信息栏"""
        return cls._copyright(width_px, ms=ms)

    @classmethod
    def copyright_mpx(cls, width_mpx: int, ms: MS = MS()) -> Image.Image:
        """绘制版权信息栏"""
        width_px = ms.x(width_mpx)
        return cls._copyright(width_px, ms=ms)