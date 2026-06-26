"""
成绩与排行组件
- AchievementComponent: 达成率显示
- DXScoreComponent: DX分数显示
- EvaluateComponent: FC/FS/Sync 评价标签
"""

from typing import Literal, Optional, Tuple
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from ..models import Diff, AchColor, Achievement, EvalInfo
from ..utils import MS, bcm, _MS_DEFAULT
from ..resources import FontManager
from .base import TextStyle, BaseDrawer


class AchievementComponent:
    """达成率显示组件"""
    
    def __init__(self, ach_percent: float, diff: Diff, color: Optional[AchColor] = None,
                 ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0,
                 font_manager: Optional[FontManager] = None):
        self.ach_percent = ach_percent
        self.diff = diff
        self.color = color
        self.ms = ms
        self.cn_level = cn_level
        self.font_manager = font_manager

    def _render_ach_frame(self, draw: ImageDraw.ImageDraw, x: float, y: float):
        """渲染达成率框架"""
        drawer = BaseDrawer(Image.new('RGBA', (1, 1), '#FFF'), draw, self.ms)
        text = " 达成率" if self.cn_level == 2 else " ACHIEVEMENT"
        
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ..constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        drawer.rounded_rect(x, y, 60, 14, fill=bcm(self.diff.bg, '#FFF9'), radius=1.5)
        style = TextStyle(fill=self.diff.frame, anchor='la',
                         font=font_manager.font('MIS_HE', size=self.ms.x(2)))
        drawer.text(x, y, text=text, style=style)

    def render_frame(self, draw: ImageDraw.ImageDraw, x: float, y: float):
        """渲染达成率框（外部调用）"""
        self._render_ach_frame(draw, x, y)

    def render_value(self, draw: ImageDraw.ImageDraw, x: float, y: float) -> AchColor:
        """渲染达成率数值，返回使用的颜色"""
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ..constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        if -100 < self.ach_percent < 1000:
            text = f"{self.ach_percent:.4f}%".replace('0', 'O').rjust(9)
            color = self.color or Achievement.get_by_percent(self.ach_percent)
        else:
            text = " --.----%"
            color = self.color or Achievement.B.value

        drawer = BaseDrawer(Image.new('RGBA', (1, 1), '#FFF'), draw, self.ms)
        style = TextStyle(fill=color.fill, anchor='la',
                         font=font_manager.font('JBM_EB', size=self.ms.x(10)),
                         stroke_width=0.35, stroke_fill=color.stroke,
                         shadow_width=0.4, shadow_color=color.shadow)
        drawer.text(x, y, text=text, style=style)
        return color


class DXScoreComponent:
    """DX 分数显示组件"""
    
    def __init__(self, score: int, max_score: int, star_count: int, diff: Diff,
                 lite: bool = False, ms: MS = _MS_DEFAULT, 
                 cn_level: Literal[0, 1, 2] = 0,
                 font_manager: Optional[FontManager] = None):
        self.score = score
        self.max_score = max_score
        self.star_count = star_count
        self.diff = diff
        self.lite = lite
        self.ms = ms
        self.cn_level = cn_level
        self.font_manager = font_manager

    def _get_dxscore_info(self) -> Tuple[str, str, str, str]:
        """获取 DX 分数信息"""
        from ..models import COLOR_DXSCORE_GN, COLOR_DXSCORE_OR, COLOR_DXSCORE_GD
        
        title = {0: " でらっくスコア", 1: " DXSCORE", 2: " DX分数"}[self.cn_level]
        text = f"{self.score} / {self.max_score}"
        
        if self.star_count == 5:
            color = COLOR_DXSCORE_GD
        elif self.star_count >= 3:
            color = COLOR_DXSCORE_OR
        else:
            color = COLOR_DXSCORE_GN
        
        star_text = "✦ " * self.star_count if 0 <= self.star_count <= 5 else ""
        return title, text, star_text.strip(), color

    def render(self, draw: ImageDraw.ImageDraw, x: float, y: float):
        """渲染 DX 分数"""
        from ..models import COLOR_DXSCORE_GN
        
        title, text, star_text, star_color = self._get_dxscore_info()
        
        font_manager = self.font_manager
        if not font_manager:
            from ..resources import FontManager
            from ..constants import ASSETS_PATH
            font_manager = FontManager(ASSETS_PATH / "fonts")
        
        drawer = BaseDrawer(Image.new('RGBA', (1, 1), '#FFF'), draw, self.ms)
        
        if self.lite:
            drawer.rounded_rect(x, y, 42, 3, fill=bcm(self.diff.bg, '#FFF9'), radius=2)
            style_title = TextStyle(fill=COLOR_DXSCORE_GN, anchor='lm',
                                   font=font_manager.font('MIS_HE', size=self.ms.x(2)))
            drawer.text(x + 0.5, y + 1.5, text=title, style=style_title)
            
            style_text = TextStyle(fill='#333', anchor='rm',
                                  font=font_manager.font('MIS_DB', size=self.ms.x(2.5)))
            drawer.text(x + 40, y + 1.5, text=text, style=style_text)
            
            style_star = TextStyle(fill=star_color, anchor='mm',
                                  font=font_manager.font('NSS_RG', size=self.ms.x(2.2)))
            drawer.text(x + 20, y + 1.8, text=star_text, style=style_star)
        else:
            drawer.rounded_rect(x, y, 24, 9, fill=bcm(self.diff.bg, '#FFF9'), radius=1.5)
            
            style_title = TextStyle(fill=COLOR_DXSCORE_GN, anchor='la',
                                   font=font_manager.font('MIS_HE', size=self.ms.x(2)))
            drawer.text(x, y, text=title, style=style_title)
            
            style_text = TextStyle(fill='#333', anchor='mm',
                                  font=font_manager.font('MIS_DB', size=self.ms.x(3)))
            drawer.text(x + 12, y + 4.5, text=text, style=style_text)
            
            style_star = TextStyle(fill=star_color, anchor='ma',
                                  font=font_manager.font('NSS_RG', size=self.ms.x(2.2)))
            drawer.text(x + 12, y + 6, text=star_text, style=style_star)


class EvaluateComponent:
    """FC/FS/Sync 评价标签组件"""
    
    def __init__(self, eval: Optional[EvalInfo], mini: bool = False,
                 ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0,
                 font_manager: Optional[FontManager] = None):
        self.eval = eval
        self.mini = mini
        self.ms = ms
        self.cn_level = cn_level
        self.font_manager = font_manager

    @lru_cache(maxsize=18)
    def _render_evaluate(self, eval_code: int, mini: bool, ms: MS, cn_level: Literal[0, 1, 2]) -> Image.Image:
        """渲染评价标签（缓存版）"""
        from ..models import Combo, Sync
        
        size = ms.xy(20, 5) if mini else ms.xy(40, 5)
        img = Image.new('RGBA', size, "#FFFFFF00")
        
        if eval_code >= 0:
            # 根据代码获取评价信息
            if eval_code <= 4:
                eval_info = Combo.get(eval_code)
            else:
                eval_info = Sync.get(eval_code - 10)  # 假设 Sync 代码偏移 10
            
            draw = ImageDraw.Draw(img)
            drawer = BaseDrawer(img, draw, ms)
            
            font_manager = self.font_manager
            if not font_manager:
                from ..resources import FontManager
                from ..constants import ASSETS_PATH
                font_manager = FontManager(ASSETS_PATH / "fonts")
            
            text = eval_info.short_name if mini else (eval_info.cn_name if cn_level == 2 else eval_info.full_name)
            style = TextStyle(fill=eval_info.color.fill, anchor='lm',
                            font=font_manager.font('MIS_HE', ms.x(3)),
                            stroke_width=0.5, stroke_fill=eval_info.color.shadow,
                            shadow_width=0.65, shadow_color=eval_info.color.shadow)
            drawer.text(1, 2.5, text, style)
        
        return img

    def render(self) -> Image.Image:
        """渲染评价标签"""
        if not self.eval:
            size = self.ms.xy(20, 5) if self.mini else self.ms.xy(40, 5)
            return Image.new('RGBA', size, "#FFFFFF00")
        
        eval_code = self.eval.code
        return self._render_evaluate(eval_code, self.mini, self.ms, self.cn_level)
