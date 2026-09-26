"""
image_gen.tools
绘图工具函数
"""
import io
import bisect
from typing import Optional, Iterable, Sequence, Literal
from PIL import Image, ImageDraw, ImageFont

from .color import TRANSPARENT


__all__ = [
    # 全半角转换
    "convert_to_full_width",
    # dxrating 外框
    "get_dxra_frame_filename",
    # 文本限制函数
    "limit_text",
    # PIL Image 转字节流
    "get_image_bytes",
    # 圆角矩形切割
    "rounded_image",
    # 网格化排列图片
    "image_grid_board",
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
    BOTH = [
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
    
    @classmethod
    def both(cls):
        return cls.BOTH
    
    @classmethod
    def dx(cls):
        return cls.BOTH + cls.DX

    @classmethod
    def cirp(cls):
        return cls.BOTH + cls.CIRP

    @classmethod
    def both_length(cls):
        return len(cls.BOTH)

def get_dxra_frame_filename(dxrating: int,
                            cirp_frame: bool = True,
                            scale: Literal[50, 35, 15] = 50) -> str:
    """根据 DX Rating 获取对应的外框文件名。"""
    
    if cirp_frame:
        bounds = _DXRatingBoundaries.cirp()
    else:
        bounds = _DXRatingBoundaries.dx()
    if scale != 50:
        # 适应 b50 图片中需要对 b35 和 b15 考虑颜色的关系
        dxrating = int(dxrating * (50 / scale))

    idx = max(0, bisect.bisect_right(bounds, dxrating) - 1)
    # 对 14000+ 以上的 dxrating，若启用 cirp_frame，则使用 JP_CIRP_*.png 文件
    if (idx >= _DXRatingBoundaries.both_length() and cirp_frame):
        return f"JP_CIRP_{idx}.png"
    return f"JP_{idx}.png"

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
