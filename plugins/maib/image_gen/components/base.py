"""
基础绘制工具与样式定义
- TextStyle: 文本样式数据类
- BaseDrawer: 通用绘制工具类
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from ..utils import MS, limit_text, _MS_DEFAULT


@dataclass
class TextStyle:
    """文本样式配置"""
    fill: Optional[str] = '#FFF'
    anchor: str = 'lm'
    font: Optional[ImageFont.FreeTypeFont] = None
    stroke_width: float = 0
    stroke_fill: Optional[str] = None
    shadow_width: float = 0
    shadow_color: Optional[str] = None
    shadow2_width: float = 0
    shadow2_color: Optional[str] = None
    shadow2_offset: float = 0
    margin: int = 1
    limit: int = -1


class BaseDrawer:
    """基础绘制工具类"""
    
    def __init__(self, img: Image.Image, draw: ImageDraw.ImageDraw, ms: MS = _MS_DEFAULT):
        """初始化绘制器"""
        self.img = img
        self.draw = draw
        self.ms = ms

    def _text(self, x: float, y: float, text: Optional[str], fill: Optional[str], 
              anchor: str, font: ImageFont.FreeTypeFont,
              stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """基础文本绘制方法"""
        xy, sw = self.ms.xy(x, y), self.ms.x(stroke_width)
        text = text if text else ''
        self.draw.text(xy, text=text, fill=fill, anchor=anchor, font=font, 
                      stroke_width=sw, stroke_fill=stroke_fill)

    def text(self, x: float, y: float, text: str, style: TextStyle):
        """高级文本绘制方法（支持阴影、描边）"""
        if not style.font:
            raise ValueError("TextStyle.font 不能为空")
            
        if '\n' in text:
            self.double_text(x, y, text, style)
            return
            
        text = limit_text(text, style.font, style.limit) if style.limit > 0 else text
        
        # 下移阴影层
        if style.shadow2_width:
            self._text(x, y + style.shadow2_offset, text=text, 
                      fill=style.shadow2_color, anchor=style.anchor, 
                      font=style.font, stroke_fill=style.shadow2_color, 
                      stroke_width=style.shadow2_width)
        
        # 标准阴影层
        if style.shadow_width:
            self._text(x, y, text=text, fill=style.shadow_color, 
                      anchor=style.anchor, font=style.font,
                      stroke_fill=style.shadow_color, stroke_width=style.shadow_width)
        
        # 主文本层
        self._text(x, y, text=text, fill=style.fill, anchor=style.anchor, 
                  font=style.font, stroke_fill=style.stroke_fill, 
                  stroke_width=style.stroke_width)

    def double_text(self, x: float, y: float, text: str, style: TextStyle):
        """多行文本绘制"""
        if not style.font:
            raise ValueError("TextStyle.font 不能为空")
            
        text_list = text.split('\n')
        size = self.ms.rev(style.font.size)
        line_count = len(text_list)
        first_y = (y - (line_count - 1) / 2 * (size + style.margin)) if style.anchor[1:] == 'm' else y
        
        for i in range(line_count):
            dy = first_y + i * (size + style.margin)
            self.text(x, dy, text=text_list[i], style=style)

    def rounded_rect(self, x: float, y: float, w: float, h: float, fill: Optional[str], 
                    radius: float, outline: Optional[str] = None, width: float = 0):
        """绘制圆角矩形"""
        self.draw.rounded_rectangle(self.ms.size(x, y, w, h), radius=self.ms.x(radius), 
                                   fill=fill, outline=outline, width=self.ms.x(width))

    def cut_line(self, x: float, y: float, w: float, h: float, radius: float, 
                line_y: float, line_h: float, fill: str):
        """绘制切割线条（在圆角矩形内）"""
        box = self.ms.size(x, y, w, h)
        px_x0, px_y0 = int(box[0]), int(box[1])
        px_w, _px_h = int(box[2] - px_x0), int(box[3] - px_y0)
        
        mask = self.get_mask(w, h, radius=radius)
        
        # 计算线段在局部坐标系中的范围
        rel_ly0 = int(self.ms.x(line_y - y))
        rel_lh = int(self.ms.x(line_h))
        rel_ly1 = rel_ly0 + rel_lh
        
        # 裁切 Mask
        line_mask_section = mask.crop((0, rel_ly0, px_w, rel_ly1))
        
        # 纯色线段粘贴
        line_layer = Image.new("RGBA", (px_w, rel_lh), fill)
        self.img.paste(line_layer, (px_x0, px_y0 + rel_ly0), mask=line_mask_section)

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont, 
             fill: str = '#FFF', line_height: float = 3.4, limit_width: float = -1):
        """绘制信息列表"""
        lines_new = [limit_text(line, font, limit_width) for line in lines] if limit_width > -1 else lines
        offset = line_height / 2 if len(lines_new) % 2 == 0 else 0
        
        for i in range(len(lines_new)):
            dy = y + (i - len(lines_new) // 2) * line_height + offset
            style = TextStyle(fill=fill, anchor='lm', font=font)
            self.text(x, dy, text=lines_new[i], style=style)

    @lru_cache(maxsize=8)
    def get_mask(self, w: int, h: int, radius: float) -> Image.Image:
        """获取圆角遮罩"""
        mask = Image.new('L', self.ms.xy(w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle(self.ms.size(0, 0, w, h), radius=self.ms.x(radius), fill=255)
        return mask
