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
from ..tools import bcm
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
        img = cls.box(
            maidata=maidata, difficulty=difficulty, server=server, ms=ms, ui_code=ui_code
        )
        drawer = Drawer(img, ms=ms)
        drawer.rounded_rect(54, 25, 42, 5, fill=bcm(get_difficulty_style(chart.difficulty).bg, '#0009'), radius=4)
        drawer.rounded_rect(54, 25, 16, 5, fill='#006', radius=4)
        b_type = '15' if is_b15 else '35'
        drawer.text(62, 27.5, f"b{b_type} #{index}", tds=TextDrawStyle(
            fill='#FFF', anchor='mm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3))
        ))
        drawer.text(74, 27.5, f"{chart.lv:.1f} > {maidata.get_chart_dxrating(difficulty, server, current_version)}", tds=TextDrawStyle(
            fill='#FFF', anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3))
        ))
        return img
