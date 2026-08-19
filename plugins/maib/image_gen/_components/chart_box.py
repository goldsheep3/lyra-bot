"""
image_gen.components.chart_box
谱面及成绩盒子组件
"""
from typing import Literal, Optional
from PIL import Image
from functools import lru_cache

from ...utils import MaiChart
from ...utils.enums import UICode, Server
from ...utils.map import DifficultyID
from ..utils import MS, FontCode, FontManager
from ..color import TRANSPARENT, HALF_TRANSPARENT, BLACK, WHITE
from ..style import get_difficulty_style, _DIFFICULTY_TYPE, get_note_designer_text
from ..tools import bcm, rounded_image
from .base import TextDrawStyle, Drawer
from . import (
    DifficultyBadge, LevelBadge, CabinetBadge, EvaluateBadge, AchievementBadge, DXScoreBadge,
)


# TODO 不再修整，待调用方全部过渡到 V2 后直接删除
class ChartBoxBadge:
    """谱面信息框组件"""

    @classmethod
    @lru_cache(maxsize=32)
    def _chart_box_base(cls, difficulty: DifficultyID, is_cabinet_dx: bool, w: int, h: int, ow: int,
                       ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        style = get_difficulty_style(difficulty, is_cn_all=ui_code.is_cn_all)
        
        img = Image.new('RGBA', ms.xy(w + ow * 2, h + ow * 2), '#FFFFFF00')
        drawer = Drawer(img, ms=ms)
        drawer.rounded_rect(ow, ow, w, h, radius=4, fill=style.bg)
        drawer.cut_line(ow, ow, w, h, radius=4, line_y=ow + 2, line_h=5, fill=style.title_bg)
        drawer.rounded_rect(ow, ow, w, h, radius=4, fill=None, outline=style.frame, width=1)
    
        difficulty_img = DifficultyBadge.difficulty(difficulty=difficulty, ms=ms, ui_code=ui_code)
        diff_height = ms.rev(difficulty_img.size[1])
        img.paste(difficulty_img, ms.xy(ow + 2.5, ow + 4.3 - diff_height / 2), difficulty_img)
        cabinet = 'DX' if is_cabinet_dx else 'SD'
        badge = CabinetBadge.cabinet_badge(cabinet=cabinet, ms=ms, ui_code=ui_code)
        img.paste(badge, ms.xy(ow + 85, ow + 2), badge)
        return img


    @classmethod
    def box(cls, chart: MaiChart, is_cabinet_dx: bool, server: Server, plus_level: int = 6, is_utage: bool = False,
            ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """组件：谱面信息框"""
        w, h, ow = 108, 36, 1  # w, h, outline_width       
        img = cls._chart_box_base(difficulty=chart.difficulty, is_cabinet_dx=is_cabinet_dx, w=w, h=h, ow=ow, ms=ms, ui_code=ui_code).copy()
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        level_img = LevelBadge.level(chart.lv, chart.difficulty, plus, 'question_mask' if is_utage else 'display',
                                     ms=ms, ui_code=ui_code)
        img.paste(level_img, ms.xy(ow + 64, ow + 7.4), level_img)
        # 达成率
        ach = chart.get_ach(server=server)
        ach_img = AchievementBadge.achievement(round(ach.achievement*10000), chart.difficulty, buddy=False, ms=ms, ui_code=ui_code)
        img.paste(ach_img, ms.xy(ow + 2, ow + 9), ach_img)
        dxs, dxs_max, _ = ach.dxscore_tuple
        dxscore_img = DXScoreBadge.dxscore_badge(dxs, dxs_max, lite=False, ms=ms, ui_code=ui_code)
        img.paste(dxscore_img, ms.xy(ow + 38, ow + 25), dxscore_img)
        # 评价图标
        fc = EvaluateBadge.combo(ach.combo, mini=False, ms=ms, ui_code=ui_code)
        fs = EvaluateBadge.sync(ach.sync, mini=False, ms=ms, ui_code=ui_code)
        img.paste(fc, ms.xy(ow + 2.5, ow + 27-3), fc)
        img.paste(fs, ms.xy(ow + 2.5, ow + 32-3), fs)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.lv_synh:.4f}" if chart.lv_synh else '',
        ]

        drawer = Drawer(img, ms=ms)
        drawer.rounded_rect(ow + 64, ow + 9, 42, 25, fill=bcm(get_difficulty_style(chart.difficulty).bg, HALF_TRANSPARENT), radius=1.5)
        drawer.infos(ow + 65.5, ow + 21.65, lines=(info_line5 + [''] * 5)[:5],
                     font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3.2)))

        return img

    @classmethod
    def box_lite(cls, chart: MaiChart, is_cabinet_dx: bool, server: Server, plus_level: int = 6, is_utage: bool = False,
                 ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """组件：谱面信息框 Lite"""
        w, h, ow = 108, 25, 1  # w, h, outline_width

        img = cls._chart_box_base(difficulty=chart.difficulty, is_cabinet_dx=is_cabinet_dx, w=w, h=h, ow=ow, ms=ms, ui_code=ui_code).copy()
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        level_img = LevelBadge.level(chart.lv, chart.difficulty, plus, 'question_mask' if is_utage else 'display',
                                     ms=ms, ui_code=ui_code)
        img.paste(level_img, ms.xy(ow + 64, ow + 7.4), level_img)
        # 达成率
        ach = chart.get_ach(server=server)
        ach_img = AchievementBadge.achievement(round(ach.achievement*10000), chart.difficulty, buddy=False, ms=ms, ui_code=ui_code)
        img.paste(ach_img, ms.xy(ow + 46, ow + 9), ach_img)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        dxscore_img = DXScoreBadge.dxscore_badge(dxs, dxs_max, lite=True, ms=ms, ui_code=ui_code)
        img.paste(dxscore_img, ms.xy(ow + 2, ow + 20), dxscore_img)
        # 评价图标
        fc = EvaluateBadge.combo(ach.combo, mini=False, ms=ms, ui_code=ui_code)
        fs = EvaluateBadge.sync(ach.sync, mini=False, ms=ms, ui_code=ui_code)
        img.paste(fc, ms.xy(ow + 2.5, ow + 12 - 3), fc)
        img.paste(fs, ms.xy(ow + 2.5, ow + 17 - 3), fs)
        return img

    @classmethod
    def chart_box(cls, chart: MaiChart, is_cabinet_dx: bool, server: Server, plus_level: int = 6, is_utage: bool = False,
                  ms: MS = MS(), ui_code: UICode = UICode.JP, lite: bool = False) -> Image.Image:
        """组件：谱面信息框"""
        if lite:
            return cls.box_lite(chart=chart, is_cabinet_dx=is_cabinet_dx, server=server, plus_level=plus_level,
                                is_utage=is_utage, ms=ms, ui_code=ui_code)
        else:
            return cls.box(chart=chart, is_cabinet_dx=is_cabinet_dx, server=server, plus_level=plus_level,
                        is_utage=is_utage, ms=ms, ui_code=ui_code)


class ChartBoxBadgeV2:

    _width = 127
    _height = 28
    _ow = 1

    @classmethod
    def size(cls) -> tuple[int, int]:
        width = cls._width + cls._ow * 2
        height = cls._height + cls._ow * 2
        return width, height

    @classmethod
    def _base(cls, difficulty: _DIFFICULTY_TYPE, cabinet: Literal['SD', 'DX'],
              *, is_cn: bool, is_cn_all: bool = False, ms: MS = MS()) -> Image.Image:
        is_cn = is_cn or is_cn_all

        width, height = cls.size()
        ow = cls._ow
        style = get_difficulty_style(difficulty, is_cn_all=is_cn_all)

        img = Image.new('RGBA', ms.xy(width, height), style.bg)
        drawer = Drawer(img, ms=ms)

        drawer.rounded_rect(0, ow+2, width, 5, fill=style.title_bg, radius=0, outline=None, width=0)
        
        difficulty_img = DifficultyBadge.difficulty(difficulty=difficulty, ms=ms, is_cn_all=is_cn_all)
        diff_height_px = difficulty_img.size[1]
        img.paste(difficulty_img, (ms.x(ow+2), (ms.x(ow+4.4) - diff_height_px // 2)), difficulty_img)
        
        cabinet_img = CabinetBadge.cabinet_badge(cabinet=cabinet, ms=ms, is_cn=is_cn)
        img.paste(cabinet_img, ms.xy(ow+84.5, ow+1.5), cabinet_img)
        
        return img
        
    @classmethod
    def _box(cls, chart: MaiChart, cabinet: Literal['SD', 'DX'], server: Server, plus: bool,
             utage: Optional[Literal['utage', 'buddy']] = None, floor_rating: Optional[int] = None,
             *, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        ow = cls._ow
        difficulty_style = get_difficulty_style(chart.difficulty, ui_code.is_cn_all)
        ach_server = server
        if server == Server.CN and chart.lv_cn is not None:
            level = chart.lv_cn
        else:
            ach_server = Server.JP
            level = chart.lv
        level_img = LevelBadge.level(
            level, chart.difficulty, plus, 'question_mask' if utage else 'display', ms=ms, ui_code=ui_code
        )
        
        img = cls._base(difficulty=chart.difficulty, cabinet=cabinet,
                        is_cn=ach_server == Server.CN, is_cn_all=ui_code.is_cn_all, ms=ms).copy()
        drawer = Drawer(img, ms=ms)

        # 等级定数
        img.paste(level_img, (ms.x(ow+106), round(ms.x(ow+4.5) - level_img.size[1] / 2)), level_img)
        # 达成率
        ach = chart.get_ach(server=ach_server)
        ach_value = round(ach.achievement * 10000)
        ach_img = AchievementBadge.achievement(ach_value, chart.difficulty, buddy=utage == 'buddy', ms=ms, ui_code=ui_code)
        img.alpha_composite(ach_img, ms.xy(ow+2, ow+9))
        # DX分数
        dxs_img = DXScoreBadge.dxscore_badge(*ach.dxscore_tuple[:2], lite=True, ms=ms, ui_code=ui_code)
        img.alpha_composite(dxs_img, ms.xy(ow+63, ow+20))
        # 连击
        combo_img = EvaluateBadge.combo(ach.combo, mini=False, ms=ms, ui_code=ui_code)
        combo_height_px = combo_img.size[1]
        img.paste(combo_img, ms.xy(ow+63, ow+9), combo_img)
        # 同步
        sync_img = EvaluateBadge.sync(ach.sync, mini=False, ms=ms, ui_code=ui_code)
        sync_height_px = sync_img.size[1]
        sync_y_px = round((ms.x(20-9)-combo_height_px-sync_height_px)/2+ms.x(9)+combo_height_px+ms.x(ow))
        img.paste(sync_img, (ms.x(ow+63), sync_y_px), sync_img)
        # 谱师
        designer_text = chart.des or "--"
        content = get_note_designer_text(is_cn_all=ui_code.is_cn_all) + designer_text
        drawer.text(3, 26, content, tds=TextDrawStyle(
            fill=difficulty_style.level_text, anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2.4))
        ))
        # 拟合定数 / 可获得的 DXRating
        for i in range(5):
            y = 9+(11/3)*i
            if i == 0:
                # 位置1 拟合定数
                capsule_fill = difficulty_style.title_bg
                fill = difficulty_style.text

                if chart.lv_synh is None:
                    # 没有拟合数据
                    if chart.lv_cn is None:
                        # 国服没上线，无法统计，不显示拟合定数
                        continue
                    else:
                        content = "     Unknown"
                else:
                    delta_level_number = chart.lv_synh - level
                    if delta_level_number > 0:
                        delta_level = f"↑{round(delta_level_number, 1):.1f}"
                    elif delta_level_number < 0:
                        delta_level = f"↓{round(-delta_level_number, 1):.1f}"
                    else:
                        delta_level = " "*4
                    content = f"     {round(chart.lv_synh, 1)} {delta_level}"

            else:
                # 位置2~5 DXRating分数显示
                capsule_fill = HALF_TRANSPARENT
                fill = BLACK

                # TODO 推分建议
                content = 'SSS+  310  ↑18'
                
            capsule_img = Image.new('RGBA', ms.xy(20, 3), TRANSPARENT)
            Drawer(capsule_img, ms=ms).capsule(0, 0, 20, 3, fill=capsule_fill)
            img.alpha_composite(capsule_img, ms.xy(ow+106, ow+y))
            capsule_img.close()
            drawer.text(ow+116, ow+y+1.5, content.replace('0', 'O'), tds=TextDrawStyle(
                fill=fill, anchor='mm', font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(2.1))
            ))
            if i == 0:
                drawer.text(ow+107, ow+y+1.5, "拟合:", tds=TextDrawStyle(
                    fill=fill, anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2.1))
                ))

        # 切圆角
        weight, height = cls.size()
        final_img = rounded_image(img, size=ms.xy(weight, height), outline_width=ms.x(ow), radius=ms.x(4))
        img.close()
        Drawer(final_img, ms=ms).rounded_rect(ow, ow, weight-ow, height-ow, radius=4, fill=None,
                                              outline=difficulty_style.frame, width=1)

        return final_img
