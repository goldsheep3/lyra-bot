"""
image_gen.components.base
绘图组件基类
"""
from dataclasses import dataclass
from typing import Optional, Callable

from PIL import Image, ImageDraw, ImageFont

from ..utils import MS
from ..tools import limit_text


__all__ = ['TextDrawStyle', 'Drawer']


@dataclass(frozen=True)
class TextDrawStyle:
    """文本样式配置"""
    font: ImageFont.FreeTypeFont
    anchor: str
    margin: float = 1.0
    limit: Optional[int] = None

    fill: Optional[str] = None
    stroke: Optional[str] = None
    stroke_width: float = 0.0
    shadow: Optional[str] = None
    shadow_width: float = 0.0
    shadow2: Optional[str] = None
    shadow2_width: float = 0.0
    shadow2_offset: float = 0.0


class Drawer:
    """基础绘制工具类"""
    
    def __init__(self, img: Image.Image, draw: Optional[ImageDraw.ImageDraw] = None, *, ms: MS = MS()):
        """初始化绘制器"""
        self.img = img
        self.draw = draw if draw is not None else ImageDraw.Draw(img)
        self.ms = ms

    def _text(self, x: float, y: float, text: Optional[str], fill: Optional[str], 
              anchor: str, font: ImageFont.FreeTypeFont,
              stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """基础文本绘制方法"""
        xy, sw = self.ms.xy(x, y), self.ms.x(stroke_width)
        text = text if text else ''
        self.draw.text(xy, text=text, fill=fill, anchor=anchor, font=font, 
                      stroke_width=sw, stroke_fill=stroke_fill)
        return

    def _multi_text(self, x: float, y: float, text: str, *, tds: TextDrawStyle):
        """多行文本绘制"""
            
        text_list = text.split('\n')
        size = self.ms.rev(round(tds.font.size))
        first_y = (y - (len(text_list) - 1) / 2 * (size + tds.margin)) if tds.anchor[1:] == 'm' else y

        for index, line in enumerate(text_list):
            dy = first_y + index * (size + tds.margin)
            # 由于是单行文本，直接调用即可，不会形成传递链
            self.text(x, dy, text=line, tds=tds)
        return

    def text(self, x: float, y: float, text: str, *, tds: TextDrawStyle):
        """文本绘制"""
        # 多行文本传递
        if '\n' in text:
            return self._multi_text(x, y, text, tds=tds)

        # 单行文本绘制
        text = text if tds.limit is None else limit_text(text, tds.font, tds.limit)
        # 下移阴影层
        if text and tds.shadow2_width:
            self._text(
                x, y + tds.shadow2_offset,
                text=text, fill=tds.shadow2, anchor=tds.anchor, font=tds.font,
                stroke_fill=tds.shadow2, stroke_width=tds.shadow2_width
            )
        # 标准阴影层
        if text and tds.shadow_width:
            self._text(
                x, y,
                text=text, fill=tds.shadow, anchor=tds.anchor, font=tds.font,
                stroke_fill=tds.shadow, stroke_width=tds.shadow_width
            )
        if text:
            # 主文本层
            self._text(
                x, y,
                text=text, fill=tds.fill, anchor=tds.anchor, font=tds.font,
                stroke_fill=tds.stroke, stroke_width=tds.stroke_width
            )
        return

    def rounded_rect(self, x: float, y: float, w: float, h: float, fill: Optional[str], 
                    radius: float, outline: Optional[str] = None, width: float = 0):
        """绘制圆角矩形"""
        if radius <= 0:
            self.draw.rectangle(
                self.ms.size(x, y, w, h),
                fill=fill,
                outline=outline, width=self.ms.x(width))
            return
        self.draw.rounded_rectangle(
            self.ms.size(x, y, w, h),
            radius=self.ms.x(radius), fill=fill,
            outline=outline, width=self.ms.x(width)
        )
        return

    def capsule(self, x: float, y: float, w: float, h: float, fill: Optional[str],
                outline: Optional[str] = None, width: float = 0):
        """绘制胶囊形状"""
        x, y = self.ms.xy(x, y)
        w, h =self.ms.xy(w, h)
        radius = round(min(w, h) / 2)
        self.draw.rounded_rectangle(
            (x, y, x + w, y + h), 
            radius=radius, fill=fill, outline=outline, width=self.ms.x(width)
        )

    def cut_line(self, x: float, y: float, w: float, h: float, radius: float, 
                line_y: float, line_h: float, fill: str):
        """绘制切割线条（在圆角矩形内）"""
        # TODO 后续删除，最终形成图片进行手动圆角裁切，而不是裁切后覆盖
        box = self.ms.size(x, y, w, h)
        px_x0, px_y0 = int(box[0]), int(box[1])
        px_w, _px_h = int(box[2] - px_x0), int(box[3] - px_y0)
        
        mask = self.get_mask(w, h, radius=radius, ms=self.ms)
        
        # 计算线段在局部坐标系中的范围
        rel_ly0 = int(self.ms.x(line_y - y))
        rel_lh = int(self.ms.x(line_h))
        rel_ly1 = rel_ly0 + rel_lh
        
        # 裁切 Mask
        line_mask_section = mask.crop((0, rel_ly0, px_w, rel_ly1))
        
        # 纯色线段粘贴
        line_layer = Image.new("RGBA", (px_w, rel_lh), fill)
        self.img.paste(line_layer, (px_x0, px_y0 + rel_ly0), mask=line_mask_section)
        return

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont, 
             fill: str = '#FFF', limit: Optional[float] = None):
        """绘制信息列表"""
        line_height = self.ms.rev(round(font.size)) * 1.1
        lines_new = [limit_text(line, font, limit) for line in lines] if limit is not None else lines
        offset = line_height / 2 if len(lines_new) % 2 == 0 else 0
        
        for index, line in enumerate(lines_new):
            dy = y + (index - len(lines_new) // 2) * line_height + offset
            tds = TextDrawStyle(fill=fill, anchor='lm', font=font)
            self.text(x, dy, text=line, tds=tds)
        return

    @classmethod
    def get_mask(cls, w: float, h: float, radius: float, *, ms: MS = MS()) -> Image.Image:
        """获取圆角遮罩"""
        mask = Image.new('L', ms.xy(w, h), 0)
        drawer = cls(mask, ms=ms)
        drawer.rounded_rect(0, 0, w, h, fill='#FFFFFF', radius=radius)
        return mask
