"""
image_gen.components.b50_box
b50 盒子组件
"""
from PIL import Image
from typing import Optional

from ...utils import MaiData, get_ap_bonus_value
from ...utils.enums import UICode, Server, SLevelSource
from ...utils.map import DifficultyID, VersionID, Versions

from ..color import TRANSPARENT, WHITE
from ..utils import MS, FontManager, FontCode
from ..style import get_difficulty_style
from .base import Drawer, TextDrawStyle
from .mini_box import MiniBoxBadge
from . import DifficultyBadge, UserHeaderBadge


class B50BoxBadge(MiniBoxBadge):

    @classmethod
    def b50_box(cls, maidata: MaiData, difficulty: DifficultyID, server: Server,
                current_version: int, index: int, is_b15: bool = False, *,
                ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        chart = maidata.charts.get(difficulty)
        if chart is None:
            return cls.empty(ms=ms)
        
        img = cls.box(maidata=maidata, difficulty=difficulty, server=server, ms=ms, ui_code=ui_code)
        drawer = Drawer(img, ms=ms)
        
        # Level / Best / Rating
        past_last = 15 if is_b15 else 35
        scope = SLevelSource.parse(server)
        level = getattr(chart, scope.lv_field, 0)
        ap_bonus = get_ap_bonus_value(current_version)
        ra = maidata.get_chart_dxrating(difficulty, server, ap_bonus=ap_bonus)
        text = f"b{past_last}#{index:<2}   {level:>4.1f} -> {ra:>3}"
        
        style = get_difficulty_style(difficulty, is_cn_all=ui_code.is_cn_all)
        # tds = DifficultyBadge.tds(style=style, font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(2.8)), scale=0.6).new(
        #     fill=style.level_text, shadow_width=0.5, shadow=style.title_bg
        # )
        tds = TextDrawStyle(
            fill=style.frame, font=FontManager.font(FontCode.MiSans_Heavy, size=ms.x(2.5)), anchor='ls',
            shadow_width=0.4, shadow=WHITE
        )
        drawer.text(cls.cover_size + 1.5, cls.evaluate_height + 7, text, tds=tds)

        return img

    @classmethod
    def header_box(cls, dxrating: int, latest_version: VersionID, is_b15: bool = False,
                   *, cirp_frame: bool = True, ms: MS = MS()) -> Image.Image:
        """绘制 b50 的头部盒子（非歌曲数据）"""
        img = Image.new("RGBA", ms.xy(*cls.size()), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        
        dxra_img = UserHeaderBadge.dxrating(dxrating=dxrating, cirp_frame=cirp_frame, ms=MS(ms*16/15))
        img.paste(dxra_img, ms.xy(0, 9), dxra_img)
        
        # 这里颜色通过判断最多的难度的颜色来确定，现在硬编码 5 (master)
        style = get_difficulty_style(5, is_cn_all=False)
        font_pol = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(6))
        tds_pol = DifficultyBadge.tds(style=style, font=font_pol, scale=1).new(anchor='ls')
        text_pol = f"Best{15 if is_b15 else 35}"
        drawer.text(2, 7, text_pol, tds=tds_pol)
        
        w = ms.rev(round(font_pol.getlength(text_pol) * 1.17))
        font_ver = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4.5))
        tds_ver = DifficultyBadge.tds(style=style, font=font_ver, scale=0.8).new(anchor='ls')
        drawer.text(w, 7, f"~ {Versions.text_name(latest_version)}", tds=tds_ver)

        return img