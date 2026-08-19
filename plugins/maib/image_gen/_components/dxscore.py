"""
image_gen.components.dxscore
DX分数组件

> DXSCORE ✦✦✦✦✦ 597/597 / ...
"""
from PIL import Image

from ...utils.enums import UICode
from ..color import TRANSPARENT, BLACK
from ..utils import MS, FontCode, FontManager
from .base import TextDrawStyle, Drawer
from ..style import get_dxscore_style


class DXScoreBadge:
    """DX 分数组件"""
    
    _width_lite = 33
    _height_lite = 3
    _width = 24
    _height = 9
    
    @classmethod
    def _size(cls, lite: bool = False) -> tuple[int, int]:
        if lite:
            return cls._width_lite, cls._height_lite
        else:
            return cls._width, cls._height

    @classmethod
    def _dxscore_badge_mini(cls, dxscore: int, max_dxscore: int, ms: MS = MS(),
                            is_jp: bool = True, is_cn: bool = False) -> Image.Image:
        style = get_dxscore_style(dxscore, max_dxscore, is_jp=is_jp, is_cn=is_cn)
        width, height = cls._size(lite=True)
        img = Image.new('RGBA', ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)

        # 背景
        drawer.capsule(0, 0, width, height, fill=style.fill)
        # 标题
        title_font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(1.6))
        drawer.text(1.2, height/2, text=style.title, tds=TextDrawStyle(fill=style.title_fill, anchor='lm', font=title_font))
        title_width = ms.rev(int(title_font.getlength(style.title)+1))
        # 星星
        star_font = FontManager.font(FontCode.NotoSansSymbols2, size=ms.x(2))
        drawer.text(2.6+title_width, height/2+0.2, text=style.star, tds=TextDrawStyle(fill=style.star_fill, anchor='lm', font=star_font))
        # 分数
        score_font = FontManager.font(FontCode.JBMono_Medium, size=ms.x(2))
        drawer.text(width-1.6, height/2, text=style.content.replace('0', 'O'), tds=TextDrawStyle(fill='#333', anchor='rm', font=score_font))

        return img

    @classmethod
    def _dxscore_badge(cls, dxscore: int, max_dxscore: int, ms: MS = MS(),
                       is_jp: bool = True, is_cn: bool = False) -> Image.Image:
        style = get_dxscore_style(dxscore, max_dxscore, is_jp=is_jp, is_cn=is_cn)
        width, height = cls._size(lite=False)
        img = Image.new('RGBA', ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)

        # 背景
        drawer.capsule(0, 0, width, height, fill=style.fill)
        # 标题
        title_font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(2))
        drawer.text(0.5, 0.5, text=style.title, tds=TextDrawStyle(fill=style.title_fill, anchor='lt', font=title_font))
        # 分数
        score_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2.5))
        drawer.text(width/2, height/2, text=style.content, tds=TextDrawStyle(fill='#333', anchor='mm', font=score_font))
        # 星星
        star_font = FontManager.font(FontCode.NotoSansSymbols2, size=ms.x(2.2))
        drawer.text(width/2, height-0.5, text=style.star or '', tds=TextDrawStyle(fill=style.star_fill, anchor='ms', font=star_font))

        return img

    @classmethod
    def dxscore_badge(cls, dxscore: int, max_dxscore: int, lite: bool = False,
                      ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """获取 DX 分数组件图像"""
        is_jp = ui_code.is_jp
        is_cn = ui_code.is_cn
        if lite:
            return cls._dxscore_badge_mini(dxscore, max_dxscore, ms=ms, is_jp=is_jp, is_cn=is_cn)
        else:
            return cls._dxscore_badge(dxscore, max_dxscore, ms=ms, is_jp=is_jp, is_cn=is_cn)
