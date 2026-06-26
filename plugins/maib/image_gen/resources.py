"""
image_gen 资源管理器
- FontManager: 字体加载与缓存
- AssetsManager: 图片资源加载与缓存
"""

from pathlib import Path
from typing import Optional, Tuple
from functools import lru_cache

from PIL import Image, ImageFont


class FontManager:
    """字体管理器 - 负责加载和缓存字体文件"""
    
    _font_dict = {
        'MIS_DB': "MiSans-Demibold.otf",
        'MIS_HE': "MiSans-Heavy.otf",
        'JBM_MD': "JetBrainsMono-Medium.ttf",
        'JBM_BD': "JetBrainsMono-Bold.ttf",
        'JBM_EB': "JetBrainsMono-ExtraBold.ttf",
        'NCE_RG': 'NotoColorEmoji-Regular.ttf',
        'NSS_RG': "NotoSansSymbols2-Regular.ttf",
    }

    def __init__(self, font_path: Path):
        """初始化字体管理器"""
        self._font_path = font_path

    @lru_cache(maxsize=128)
    def _get_font(self, font_file: Path, size: int) -> ImageFont.FreeTypeFont:
        """从文件加载字体（有缓存）"""
        if size <= 0:
            return ImageFont.truetype(str(font_file), 10000)
        return ImageFont.truetype(str(font_file), size)

    def font(self, font_code: str, size: float) -> ImageFont.FreeTypeFont:
        """
        获取指定代码和大小的字体
        
        Args:
            font_code: 字体代码（如 'MIS_DB'）或文件名
            size: 字体大小（浮点数会四舍五入）
            
        Returns:
            ImageFont.FreeTypeFont 对象
        """
        istool_size = int(round(size))

        font_name = self._font_dict.get(font_code, f"{font_code}.ttf")
        font_file = self._font_path / font_name
        if not font_file.exists():
            # 尝试直接使用 font_code 作为文件名
            font_file = self._font_path / f"{font_code}.ttf"
        if not font_file.exists():
            # 尝试直接读取 font_code 作为路径
            font_file = Path(font_code)

        try:
            return self._get_font(font_file, istool_size)
        except Exception as e:
            if not font_file.exists():
                raise FileNotFoundError(f"字体文件缺失: {font_file}")
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
