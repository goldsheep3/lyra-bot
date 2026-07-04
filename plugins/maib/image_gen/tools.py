"""image_gen/tools.py 绘图基础工具"""
import io
import bisect
from typing import Optional, Literal
from PIL import Image, ImageFont

from ..constants import GENRE_MAP
from .models import COLOR_THEME


__all__ = [
    # 全半角转换
    "convert_to_full_width",
    # dxrating 外框
    "get_dxra_frame_filename",
    # 颜色混合函数
    "bcm",
    # 文本限制函数
    "limit_text",
    # 流派信息获取函数
    "get_genre",
    # PIL Image 转字节流
    "get_image_bytes",
]


# --- 全半角转换 ---
class FullWidthConverter:
    
    _char_full_width_table: Optional[dict[int, int]] = None
    
    @classmethod
    def table(cls) -> dict[int, int]:
        if cls._char_full_width_table is None:
            # 半角空格 (32) 对应全角空格 (12288)
            # 其他 ASCII 可打印字符 (33-126) 对应全角 (65281-65374)
            # 偏移量通常为 0xFEE0 (65248)
            half_width = "".join(chr(i) for i in range(32, 127))
            full_width = "　" + "".join(chr(i + 0xFEE0) for i in range(33, 127))
            cls._char_full_width_table = str.maketrans(half_width, full_width)
        return cls._char_full_width_table

    @classmethod
    def convert(cls, text: str) -> str:
        """将文本中的半角 ASCII 字符转换为全角形式"""
        if not text:
            return ""
        return text.translate(cls.table())

convert_to_full_width = FullWidthConverter.convert
    

# --- dxrating 外框 ---
class _DXRatingBoundaries:
    FINALE = [
        0,      # 白框
        1000,   # 蓝框
        2000,   # 绿框
        5000,   # 黄框
        7000,   # 红框
        10000,  # 紫框
        12000,  # 铜框
        13000,  # 银框
    ]
    DX = [
        14000,  # 金框
        14500,  # 白金框
        15000,  # 虹框
    ]
    CIRP = [
        14000,  # 金框 ★1
        14250,  # 金框 ★2
        14500,  # 白金框 ★1
        14750,  # 白金框 ★2
        15000,  # 虹框（彩框）★1
        15250,  # 虹框（彩框）★2
        15500,  # 虹框（彩框）★3
        15750,  # 虹框（彩框）★4
        16000,  # 虹框（極）（极彩框）★1
        16250,  # 虹框（極）（极彩框）★2
        16500,  # 虹框（極）（极彩框）★3
        16750,  # 虹框（極）（极彩框）★4
    ]
    
    @property
    def finale(self):
        return self.FINALE
    
    @property
    def dx(self):
        return self.FINALE + self.DX

    @property
    def cirp(self):
        return self.FINALE + self.CIRP

_BOUNDS = _DXRatingBoundaries()

def get_dxra_frame_filename(dxrating: int, cirp_frame: bool = True) -> str:
    """根据 DX Rating 获取对应的外框文件名。"""

    bounds = _BOUNDS.cirp if cirp_frame else _BOUNDS.dx

    idx = max(0, bisect.bisect_right(bounds, dxrating) - 1)
    if idx < len(_BOUNDS.finale):
        return f"JP_{idx}.png"
    if cirp_frame:
        return f"JP_CIRP_{idx}.png"
    return f"JP_{idx}.png"

# --- 颜色混合函数 ---
def bcm(t: str, f: str) -> str:
    """
    颜色混合函数 (背景色 t，前景色 f)
    
    使用 Alpha 混合模式
    """
    # TODO 最终要更换成 Pillow 的 mask 混合
    r1, g1, b1 = (int(t[i] * 2, 16) for i in range(1, 4))
    r2, g2, b2, a = \
        (int(f[i] * 2, 16) for i in range(1, 5)) if len(f) == 5 else (int(f[i:i + 2], 16) for i in range(1, 9, 2))
    alpha = a / 255.0
    r = int(r1 + (r2 - r1) * alpha)
    g = int(g1 + (g2 - g1) * alpha)
    b = int(b1 + (b2 - b1) * alpha)
    return f"#{r:02X}{g:02X}{b:02X}"

# --- 文本限制函数 ---
def limit_text(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
    """
    限制文本显示宽度（超过则截断并添加 ...）
    
    Args:
        text: 要处理的文本
        font: PIL 字体对象
        max_width: 最大显示宽度像素数
        
    Returns:
        截断后的文本
    """
    full_width = font.getlength(text)
    if full_width <= max_width or len(text) < 4 or max_width < 0:
        return text

    # 启发式预测截断位置
    avg_char_w = full_width / len(text)
    guess_len = int((max_width - avg_char_w * 3) / avg_char_w)
    guess_len = max(0, min(len(text), guess_len))
    
    # 单侧探测与微调
    current_text = text[:guess_len] + '...'
    current_width = font.getlength(current_text)

    if current_width > max_width:
        # 过宽，向左收缩
        while guess_len > 0:
            guess_len -= 1
            current_text = text[:guess_len] + '...'
            if font.getlength(current_text) <= max_width:
                break
    else:
        # 过窄，向右扩展
        while guess_len < len(text):
            next_text = text[:guess_len + 1] + '...'
            if font.getlength(next_text) > max_width:
                break
            guess_len += 1
            current_text = next_text

    return current_text

# --- 流派信息获取函数 ---
def get_genre(genre_id: int, cn_level: Literal[0, 1, 2]) -> tuple[str, str]:
    """获取流派信息"""
    genre_info = GENRE_MAP.get(genre_id, {})
    target = {0: 'jp', 1: 'intl', 2: 'cn'}
    genre = genre_info.get(target.get(cn_level, 'jp'), 'N/A').replace('\\n', '\n')
    color = genre_info.get('color', COLOR_THEME)
    return genre, color

# --- PIL Image 转字节流 ---
def get_image_bytes(img: Image.Image, format: str = "jpeg") -> bytes:
    """将 PIL Image 对象转换为字节流"""
    with io.BytesIO() as output:
        if format.lower() == "jpeg" and max(img.size) > 65500:
            format = "png"
        try:
            img.save(output, format=format)
        except OSError:
            if format.lower() != "jpeg":
                raise
            output.seek(0)
            output.truncate(0)
            img.save(output, format="png")
        return output.getvalue()