"""
image_gen.components.simple_list
SimpleList 看板构建器
"""
from typing import Optional
from PIL import Image, ImageFont
from ..utils import MS, FontCode, FontManager
from .base import TextDrawStyle, Drawer


class SimpleListBoard:
    """文本列表看板"""
    
    @classmethod
    def list(cls, text: str, font: Optional[ImageFont.FreeTypeFont] = None, ms: MS = MS()) -> Image.Image:
        # font 必须是 px 尺寸（用 ms.x(mpx) 生成）；否则底图按 mpx 放大后文字会小 multiple 倍
        font = font or FontManager.font(FontCode.MiSans_Demibold, size=ms.x(16))
        lines = text.splitlines() or [""]
        # 度量按 px 计算，再 rev 回 mpx 交给 ms 换算画布，避免画布被二次缩放
        width = ms.rev(round(max(font.getlength(line) for line in lines)))
        height = ms.rev(round(len(lines) * font.size * 1.5))
        img = Image.new("RGB", ms.xy(width+1, height+1), color="#FFF")
        drawer = Drawer(img, ms=ms)
        drawer.text(0.5, 0.5, text=text, tds=TextDrawStyle(fill="#000", anchor="la", font=font))
        return img


draw_simple_board = SimpleListBoard.list
