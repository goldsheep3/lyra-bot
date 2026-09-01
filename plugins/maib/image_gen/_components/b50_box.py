"""
image_gen.components.b50_box
b50 盒子组件
"""
import zipfile
from PIL import Image
from typing import Optional

from ...utils import MaiData
from ...utils.enums import UICode, Server

from ..utils import MS, FontCode, FontManager
from ..style import get_difficulty_style
from ..color import TRANSPARENT, WHITE
from .base import TextDrawStyle, Drawer
from .mini_box import MiniBoxBadge


class B50BoxBadge(MiniBoxBadge):

    @classmethod
    def b50_box(cls, maidata: MaiData, difficulty: int, server: Server,
                current_version: int, index: int, is_b15: Optional[bool] = None,
                ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        chart = maidata.get_chart(difficulty)
        if not chart:
            return cls.empty(ms=ms)
        base_img = cls.box(
            maidata=maidata, difficulty=difficulty, server=server, ms=ms, ui_code=ui_code
        )
        
        img = Image.new('RGBA', ms.xy(42, 5), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        bg_color = get_difficulty_style(chart.difficulty).bg
        drawer.capsule(0, 0, 42, 5, fill=f"{bg_color}99")
        drawer.capsule(0, 0, 16, 5, fill=f"{bg_color}55")
        b_type = '15' if is_b15 else '35'
        tds = TextDrawStyle(fill=WHITE, anchor='mm', font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(3)))
        drawer.text(8, 2.5, f"b{b_type} #{index}", tds=tds)
        drawer.text(29, 2.5, f"{chart.lv:.1f} > {maidata.get_chart_dxrating(difficulty, server, current_version)}", tds=tds)
        base_img.alpha_composite(img, ms.xy(54, 25))
        
        return base_img
