"""
image_gen.components.chart_box
谱面及成绩盒子组件
"""
from typing import Literal, Optional, cast
from PIL import Image
from functools import lru_cache

from ...utils import MaiChart
from ...utils.enums import UICode, Server
from ...utils.map import DifficultyID, AchievementMap
from ...utils.type import Achievement
from ..utils import MS, FontCode, FontManager
from ..color import TRANSPARENT, HALF_TRANSPARENT, BLACK, WHITE
from ..style import get_difficulty_style, _DIFFICULTY_TYPE, DifficultyStyle, get_note_designer_text
from ..tools import bcm, rounded_image
from .base import TextDrawStyle, Drawer
from . import (
    DifficultyBadge, LevelBadge, CabinetBadge, EvaluateBadge, AchievementBadge, DXScoreBadge,
)


class ChartBoxBadgeV2:

    width = 118
    height = 28
    ow = 1

    @classmethod
    def size(cls) -> tuple[int, int]:
        width = cls.width + cls.ow * 2
        height = cls.height + cls.ow * 2
        return width, height

    @classmethod
    def _base(cls, difficulty: _DIFFICULTY_TYPE, cabinet: Literal['SD', 'DX'],
              *, is_cn: bool, is_cn_all: bool = False, ms: MS = MS()) -> Image.Image:
        is_cn = is_cn or is_cn_all

        width, height = cls.size()
        ow = cls.ow
        style = get_difficulty_style(difficulty, is_cn_all=is_cn_all)

        img = Image.new('RGBA', ms.xy(width, height), style.bg)
        drawer = Drawer(img, ms=ms)

        drawer.rounded_rect(0, ow+2, width, 5, fill=style.title_bg, radius=0, outline=None, width=0)
        
        difficulty_img = DifficultyBadge.difficulty(difficulty=difficulty, ms=ms, is_cn_all=is_cn_all)
        diff_height_px = difficulty_img.size[1]
        img.paste(difficulty_img, (ms.x(ow+2), (ms.x(ow+4.4) - diff_height_px // 2)), difficulty_img)
        
        cabinet_img = CabinetBadge.cabinet_badge(cabinet=cabinet, ms=ms, is_cn=is_cn)
        img.paste(cabinet_img, ms.xy(ow+96.5, ow+1.5), cabinet_img)
        
        return img

    @classmethod
    def _capsule(cls, chart: MaiChart, level: float, floor_rating: Optional[int], difficulty_style: DifficultyStyle,
                 server: Server = Server.JP, ms: MS = MS()):
        w, h = 20, 3
        margin = 2/3
        count = 5
        style = difficulty_style
        img = Image.new('RGBA', ms.xy(w, (h+margin)*count), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        i = 0
        
        # 位置1 拟合定数
        if chart.lv_synh is None:
            if chart.lv_cn is None:
                # 没有拟合数据，且国服没上线，无法统计，不显示拟合定数
                content = ''
            else:
                # 没有拟合数据，但国服上线了，显示 Unknown 表示拟合数据异常
                content = "Unknown"
        else:
            # 存在拟合数据，显示拟合数据
            delta_lv = chart.lv_synh - level
            if abs(delta_lv) < 0.1:
                delta_level = "≈"
            else:
                delta_level = "↑" if delta_lv > 0 else "↓"
            content = f"{round(chart.lv_synh, 4):<8} {delta_level}"

        content = content.rjust(14)
        if content.strip():
            # 非空文本，进行绘制
            drawer.capsule(0, 0, w, h, fill=style.title_bg)
            drawer.text(w/2, h/2, content, tds=TextDrawStyle(
                fill=style.text, anchor='mm', font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(2.1))
            ))
            drawer.text(w/24, h/2, "拟合:", tds=TextDrawStyle(
                fill=difficulty_style.text, anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2))
            ))
            i += 1

        window_size = 5 - i
        if window_size <= 0:
            return img
        
        # 位置2~5 DXRating分数显示
        _r: list[str] = ['SSS+', 'SSS', 'SS+', 'SS', 'S+', 'S']

        _r_a_map: dict[str, Achievement] = {}
        missing: list[str] = []

        for r in _r:
            achievement = AchievementMap.find_achievement(r)
            if achievement is None:
                missing.append(r)
            else:
                _r_a_map[r] = achievement

        if missing:
            raise ValueError(f"找不到 achievement: {', '.join(missing)}")

        _maps: dict[str, tuple[Achievement, str]] = {}

        for r, achievement in _r_a_map.items():
            ra = chart.get_dxrating(server, ap_bonus=0, achievement=achievement)
            ra_delta = ""

            if isinstance(floor_rating, int):
                _ra_delta = ra - floor_rating
                if _ra_delta > 0:
                    ra_delta = f"+{_ra_delta}"

            _maps[r] = (ra, ra_delta)

        items = list(_maps.items())
        maps: dict[str, tuple[Achievement, str]] = {}

        if window_size >= len(items):
            maps = dict(items)
        else:
            for j in range(len(items) - window_size + 1):
                maps = dict(items[j: j + window_size])
                last_key = _r[j + window_size - 1]
                _, last_delta = _maps[last_key]
                if not last_delta:
                    # 当前窗口的最后一档没有分数变化了，结束
                    break

        tds = TextDrawStyle(fill=BLACK, anchor='mm', font=FontManager.font(FontCode.JBMono_Medium, size=ms.x(2.1)))
        for r, (ra, ra_delta) in maps.items():
            content = f"{r:<4} {ra:>4} {ra_delta:>4}"
            y = h*i + margin*i
            drawer.capsule(0, y, w, h, fill=HALF_TRANSPARENT)
            drawer.text(w/2, y+h/2, content.replace('0', 'O'), tds=tds)
            i += 1
        
        return img

    @classmethod
    def _box(cls, chart: MaiChart, cabinet: Literal['SD', 'DX'], server: Server, plus: bool,
             utage: Optional[Literal['utage', 'buddy']] = None, floor_rating: Optional[int] = None,
             *, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        ow = cls.ow
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
        img.paste(level_img, (round(ms.x(ow+96) - level_img.size[0]), round(ms.x(ow+4.5) - level_img.size[1] / 2)), level_img)
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
        drawer.text(3.1, 26.5, content, tds=TextDrawStyle(
            fill=difficulty_style.level_text, anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(2.4)),
            shadow=difficulty_style.title_bg, shadow_width=0.2,
        ))
        # 拟合定数 / 可获得的 DXRating
        capsule_img = cls._capsule(chart, level, floor_rating, difficulty_style, server=ach_server, ms=ms)
        img.alpha_composite(capsule_img, ms.xy(ow+97, ow+9))
        capsule_img.close()

        # 切圆角
        weight, height = cls.size()
        final_img = rounded_image(img, size=ms.xy(weight, height), outline_width=ms.x(ow), radius=ms.x(4))
        img.close()
        Drawer(final_img, ms=ms).rounded_rect(ow, ow, weight-ow, height-ow, radius=4, fill=None,
                                              outline=difficulty_style.frame, width=1)

        return final_img

    @classmethod
    def box(cls, chart: MaiChart, cabinet: Literal['SD', 'DX'], server: Server, plus: bool,
            utage: Optional[Literal['utage', 'buddy']] = None, floor_rating: Optional[int] = None,
            *, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        return cls._box(chart=chart, cabinet=cabinet, server=server, plus=plus,
                        utage=utage, floor_rating=floor_rating,
                        ms=ms, ui_code=ui_code)
