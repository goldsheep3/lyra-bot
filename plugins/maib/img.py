import yaml
from pathlib import Path
from enum import IntEnum
from typing import Optional, Tuple, Dict, Literal
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont, ImageChops

from .utils import MaiData, MaiChart, MaiChartAch

# ========================================
# 基础常量
# ========================================

# 模块版本
MODEL_VERSION: str = "260214"

# assets 资源常量
ASSETS_PATH = Path.cwd() / "assets"

# 字体常量
FONT_PATH = ASSETS_PATH / "fonts"
MIS_DB = ImageFont.truetype(FONT_PATH / "MiSans-Demibold.otf", 10.5)
MIS_HE = ImageFont.truetype(FONT_PATH / "MiSans-Heavy.otf", 10.5)
JBM_BD = ImageFont.truetype(FONT_PATH / "JetBrainsMono-Bold.ttf", 10.5)
JBM_EB = ImageFont.truetype(FONT_PATH / "JetBrainsMono-ExtraBold.ttf", 10.5)
NSS_RG = ImageFont.truetype(FONT_PATH / "NotoSansSymbols2-Regular.ttf", 10.5)

# 图片路径常量
IMG_PATH = ASSETS_PATH / "img"
PIC_PATH = ASSETS_PATH / "pic"
DXRATING_PATH = PIC_PATH / "dxrating"
PLATE_PATH = PIC_PATH / "plate"
VER_PATH = PIC_PATH / "ver"

# 基础颜色常量
COLOR_DXSCORE_GN = '#0A5'
COLOR_DXSCORE_OR = '#C72'
COLOR_DXSCORE_GD = '#ED4'
COLOR_THEME = '#64d2ce'


# 难度颜色组
@dataclass
class Difficulty:
    text_title: str
    text_title_cn: str
    bg: str
    frame: str
    text: str
    deep: str
    title_bg: str
    _level_text: Optional[str] = None

    @property
    def level_text(self): return self._level_text if self._level_text else self.text


BASIC = Difficulty("BASIC", "基础", bg='#7E6', frame='#053', text='#FFF', deep='#8D5', title_bg='#2B5')
ADVANCED = Difficulty("ADVANCED", "高级", bg='#FD3', frame='#B41', text='#FFF', deep='#FB1', title_bg='#F92')
EXPERT = Difficulty("EXPERT", "专家", bg='#F88', frame='#C23', text='#FFF', deep='#F9A', title_bg='#F46')
MASTER = Difficulty("MASTER", "大师", bg='#C7F', frame='#618', text='#FFF', deep='#B3D', title_bg='#94E')
REMASTER = Difficulty("Re:MASTER", "宗师",
                      bg='#EDE', frame='#82D', text='#D5F', deep='#FFF', title_bg='#B6F', _level_text='#FFF')
UTAGE = Difficulty("U·TA·GE", "宴·会·场", bg='#E6E', frame='#D0B', text='#FFF', deep='#F6F', title_bg='#F4F')  # 是圆形重复

DIFFICULTIES = [
    None,  # 0 - NONE
    None,  # 1 - EASY
    BASIC,  # 2 - BASIC
    ADVANCED,  # 3 - ADVANCED
    EXPERT,  # 4 - EXPERT
    MASTER,  # 5 - MASTER
    REMASTER,  # 6 - Re:MASTER
    UTAGE  # 7 - UTAGE
]

COLOR_UTAGE_TAG_BG = '#236'
COLOR_UTAGE_TAG_FRAME = '#BEF'
COLOR_BUDDY_TAG_BG = '#411'
COLOR_BUDDY_TAG_FRAME = '#FEA'


# 达成率颜色组
@dataclass
class AchColor:
    fill: str
    stroke: str
    shadow: str


ACH_S = AchColor(fill='#F93', stroke='#C00', shadow='#EB5')
ACH_A = AchColor(fill='#D77', stroke='#834', shadow='#B77')
ACH_B = AchColor(fill='#3AD', stroke='#239', shadow='#58B')


# 评价颜色组
@dataclass
class EvaluateColor:
    fill: str
    shadow: str


EVAL_GN = EvaluateColor(fill='#7D5', shadow='#162')  # FC / FC+
EVAL_GD = EvaluateColor(fill='#FE2', shadow='#A02')  # AP / AP+ / FDX / FDX+
EVAL_BE = EvaluateColor(fill='#6DF', shadow='#038')  # FS / FS+
EVAL_DB = EvaluateColor(fill='#038', shadow='#FFF')  # SYNC PLAY


# 评价类型
class Combo(IntEnum):
    NONE = 0
    FC = 1
    FC_PLUS = 2
    AP = 3
    AP_PLUS = 4


class Sync(IntEnum):
    NONE = 0
    SYNC = 1
    FS = 2
    FS_PLUS = 3
    FDX = 4
    FDX_PLUS = 5


COMBO_DICT = {
    0: (EVAL_GN, '···', '···', '···'),
    1: (EVAL_GN, 'FULL COMBO', 'FC', '全连击'),
    2: (EVAL_GN, 'FULL COMBO +', 'FC+', '全连击+'),
    3: (EVAL_GD, 'ALL PERFECT', 'AP', '完美无缺'),
    4: (EVAL_GD, 'ALL PERFECT +', 'AP+', '完美无缺+'),
}
SYNC_DICT = {
    0: (EVAL_DB, '···', '···', '···'),
    1: (EVAL_DB, 'SYNC PLAY', 'SYNC', '同步游玩'),
    2: (EVAL_BE, 'FULL SYNC', 'FS', '全完同步'),  # 原文如此
    3: (EVAL_BE, 'FULL SYNC +', 'FS+', '全完同步+'),
    4: (EVAL_GD, 'FULL SYNC DX', 'FDX', '完全同步DX'),
    5: (EVAL_GD, 'FULL SYNC DX +', 'FDX+', '完全同步DX+'),
}


# ========================================
# 辅助函数
# ========================================

# 颜色混合函数 (背景色 t，前景色 f)
def bcm(t: str, f: str):
    r1, g1, b1 = (int(t[i] * 2, 16) for i in range(1, 4))
    r2, g2, b2, a = \
        (int(f[i] * 2, 16) for i in range(1, 5)) if len(f) == 5 else (int(f[i:i + 2], 16) for i in range(1, 9, 2))
    alpha = a / 255.0
    r = int(r1 + (r2 - r1) * alpha)
    g = int(g1 + (g2 - g1) * alpha)
    b = int(b1 + (b2 - b1) * alpha)
    return f"#{r:02X}{g:02X}{b:02X}"


# 倍率缩放类
class MS:
    def __init__(self, multiple: int):
        self.multiple = multiple

    def x(self, x: int | float) -> int:
        return int(x * self.multiple)

    def xy(self, x: int | float, y: int | float) -> tuple[int, int]:
        return self.x(x), self.x(y)

    def size(self, x: int | float, y: int | float, w: int | float, h: int | float) -> tuple[int, int, int, int]:
        return self.x(x), self.x(y), self.x(x + w), self.x(y + h)

    def rev(self, x: float) -> float:
        return x / self.multiple

    # 魔法方法：乘运算，将数值和 self.multiple 相乘，返回新 MS 对象
    def __mul__(self, other: int | float) -> 'MS':
        return MS(int(self.multiple * other))


def genre_split_and_get_color(genre: str) -> Tuple[str, str]:
    """分割流派字符串"""
    def is_genre(*args) -> bool: return any(g in genre.lower() for g in args)

    if is_genre('nico', 'ニコ'):
        if '&' in genre:
            genre = genre.replace('&', '$\n')
        elif 'niconico' in genre:
            genre = genre.replace('niconico', 'niconico&\n')
        elif 'ニコニコ' in genre:
            genre = genre.replace('ニコニコ', 'ニコニコ&\n')
        return genre, '#02c8d3'  # niconico&VOCALOID
    elif is_genre('pops', '流行'):
        return genre, '#ff972a'
    elif is_genre('project'):
        return genre, '#ad59ee'
    elif is_genre('game', 'ゲーム', '其他游戏'):
        return genre, '#4be070'
    elif is_genre('maimai', '舞萌'):
        return genre, '#f64849'
    elif is_genre('chunithm'):
        genre = genre.replace('chu', '\nchu')
        return genre, '#3584fe'
    elif is_genre('会', 'TA'):
        return genre, '#dc39b8'
    return genre, COLOR_THEME


# ========================================
# 元件方法
# ========================================


class DrawUnit:
    def __init__(self, img: Image.Image, multiple: MS | int = 8, cn: Literal[0, 1, 2] = 0):
        self.img: Image.Image = img
        self.draw: ImageDraw.ImageDraw = ImageDraw.Draw(self.img)
        self.ms: MS = multiple if isinstance(multiple, MS) else MS(multiple)

        self.cn = cn

    @staticmethod
    def limit_text(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
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
            # 过宽，向左
            while guess_len > 0:
                guess_len -= 1
                current_text = text[:guess_len] + '...'
                if font.getlength(current_text) <= max_width:
                    break
        else:
            # 过窄，向右
            while guess_len < len(text):
                next_text = text[:guess_len + 1] + '...'
                if font.getlength(next_text) > max_width:
                    break
                guess_len += 1
                current_text = next_text

        return current_text

    def _text(self, x: float, y: float, text: str, fill: str, anchor: str, font: ImageFont.FreeTypeFont,
              stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """text 绘制简化方法"""
        xy, sw = self.ms.xy(x, y), self.ms.x(stroke_width)
        self.draw.text(xy, text=text, fill=fill, anchor=anchor, font=font, stroke_width=sw, stroke_fill=stroke_fill)

    def text(self, x: float, y: float, text: str, fill: str, anchor: str, font: ImageFont.FreeTypeFont,
             margin: int = 1, limit: int = -1, stroke: Tuple[float, str] = (0, ''),
             shadow: Tuple[float, str] = (0, ''), shadow2: Tuple[float, str, float] = (0, '', 0)):
        """总的 text 绘制方法"""
        if '\n' in text:
            # 传递多行文字
            self.double_text(x, y, text, fill, anchor, font, margin, limit, stroke, shadow, shadow2)
            return  # 若传递，则不继续往下执行
        text = self.limit_text(text, font, limit) if limit > 0 else text
        if shadow2[0]:
            # 下移阴影层
            self._text(x, y + shadow2[2], text=text, fill=shadow2[1], anchor=anchor, font=font,
                       stroke_fill=shadow2[1], stroke_width=shadow2[0])
        if shadow[0]:
            # 标准阴影层
            self._text(x, y, text=text, fill=shadow[1], anchor=anchor, font=font,
                       stroke_fill=shadow[1], stroke_width=shadow[0])
        # 主文字层
        self._text(x, y, text=text, fill=fill, anchor=anchor, font=font, stroke_fill=stroke[1], stroke_width=stroke[0])

    def double_text(self, x: float, y: float, text: str, fill: str, anchor: str, font: ImageFont.FreeTypeFont,
                    margin: int = 1, limit: int = -1, stroke: Tuple[float, str] = (0, ''),
                    shadow: Tuple[float, str] = (0, ''), shadow2: Tuple[float, str, float] = (0, '', 0)):
        text_list = text.split('\n')
        size = self.ms.rev(font.size)
        line_count = len(text_list)
        _total_height = margin * (line_count - 1) + size * line_count
        first_y = (y - (line_count - 1) / 2 * (size + margin)) if anchor[1:] == 'm' else y
        for i in range(line_count):
            dy = first_y + i * (size + margin)
            self.text(x, dy, text=text_list[i], fill=fill, anchor=anchor, font=font,
                      limit=limit, stroke=stroke, shadow=shadow, shadow2=shadow2)

    def rounded_rect(self, x: float, y: float, w: float, h: float, fill: Optional[str], radius: float,
                     outline: Optional[str] = None, width: float = 0):
        self.draw.rounded_rectangle(self.ms.size(x, y, w, h), radius=self.ms.x(radius), fill=fill,
                                    outline=outline, width=self.ms.x(width))

    def cut_line(self, x: float, y: float, w: float, h: float, radius: float, line_y: float, line_h: float, fill: str):
        box_size = self.ms.size(x, y, w, h)

        # 主图“截取”
        temp_layer = self.img.crop(box_size).convert("RGBA")
        temp_draw = ImageDraw.Draw(temp_layer)

        rel_line_y = self.ms.x(line_y - y)
        rel_line_h = self.ms.x(line_h)
        # temp_layer.width 获取的是像素宽度
        temp_draw.rectangle([0, rel_line_y, temp_layer.width, rel_line_y + rel_line_h], fill=fill)

        # 创建圆角遮罩 (L 模式)
        mask = Image.new('L', temp_layer.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, temp_layer.width, temp_layer.height],
                                    radius=self.ms.x(radius), fill=255)

        self.img.paste(temp_layer, (int(box_size[0]), int(box_size[1])), mask=mask)

    def difficulty(self, x: float, y: float, diff: Difficulty, text: Optional[str] = None, limit_width: float = -1):
        f = MIS_HE.font_variant(size=self.ms.x(4.8))
        if all((not text, self.cn == 2)):
            fs = MIS_HE.font_variant(size=self.ms.x(3.3))
            x1, y1, x2, y2 = f.getbbox(diff.text_title, anchor='lm', stroke_width=self.ms.x(0.8))
            mx2, my2 = self.ms.rev(x2), self.ms.rev(y2)
            self.text(x+mx2+0.5, y+my2, diff.text_title_cn, diff.text, 'ld',
                      fs, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))
        elif text and limit_width > -1:
            # 此处处理文字宽度限制
            text = self.limit_text(text, f, limit_width)
        text = text if text else diff.text_title
        self.text(x, y, text, diff.text, 'lm', f, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))

    def draw_sd_badge(self, x: float, y: float):
        COLOR_SD = '#4AF'

        self.rounded_rect(x, y, 20, 5, fill=COLOR_SD, radius=5)
        offset = 0.6 if self.cn else 0
        font = MIS_HE.font_variant(size=self.ms.x(3 + offset))
        if self.cn:
            text = "标 准"
        else:
            text = "スタンダード"
        self.text(x+10, y+2.5, text, '#FFF', 'mm', font)

    def draw_dx_badge(self, x: float, y: float):
        COLOR_DX = '#F71'
        COLOR_DELUXE = ('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6')

        self.rounded_rect(x, y, 20, 5, fill='#FFF', radius=5)
        offset = 0.4 if self.cn else 0
        font = MIS_HE.font_variant(size=self.ms.x(3.5 + offset))
        if self.cn:
            text = "DX"
            self.text(x+10, y+2.5, text, COLOR_DX, 'mm', font)
        else:
            text = "でらっくす"
            total_text_width = self.ms.rev(font.getlength(text))
            start_x = (x + 10) - (total_text_width / 2)
            current_x = start_x
            center_y = y + 2.5
            for char, color in zip(text, COLOR_DELUXE):
                self.text(current_x, center_y, char, color, 'lm', font)
                char_width = self.ms.rev(font.getlength(char))
                current_x += char_width

    def level(self, x: float, y: float, diff: Difficulty, level: float, plus: bool = False,
              ignore_decimal: bool = False):
        draw = self.draw
        ms = self.ms

        f = f"{str(int(level // 1)).replace('0', 'O'):>2}"  # 整数部分
        d = str(round(level % 1 * 10)).replace('0', 'O')  # 小数部分

        # 等级 `LV`
        if self.cn == 2:
            draw.text(ms.xy(x - 1, y), text="等级", fill=diff.frame, anchor='ls',
                      font=MIS_DB.font_variant(size=ms.x(3)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x - 1, y), text="等级", fill=diff.level_text, anchor='ls',
                      font=MIS_DB.font_variant(size=ms.x(3)))
        else:
            draw.text(ms.xy(x, y), text="LV", fill=diff.frame, anchor='ls', font=JBM_BD.font_variant(size=ms.x(4)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x, y), text="LV", fill=diff.level_text, anchor='ls', font=JBM_BD.font_variant(size=ms.x(4)))
        # 等级 `xx.x`
        draw.text(ms.xy(x + 6, y), text=f, fill=diff.frame, anchor='ls', font=JBM_BD.font_variant(size=ms.x(6)),
                  stroke_width=ms.x(0.5), stroke_fill=diff.frame)
        draw.text(ms.xy(x + 6, y), text=f, fill=diff.level_text, anchor='ls', font=JBM_BD.font_variant(size=ms.x(6)))
        if not ignore_decimal:
            draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.frame, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(5)), stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.level_text, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(5)))
        # 等级 `+`
        if plus:
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.frame, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(3.5)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.level_text, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(3.5)))

    def ach_frame(self, x: float, y: float, diff: Difficulty):
        text = " 达成率" if self.cn == 2 else " ACHIEVEMENT"

        self.rounded_rect(x, y, 60, 14, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=text, fill=diff.frame, anchor='la', font=MIS_HE.font_variant(size=self.ms.x(2)))

    def ach_value(self, x: float, y: float, ach_percent: float, color: Optional[AchColor] = None):
        if -100 < ach_percent < 1000:
            text = f"{ach_percent:.4f}%".replace('0', 'O').rjust(9)
            if not color:
                if ach_percent >= 97:
                    color = ACH_S
                elif ach_percent >= 80:
                    color = ACH_A
                else:
                    color = ACH_B
        else:
            text = " --.----%"
            color = ACH_B

        self.text(x, y, text=text, fill=color.fill, anchor='la', font=JBM_EB.font_variant(size=self.ms.x(10)),
                  shadow=(0.4, color.shadow), stroke=(0.35, color.stroke))

    def ach(self, x: float, y: float, diff: Difficulty, ach_percent: float, color: Optional[AchColor] = None):
        self.ach_frame(x=x, y=y, diff=diff)
        self.ach_value(x=x + 2.8, y=y + 1.5, ach_percent=ach_percent, color=color)

    @staticmethod
    def _dxscore(cn_level: Literal[0, 1, 2], score: int, max_score: int, star_count: int) -> Tuple[str, str, str, str]:
        title = {0: " でらっくスコア", 1: " DXSCORE", 2: " DX分数"}[cn_level]
        text = f"{score} / {max_score}"
        # Color
        if star_count == 5:
            color = COLOR_DXSCORE_GD
        elif star_count >= 3:
            color = COLOR_DXSCORE_OR
        else:
            color = COLOR_DXSCORE_GN
        star_text = "✦ " * star_count if 0 <= star_count <= 5 else ""
        return title, text, star_text.strip(), color

    def dxscore(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Difficulty):
        title, text, star_text, star_color = self._dxscore(cn_level=self.cn, score=score, max_score=max_score,
                                                           star_count=star_count)

        self.rounded_rect(x, y, 24, 9, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=title, fill=COLOR_DXSCORE_GN, anchor='la', font=MIS_HE.font_variant(size=self.ms.x(2)))
        self.text(x + 12, y + 4.5, text=text, fill='#333', anchor='mm', font=MIS_DB.font_variant(size=self.ms.x(3)))
        self.text(x + 12, y + 6, text=star_text, fill=star_color, anchor='ma',
                  font=NSS_RG.font_variant(size=self.ms.x(2.2)))

    def dxscore_lite(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Difficulty):
        title, text, star_text, star_color = self._dxscore(cn_level=self.cn, score=score, max_score=max_score,
                                                           star_count=star_count)

        self.rounded_rect(x, y, 42, 3, fill=bcm(diff.bg, '#FFF9'), radius=2)
        self.text(x + 0.5, y + 1.5, text=title, fill=COLOR_DXSCORE_GN, anchor='lm',
                  font=MIS_HE.font_variant(size=self.ms.x(2)))
        self.text(x + 40, y + 1.5, text=text, fill='#333', anchor='rm', font=MIS_DB.font_variant(size=self.ms.x(2.5)))
        self.text(x + 20, y + 1.8, text=star_text, fill=star_color, anchor='mm',
                  font=NSS_RG.font_variant(size=self.ms.x(2.2)))

    def evaluate(self, x: float, y: float, text: str, color: EvaluateColor, offset: float = 0):
        self.text(x, y, text=text, fill=color.fill, anchor='lm', font=MIS_HE.font_variant(size=self.ms.x(3 + offset)),
                  stroke=(0.65, color.shadow), shadow=(0.5, color.shadow))

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont, fill='#FFF',
              line_height: float = 3.4, limit_width: float = -1):
        lines_new = [self.limit_text(line, font, limit_width) for line in lines] if limit_width > -1 else lines
        offset = line_height / 2 if len(lines_new) % 2 == 0 else 0  # 偶数行偏移
        for i in range(len(lines_new)):
            dy = y + (i - len(lines_new) // 2) * line_height + offset
            self.text(x, dy, text=lines_new[i], fill=fill, anchor='lm', font=font)

    def image(self, x: float, y: float, w: float, h: float, png: Image.Image | Path, radius: float = 1.5,
              outline: Optional[str] = None, outline_width: float = 0):
        try:
            overlay = (png if isinstance(png, Image.Image) else Image.open(png)).convert('RGBA')
            overlay = overlay.resize(self.ms.xy(w, h), Image.Resampling.LANCZOS)
            alpha = overlay.getchannel('A')

            mask = Image.new('L', overlay.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, overlay.size[0], overlay.size[1]), radius=self.ms.x(radius), fill=255)
            combined_mask = ImageChops.darker(mask, alpha)

            self.img.paste(overlay, self.ms.xy(x, y), mask=combined_mask)

        except (FileNotFoundError, AttributeError, Exception):
            return

        # 绘制边框（即使图片加载失败）
        if outline and outline_width > 0:
            self.draw.rounded_rectangle(self.ms.size(x, y, w, h), radius=self.ms.x(radius),
                                        outline=outline, width=self.ms.x(outline_width))


# ========================================
# 组装工厂
# ========================================


class DrawFactory:

    def __init__(self, width: int, height: int, ms_multiple: int | MS = 10, cn_level: Literal[0, 1, 2] = 0):
        ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
        self.ms = ms  # 缩放倍率

        # 预生成字体
        self.font_mdb = {k: MIS_DB.font_variant(size=ms.x(k)) for k in range(2, 15)}
        # 背景图片
        img = Image.open(IMG_PATH / "bakamai.png").convert('RGBA')
        self.img = img.resize(ms.xy(width, height), Image.Resampling.LANCZOS)

        # 绘图单元
        self.cn_level = cn_level
        self.du = DrawUnit(self.img, multiple=ms, cn=cn_level)

    def get_image(self) -> Image.Image:
        """获取绘制完成的图像"""
        return self.img

    def chart_box(self, x, y, chart: MaiChart, cabinet_dx: bool, plus_level: int = 6,
                  is_utage: bool = False) -> Tuple[int, int]:
        """组件：谱面信息框"""
        du = self.du
        diff = DIFFICULTIES[chart.difficulty]

        width, height = 108, 36
        # noinspection DuplicatedCode
        du.rounded_rect(x, y, width, height, radius=4, fill=diff.bg)
        du.cut_line(x, y, width, height, radius=4, line_y=y + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(x, y, width, height, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        du.difficulty(x + 2.5, y + 4.3, diff)
        du.draw_dx_badge(x + 85, y + 2) if cabinet_dx else du.draw_sd_badge(x + 85, y + 2)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(x + 64, y + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        du.ach(x + 2, y + 9, diff, chart.ach.achievement)
        dxs, dxs_max, dxs_star = chart.ach.dxscore_tuple
        du.dxscore(x + 38, y + 25, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        c, t, tl, tc = COMBO_DICT[chart.ach.combo]
        du.evaluate(x + 3, y + 27, text=tc if self.du.cn == 2 else t, color=c)
        c, t, tl, tc = SYNC_DICT[chart.ach.sync]
        du.evaluate(x + 3, y + 32, text=tc if self.du.cn == 2 else t, color=c)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.diving_fish_lv}" if chart.diving_fish_lv else '',
        ]

        du.rounded_rect(x + 64, y + 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
        du.infos(x + 65.5, y + 21.65, lines=(info_line5 + [''] * 5)[:5], line_height=4.5, limit_width=-1,
                 font=MIS_DB.font_variant(size=self.ms.x(3.2)))

        return width, height

    def chart_box_lite(self, x, y, chart: MaiChart, cabinet_dx: bool, plus_level: int = 6,
                       is_utage: bool = False) -> Tuple[int, int]:
        """组件：谱面信息框 Lite"""
        du = self.du
        diff = DIFFICULTIES[chart.difficulty]

        width, height = 108, 26
        # noinspection DuplicatedCode
        du.rounded_rect(x, y, width, height, radius=4, fill=diff.bg)
        du.cut_line(x, y, width, height, radius=4, line_y=y + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(x, y, width, height, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        du.difficulty(x + 2.5, y + 4.3, diff)
        du.draw_dx_badge(x + 85, y + 2) if cabinet_dx else du.draw_sd_badge(x + 85, y + 2)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(x + 64, y + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        du.ach(x + 46, y + 9, diff, chart.ach.achievement)
        dxs, dxs_max, dxs_star = chart.ach.dxscore_tuple
        du.dxscore_lite(x + 2, y + 21, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        c, t, tl, tc = COMBO_DICT[chart.ach.combo]
        du.evaluate(x + 3, y + 12, text=tc if self.du.cn == 2 else t, color=c)
        c, t, tl, tc = SYNC_DICT[chart.ach.sync]
        du.evaluate(x + 3, y + 17, text=tc if self.du.cn == 2 else t, color=c)

        return width, height


class DrawInfo(DrawFactory):
    """实现 `info11951` 图像的绘制"""

    def __init__(self, maidata: MaiData, version_config: Dict[int, str], multiple: float = 1,
                 cn_level: Literal[0, 1, 2] = 0):
        super().__init__(width=240, height=240, ms_multiple=int(10 * multiple), cn_level=cn_level)
        self.maidata = maidata
        self.ver_cfg = version_config
        self._info()

    def _info(self):
        """实现 `info11951` 图像的绘制"""
        x, y = 10, 10
        width = 220
        margin = 5
        du = self.du
        maidata = self.maidata

        # ========== Module.1 曲绘和基本信息 ==========
        # 曲绘
        cover_size = 54
        du.image(x, y, cover_size, cover_size, radius=5, outline='#FFF', outline_width=1, png=maidata.image)
        t = cover_size + margin
        # 标题
        du.text(x + t, y, text=maidata.title, fill='#FFF', anchor='la',
                font=MIS_HE.font_variant(size=self.ms.x(11)))
        # 艺术家
        du.text(x + t, y + 14, text=maidata.artist, fill='#FFF', anchor='la', font=self.font_mdb[5])
        # ShortID, BPM
        du.text(x + t, y + 23, text=f"ID {maidata.shortid}", fill='#FFF', anchor='la', font=self.font_mdb[6])
        du.text(x + t + 30, y + 23, text=f"BPM {maidata.bpm}", fill='#FFF', anchor='la', font=self.font_mdb[6])
        # Genre, Version
        gvv_title = y + 34
        gvv_la = gvv_title + 5
        gvv_mm = gvv_la + 9

        du.text(x+t, gvv_title, text="流派", fill='#FFF', anchor='la', font=self.font_mdb[4])
        du.text(x+t+38, gvv_title, text="JP", fill='#FFF', anchor='la', font=self.font_mdb[4])
        du.text(x+t+73, gvv_title, text="CN", fill='#FFF', anchor='la', font=self.font_mdb[4])

        # Genre
        genre_text, genre_fill = genre_split_and_get_color(maidata.genre)
        du.text(x+t+17, gvv_mm, text=genre_text, fill='#FFF', anchor='mm', font=self.font_mdb[5],
                shadow=(1.5, '#FFF'))
        du.text(x+t+17, gvv_mm, text=genre_text, fill=genre_fill, anchor='mm', font=self.font_mdb[5],
                shadow=(1, '#FFF'))
        # JP
        ver_jp_path = VER_PATH / f"{maidata.version}.png"
        if ver_jp_path.exists():
            du.image(x+t+38, gvv_la, 34, 18, radius=0, png=ver_jp_path)
        else:
            text = self.ver_cfg.get(maidata.version, str(maidata.version))
            text = text.replace(' ', '\n')
            du.text(x+t+38+19, gvv_mm, text=text,
                    fill='#FFF', anchor='mm', font=self.font_mdb[5])
        # CN: 需要考虑不存在
        if maidata.version_cn:
            ver_cn_path = VER_PATH / f"{maidata.version_cn}.png"
            if ver_cn_path.exists():
                du.image(x+t+73, gvv_la, 34, 18, radius=0, png=ver_cn_path)
            else:
                text = self.ver_cfg.get(maidata.version_cn, str(maidata.version_cn))
                text = text.replace(' ', '\n')
                du.text(x+t+73+19, gvv_mm, text=text,
                        fill='#FFF', anchor='mm', font=self.font_mdb[5])
        else:
            du.text(x + t + 91, gvv_mm, text="X\n", fill='#F00', anchor='mm', font=self.font_mdb[4],
                    stroke=(0.8, '#FFF'))
            du.text(x + t + 91, gvv_mm, text="\n国服无此乐曲", fill='#FFF', anchor='mm', font=self.font_mdb[4])

        y += cover_size + margin

        # ========== Module.2 乐曲别名数据 ==========
        if maidata.aliases:
            line_height = 7
            padding = 5

            # 绘制标题
            du.text(x, y, text="这首歌的别名包括：", fill='#FFF', anchor='la', font=self.font_mdb[5])
            y += line_height
            current_x_offset = 0

            for alias in maidata.aliases:
                alias_width = self.ms.rev(self.font_mdb[5].getlength(alias))
                if current_x_offset + alias_width > width:
                    y += line_height
                    current_x_offset = 0

                du.text(x + current_x_offset, y, text=alias, fill='#FFF', anchor='la', font=self.font_mdb[5])
                current_x_offset += alias_width + padding

            y += line_height + margin

        # ========== Module.3 详细谱面数据 ==========
        now_x = x
        for i, chart in enumerate(maidata.charts):
            if not chart.ach:
                chart.ach = MaiChartAch(-101, 0, 0, 0, 0)
            if chart.difficulty >= 4:
                _w, h = self.chart_box(now_x, y, chart, cabinet_dx=maidata.is_cabinet_dx)
            else:
                _w, h = self.chart_box_lite(now_x, y, chart, cabinet_dx=maidata.is_cabinet_dx)
            if (i + 1) % 2 == 1:
                now_x = 123
                if len(maidata.charts) - i == 1:
                    y += h + margin  # 向下传递
            else:
                now_x = 10
                y += h + margin

        # ========== Module.4 版权信息 ==========
        CR_INFO = "    |    ".join([
            "Powered by LyraBot (@GoldSheep3)",
            f"Version: {MODEL_VERSION}",
            "Designer by Bakamai⑨'s Members",
            "Background Artist by @银色山雾"
        ])
        du.rounded_rect(0, y, 240, 6, fill='#313d7c', radius=0)  # 后续修改为遮罩渐变合成
        du.text(120, y + 3, text=CR_INFO, fill=COLOR_THEME, anchor='mm',
                font=MIS_DB.font_variant(size=self.ms.x(3.5)))
        # 切割
        self.img = self.img.crop((0, 0, self.ms.x(240), self.ms.x(y + 6)))
        self.img = self.img.convert('RGB')


# todo info_box_mini 等元件的新写法转换
def info_box_mini(
        diff: int | Difficulty,
        level: float,
        achievement: float,
        combo: Optional[Combo | int] = None,
        sync: Optional[Sync | int] = None,
        all_cn: bool = False,
        ms_multiple: int | MS = 10,
) -> Image.Image:
    """InfoBox Mini: 适用于 InfoBoard 信息板显示非目标查询曲目信息的曲目细节"""
    # 参数处理
    ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
    diff = diff if isinstance(diff, Difficulty) else DIFFICULTIES[diff]

    img = Image.new('RGBA', (ms.x(43) + 2, ms.x(16) + 2), color='#FFFFFF00')
    # 绘图单元
    du = DrawUnit(img, multiple=ms)
    ms_multiple_value = (ms_multiple.multiple if isinstance(ms_multiple, MS) else ms_multiple)
    du_lite_1 = DrawUnit(img, multiple=int(ms_multiple_value / 1.25))
    du_lite_2 = DrawUnit(img, multiple=int(ms_multiple_value / 1.5))

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 43, 16), radius=ms.x(2.5), fill=diff.bg, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    # 难度 / 定数
    du_lite_1.difficulty(2, 4, diff, text=f"{diff.text_title_cn if all_cn else diff.text_title}  {level:.1f}")

    # 达成率
    du_lite_2.ach_value(16, 11.5, ach_percent=achievement)

    du_evaluate = du_lite_2 if all_cn else du_lite_1
    # FC/FC+/AP/AP+
    if combo:
        c, t, tl, tc = COMBO_DICT[combo]
        du_evaluate.evaluate(2, 15, text=tc if all_cn else tl, color=c)
    # SYNC/FS/FS+/FDX/FDX+
    if sync:
        c, t, tl, tc = SYNC_DICT[sync]
        du_evaluate.evaluate(2, 21, text=tc if all_cn else tl, color=c)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 43, 16), radius=ms.x(2.5), fill=None, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    return img


def b50_box(
        diff: int | Difficulty,
        cabinet_dx: bool,
        short_id: int,
        title: str,
        level: float,
        ra: int,
        achievement: float,
        bg_path: Path,
        dxscore: Tuple[int, int, int],
        new_song: bool,
        index: int,
        combo: Optional[Combo | int] = None,
        sync: Optional[Sync | int] = None,
        all_cn: bool = False,
        ms_multiple: int | MS = 10,
) -> Image.Image:
    ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
    diff = diff if isinstance(diff, Difficulty) else DIFFICULTIES[diff]

    img = Image.new('RGBA', (ms.x(91) + 2, ms.x(36) + 2), color='#FFFFFF00')

    # 绘图单元
    du = DrawUnit(img, multiple=ms)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 91, 36), radius=ms.x(2.5), fill=diff.bg, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    # 标题栏
    du.draw.rectangle(ms.size(0, 2, 91, 5), fill=diff.title_bg)

    # 标题栏文字
    limit_t = MIS_HE.font_variant(size=ms.x(4.6)).getlength('I' * 62)  # 实测结果 todo 修改为width计算
    du.difficulty(2, 4.2, diff, text=f'#{short_id}  {title}', limit_width=limit_t)

    # 曲绘
    du.image(2, 9, 25, 25, radius=1.5, outline=diff.deep, outline_width=0.3, png=bg_path)

    # 谱面类型 (SD/DX) - 进行了额外的 MS 缩放
    tv = ms.multiple * 1
    ms.multiple = tv * 0.5
    tx, ty = MS(2).xy(1.25, 8.5)
    du.draw_dx_badge(tx, ty) if cabinet_dx else du.draw_sd_badge(tx, ty)
    ms.multiple = tv * 1

    # 达成率
    du.ach(29, 9, diff, ach_percent=achievement)

    # DXSCORE
    du.dxscore(65, 25, score=dxscore[0], max_score=dxscore[1], star_count=dxscore[2], diff=diff)

    offset = 1 if all_cn else 0
    # FC/FC+/AP/AP+
    if combo:
        c, t, tl, tc = COMBO_DICT[combo]
        du.evaluate(30, 27, text=tc if all_cn else tl, color=c)
    # SYNC/FS/FS+/FDX/FDX+
    if sync:
        c, t, tl, tc = SYNC_DICT[sync]
        du.evaluate(30, 32, text=tc if all_cn else tl, color=c, offset=offset)

    # INFO
    du.rounded_rect(43, 25, 20, 9, fill=bcm(diff.bg, '#0009'), radius=1.5)
    du.infos(44.5, 29.5, lines=[f'b{'1' if new_song else '3'}5#{index}', f'{level:.1f} > {ra}'], line_height=3.4,
             font=MIS_DB.font_variant(size=ms.x(2.5)))

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 91, 36), radius=ms.x(2.5), fill=None, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    return img


# 示例用法
if __name__ == "__main__":
    maidata = MaiData(
        shortid=101,
        title="おちゃめ機能",
        bpm=150,
        artist="ゴジマジP",
        genre="niconicoボーカロイド",
        cabinet='SD',
        version=28,
        version_cn=2022,
        converter="PreData",
        img_path=Path(r"C:\Users\sanji\AppData\Roaming\JetBrains\PyCharm2025.3\scratches\bg.png"),
        aliases=["ochamekinou", "五月病", "天真浪漫机能", "天真烂漫机能", "机能"] * 5
    )

    for i in range(2, 7):
        maidata.set_chart(MaiChart(
            difficulty=i,
            lv=3.6 + i * 1.8,
            des="chartDes",
            ach=MaiChartAch(
                achievement=70 + 2.63 ** (i/1.7),
                dxscore=200 + i * 100,
                dxscore_max=300 + i * 100,
                combo=Combo(i - 2),
                sync=Sync(i - 1)
            )
        ))

    config_yaml_path = Path.cwd() / "versions.yaml"
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        ver_cfg: Dict[int, str] = yaml.safe_load(f)

    target = DrawInfo(maidata, ver_cfg, multiple=0.3, cn_level=1).get_image()

    from PIL import ImageTk
    import tkinter as tk

    root = tk.Tk()
    tk_image = ImageTk.PhotoImage(target)
    label = tk.Label(root, image=tk_image)
    label.pack()
    label.image = tk_image
    root.mainloop()
