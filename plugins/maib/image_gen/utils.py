"""image_gen/utils.py 绘图基础管理器"""

import zipfile
from pathlib import Path
from enum import StrEnum
from typing import Optional, Literal
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from ..utils import MaiData, MaiChart, get_git_head_hash
from ..constants import ASSETS_PATH, server
from .models import (
    Diff, Difficulty, 
    AchColor, EvalInfo, Combo, Sync,
    COLOR_DXSCORE_GN, COLOR_DXSCORE_OR, COLOR_DXSCORE_GD,
    COLOR_THEME,
)
from .tools import bcm, limit_text, get_dxra_frame_filename


__all__ = [
    # 缩放工具类
    "MS",
    # 字体
    "FontCode", "FontManager",
    # 图像
    "ImageManager",
    # 绘图器
    "DrawUnit", "ImageUnit",
]



# --- 坐标倍率缩放器 ---
class MS:
    """倍率缩放器"""
    # 全局缓存，按倍率分组
    # {multiple: {val_int: scaled_value, ...}, ...}
    _cache: dict[float, dict[float, int]] = {}
    
    def __init__(self, multiple: float = 5.0):
        self.multiple = round(multiple, 2)

    def x(self, mpx: float) -> int:
        """根据 mpx 值计算单个 px 值"""
        val_int = round(float(mpx), 2)
        # 获取或创建该倍率对应的子缓存字典
        sub_cache = self._cache.setdefault(self.multiple, {})
        if val_int in sub_cache:
            return sub_cache[val_int]
        scaled = round(val_int * self.multiple)
        sub_cache[val_int] = scaled
        return scaled

    def xy(self, mpx_x: float, mpx_y: float) -> tuple[int, int]:
        """计算 `x`,`y` 坐标 px 值"""
        return self.x(mpx_x), self.x(mpx_y)

    def size(self, mpx_x: float, mpx_y: float, mpx_w: float, mpx_h: float) -> tuple[int, int, int, int]:
        """计算 `x`,`y`,`x+w`,`y+h` 坐标 px 值"""
        return self.x(mpx_x), self.x(mpx_y), self.x(mpx_x + mpx_w), self.x(mpx_y + mpx_h)

    def rev(self, px: int) -> float:
        """将 px 值还原为 mpx 值"""
        return px / self.multiple

    @property
    def key(self) -> str:
        """返回可用于缓存的字符串键"""
        return f"{self.multiple:.2f}"

    def __repr__(self): 
        return f"MS(multiple={self.multiple})"

    def __mul__(self, other: float) -> 'MS':
        if not isinstance(other, (int, float)):
            return NotImplemented
        return MS(self.multiple * other)

    def __hash__(self): 
        return hash(self.multiple)

    def __int__(self): 
        raise NotImplementedError("MS Object cannot be converted to int directly.")

    def __float__(self): 
        return float(self.multiple)


class FontCode(StrEnum):
    """字体名称枚举"""
    
    # SmileySans (得意黑) 字体
    SmileySans = "SmileySans/SmileySans-Oblique.ttf"
    
    # Electrolize 字体
    # Electrolize = "Electrolize/Electrolize-Regular.ttf"
    
    # JetBrains Mono 变量字体
    # JBMono_Variable = "JetBrains_Mono/JetBrainsMono-VariableFont_wght.ttf"
    # JBMono_Italic_Variable = "JetBrains_Mono/JetBrainsMono-Italic-VariableFont_wght.ttf"
    
    # JetBrains Mono 静态字体
    # JBMono_Thin = "JetBrains_Mono/static/JetBrainsMono-Thin.ttf"
    # JBMono_ThinItalic = "JetBrains_Mono/static/JetBrainsMono-ThinItalic.ttf"
    # JBMono_ExtraLight = "JetBrains_Mono/static/JetBrainsMono-ExtraLight.ttf"
    # JBMono_ExtraLightItalic = "JetBrains_Mono/static/JetBrainsMono-ExtraLightItalic.ttf"
    # JBMono_Light = "JetBrains_Mono/static/JetBrainsMono-Light.ttf"
    # JBMono_LightItalic = "JetBrains_Mono/static/JetBrainsMono-LightItalic.ttf"
    # JBMono_Regular = "JetBrains_Mono/static/JetBrainsMono-Regular.ttf"
    # JBMono_Italic = "JetBrains_Mono/static/JetBrainsMono-Italic.ttf"
    JBMono_Medium = "JetBrains_Mono/static/JetBrainsMono-Medium.ttf"
    # JBMono_MediumItalic = "JetBrains_Mono/static/JetBrainsMono-MediumItalic.ttf"
    # JBMono_SemiBold = "JetBrains_Mono/static/JetBrainsMono-SemiBold.ttf"
    # JBMono_SemiBoldItalic = "JetBrains_Mono/static/JetBrainsMono-SemiBoldItalic.ttf"
    JBMono_Bold = "JetBrains_Mono/static/JetBrainsMono-Bold.ttf"
    # JBMono_BoldItalic = "JetBrains_Mono/static/JetBrainsMono-BoldItalic.ttf"
    JBMono_ExtraBold = "JetBrains_Mono/static/JetBrainsMono-ExtraBold.ttf"
    # JBMono_ExtraBoldItalic = "JetBrains_Mono/static/JetBrainsMono-ExtraBoldItalic.ttf"
    
    # MiSans 变量字体
    # MiSans_VF = "MiSans/MiSansVF.ttf"
    
    # MiSans 静态字体
    # MiSans_Thin = "MiSans/static/MiSans-Thin.ttf"
    # MiSans_ExtraLight = "MiSans/static/MiSans-ExtraLight.ttf"
    # MiSans_Light = "MiSans/static/MiSans-Light.ttf"
    # MiSans_Normal = "MiSans/static/MiSans-Normal.ttf"
    # MiSans_Regular = "MiSans/static/MiSans-Regular.ttf"
    # MiSans_Medium = "MiSans/static/MiSans-Medium.ttf"
    # MiSans_Semibold = "MiSans/static/MiSans-Semibold.ttf"  # 小写b
    MiSans_Demibold = "MiSans/static/MiSans-Demibold.ttf"    # 大写B
    # MiSans_Bold = "MiSans/static/MiSans-Bold.ttf"
    MiSans_Heavy = "MiSans/static/MiSans-Heavy.ttf"
    
    # Noto 字体家族
    # NotoEmoji = "Noto_Emoji/NotoEmoji-VariableFont_wght.ttf"
    NotoSansSymbols2 = "Noto_Sans_Symbols_2/NotoSansSymbols2-Regular.ttf"
    
    # NotoSansSC 变量字体
    # NotoSansSC_Variable = "Noto_Sans_SC/NotoSansSC-VariableFont_wght.ttf"
    
    # NotoSansSC 静态字体
    # NotoSansSC_Thin = "Noto_Sans_SC/static/NotoSansSC-Thin.ttf"
    # NotoSansSC_Light = "Noto_Sans_SC/static/NotoSansSC-Light.ttf"
    # NotoSansSC_ExtraLight = "Noto_Sans_SC/static/NotoSansSC-ExtraLight.ttf"
    # NotoSansSC_Regular = "Noto_Sans_SC/static/NotoSansSC-Regular.ttf"
    # NotoSansSC_Medium = "Noto_Sans_SC/static/NotoSansSC-Medium.ttf"
    # NotoSansSC_SemiBold = "Noto_Sans_SC/static/NotoSansSC-SemiBold.ttf"
    # NotoSansSC_Bold = "Noto_Sans_SC/static/NotoSansSC-Bold.ttf"
    # NotoSansSC_ExtraBold = "Noto_Sans_SC/static/NotoSansSC-ExtraBold.ttf"
    # NotoSansSC_Black = "Noto_Sans_SC/static/NotoSansSC-Black.ttf"
    
    # Oxanium 变量字体
    # Oxanium_Variable = "Oxanium/Oxanium-VariableFont_wght.ttf"
    
    # Oxanium 静态字体
    # Oxanium_ExtraLight = "Oxanium/static/Oxanium-ExtraLight.ttf"
    # Oxanium_Light = "Oxanium/static/Oxanium-Light.ttf"
    # Oxanium_Regular = "Oxanium/static/Oxanium-Regular.ttf"
    # Oxanium_Medium = "Oxanium/static/Oxanium-Medium.ttf"
    # Oxanium_SemiBold = "Oxanium/static/Oxanium-SemiBold.ttf"
    # Oxanium_Bold = "Oxanium/static/Oxanium-Bold.ttf"
    # Oxanium_ExtraBold = "Oxanium/static/Oxanium-ExtraBold.ttf"


class FontManager:
    """字体管理器 - 负责加载和缓存字体文件（类方法版）"""
    
    _font_path: Path = Path()

    @classmethod
    def init(cls, font_path: Path):
        """全局初始化字体路径"""
        cls._font_path = Path(font_path)

    @classmethod
    @lru_cache(maxsize=128)
    def _get_font(cls, font_file: Path, size: int) -> ImageFont.FreeTypeFont:
        """从文件加载字体（有缓存）"""
        if size <= 0:
            return ImageFont.truetype(str(font_file), 10000)
        return ImageFont.truetype(str(font_file), size)

    @classmethod
    def font(cls, font_code: FontCode, size: float) -> ImageFont.FreeTypeFont:
        """
        获取指定代码和大小的字体
        
        :param font_code: 字体枚举（如 FontCode.MIS_DB）或自定义路径/文件名
         :param size: 字体大小（浮点数会四舍五入）
        :return: `ImageFont.FreeTypeFont` 对象
        """
        if cls._font_path is None:
            raise ValueError("FontManager 未初始化，请先调用 FontManager.init(path)")

        istool_size = int(round(size))
        font_sub_path = font_code.value if isinstance(font_code, FontCode) else font_code
        font_file = cls._font_path / font_sub_path
            
        if not font_file.exists():
            font_file = cls._font_path / f"{font_code}.ttf"
        if not font_file.exists():
            font_file = Path(font_code)
        if not font_file.exists():
            raise FileNotFoundError(f"字体文件缺失: {font_file.absolute()}")

        try:
            return cls._get_font(font_file, istool_size)
        except Exception as e:
            if not font_file.exists():
                raise FileNotFoundError(f"字体文件缺失: {font_file.absolute()}")
            raise e


class ImageManager:
    """资源管理器 - 负责加载和缓存图片文件（类方法版）"""
    
    _assets_path: Path = Path()
    _img_path: Path = Path()
    _pic_path: Path = Path()
    _dxrating_path: Path = Path()
    _plate_path: Path = Path()
    _ver_path: Path = Path()

    @classmethod
    def init(cls, assets_path: Path):
        """全局初始化资源路径"""
        cls._assets_path = Path(assets_path)
        cls._img_path = cls._assets_path / "img"         # `img` -> 直接打包的部分底图
        cls._pic_path = cls._assets_path / "pic"         # `pic` -> 静态资源
        cls._dxrating_path = cls._pic_path / "dxrating"  # `dxrating` -> DX Rating 框图
        cls._plate_path = cls._pic_path / "plate"        # `plate` -> 牌子图
        cls._ver_path = cls._pic_path / "ver"            # `ver` -> 版本图标

    @classmethod
    @lru_cache(maxsize=64)
    def _get_image(cls, path: Path, size: tuple[int, int],
                   *, resize_filter: Image.Resampling = Image.Resampling.LANCZOS) -> Optional[Image.Image]:
        """加载图片（有缓存）"""
        if not path.exists():
            return None
        try:
            img = Image.open(path).convert('RGBA')
            if min(size) > 0:
                img = img.resize(size, resize_filter)
            return img
        except Exception:
            return None

    @classmethod
    def background(cls, name: str = "bakamai.png", size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取背景图"""
        if cls._img_path is None:
            raise ValueError("ImageAssetsManager 未初始化，请先调用 ImageAssetsManager.init(path)")
        return cls._get_image(cls._img_path / name, size, **kwargs)

    @classmethod
    def version_image(cls, version: int, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取版本图标"""
        if cls._ver_path is None:
            raise ValueError("ImageAssetsManager 未初始化，请先调用 ImageAssetsManager.init(path)")
        return cls._get_image(cls._ver_path / f"{version}.png", size, **kwargs)

    @classmethod
    def dxrating_image(cls, rating_filename: str, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取 DX Rating 框图"""
        if cls._dxrating_path is None:
            raise ValueError("ImageAssetsManager 未初始化，请先调用 ImageAssetsManager.init(path)")
        return cls._get_image(cls._dxrating_path / rating_filename, size, **kwargs)

    @classmethod
    def dxrating_image_with_value(cls, dxrating: int, size: tuple[int, int] = (0, 0),
                                  cirp_frame: bool = True) -> Optional[Image.Image]:
        """根据 DX Rating 值获取对应的框图"""        
        rating_filename = get_dxra_frame_filename(dxrating, cirp_frame=cirp_frame)
        return cls.dxrating_image(rating_filename, size=size)


FontManager.init(ASSETS_PATH / "fonts")
ImageManager.init(ASSETS_PATH)


class DrawUnit:
    """绘图适配器，持有 `Image.Image` 对象并操作"""
    
    def __init__(self, img: Image.Image, multiple: MS | int = MS(), cn_level: Literal[0, 1, 2] = 0):
        from .components import BaseDrawer

        self.img = img
        self.draw = ImageDraw.Draw(img)
        self.ms = multiple if isinstance(multiple, MS) else MS(multiple)
        self.cn_level: Literal[0, 1, 2] = cn_level  # 明确标注类型
        self._drawer = BaseDrawer(img, self.draw, self.ms)

    def _text(self, x: float, y: float, text: Optional[str], fill: Optional[str], anchor: str,
              font: ImageFont.FreeTypeFont, stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """基础文本绘制"""
        from .components import TextStyle

        style = TextStyle(fill=fill, anchor=anchor, font=font, 
                         stroke_width=stroke_width, stroke_fill=stroke_fill)
        self._drawer.text(x, y, text or '', style)

    def text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str,
             font: ImageFont.FreeTypeFont, margin: int = 1, limit: int = -1,
             stroke: tuple[float, str] = (0, ''), shadow: tuple[float, str] = (0, ''),
             shadow2: tuple[float, str, float] = (0, '', 0)):
        """高级文本绘制（带阴影、描边）"""
        from .components import TextStyle

        style = TextStyle(
            fill=fill, anchor=anchor, font=font, limit=limit, margin=margin,
            stroke_width=stroke[0], stroke_fill=stroke[1],
            shadow_width=shadow[0], shadow_color=shadow[1],
            shadow2_width=shadow2[0], shadow2_color=shadow2[1], shadow2_offset=shadow2[2]
        )
        self._drawer.text(x, y, text, style)

    def double_text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str,
                   font: ImageFont.FreeTypeFont, margin: int = 1, limit: int = -1,
                   stroke: tuple[float, str] = (0, ''), shadow: tuple[float, str] = (0, ''),
                   shadow2: tuple[float, str, float] = (0, '', 0)):
        """多行文本绘制"""
        from .components import TextStyle

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
        from .components import LevelBadge

        badge = LevelBadge(level, diff, plus, ignore_decimal, self.cn_level)
        badge.render(self.draw, self.ms, x, y)

    def ach_frame(self, x: float, y: float, diff: Diff):
        """绘制达成率框架"""
        from .components import AchievementComponent

        component = AchievementComponent(0, diff, ms=self.ms, cn_level=self.cn_level)
        component.render_frame(self.draw, x, y)

    def ach_value(self, x: float, y: float, ach_percent: float, color: Optional[AchColor] = None):
        """绘制达成率数值"""
        from .components import AchievementComponent

        component = AchievementComponent(ach_percent, Difficulty.NONE.value, color, ms=self.ms, cn_level=self.cn_level)
        component.render_value(self.draw, x, y)

    def ach(self, x: float, y: float, diff: Diff, ach_percent: float, color: Optional[AchColor] = None):
        """绘制达成率（完整）"""
        from .components import AchievementComponent

        component = AchievementComponent(ach_percent, diff, color, ms=self.ms, cn_level=self.cn_level)
        component.render_frame(self.draw, x, y)
        component.render_value(self.draw, x + 2.8, y + 1.5)

    @staticmethod
    def _dxscore(cn_level: Literal[0, 1, 2], score: int, max_score: int, star_count: int) -> tuple[str, str, str, str]:
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
        from .components import DXScoreComponent

        component = DXScoreComponent(score, max_score, star_count, diff,
                                    lite=False, ms=self.ms, cn_level=self.cn_level)
        component.render(self.draw, x, y)

    def dxscore_lite(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Diff):
        """绘制简化版 DX 分数"""
        from .components import DXScoreComponent

        component = DXScoreComponent(score, max_score, star_count, diff,
                                    lite=True, ms=self.ms, cn_level=self.cn_level)
        component.render(self.draw, x, y)

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont,
             fill: str = '#FFF', line_height: float = 3.4, limit_width: float = -1):
        """绘制信息列表"""
        self._drawer.infos(x, y, lines, font, fill, line_height, limit_width)


class ImageUnit:
    """图像组件器，返回独立的 `Image.Image` 对象"""

    # 获取圆角 L 遮罩
    @classmethod
    @lru_cache(maxsize=8)
    def get_mask(cls, w: int, h: int, radius: float,
                 ms: MS = MS()) -> Image.Image:
        # 画布大小应包含完整的 w 和 h
        mask = Image.new('L', ms.xy(w, h), 0)
        draw = ImageDraw.Draw(mask)
        # 直接绘制充满画布的圆角矩形，坐标为 (0, 0, w, h)
        draw.rounded_rectangle(ms.size(0, 0, w, h), radius=ms.x(radius), fill=255)
        return mask

    # 难度式文本样式
    @classmethod
    def diff_text(cls, diff: Diff, text: Optional[str] = None, limit_width: float = -1, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0):
        # 处理文字长度并计算位置
        font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(4.8))
        if text:
            # 自定义文本，需处理宽度顺序
            text = limit_text(text, font, limit_width) if limit_width > 0 else text
            display_text = text
        else:
            display_text = diff.text_title

        x1, y1, x2, y2 = font.getbbox(display_text, anchor='lm', stroke_width=ms.x(0.8))
        if cn_level == 2 and not text:
            # 特殊处理中文默认难度标题的位置
            cn_font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(3.3))
            cn_x1, _cn_y1, cn_x2, _cn_y2 = cn_font.getbbox(diff.text_title_cn, anchor='lm', stroke_width=ms.x(0.8))
            cn_width = ms.rev(round(cn_x2 - cn_x1))
        else:
            cn_width = 0
        width = (ms.rev(round(x2 - x1)) + cn_width) * 1.2
        height = ms.rev(round(y2 - y1)) * 1.2

        # 实际渲染逻辑
        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.text(1, height / 2, display_text, diff.text, 'lm', font, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))
        if cn_width:
            du.text(ms.rev(round(x2 - x1)) * 1.1, ms.rev(round(y2 - y1)) * 1.1, diff.text_title_cn, diff.text, 'ld', FontManager.font(FontCode.MiSans_Heavy, size=ms.x(3.3)),
                    shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))

        return img

    # 难度文本
    @classmethod
    @lru_cache(maxsize=10)
    def difficulty(cls, diff: Diff, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return cls.diff_text(diff=diff, text=None, limit_width=-1, ms=ms, cn_level=cn_level)

    # FC / FS 评定文本
    @classmethod
    @lru_cache(maxsize=18)
    def evaluate(cls, eval: EvalInfo | None, mini: bool = False, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        size = ms.xy(20, 5) if mini else ms.xy(40, 5)
        img = Image.new('RGBA', size, "#FFFFFF00")
        if eval:
            du = DrawUnit(img, multiple=ms, cn_level=cn_level)
            text = eval.short_name if mini else (eval.cn_name if cn_level == 2 else eval.full_name)
            du.text(1, 2.5, text, eval.color.fill, 'lm', FontManager.font(FontCode.MiSans_Heavy, size=ms.x(3)),
                stroke=(0.5, eval.color.shadow), shadow=(0.65, eval.color.shadow))
        return img

    # 谱面类型标记（标准）
    @classmethod
    def draw_sd_badge(cls, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_SD = '#4AF'
        du.rounded_rect(0, 0, 20, 5, fill=COLOR_SD, radius=5)
        offset = 0.6 if cn_level else 0
        font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(3 + offset))
        text = "标 准" if cn_level else "スタンダード"
        du.text(10, 2.5, text, '#FFF', 'mm', font)
        return img

    # 谱面类型标记（DX）
    @classmethod
    def draw_dx_badge(cls, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_DX = ('#FF7711', '#FFFFFF')
        COLOR_DELUXE = ('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6', '#2299EE')

        du.rounded_rect(0, 0, 20, 5, fill='#FFF', radius=5, outline=COLOR_DX[1] if cn_level else COLOR_DELUXE[-1], width=0.5)
        if cn_level:
            text = "DX"
            du.text(10, 2.5, text, COLOR_DX[0], 'mm', FontManager.font(FontCode.MiSans_Heavy, size=ms.x(4.1)))
        else:
            font = FontManager.font(FontCode.MiSans_Heavy, size=ms.x(3.2))
            text = "でらっくす"
            total_text_width = ms.rev(round(font.getlength(text)))
            start_x = (10) - (total_text_width / 2)
            current_x = start_x
            center_y = 2.5
            for char, color in zip(text, COLOR_DELUXE):
                du.text(current_x, center_y, char, color, 'lm', font)
                char_width = ms.rev(round(font.getlength(char)))
                current_x += char_width
        return img

    # 谱面类型标记
    @classmethod
    @lru_cache(maxsize=4)
    def draw_badge(cls, is_cabinet_dx: bool, ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return cls.draw_dx_badge(ms=ms, cn_level=cn_level) if is_cabinet_dx else cls.draw_sd_badge(ms=ms, cn_level=cn_level)

    # 版权信息栏
    @classmethod
    @lru_cache(maxsize=4)
    def copyright_bar(cls, width: int, lines: list[str] | None = None,
                      ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        if lines is None:
            lines = [
                "Powered by LyraBot (@GoldSheep3)",
                "Designer by Bakamai⑨'s Members",
                "Background Artist by @银色山雾",
            ]
            if git_hash := get_git_head_hash():
                lines.append(f"Version: {git_hash}")
        
        cr_info = "    |    ".join(lines)
        
        # 基准测量
        base_size = 5.0
        test_font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(base_size))
        tx1, ty1, tx2, ty2 = test_font.getbbox(cr_info)
        raw_width = tx2 - tx1
        raw_height = ty2 - ty1

        target_content_width = width * 0.9  # 预留两侧各 5% 的空白边距
        # 缩放系数 = 目标宽度 / 原始宽度
        ratio = min(target_content_width / (raw_width / ms.multiple), 1.0)
        final_size = max(base_size * ratio, 1.2)
        
        font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(final_size))
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
    @classmethod
    def chart_box(cls, chart: MaiChart, cabinet_dx: bool, server: server, plus_level: int = 6, is_utage: bool = False,
                  ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框"""
        w, h, ow = 108, 36, 1  # w, h, outline_width
        diff = Difficulty.get(chart.difficulty)

        img = cls.chart_box_base(diff=diff, cabinet_dx=cabinet_dx, w=w, h=h, ow=ow, ms=ms, cn_level=cn_level).copy()
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
        fc = cls.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 27-3), fc)
        fs = cls.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 32-3), fs)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.lv_synh:.4f}" if chart.lv_synh else '',
        ]

        du.rounded_rect(ow + 64, ow + 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
        du.infos(ow + 65.5, ow + 21.65, lines=(info_line5 + [''] * 5)[:5], line_height=4.5, limit_width=-1,
                 font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3.2)))

        return img

    @classmethod
    def chart_box_lite(cls, chart: MaiChart, cabinet_dx: bool, server: server, plus_level: int = 6, is_utage: bool = False,
                       ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框 Lite"""
        w, h, ow = 108, 25, 1  # w, h, outline_width
        diff = Difficulty.get(chart.difficulty)

        img = cls.chart_box_base(diff=diff, cabinet_dx=cabinet_dx, w=w, h=h, ow=ow, ms=ms, cn_level=cn_level).copy()
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
        fc = cls.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 12 - 3), fc)
        fs = cls.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 17 - 3), fs)
        return img

    @classmethod
    @lru_cache(maxsize=32)
    def chart_box_base(cls, diff: Diff, cabinet_dx: bool, w: int, h: int, ow: int,
                       ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(w + ow * 2, h + ow * 2), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, radius=4, fill=diff.bg)
        du.cut_line(ow, ow, w, h, radius=4, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, radius=4, fill=None, outline=diff.frame, width=1)
        difficulty = cls.difficulty(diff=diff, ms=ms, cn_level=cn_level)
        diff_height = ms.rev(difficulty.size[1])
        img.paste(difficulty, ms.xy(ow + 2.5, ow + 4.3 - diff_height / 2), difficulty)
        badge = cls.draw_badge(is_cabinet_dx=cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 85, ow + 2), badge)
        return img

    @classmethod
    @lru_cache(maxsize=12)
    def mini_box_base(cls, diff: Diff, is_cabinet_dx: bool, shortid: int, w: int, h: int, ow: int,
                      ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(w + ow * 2, h + ow * 2), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, diff.bg, radius=2.5, outline=diff.frame)
        du.cut_line(ow, ow, w, h, radius=0, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, None, radius=2.5, outline=diff.title_bg, width=1)
        badge = cls.draw_badge(is_cabinet_dx=is_cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 75, ow + 2), badge)
        shortid_img = cls.diff_text(diff=diff, text=f'#{shortid}', ms=ms, cn_level=cn_level)
        img.paste(shortid_img, ms.xy(ow + 35, ow + 4.2 - ms.rev(round(shortid_img.size[1] / 2))), shortid_img)
        return img

    @classmethod
    def mini_box(cls, maidata: MaiData | None, difficulty: int, server: server,
                 ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0,
                 shared_zip: zipfile.ZipFile | None = None) -> Image.Image | tuple[int, int]:
        w, h, ow = 97, 36, 1  # w, h, outline_width
        width, height = w + ow * 2, h + ow * 2
        diff = Difficulty.get(difficulty)

        chart = maidata.get_chart(difficulty) if maidata else None
        if not chart or maidata is None:
            return width, height  # 视为占位，返回尺寸供布局使用
        ach = chart.get_ach(server=server)

        img = cls.mini_box_base(
            diff=diff,
            is_cabinet_dx=maidata.is_cabinet_dx,
            shortid=maidata.shortid,
            w=w,
            h=h,
            ow=ow,
            ms=ms,
            cn_level=cn_level,
        ).copy()
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        # 曲绘
        cover = maidata.get_image(shared_zip=shared_zip)
        if cover:
            mask = cls.get_mask(w=32, h=32, radius=1.5, ms=ms)
            cover_img = cover.resize(ms.xy(32, 32), Image.Resampling.LANCZOS)
            img.paste(cover_img, ms.xy(ow + 2, ow + 2), mask)
        # 达成率
        du.ach(ow + 35, ow + 9, diff, ach_percent=ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(ow + 53, ow + 31, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = cls.evaluate(Combo.get(ach.combo), mini=True, ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 36, ow + 24), fc)
        fs = cls.evaluate(Sync.get(ach.sync), mini=True, ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 36, ow + 29), fs)
        return img

    @classmethod
    def b50_box(cls, maidata: MaiData, difficulty: int, server: server,
                current_version: int, index: int, is_b15: Optional[bool] = None,
                ms: MS = MS(), cn_level: Literal[0, 1, 2] = 0,
                shared_zip: zipfile.ZipFile | None = None) -> Image.Image | None:
        chart = maidata.get_chart(difficulty)
        if not chart:
            return None
        img = cls.mini_box(maidata=maidata, difficulty=difficulty, server=server, ms=ms, cn_level=cn_level, shared_zip=shared_zip)
        if isinstance(img, tuple):
            return None
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.rounded_rect(54, 25, 42, 5, fill=bcm(Difficulty.get(difficulty).bg, '#0009'), radius=4)
        du.rounded_rect(54, 25, 16, 5, fill='#006', radius=4)
        b_type = '15' if is_b15 else '35'
        du.text(62, 27.5, f"b{b_type} #{index}", fill='#FFF', anchor='mm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3)))
        du.text(74, 27.5, f"{chart.lv:.1f} > {maidata.get_chart_dxrating(difficulty, server, current_version)}", fill='#FFF', anchor='lm', font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3)))
        return img
