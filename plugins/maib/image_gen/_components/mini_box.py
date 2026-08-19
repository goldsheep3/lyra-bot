"""
image_gen.components.mini_box
基础盒子组件
"""
from typing import Literal
from PIL import Image
from functools import lru_cache

from ...utils import MaiData
from ...utils.enums import UICode, Server
from ...utils.map import DifficultyID
from ..utils import MS, FontManager, FontCode
from ..color import TRANSPARENT, GRAY
from ..style import get_difficulty_style, DIFFICULTY_TYPE, get_rate_style
from .base import TextDrawStyle, Drawer
from . import (
    DifficultyBadge, CabinetBadge, EvaluateBadge, AchievementBadge, CabinetBadge
)


class MiniBoxBadge:
    """小谱面盒子组件"""

    width: float = 80
    height: float = 27
    outline: float = 0.7
    radius: float = 2.5

    @classmethod
    def size(cls) -> tuple[float, float]:
        return cls.width, cls.height

    @classmethod
    def empty(cls, ms: MS = MS()) -> Image.Image:
        return Image.new('RGBA', ms.xy(*cls.size()), TRANSPARENT)

    linebar_height: float = 5
    linebar_y: float = 0
    linebar_id_radius: float = linebar_height / 3
    
    cover_size: float = height

    @classmethod
    @lru_cache(maxsize=12)
    def _base(cls, difficulty: DIFFICULTY_TYPE, cabinet: Literal['SD', 'DX'],
              *, is_cn: bool = True, is_cn_all: bool = False, ms: MS = MS()) -> Image.Image:
        is_cn = is_cn or is_cn_all
        style = get_difficulty_style(difficulty, is_cn_all=is_cn_all)
        
        img = Image.new('RGBA', ms.xy(*cls.size()), style.bg)
        drawer = Drawer(img, ms=ms)
        drawer.rounded_rect(0, cls.outline+cls.linebar_y, cls.width, cls.linebar_height,
                            fill=style.title_bg)
        # id 显示
        radius = CabinetBadge.size()[1] / 2
        drawer.rounded_rect(cls.outline, cls.outline, cls.cover_size+11.5, cls.linebar_height,
                            fill=style.frame, radius=radius)
        # 谱面类型
        difficulty_img = CabinetBadge.cabinet_badge2(cabinet=cabinet, ms=MS(ms*3/5), is_cn=is_cn)
        img.alpha_composite(difficulty_img, ms.xy(cls.outline+cls.cover_size-0.5, cls.outline))

        # 边框
        drawer.rounded_rect(0, 0, cls.width, cls.height, None, radius=cls.radius, outline=style.frame, width=cls.outline)
        return img

    evaluate_height = linebar_y + linebar_height + 13

    @classmethod
    def box(cls, maidata: MaiData, difficulty: DifficultyID, server: Server,
            ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        chart = maidata.get_chart(difficulty) if maidata else None
        if not chart:
            return cls.empty(ms=ms)
        ach = chart.get_ach(server=server)
        style = get_difficulty_style(difficulty, is_cn_all=ui_code.is_cn_all)
        
        img = cls._base(difficulty, maidata.cabinet, is_cn=ui_code.is_cn, is_cn_all=ui_code.is_cn_all, ms=ms).copy()
        drawer = Drawer(img, ms=ms)
        # 曲绘
        with maidata.image() as cover:
            if cover:
                cover_img = cover.resize(ms.xy(cls.cover_size, cls.cover_size), Image.Resampling.LANCZOS)
            else:
                cover_img = Image.new('RGBA', ms.xy(cls.cover_size, cls.cover_size), GRAY)
            Drawer.masked(cover_img, radius=cls.radius, ms=ms)
            img.paste(cover_img, ms.xy(0, 0), cover_img)
            drawer.rounded_rect(0, 0, cls.cover_size, cls.cover_size, None, radius=cls.radius,
                                outline=style.frame, width=cls.outline)
        # id
        drawer.text(cls.cover_size+5.5, cls.linebar_y + CabinetBadge.size()[1]*3/5 + 0.2,
                    text=f' #{maidata.shortid}'.replace('0', 'O'), tds=TextDrawStyle(
            fill=style.level_text, anchor='ma', font=FontManager.font(FontCode.NotoSansSC_Medium, ms.x(1.6)))
        )
        # title
        title_tds = DifficultyBadge.tds(style, font=FontManager.font(FontCode.NotoSansSC_Bold, ms.x(3.5)), scale=0.65)
        drawer.text(cls.cover_size + CabinetBadge.size()[0]*3/5 + 1, cls.linebar_y + cls.linebar_height/2,
                    text=maidata.title, tds=title_tds)
        
        # Achievement
        achievement = int(ach.achievement*10000)
        # rate_style = get_rate_style(achievement, buddy=False)
        # drawer.text(
        #     cls.cover_size + 1, cls.linebar_y + cls.linebar_height + 0.5,
        #     text=rate_style.content.replace('0', 'O'), tds=AchievementBadge.tds(
        #         rate_style, font=FontManager.font(FontCode.JBMono_ExtraBold, ms.x(8)), scale=0.7).new(anchor='la')
        # )
        achievement_img = AchievementBadge.achievement(achievement, difficulty, buddy=maidata.buddy, 
                                                       ms=MS(ms*0.8), ui_code=ui_code)
        img.paste(achievement_img, ms.xy(cls.cover_size + 1, cls.linebar_y + cls.linebar_height + 1.5), achievement_img)

        # FC / FS
        fc = EvaluateBadge.combo(ach.combo, mini=False, ms=ms, ui_code=ui_code)
        fs = EvaluateBadge.sync(ach.sync, mini=False, ms=ms, ui_code=ui_code)
        img.paste(fc, ms.xy(cls.cover_size + 1, cls.evaluate_height), fc)
        img.paste(fs, ms.xy(cls.cover_size + 27, cls.evaluate_height), fs)

        return Drawer.masked(
            img,
            radius=2.5, ms=ms
        )
