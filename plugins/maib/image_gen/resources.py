"""
image_gen 资源管理器
- FontManager: 字体加载与缓存
- AssetsManager: 图片资源加载与缓存
"""

from pathlib import Path
from typing import Optional, Tuple, Union
from functools import lru_cache
from enum import StrEnum

from PIL import Image, ImageFont


class FontCode(StrEnum):
    """字体名称枚举"""
    
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
    """字体管理器 - 负责加载和缓存字体文件"""

    def __init__(self, font_path: Path):
        """初始化字体管理器"""
        self._font_path = font_path

    @lru_cache(maxsize=128)
    def _get_font(self, font_file: Path, size: int) -> ImageFont.FreeTypeFont:
        """从文件加载字体（有缓存）"""
        if size <= 0:
            return ImageFont.truetype(str(font_file), 10000)
        return ImageFont.truetype(str(font_file), size)

    def font(self, font_code: FontCode, size: float) -> ImageFont.FreeTypeFont:
        """
        获取指定代码和大小的字体
        
        Args:
            font_code: 字体枚举（如 FontCode.MIS_DB）或自定义路径/文件名
            size: 字体大小（浮点数会四舍五入）
            
        Returns:
            ImageFont.FreeTypeFont 对象
        """
        istool_size = int(round(size))

        # 1. 无论是枚举还是普通字符串，StrEnum 的 value 直接就是路径字符串
        # 如果传入的是枚举，通过 font_code.value 获取路径；如果是普通文本则直接作为路径
        font_sub_path = font_code.value if isinstance(font_code, FontCode) else font_code
        
        # 2. 拼接完整路径
        font_file = self._font_path / font_sub_path
            
        # 3. 兜底：如果路径不存在，尝试拼 .ttf 或是绝对路径（兼容你原本的灵活性）
        if not font_file.exists():
            font_file = self._font_path / f"{font_code}.ttf"
        if not font_file.exists():
            font_file = Path(font_code)

        try:
            return self._get_font(font_file, istool_size)
        except Exception as e:
            if not font_file.exists():
                raise FileNotFoundError(f"字体文件缺失: {font_file.absolute()}")
            raise e


class AssetsManager:
    """资源管理器 - 负责加载和缓存图片文件"""
    
    def __init__(self, assets_path: Path):
        """
        初始化资源管理器
        
        Args:
            assets_path: 资源根目录路径
        """
        self._assets_path = assets_path
        self._pic_path = self._assets_path / "pic"
        self._dxrating_path = self._pic_path / "dxrating"
        self._plate_path = self._pic_path / "plate"
        self._ver_path = self._pic_path / "ver"

    @staticmethod
    @lru_cache(maxsize=64)
    def _get_image(path: Path, size: Tuple[int, int] | None = None) -> Image.Image | None:
        """加载图片（有缓存）"""
        if not path.exists():
            return None
        try:
            img = Image.open(path).convert('RGBA')
            if size is not None:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception:
            return None

    def version_image(self, version: int, size: Tuple[int, int] | None = None) -> Image.Image | None:
        """获取版本图标"""
        return self._get_image(self._ver_path / f"{version}.png", size)

    def dxrating_image(self, rating_filename: str, size: Tuple[int, int] | None = None) -> Image.Image | None:
        """获取 DX Rating 框图"""
        return self._get_image(self._dxrating_path / rating_filename, size)

    def background(self, size: Tuple[int, int] | None = None) -> Image.Image | None:
        """获取背景图"""
        return self._get_image(self._assets_path / "img" / "bakamai.png", size)
