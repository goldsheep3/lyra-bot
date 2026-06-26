"""
image_gen 绘图模块的基础工具函数
- MS 坐标缩放器
- bcm 颜色混合函数
- 文本处理工具
- 其他计算工具
"""

import bisect
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageFont


# ========================================
# 全角字符转换表
# ========================================

def _build_full_width_table():
    """构建半角到全角的转换表"""
    # 半角空格 (32) 对应全角空格 (12288)
    # 其他 ASCII 可打印字符 (33-126) 对应全角 (65281-65374)
    # 偏移量通常为 0xFEE0 (65248)
    half_width = "".join(chr(i) for i in range(32, 127))
    full_width = "　" + "".join(chr(i + 0xFEE0) for i in range(33, 127))
    return str.maketrans(half_width, full_width)


CHAR_FULL_WIDTH_TABLE = _build_full_width_table()


# ========================================
# DXRating 分界线常量
# ========================================

BOUNDARIES_DX_RATING = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14500, 15000]
BOUNDARIES_DX_RATING_NEW = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14250, 14500, 14750, 15000, 15250, 15500, 15750, 16000, 16250, 16500, 16750]


# ========================================
# 坐标缩放类
# ========================================

class MS:
    """倍率缩放器 - 用于 UI 响应式设计"""
    
    def __init__(self, multiple: float):
        self.multiple = multiple
        self._cache: dict[float, int] = {}  # 计算缓存

    def set_multiple(self, multiple: float):
        """重新设置倍率"""
        self.multiple = multiple
        self._cache = {}

    def x(self, val: int | float) -> int:
        """缩放单个值"""
        val = float(val)
        if result := self._cache.get(val):
            return result
        self._cache[val] = round(val * self.multiple)
        return self._cache[val]

    def xy(self, x: int | float, y: int | float) -> tuple[int, int]:
        """缩放坐标对"""
        return self.x(x), self.x(y)

    def size(self, x: int | float, y: int | float, w: int | float, h: int | float) -> tuple[int, int, int, int]:
        """缩放矩形框 (x, y, x+w, y+h)"""
        return self.x(x), self.x(y), self.x(x + w), self.x(y + h)

    def rev(self, x: float) -> float:
        """反向缩放（从缩放后的值恢复原始值）"""
        return x / self.multiple

    def __repr__(self):
        return f"MS(multiple={self.multiple})"

    def __mul__(self, other: int | float) -> 'MS':
        """倍数相乘"""
        if not isinstance(other, (int, float)):
            return NotImplemented
        return MS(self.multiple * other)

    def __hash__(self):
        # 仅根据 multiple 计算哈希值，忽略缓存
        return hash(self.multiple)


_MS_DEFAULT = MS(5)  # 默认倍率


# ========================================
# 颜色混合函数
# ========================================

def bcm(t: str, f: str) -> str:
    """
    颜色混合函数 (背景色 t，前景色 f)
    
    使用 Alpha 混合模式
    """
    # TODO: 最终要更换成 Pillow 的混合函数
    r1, g1, b1 = (int(t[i] * 2, 16) for i in range(1, 4))
    r2, g2, b2, a = \
        (int(f[i] * 2, 16) for i in range(1, 5)) if len(f) == 5 else (int(f[i:i + 2], 16) for i in range(1, 9, 2))
    alpha = a / 255.0
    r = int(r1 + (r2 - r1) * alpha)
    g = int(g1 + (g2 - g1) * alpha)
    b = int(b1 + (b2 - b1) * alpha)
    return f"#{r:02X}{g:02X}{b:02X}"


# ========================================
# 文本处理工具
# ========================================

def get_full_width_text(text: str) -> str:
    """将文本中的半角 ASCII 字符转换为全角形式"""
    if not text:
        return ""
    return text.translate(CHAR_FULL_WIDTH_TABLE)


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


# ========================================
# 其他工具函数
# ========================================

def get_image_from_path_or_weburl(path: Path) -> Optional[Image.Image]:
    """从本地路径获取图片"""
    if path.exists():
        try:
            return Image.open(path).convert('RGBA')
        except (FileNotFoundError, OSError):
            return None
    return None


def get_range_index_left_closed(boundaries: list[int], value: int) -> int:
    """
    根据左闭右开区间 [b[i], b[i+1]) 返回索引 i
    """
    # 如果值小于最小值，返回 -1
    if value < boundaries[0]:
        return -1

    idx = bisect.bisect_right(boundaries, value) - 1
    
    # 边界检查：如果值超出了最大边界
    if idx >= len(boundaries):
        return len(boundaries) - 1
        
    return idx
