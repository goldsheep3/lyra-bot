"""
image_gen.components.achievement
达成率组件

> 100.4999% / ...
"""
from PIL import Image
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ...utils.type import Achievement
from ..style import _DIFFICULTY_TYPE, get_rate_style, get_rate_frame_style
from .base import TextDrawStyle, Drawer


class AchievementBadge:
    """达成率组件"""

    @classmethod
    @lru_cache(maxsize=6)
    def _achievement_badge_bg(cls, difficulty: _DIFFICULTY_TYPE, ms: MS = MS(), is_cn_all: bool = False) -> Image.Image:
        """获取达成率组件背景图像"""
        img = Image.new('RGBA', ms.xy(60, 14), "#FFFFFF00")
        drawer = Drawer(img, ms=ms)

        # 底圆角
        frame_style = get_rate_frame_style(difficulty, is_cn_all=is_cn_all)
        frame_content = f"{frame_style.content}"
        drawer.rounded_rect(0, 0, 60, 14, fill=frame_style.bg_fill, radius=1.5)
        # 左上角提示文本
        frame_font = FontManager.font(FontCode.MiSans_Heavy, ms.x(2.5))
        drawer.text(0.5, 1.5, text=frame_content, tds=TextDrawStyle(fill=frame_style.fill, anchor='lm', font=frame_font))

        return img

    @classmethod
    def _achievement_badge(cls, achievement: Achievement | None, difficulty: _DIFFICULTY_TYPE | None = None,
                           buddy: bool = False, ms: MS = MS(), is_cn_all: bool = False) -> Image.Image:
        achievement = achievement if achievement is not None else 0
        style = get_rate_style(achievement, buddy=buddy)
        content = (style.content.replace('0', 'O') if achievement else "--.----%").rjust(9)

        img = cls._achievement_badge_bg(difficulty, ms=ms, is_cn_all=is_cn_all).copy()
        drawer = Drawer(img, ms=ms)

        # 达成率文本
        font = FontManager.font(FontCode.JBMono_ExtraBold, ms.x(10))
        drawer.text(30, 8, text=content, tds=TextDrawStyle(
            fill=style.fill, anchor='mm', font=font,
            stroke=style.stroke, stroke_width=0.35,
            shadow=style.shadow, shadow_width=0.4
        ))
        return img

    @classmethod
    def _achievement(cls, achievement: Achievement, difficulty: _DIFFICULTY_TYPE | None = None,
                    buddy: bool = False, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        return cls._achievement_badge(achievement, difficulty=difficulty, buddy=buddy, ms=ms, is_cn_all=ui_code.is_cn_all)

    @classmethod
    @lru_cache(maxsize=4)
    def _not_exist_achievement(cls, difficulty: _DIFFICULTY_TYPE | None = None,
                               ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        return cls._achievement_badge(None, difficulty=difficulty, buddy=False, ms=ms, is_cn_all=ui_code.is_cn_all)

    @classmethod
    def achievement(cls, achievement: Achievement | None, difficulty: _DIFFICULTY_TYPE | None = None,
                    buddy: bool = False, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """获取达成率组件图像"""
        if achievement is None:
            return cls._not_exist_achievement(difficulty=difficulty, ms=ms, ui_code=ui_code).copy()

        if achievement >= 10000000 or achievement <= -1000000:
            # 不合法的显示范围，显示为 `--.----%`
            return cls._not_exist_achievement(difficulty=difficulty, ms=ms, ui_code=ui_code).copy()

        # 合法显示，生成图片
        return cls._achievement(achievement, difficulty=difficulty, buddy=buddy, ms=ms, ui_code=ui_code).copy()
