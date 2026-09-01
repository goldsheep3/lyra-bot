"""
image_gen.components.mini_box
基础盒子组件
"""
from typing import Optional
from PIL import Image
from functools import lru_cache

from ...utils import MaiData
from ...utils.enums import UICode, Server
from ...utils.map import DifficultyID
from ..utils import MS
from ..color import TRANSPARENT
from ..style import get_difficulty_style
from .base import TextDrawStyle, Drawer
from . import (
    DifficultyBadge, CabinetBadge, EvaluateBadge, AchievementBadge, DXScoreBadge,
)


class MiniBoxBadge:
    """小谱面盒子组件"""

    @classmethod
    def size(cls) -> tuple[int, int]:
        w, h, ow = 97, 36, 1
        width, height = w + ow * 2, h + ow * 2
        return width, height

    @classmethod
    def empty(cls, ms: MS = MS()) -> Image.Image:
        return Image.new('RGBA', ms.xy(*cls.size()), TRANSPARENT)

    @classmethod
    @lru_cache(maxsize=12)
    def base(cls, difficulty: DifficultyID, is_cabinet_dx: bool, shortid: int, w: int, h: int, ow: int,
             ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        style = get_difficulty_style(difficulty, is_cn_all=ui_code.is_cn_all)
        
        img = Image.new('RGBA', ms.xy(*cls.size()), '#FFFFFF00')
        drawer = Drawer(img, ms=ms)

        # TODO 待修整
        drawer.rounded_rect(ow, ow, w, h, style.bg, radius=2.5, outline=style.frame)
        drawer.cut_line(ow, ow, w, h, radius=0, line_y=ow + 2, line_h=5, fill=style.title_bg)
        drawer.rounded_rect(ow, ow, w, h, None, radius=2.5, outline=style.title_bg, width=1)
        cabinet = 'DX' if is_cabinet_dx else 'SD'
        badge = CabinetBadge.cabinet_badge(cabinet=cabinet, ms=ms, ui_code=ui_code)
        img.paste(badge, ms.xy(ow + 75, ow + 2), badge)
        shortid_img = DifficultyBadge.draw_text(difficulty=difficulty, text=f'#{shortid}', ms=ms)
        img.paste(shortid_img, ms.xy(ow + 35, ow + 4.2 - ms.rev(round(shortid_img.size[1] / 2))), shortid_img)
        return img

    @classmethod
    def box(cls, maidata: MaiData, difficulty: DifficultyID, server: Server,
            ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        w, h, ow = 97, 36, 1  # w, h, outline_width

        chart = maidata.get_chart(difficulty) if maidata else None
        if not chart:
            return cls.empty(ms=ms)
        ach = chart.get_ach(server=server)

        img = cls.base(
            difficulty=chart.difficulty,
            is_cabinet_dx=maidata.is_cabinet_dx,
            shortid=maidata.shortid,
            w=w,
            h=h,
            ow=ow,
            ms=ms,
            ui_code=ui_code,
        ).copy()
        # 曲绘
        with maidata.image() as cover:
            if cover:
                mask = Drawer.get_mask(w=32, h=32, radius=1.5, ms=ms)
                cover_img = cover.resize(ms.xy(32, 32), Image.Resampling.LANCZOS)
                img.paste(cover_img, ms.xy(ow + 2, ow + 2), mask)
        # 达成率
        ach_img = AchievementBadge.achievement(round(ach.achievement*10000), chart.difficulty, buddy=False, ms=ms, ui_code=ui_code)
        img.paste(ach_img, ms.xy(ow + 35, ow + 9), ach_img)
        dxs, dxs_max, _ = ach.dxscore_tuple
        dxscore_img = DXScoreBadge.dxscore_badge(dxs, dxs_max, lite=True, ms=ms, ui_code=ui_code)
        img.paste(dxscore_img, ms.xy(ow + 53, ow + 31), dxscore_img)
        # 评价图标
        fc = EvaluateBadge.combo(ach.combo, mini=True, ms=ms, ui_code=ui_code)
        fs = EvaluateBadge.sync(ach.sync, mini=True, ms=ms, ui_code=ui_code)
        img.paste(fc, ms.xy(ow + 35.5, ow + 24), fc)
        img.paste(fs, ms.xy(ow + 35.5, ow + 29), fs)
        return img
