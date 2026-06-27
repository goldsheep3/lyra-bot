"""
Maimai Bot 图片生成模块 - image_gen
负责生成所有与 Maimai 谱面相关的图片内容

主要导出的 API:
  - draw_info_box: 生成曲目详细信息图
  - draw_b50: 生成 B50 成绩排行图
  - simple_list: 生成简单文本列表图
"""

import io
import zipfile
from pathlib import Path
from typing import Optional, Tuple, Literal, List
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .resources import FontCode
from ..utils import MaiData, MaiChart, MaiUser, parse_dxrating_filename
from ..constants import *

# 导入各个子模块的组件
from .config import MODEL_VERSION
from .models import (
    Diff, Difficulty, 
    AchColor, Achievement, 
    EvaluateColor, EvalInfo, Combo, Sync,
    COLOR_DXSCORE_GN, COLOR_DXSCORE_OR, COLOR_DXSCORE_GD,
    COLOR_THEME, NO_COLOR,
    COLOR_UTAGE_TAG_BG, COLOR_UTAGE_TAG_FRAME,
    COLOR_BUDDY_TAG_BG, COLOR_BUDDY_TAG_FRAME,
)
from .utils import (
    MS, bcm, get_full_width_text, limit_text,
    get_image_from_path_or_weburl, get_range_index_left_closed,
    CHAR_FULL_WIDTH_TABLE,
    BOUNDARIES_DX_RATING, BOUNDARIES_DX_RATING_NEW,
    _MS_DEFAULT
)
from .resources import FontManager, AssetsManager
from .components import TextStyle, BaseDrawer, LevelBadge, DifficultyBadge, DrawBadge
from .components import AchievementComponent, DXScoreComponent, EvaluateComponent

# ========================================
# 全局资源实例化
# ========================================

# 字体管理器实例化
FONT = FontManager(ASSETS_PATH / "fonts")

# 资源管理器实例化
ASSETS = AssetsManager(ASSETS_PATH)


def get_genre(genre_id: int, cn_level: Literal[0, 1, 2]) -> Tuple[str, str]:
    """获取流派信息"""
    genre_info = GENRES_DATA.get(genre_id, {})
    target = {0: 'jp', 1: 'intl', 2: 'cn'}
    genre = genre_info.get(target.get(cn_level, 'jp'), 'N/A').replace('\\n', '\n')
    color = genre_info.get('color', COLOR_THEME)
    return genre, color


# ========================================
# 绘图适配器（简化的 DrawUnit）
# ========================================

class DrawUnit:
    """绘图适配器 - 保留 API 兼容性，内部使用新的组件"""
    
    def __init__(self, img: Image.Image, multiple: MS | int = 8, cn_level: Literal[0, 1, 2] = 0):
        self.img = img
        self.draw = ImageDraw.Draw(img)
        self.ms = multiple if isinstance(multiple, MS) else MS(multiple)
        self.cn_level: Literal[0, 1, 2] = cn_level  # 明确标注类型
        self._drawer = BaseDrawer(img, self.draw, self.ms)

    def _text(self, x: float, y: float, text: Optional[str], fill: Optional[str], anchor: str,
              font: ImageFont.FreeTypeFont, stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """基础文本绘制"""
        style = TextStyle(fill=fill, anchor=anchor, font=font, 
                         stroke_width=stroke_width, stroke_fill=stroke_fill)
        self._drawer.text(x, y, text or '', style)

    def text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str,
             font: ImageFont.FreeTypeFont, margin: int = 1, limit: int = -1,
             stroke: Tuple[float, str] = (0, ''), shadow: Tuple[float, str] = (0, ''),
             shadow2: Tuple[float, str, float] = (0, '', 0)):
        """高级文本绘制（带阴影、描边）"""
        style = TextStyle(
            fill=fill, anchor=anchor, font=font, limit=limit, margin=margin,
            stroke_width=stroke[0], stroke_fill=stroke[1],
            shadow_width=shadow[0], shadow_color=shadow[1],
            shadow2_width=shadow2[0], shadow2_color=shadow2[1], shadow2_offset=shadow2[2]
        )
        self._drawer.text(x, y, text, style)

    def double_text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str,
                   font: ImageFont.FreeTypeFont, margin: int = 1, limit: int = -1,
                   stroke: Tuple[float, str] = (0, ''), shadow: Tuple[float, str] = (0, ''),
                   shadow2: Tuple[float, str, float] = (0, '', 0)):
        """多行文本绘制"""
        style = TextStyle(
            fill=fill, anchor=anchor, font=font, limit=limit, margin=margin,
            stroke_width=stroke[0], stroke_fill=stroke[1],
            shadow_width=shadow[0], shadow_color=shadow[1],
            shadow2_width=shadow2[0], shadow2_color=shadow2[1], shadow2_offset=shadow2[2]
        )
        self._drawer.double_text(x, y, text, style)

    def rounded_rect(self, x: float, y: float, w: float, h: float, fill: Optional[str],
                    radius: float, outline: Optional[str] = None, width: float = 0):
        """绘制圆角矩形"""
        self._drawer.rounded_rect(x, y, w, h, fill, radius, outline, width)

    def cut_line(self, x: float, y: float, w: float, h: float, radius: float,
                line_y: float, line_h: float, fill: str):
        """绘制切割线条"""
        self._drawer.cut_line(x, y, w, h, radius, line_y, line_h, fill)

    def level(self, x: float, y: float, diff: Diff, level: float, plus: bool = False,
             ignore_decimal: bool = False):
        """绘制等级标签"""
        badge = LevelBadge(level, diff, plus, ignore_decimal, self.cn_level)
        badge.render(self.draw, FONT, self.ms, x, y)

    def ach_frame(self, x: float, y: float, diff: Diff):
        """绘制达成率框架"""
        component = AchievementComponent(0, diff, ms=self.ms, cn_level=self.cn_level,
                                        font_manager=FONT)
        component.render_frame(self.draw, x, y)

    def ach_value(self, x: float, y: float, ach_percent: float, color: Optional[AchColor] = None):
        """绘制达成率数值"""
        component = AchievementComponent(ach_percent, Difficulty.NONE.value, color,
                                        ms=self.ms, cn_level=self.cn_level, font_manager=FONT)
        component.render_value(self.draw, x, y)

    def ach(self, x: float, y: float, diff: Diff, ach_percent: float, color: Optional[AchColor] = None):
        """绘制达成率（完整）"""
        component = AchievementComponent(ach_percent, diff, color,
                                        ms=self.ms, cn_level=self.cn_level, font_manager=FONT)
        component.render_frame(self.draw, x, y)
        component.render_value(self.draw, x + 2.8, y + 1.5)

    @staticmethod
    def _dxscore(cn_level: Literal[0, 1, 2], score: int, max_score: int, star_count: int) -> Tuple[str, str, str, str]:
        """计算 DX 分数信息"""
        title = {0: " でらっくスコア", 1: " DXSCORE", 2: " DX分数"}[cn_level]
        text = f"{score} / {max_score}"
        if star_count == 5:
            color = COLOR_DXSCORE_GD
        elif star_count >= 3:
            color = COLOR_DXSCORE_OR
        else:
            color = COLOR_DXSCORE_GN
        star_text = "✦ " * star_count if 0 <= star_count <= 5 else ""
        return title, text, star_text.strip(), color

    def dxscore(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Diff):
        """绘制 DX 分数"""
        component = DXScoreComponent(score, max_score, star_count, diff,
                                    lite=False, ms=self.ms, cn_level=self.cn_level, font_manager=FONT)
        component.render(self.draw, x, y)

    def dxscore_lite(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Diff):
        """绘制简化版 DX 分数"""
        component = DXScoreComponent(score, max_score, star_count, diff,
                                    lite=True, ms=self.ms, cn_level=self.cn_level, font_manager=FONT)
        component.render(self.draw, x, y)

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont,
             fill: str = '#FFF', line_height: float = 3.4, limit_width: float = -1):
        """绘制信息列表"""
        self._drawer.infos(x, y, lines, font, fill, line_height, limit_width)


class ImageUnit:

    # 获取圆角 L 遮罩
    @lru_cache(maxsize=8)
    def get_mask(self, w: int, h: int, radius: float,
                 ms: MS = _MS_DEFAULT) -> Image.Image:
        # 画布大小应包含完整的 w 和 h
        mask = Image.new('L', ms.xy(w, h), 0)
        draw = ImageDraw.Draw(mask)
        # 直接绘制充满画布的圆角矩形，坐标为 (0, 0, w, h)
        draw.rounded_rectangle(ms.size(0, 0, w, h), radius=ms.x(radius), fill=255)
        return mask

    # 难度式文本样式
    def diff_text(self, diff: Diff, text: Optional[str] = None, limit_width: float = -1, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0):
        # 处理文字长度并计算位置
        font = FONT.font(FontCode.MiSans_Heavy, size=ms.x(4.8))
        if text:
            # 自定义文本，需处理宽度顺序
            text = limit_text(text, font, limit_width) if limit_width > 0 else text
            display_text = text
        else:
            display_text = diff.text_title

        x1, y1, x2, y2 = font.getbbox(display_text, anchor='lm', stroke_width=ms.x(0.8))
        if cn_level == 2 and not text:
            # 特殊处理中文默认难度标题的位置
            cn_font = FONT.font(FontCode.MiSans_Heavy, size=ms.x(3.3))
            cn_x1, _cn_y1, cn_x2, _cn_y2 = cn_font.getbbox(diff.text_title_cn, anchor='lm', stroke_width=ms.x(0.8))
            cn_width = ms.rev(cn_x2 - cn_x1)
        else:
            cn_width = 0
        width = (ms.rev(x2 - x1) + cn_width) * 1.2
        height = ms.rev(y2 - y1) * 1.2

        # 实际渲染逻辑
        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.text(1, height / 2, display_text, diff.text, 'lm', font, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))
        if cn_width:
            du.text(ms.rev(x2 - x1) * 1.1, ms.rev(y2 - y1) * 1.1, diff.text_title_cn, diff.text, 'ld', FONT.font(FontCode.MiSans_Heavy, size=ms.x(3.3)),
                    shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))

        return img

    # 难度文本
    @lru_cache(maxsize=10)
    def difficulty(self, diff: Diff, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return self.diff_text(diff=diff, text=None, limit_width=-1, ms=ms, cn_level=cn_level)

    # FC / FS 评定文本
    @lru_cache(maxsize=18)
    def evaluate(self, eval: EvalInfo | None, mini: bool = False, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        size = ms.xy(20, 5) if mini else ms.xy(40, 5)
        img = Image.new('RGBA', size, "#FFFFFF00")
        if eval:
            du = DrawUnit(img, multiple=ms, cn_level=cn_level)
            text = eval.short_name if mini else (eval.cn_name if cn_level == 2 else eval.full_name)
            du.text(1, 2.5, text, eval.color.fill, 'lm', FONT.font(FontCode.MiSans_Heavy, size=ms.x(3)),
                stroke=(0.5, eval.color.shadow), shadow=(0.65, eval.color.shadow))
        return img

    # 谱面类型标记（标准）
    def draw_sd_badge(self, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_SD = '#4AF'
        du.rounded_rect(0, 0, 20, 5, fill=COLOR_SD, radius=5)
        offset = 0.6 if cn_level else 0
        font = FONT.font(FontCode.MiSans_Heavy, size=ms.x(3 + offset))
        text = "标 准" if cn_level else "スタンダード"
        du.text(10, 2.5, text, '#FFF', 'mm', font)
        return img

    # 谱面类型标记（DX）
    def draw_dx_badge(self, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_DX = ('#FF7711', '#FFFFFF')
        COLOR_DELUXE = ('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6', '#2299EE')

        du.rounded_rect(0, 0, 20, 5, fill='#FFF', radius=5, outline=COLOR_DX[1] if cn_level else COLOR_DELUXE[-1], width=0.5)
        if cn_level:
            text = "DX"
            du.text(10, 2.5, text, COLOR_DX[0], 'mm', FONT.font(FontCode.MiSans_Heavy, size=ms.x(4.1)))
        else:
            font = FONT.font(FontCode.MiSans_Heavy, size=ms.x(3.2))
            text = "でらっくす"
            total_text_width = ms.rev(font.getlength(text))
            start_x = (10) - (total_text_width / 2)
            current_x = start_x
            center_y = 2.5
            for char, color in zip(text, COLOR_DELUXE):
                du.text(current_x, center_y, char, color, 'lm', font)
                char_width = ms.rev(font.getlength(char))
                current_x += char_width
        return img

    # 谱面类型标记
    @lru_cache(maxsize=4)
    def draw_badge(self, is_cabinet_dx: bool, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return self.draw_dx_badge(ms=ms, cn_level=cn_level) if is_cabinet_dx else self.draw_sd_badge(ms=ms, cn_level=cn_level)

    # 版权信息栏
    @lru_cache(maxsize=4)
    def copyright_bar(self, width: int, lines: tuple[str, ...] | None = None,
                      ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        if lines is None:
            lines = (
                "Powered by LyraBot (@GoldSheep3)",
                "Version:" + MODEL_VERSION,
                "Designer by Bakamai⑨'s Members",
                "Background Artist by @银色山雾"
            )
        
        cr_info = "    |    ".join(lines)
        
        # 基准测量
        base_size = 5.0
        test_font = FONT.font(FontCode.MiSans_Demibold, size=ms.x(base_size))
        tx1, ty1, tx2, ty2 = test_font.getbbox(cr_info)
        raw_width = tx2 - tx1
        raw_height = ty2 - ty1

        target_content_width = width * 0.9  # 预留两侧各 5% 的空白边距
        # 缩放系数 = 目标宽度 / 原始宽度
        ratio = min(target_content_width / (raw_width / ms.multiple), 1.0)
        final_size = max(base_size * ratio, 1.2)
        
        font = FONT.font(FontCode.MiSans_Demibold, size=ms.x(final_size))
        # 预留上下各 25% 的空间，防止文字过于贴边
        bar_height = round(max((raw_height * ratio) * 1.5, ms.x(6)))

        # 实际渲染
        img = Image.new('RGBA', (ms.x(width), bar_height), '#313d7c')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.text(
            width // 2, 
            ms.rev(bar_height) // 2, 
            text=cr_info, 
            fill=COLOR_THEME, 
            anchor='mm',
            font=font
        )

        return img

    # -- 大型组件 --
    # 谱面信息框
    def chart_box(self, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6, is_utage: bool = False,
                  ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框"""
        w, h, ow = 108, 36, 1  # w, h, outline_width
        diff = Difficulty.get(chart.difficulty)

        img = IMU.chart_box_base(diff=diff, cabinet_dx=cabinet_dx, w=w, h=h, ow=ow, ms=ms, cn_level=cn_level).copy()
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(ow + 64, ow + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(ow + 2, ow + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore(ow + 38, ow + 25, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = IMU.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 27-3), fc)
        fs = IMU.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 32-3), fs)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.lv_synh:.4f}" if chart.lv_synh else '',
        ]

        du.rounded_rect(ow + 64, ow + 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
        du.infos(ow + 65.5, ow + 21.65, lines=(info_line5 + [''] * 5)[:5], line_height=4.5, limit_width=-1,
                 font=FONT.font(FontCode.MiSans_Demibold, size=ms.x(3.2)))

        return img

    def chart_box_lite(self, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6, is_utage: bool = False,
                       ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框 Lite"""
        w, h, ow = 108, 25, 1  # w, h, outline_width
        diff = Difficulty.get(chart.difficulty)

        img = IMU.chart_box_base(diff=diff, cabinet_dx=cabinet_dx, w=w, h=h, ow=ow, ms=ms, cn_level=cn_level).copy()
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(ow + 64, ow + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(ow + 46, ow + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(ow + 2, ow + 20, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = IMU.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 12 - 3), fc)
        fs = IMU.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 17 - 3), fs)
        return img

    @lru_cache(maxsize=32)
    def chart_box_base(self, diff: Diff, cabinet_dx: bool, w: int, h: int, ow: int,
                       ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(w + ow * 2, h + ow * 2), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, radius=4, fill=diff.bg)
        du.cut_line(ow, ow, w, h, radius=4, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, radius=4, fill=None, outline=diff.frame, width=1)
        difficulty = IMU.difficulty(diff=diff, ms=ms, cn_level=cn_level)
        diff_height = ms.rev(difficulty.size[1])
        img.paste(difficulty, ms.xy(ow + 2.5, ow + 4.3 - diff_height / 2), difficulty)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 85, ow + 2), badge)
        return img

    def mini_box(self, data: MaiData | None, diff_number: int, server: SERVER_TAG,
                 ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0,
                 shared_zip: zipfile.ZipFile | None = None) -> Image.Image | tuple[int, int]:
        w, h, ow = 97, 36, 1  # w, h, outline_width
        width, height = w + ow * 2, h + ow * 2
        diff = Difficulty.get(diff_number)

        chart = data.get_chart(diff_number) if data else None
        if not chart or data is None:
            return width, height  # 视为占位，返回尺寸供布局使用
        ach = chart.get_ach(server=server)

        img = IMU.mini_box_base(
            diff=diff,
            is_cabinet_dx=data.is_cabinet_dx,
            shortid=data.shortid,
            w=w,
            h=h,
            ow=ow,
            ms=ms,
            cn_level=cn_level,
        ).copy()
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        # 曲绘
        cover = data.get_image(shared_zip=shared_zip)
        if cover:
            mask = IMU.get_mask(w=32, h=32, radius=1.5, ms=ms)
            cover_img = cover.resize(ms.xy(32, 32), Image.Resampling.LANCZOS)
            img.paste(cover_img, ms.xy(ow + 2, ow + 2), mask)
        # 达成率
        du.ach(ow + 35, ow + 9, diff, ach_percent=ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(ow + 53, ow + 31, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = IMU.evaluate(Combo.get(ach.combo), mini=True, ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 36, ow + 24), fc)
        fs = IMU.evaluate(Sync.get(ach.sync), mini=True, ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 36, ow + 29), fs)
        # INFO: 留空 (x=53, y=25, w=42, h=5) 可供自定义
        return img

    @lru_cache(maxsize=12)
    def mini_box_base(self, diff: Diff, is_cabinet_dx: bool, shortid: int, w: int, h: int, ow: int,
                      ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(w + ow * 2, h + ow * 2), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, diff.bg, radius=2.5, outline=diff.frame)
        du.cut_line(ow, ow, w, h, radius=0, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, None, radius=2.5, outline=diff.title_bg, width=1)
        badge = IMU.draw_badge(is_cabinet_dx=is_cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 75, ow + 2), badge)
        shortid_img = IMU.diff_text(diff=diff, text=f'#{shortid}', ms=ms, cn_level=cn_level)
        img.paste(shortid_img, ms.xy(ow + 35, ow + 4.2 - ms.rev(shortid_img.size[1] / 2)), shortid_img)
        return img

    def b50_box(self, data: MaiData, diff_number: int, server: SERVER_TAG,
                current_version: int, index: int, is_b15: Optional[bool] = None,
                ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0,
                shared_zip: zipfile.ZipFile | None = None) -> Image.Image | None:
        chart = data.get_chart(diff_number)
        if not chart:
            return None
        img = self.mini_box(data=data, diff_number=diff_number, server=server, ms=ms, cn_level=cn_level, shared_zip=shared_zip)
        if isinstance(img, tuple):
            return None
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        # x=53 + 1 (获取到的图片坐标需要考虑 outline_width)
        du.rounded_rect(54, 25, 42, 5, fill=bcm(Difficulty.get(diff_number).bg, '#0009'), radius=4)
        du.rounded_rect(54, 25, 16, 5, fill='#006', radius=4)
        b_type = '15' if is_b15 else '35'
        du.text(62, 27.5, f"b{b_type} #{index}", fill='#FFF', anchor='mm', font=FONT.font(FontCode.MiSans_Demibold, size=ms.x(3)))
        du.text(74, 27.5, f"{chart.lv:.1f} > {data.get_chart_dxrating(diff_number, server, current_version)}", fill='#FFF', anchor='lm', font=FONT.font(FontCode.MiSans_Demibold, size=ms.x(3)))
        return img

IMU = ImageUnit()  # 全局图像元件实例


def _image_grid_board(
    image_list: list[Image.Image],
    cols: int = 4,
    gap: int = 0,
    skip_first: bool = True,
    auto_close: bool = False
) -> Image.Image | None:
    """将图片列表排列成网格看板"""
    if not image_list:
        return None

    # 获取单张图片的尺寸
    box_w, box_h = image_list[0].size
    
    # 计算布局
    total_slots = len(image_list) + (1 if skip_first else 0)
    rows = (total_slots + cols - 1) // cols
    
    board_width = cols * box_w + (cols - 1) * gap
    board_height = rows * box_h + (rows - 1) * gap
    
    board = Image.new('RGBA', (round(board_width), round(board_height)), (0, 0, 0, 0))
    
    # 开始拼接
    start_offset = 1 if skip_first else 0
    for i, img in enumerate(image_list):
        # 实际在画板上的索引
        pos_idx = i + start_offset
        
        tx = (pos_idx % cols) * (box_w + gap)
        ty = (pos_idx // cols) * (box_h + gap)
        
        if img:
            board.paste(img, (round(tx), round(ty)), img)
            
            # --- 新增：自动关闭原始图片以节省内存 ---
            if auto_close:
                img.close()
            
    return board


def _user_header_board(
    inner_width: int,
    dxrating: int,
    server: SERVER_TAG,
    user_name: str,
    user_avatar: bytes | Image.Image | None = None,
    update_time: str = 'Unknown Time',
    dxra_cirp_frame: bool = True,
    ms: MS = _MS_DEFAULT,
    cn_level: Literal[0, 1, 2] = 0
) -> Image.Image | None:

    header_h = 32
    board_title = Image.new('RGBA', ms.xy(inner_width, header_h), NO_COLOR)
    du1 = DrawUnit(board_title, multiple=ms, cn_level=cn_level)
    
    # 头像处理
    avatar_size = 32
    if user_avatar and isinstance(user_avatar, bytes):
        try:
            avatar = Image.open(io.BytesIO(user_avatar)).convert("RGBA")
        except Exception:
            avatar = None
    elif isinstance(user_avatar, Image.Image):
        avatar = user_avatar
    else:
        avatar = None
    avatar = avatar or Image.new('RGB', ms.xy(avatar_size, avatar_size), color='#CCC')
    if avatar.size != ms.xy(avatar_size, avatar_size):
        avatar = avatar.resize(ms.xy(avatar_size, avatar_size), Image.Resampling.LANCZOS)
    mask = IMU.get_mask(w=avatar_size, h=avatar_size, radius=5, ms=ms)
    board_title.paste(avatar, (0, 0), mask)
    avatar.close()
    du1.rounded_rect(0, 0, avatar_size, avatar_size, radius=5, fill=None, outline='#FFF', width=1)
    
    # DX Rating 框与数字
    dx_ra_x, dx_ra_y = 36, 0
    dxra_frame_filename = parse_dxrating_filename(dxrating, cirp_frame=dxra_cirp_frame)
    if dxra_frame := ASSETS.dxrating_image(dxra_frame_filename, size=ms.xy(70, 14)):
        board_title.paste(dxra_frame, ms.xy(dx_ra_x, dx_ra_y), dxra_frame)
    
    ra_font = FONT.font(FontCode.MiSans_Demibold, size=ms.x(8))
    for i, digit in enumerate(str(dxrating)[::-1]):
        dx = 57.5 - 5.5 * i
        du1.text(dx_ra_x + dx, dx_ra_y + 7.1, text=digit, fill='#FCC916', anchor='mm', 
                 font=ra_font, stroke=(0.35, '#333'))
                 
    # 用户名条
    du1.rounded_rect(36, 15, 100, 17, fill='#333', radius=2)
    du1.text(36, 23.5, text=' ' + get_full_width_text(user_name), fill='#FFF', anchor='lm',
             font=FONT.font(FontCode.MiSans_Demibold, size=ms.x(10)))

    # 游玩记录信息
    record_info = f"Updated: [{server}] {update_time}"
    du1.text(inner_width-2, 2, text=record_info, fill='#FFF', anchor='ra', font=FONT.font(FontCode.MiSans_Demibold, size=ms.x(5)))

    return board_title


from .builder import draw_b50, draw_info_box, get_image_bytes, simple_list, simple_maidata_box

__all__ = ["draw_info_box", "draw_b50", "simple_list"]
