"""
image_gen.tools
绘图工具函数
"""
import io
import bisect
import zipfile
from typing import Optional, Iterable, Sequence
from PIL import Image, ImageDraw, ImageFont
from contextlib import contextmanager
from pathlib import Path

from .color import TRANSPARENT
from ..utils import MaiData
from ..utils.map import DifficultyID


__all__ = [
    # 全半角转换
    "convert_to_full_width",
    # dxrating 外框
    "get_dxra_frame_filename",
    # 颜色混合函数
    "bcm",
    # 文本限制函数
    "limit_text",
    # PIL Image 转字节流
    "get_image_bytes",
    # 圆角矩形切割
    "rounded_image",
    # 网格化排列图片
    "image_grid_board",
    # 拼接图片并转换为 RGB
    "image_listed_to_rgb",
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
def limit_text(text: str, font: ImageFont.FreeTypeFont, max_width: Optional[float]) -> str:
    """
    限制文本显示宽度（超过则截断并添加 ...）
    
    Args:
        text: 要处理的文本
        font: PIL 字体对象
        max_width: 最大显示宽度像素数
        
    Returns:
        截断后的文本
    """
    if max_width is None or max_width < 0:
        # 无宽度限制值，直接返回原文本
        return text
    
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

# --- 圆角矩形切割函数 ---
def rounded_image(img: Image.Image, size: tuple[int, int], outline_width: int, radius=4):
    weight, height = size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (outline_width, outline_width, weight, height),
        radius=radius,
        fill=255,
    )

    final_img = Image.new(img.mode, size, TRANSPARENT)
    final_img.paste(img, (0, 0), mask)

    mask.close()
    return final_img

# --- 网格化排列图片 ---
def image_grid_board(image_iter: Iterable[Image.Image], 
                     cols: int = 4, 
                     gap_px: int = 0,
                     total_count: Optional[int] = None,
                     box_size_px: Optional[tuple[int, int]] = None,
                     first_img: Optional[Image.Image] = None) -> Optional[Image.Image]:
    """图片网格排列"""
    # 判断传入的是否为列表/元组等序列类型
    is_sequence = isinstance(image_iter, Sequence)
    
    # 1. 确定总数量 (用于计算画板高度)
    if total_count is None:
        if is_sequence:
            total_count = len(image_iter)
        else:
            raise ValueError("当使用生成器/迭代器时，必须显式提供 'total_count' 参数。")
            
    if total_count <= 0 and first_img is None:
        return None
    if cols <= 0:
        raise ValueError("cols 必须为正整数。")

    # 2. 确定单张尺寸 (用于计算画板宽度)
    if box_size_px is None:
        if is_sequence and len(image_iter) > 0:
            box_size_px = image_iter[0].size
        else:
            raise ValueError("当使用生成器/迭代器时，必须显式提供 'box_size' 参数，例如 (800, 600)。")
            
    box_w, box_h = box_size_px
    total_slots = total_count + (1 if first_img is not None else 0)
    rows = (total_slots + cols - 1) // cols

    # 提前创建好大画板
    board_width = cols * box_w + (cols - 1) * gap_px
    board_height = rows * box_h + (rows - 1) * gap_px
    board = Image.new("RGBA", (int(board_width), int(board_height)), (0, 0, 0, 0))
    
    # 3. 首图占位：first_img 占据第一个槽位（0×0 图视为留空，仅占槽位）
    slot = 0
    if first_img is not None:
        if first_img.size[0] > 0 and first_img.size[1] > 0:
            mask = first_img if first_img.mode == 'RGBA' else None
            board.paste(first_img, (0, 0), mask)
        slot += 1

    # 4. 核心循环：边迭代、边粘贴、边销毁
    for img in image_iter:
        tx = (slot % cols) * (box_w + gap_px)
        ty = (slot // cols) * (box_h + gap_px)
        
        # 修复之前的 Mask 隐患：只有带 Alpha 通道的图才用自身做 Mask
        if img.size[0] > 0 and img.size[1] > 0:
            mask = img if img.mode == 'RGBA' else None
            board.paste(img, (int(tx), int(ty)), mask)
        
        # 粘贴完毕，立刻关闭底层 C 缓冲，释放内存！
        if not is_sequence:
            img.close()
        slot += 1

    return board


def image_listed_to_rgb(images: Sequence[Image.Image], forward: int = 0, margin: int = 0) -> Image.Image:
    """拼接并转换为 rgb 模式"""
    # forward 指最外圈的留白，margin 指图片之间的间距0
    forward, margin = max(0, forward), max(0, margin)
    if not images:
        raise ValueError("images 列表不能为空。")
    
    images = [(img if img.mode == "RGBA" else img.convert("RGBA")) for img in images]
    
    # 计算总高度和最大宽度
    total_height = sum(img.height for img in images) + forward * (len(images) + 1) + margin * (len(images) - 1)
    max_width = max(img.width for img in images) + forward * 2
    
    # 创建一个新的 RGB 图像
    new_image = Image.new("RGBA", (max_width, total_height), (255, 255, 255, 255))
    
    # 将每张图片粘贴到新图像上
    current_y = forward
    for img in images:
        new_image.paste(img, (forward, current_y))
        current_y += img.height + margin

    final_image = new_image.convert("RGB")
    new_image.close()

    return final_image
