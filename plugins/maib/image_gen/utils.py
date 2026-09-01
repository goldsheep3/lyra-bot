"""
image_gen.utils
绘图缩放类和资源管理器
"""
from pathlib import Path
from enum import StrEnum
from typing import Optional
from functools import lru_cache

from PIL import Image, ImageFont

from ..utils.constants import ASSETS_PATH
from .tools import get_dxra_frame_filename


__all__ = [
    # 缩放工具类
    "MS",
    # 字体
    "FontCode", "FontManager",
    # 图像
    "ImageManager",
]


# --- 坐标倍率缩放器 ---
class MS:
    """倍率缩放器"""
    # 全局缓存，按倍率分组
    # {multiple: {val_int: scaled_value, ...}, ...}
    _cache: dict[float, dict[float, int]] = {}
    
    def __init__(self, multiple: float = 10.0):
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

    def __repr__(self): 
        return f"MS(multiple={self.multiple})"

    def __mul__(self, other: float) -> 'MS':
        if not isinstance(other, (int, float)):
            return NotImplemented
        return MS(self.multiple * other)

    def __hash__(self): 
        return hash(self.multiple)

    def __str__(self): 
        return f"MS({self.multiple:.2f})"

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
    NotoSansSC_Medium = "Noto_Sans_SC/static/NotoSansSC-Medium.ttf"
    # NotoSansSC_SemiBold = "Noto_Sans_SC/static/NotoSansSC-SemiBold.ttf"
    NotoSansSC_Bold = "Noto_Sans_SC/static/NotoSansSC-Bold.ttf"
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
    
    _font_path: Path = ASSETS_PATH / "fonts"

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
    
    _assets_path: Path = ASSETS_PATH
    _img_path: Path = ASSETS_PATH / "img"
    _pic_path: Path = ASSETS_PATH / "pic"
    _dxrating_path: Path = ASSETS_PATH / "pic" / "dxrating"
    _plate_path: Path = ASSETS_PATH / "pic" / "plate"
    _ver_path: Path = ASSETS_PATH / "pic" / "ver"

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
        return cls._get_image(cls._img_path / name, size, **kwargs)

    @classmethod
    def version_image(cls, version: int, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取版本图标"""
        return cls._get_image(cls._ver_path / f"{version}.png", size, **kwargs)

    @classmethod
    def dxrating_image(cls, rating_filename: str, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取 DX Rating 框图"""
        return cls._get_image(cls._dxrating_path / rating_filename, size, **kwargs)

    @classmethod
    def dxrating_image_with_value(cls, dxrating: int, size: tuple[int, int] = (0, 0),
                                  cirp_frame: bool = True) -> Optional[Image.Image]:
        """根据 DX Rating 值获取对应的框图"""        
        rating_filename = get_dxra_frame_filename(dxrating, cirp_frame=cirp_frame)
        return cls.dxrating_image(rating_filename, size=size)

    @classmethod
    def dan(cls, dan: int, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取段位图"""
        return cls._get_image(cls._pic_path / "dan" / f"{dan}.png", size, **kwargs)

    @classmethod
    def plate_default(cls, size: tuple[int, int] = (0, 0), **kwargs) -> Optional[Image.Image]:
        """获取默认的 plate 图"""
        return cls._get_image(cls._plate_path / "default.png", size, **kwargs)
