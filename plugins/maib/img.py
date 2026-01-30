import yaml
from pathlib import Path
from enum import IntEnum
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from .utils import MaiData, MaiChart, MaiChartAch

# ========================================
# 基础常量
# ========================================

# 模块版本
MODEL_VERSION: str = "260127"

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


BASIC = Difficulty("BASIC", "基础",        bg='#7E6', frame='#053', text='#FFF', deep='#8D5', title_bg='#2B5')
ADVANCED = Difficulty("ADVANCED", "高级",  bg='#FD3', frame='#B41', text='#FFF', deep='#FB1', title_bg='#F92')
EXPERT = Difficulty("EXPERT", "专家",      bg='#F88', frame='#C23', text='#FFF', deep='#F9A', title_bg='#F46')
MASTER = Difficulty("MASTER", "大师",      bg='#C7F', frame='#618', text='#FFF', deep='#B3D', title_bg='#94E')
REMASTER = Difficulty("Re:MASTER", "宗师",
                      bg='#EDE', frame='#82D', text='#D5F', deep='#FFF', title_bg='#B6F', _level_text='#FFF')
UTAGE = Difficulty("U·TA·GE", "宴·会·场",  bg='#E6E', frame='#D0B', text='#FFF', deep='#F6F', title_bg='#F4F')  # 是圆形重复

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
    0: (None, '', '', ''),
    1: (EVAL_GN, 'FULL COMBO', 'FC', '全连击'),
    2: (EVAL_GN, 'FULL COMBO+', 'FC+', '全连击+'),
    3: (EVAL_GD, 'ALL PERFECT', 'AP', '完美无缺'),
    4: (EVAL_GD, 'ALL PERFECT+', 'AP+', '完美无缺+'),
}
SYNC_DICT = {
    0: (None, '', '', ''),
    1: (EVAL_DB, 'SYNC PLAY', 'SYNC', '同步游玩'),
    2: (EVAL_BE, 'FULL SYNC', 'FS', '全完同步'),  # 原文如此
    3: (EVAL_BE, 'FULL SYNC+', 'FS+', '全完同步+'),
    4: (EVAL_GD, 'FULL SYNC DX', 'FDX', '完全同步DX'),
    5: (EVAL_GD, 'FULL SYNC DX+', 'FDX+', '完全同步DX+'),
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


# ========================================
# 元件方法
# ========================================


class DrawUnit:
    def __init__(self, img: Image.Image, multiple: MS | int = 8):
        self.img: Image.Image = img
        self.draw: ImageDraw.ImageDraw = ImageDraw.Draw(self.img)
        self.ms: MS = multiple if isinstance(multiple, MS) else MS(multiple)

    def text(self, x: float, y: float, text: str, fill: str, anchor: str, font: ImageFont.FreeTypeFont,
             size: float = -1, stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """text 绘制简化方法"""
        xy, sz, sw = self.ms.xy(x, y), self.ms.x(size), self.ms.x(stroke_width)
        font = font.font_variant(size=sz) if size > 0 else font
        self.draw.text(xy, text=text, fill=fill, anchor=anchor, font=font, stroke_width=sw, stroke_fill=stroke_fill)

    def limit_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: float, size: float = -1,
                   stroke_width: float = 0) -> str:
        font = font.font_variant(size=self.ms.x(size)) if size > 0 else font
        full_width = self.get_text_length(text, font, stroke_width, size)
        if full_width <= max_width or len(text) < 4 or max_width < 0:
            return text

        # 启发式预测截断位置
        avg_char_w = full_width / len(text)
        guess_len = int((max_width - avg_char_w * 3) / avg_char_w)
        guess_len = max(0, min(len(text), guess_len))
        # 单侧探测与微调
        current_text = text[:guess_len] + '...'
        current_width = self.get_text_length(current_text, font, size, stroke_width)

        if current_width > max_width:
            # 过宽，向左
            while guess_len > 0:
                guess_len -= 1
                current_text = text[:guess_len] + '...'
                if self.get_text_length(current_text, font, size, stroke_width) <= max_width:
                    break
        else:
            # 过窄，向右
            while guess_len < len(text):
                next_text = text[:guess_len + 1] + '...'
                if self.get_text_length(next_text, font, size, stroke_width) > max_width:
                    break
                guess_len += 1
                current_text = next_text

        return current_text

    def shadow_text(self, x: float, y: float, text: str, fill: str, anchor: str, font: ImageFont.FreeTypeFont,
                    size: float, shadow_fill: str, shadow_width: float,
                    stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """阴影 text 绘制简化方法"""
        self.text(x, y, text=text, fill=shadow_fill, anchor=anchor, font=font, size=size,
                  stroke_fill=shadow_fill, stroke_width=shadow_width)
        self.text(x, y, text=text, fill=fill, anchor=anchor, font=font, size=size,
                  stroke_fill=stroke_fill, stroke_width=stroke_width)

    def get_text_length(self, text: str, font: ImageFont.FreeTypeFont, size: float = -1,
                        stroke_width: float = 0) -> float:
        font = font.font_variant(size=self.ms.x(size)) if size > 0 else font
        return font.getlength(text) + self.ms.x(stroke_width)

    def rounded_rect(self, x: float, y: float, w: float, h: float, fill: str, radius: float,
                     outline: Optional[str] = None, width: float = 0):
        self.draw.rounded_rectangle(self.ms.size(x, y, w, h), radius=self.ms.x(radius), fill=fill,
                                    outline=outline, width=self.ms.x(width))

    def difficulty(self, x: float, y: float, diff: Difficulty, text: Optional[str] = None, limit_width: float = -1,
                   all_cn: bool = False):
        if all_cn and (not text):
            _, _, x2, y2 = self.draw.textbbox(self.ms.xy(x, y), text=diff.text_title, anchor='lm',
                                              font=MIS_HE.font_variant(size=self.ms.x(4.6)))
            mx2, my2 = self.ms.rev(x2), self.ms.rev(y2)
            self.text(mx2 + 1.2, my2 + 1.3, diff.text_title_cn, diff.frame, 'ld', MIS_HE, 3.3, diff.frame, 0.8)
            self.shadow_text(mx2 + 1.2, my2 + 0.6, diff.text_title_cn, diff.text, 'ld', MIS_HE, 3.3, diff.deep, 0.6)
        elif text and limit_width > -1:
            # 此处处理文字宽度限制
            text = self.limit_text(text, MIS_HE, limit_width, 4.6, stroke_width=0.8)
        text = text if text else diff.text_title
        self.text(x, y + 0.7, text, diff.frame, 'lm', MIS_HE, 4.6, diff.frame, 0.8)
        self.shadow_text(x, y, text, diff.text, 'lm', MIS_HE, 4.6, diff.deep, 0.8)

    def sd(self, x: float, y: float, cn: bool = False):
        COLOR_SD = '#4AF'
        text = "标 准" if cn else "スタンダード"
        offset = 0.4 if cn else 0

        self.rounded_rect(x, y, 20, 5, fill=COLOR_SD, radius=5)
        self.text(x + 10, y + 2.5, text, '#FFF', 'mm', MIS_HE, 2.8 + offset)

    def dx(self, x: float, y: float, cn: bool = False):
        # todo: DX 的多彩机制
        text = "DX" if cn else "でらっくす"
        offset = 0.4 if cn else 0

        self.rounded_rect(x, y, 20, 5, fill='#FFF', radius=5)
        self.text(x + 10, y + 2.5, text, '#F71', 'mm', MIS_HE, 2.8 + offset)

    def level(self, x: float, y: float, diff: Difficulty, level: float, plus: bool = False,
              all_cn: bool = False):
        draw = self.draw
        ms = self.ms

        f = f"{str(int(level // 1)).replace('0', 'O'):>2}"  # 整数部分
        d = str(round(level % 1 * 10)).replace('0', 'O')  # 小数部分

        # 等级 `LV`
        if all_cn:
            draw.text(ms.xy(x - 1, y), text="等级", fill=diff.frame, anchor='ls', font=MIS_DB.font_variant(size=ms.x(3)),
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
        draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.frame, anchor='ls', font=JBM_BD.font_variant(size=ms.x(5)),
                  stroke_width=ms.x(0.5), stroke_fill=diff.frame)
        draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.level_text, anchor='ls',
                  font=JBM_BD.font_variant(size=ms.x(5)))
        # 等级 `+`
        if plus:
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.frame, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(3.5)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.level_text, anchor='ls',
                      font=JBM_BD.font_variant(size=ms.x(3.5)))

    def ach_frame(self, x: float, y: float, diff: Difficulty, all_cn: bool = False):
        text = " 达成率" if all_cn else " ACHIEVEMENT"

        self.rounded_rect(x, y, 60, 14, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=text, fill=diff.frame, anchor='la', font=MIS_HE, size=2)

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

        self.shadow_text(x, y, text=text, fill=color.fill, anchor='la', font=JBM_EB, size=10,
                         shadow_fill=color.shadow, shadow_width=0.4, stroke_fill=color.stroke, stroke_width=0.35)

    def ach(self, x: float, y: float, diff: Difficulty, ach_percent: float, color: Optional[AchColor] = None,
            all_cn: bool = False):
        self.ach_frame(x=x, y=y, diff=diff, all_cn=all_cn)
        self.ach_value(x=x + 2.8, y=y + 1.5, ach_percent=ach_percent, color=color)

    @staticmethod
    def _dxscore(count: int) -> Tuple[str, str]:
        if count == 5:
            color = COLOR_DXSCORE_GD
        elif count >= 3:
            color = COLOR_DXSCORE_OR
        else:
            color = COLOR_DXSCORE_GN
        return ("✦ " * count if 0 <= count <= 5 else "").rstrip(), color

    def dxscore(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Difficulty,
                cn: bool = False, all_cn: bool = False):
        title = " でらっくスコア" if not cn else " DXSCORE"
        title = " DX分数" if all_cn else title
        text = f"{score} / {max_score}"
        star_text, star_color = self._dxscore(star_count)

        self.rounded_rect(x, y, 24, 9, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=title, fill=COLOR_DXSCORE_GN, anchor='la', font=MIS_HE, size=2)
        self.text(x+12, y+4.5, text=text, fill='#333', anchor='mm', font=MIS_DB, size=3)
        self.text(x+12, y+6, text=star_text, fill=star_color, anchor='ma', font=NSS_RG, size=2.2)

    def dxscore_lite(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Difficulty,
                     cn: bool = False, all_cn: bool = False):
        title = " でらっくスコア" if not cn else " DXSCORE"
        title = " DX分数" if all_cn else title
        text = f"{score} / {max_score}"
        star_text, star_color = self._dxscore(star_count)

        self.rounded_rect(x, y, 42, 3, fill=bcm(diff.bg, '#FFF9'), radius=2)
        self.text(x+0.5, y+1.5, text=title, fill=COLOR_DXSCORE_GN, anchor='lm', font=MIS_HE, size=2)
        self.text(x+40, y+1.5, text=text, fill='#333', anchor='rm', font=MIS_DB, size=2.5)
        self.text(x+20, y+1.8, text=star_text, fill=star_color, anchor='mm', font=NSS_RG, size=2.2)

    def evaluate(self, x: float, y: float, text: str, color: EvaluateColor, size_offset: float = 0):
        self.text(x, y, text=text, fill=color.shadow, anchor='lm', font=MIS_HE, size=3 + size_offset,
                  stroke_fill=color.shadow, stroke_width=0.65)
        self.shadow_text(x, y, text=text, fill=color.fill, anchor='lm', font=MIS_HE, size=3 + size_offset,
                         shadow_fill=color.shadow, shadow_width=0.5)

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont, size: float = -1, fill='#FFF',
              line_height: float = 3.4, limit_width: float = -1):
        font = font.font_variant(size=self.ms.x(size)) if size > 0 else font
        lines_new = [self.limit_text(line, font, limit_width) for line in lines] if limit_width > -1 else lines
        offset = line_height / 2 if len(lines_new) % 2 == 0 else 0  # 偶数行偏移
        for i in range(len(lines_new)):
            dy = y + (i - len(lines_new) // 2) * line_height + offset
            self.text(x, dy, text=lines_new[i], fill=fill, anchor='lm', font=font)

    def bg_png(self, x: float, y: float, w: float, h: float, png: Image.Image | Path, radius: float = 1.5,
               outline: Optional[str] = None, outline_width: float = 0):
        try:
            overlay = (png if isinstance(png, Image.Image) else Image.open(png)).convert('RGBA')
            overlay = overlay.resize(self.ms.xy(w, h), Image.Resampling.LANCZOS)
            mask = Image.new('L', overlay.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, overlay.size[0], overlay.size[1]), radius=self.ms.x(radius), fill=255)

            self.img.paste(overlay, self.ms.xy(x, y), mask=mask)
        except (FileNotFoundError, AttributeError):
            return

        # 绘制边框（即使图片加载失败）
        if outline and outline_width > 0:
            self.draw.rounded_rectangle(self.ms.size(x, y, w, h), radius=self.ms.x(radius),
                                        outline=outline, width=self.ms.x(outline_width))


# ========================================
# 组装工厂
# ========================================


def info_box(
        diff: int | Difficulty,
        cabinet_dx: bool,
        level: float,
        achievement: float,
        dxscore: Tuple[int, int, int],
        combo: Optional[Combo | int] = None,
        sync: Optional[Sync | int] = None,
        note_designer: Optional[str] = None,
        level_diving_fish: float = -1,
        score_up: Optional[Dict[str, int]] = None,
        new_song: bool = False,
        cn: bool = False,
        all_cn: bool = False,
        plus_level: int = 6,
        ms_multiple: int | MS = 10,
) -> Image.Image:
    # 参数处理
    cn = True if all_cn else cn
    ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
    diff = diff if isinstance(diff, Difficulty) else DIFFICULTIES[diff]

    img = Image.new('RGBA', (ms.x(108) + 2, ms.x(36) + 2), color='#FFFFFF00')

    # 绘图单元
    du = DrawUnit(img, multiple=ms)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 108, 36), radius=ms.x(2.5), fill=diff.bg, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    # 标题栏
    du.draw.rectangle(ms.size(0, 2, 108, 5), fill=diff.title_bg)

    # 标题栏文字
    du.difficulty(2, 4.2, diff, all_cn=all_cn)

    # 谱面类型 (SD/DX)
    du.dx(64, 2, cn=cn) if cabinet_dx else du.sd(64, 2, cn=cn)

    # 等级 `LV`
    plus = round(level % 1 * 10) >= plus_level
    if diff is UTAGE:
        pass
    else:
        du.level(86, 7.4, diff, level, plus=plus, all_cn=all_cn)

    # 达成率
    du.ach(2, 9, diff, ach_percent=achievement, all_cn=all_cn)

    # DXSCORE
    du.dxscore(38, 25, score=dxscore[0], max_score=dxscore[1], star_count=dxscore[2], diff=diff, cn=cn, all_cn=all_cn)

    # FC/FC+/AP/AP+
    if combo:
        c, t, tl, tc = COMBO_DICT[combo]
        du.evaluate(3, 27, text=tc if all_cn else t, color=c)
    # SYNC/FS/FS+/FDX/FDX+
    if sync:
        c, t, tl, tc = SYNC_DICT[sync]
        du.evaluate(3, 32, text=tc if all_cn else t, color=c)

    # INFO
    line5 = [
        f"谱师: {note_designer}",
        f"拟合定数: {level_diving_fish}" if level_diving_fish >= 0 else '',
    ]

    if score_up:
        line5.append(f"推分 [B{'15' if new_song else '35'}]:")
        for r, s in score_up.items():
            line5.append(f"      {r}  ↑{s}")
        line5 = (line5 + [''] * 5)[:5]
    else:
        line5 += [''] * 3
    limit_w = du.get_text_length('I' * 56, MIS_DB, 2.5) *10
    du.rounded_rect(64, 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
    du.infos(65.5, 21.65, lines=line5, line_height=4.5, limit_width=limit_w, font=MIS_DB, size=3.2)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 108, 36), radius=ms.x(2.5), fill=None, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    return img

def info_box_lite(
        diff: int | Difficulty,
        cabinet_dx: bool,
        level: float,
        achievement: float,
        dxscore: Tuple[int, int, int],
        combo: Optional[Combo | int] = None,
        sync: Optional[Sync | int] = None,
        note_designer: Optional[str] = None,
        level_diving_fish: float = -1,
        score_up: Optional[Dict[str, int]] = None,
        new_song: bool = False,
        cn: bool = False,
        all_cn: bool = False,
        plus_level: int = 6,
        ms_multiple: int | MS = 10,
) -> Image.Image:
    # Lite 版本不显示的信息，用于参数占位
    _ = (note_designer, level_diving_fish, score_up, new_song)  # 该行仅为避免未使用参数警告
    # 参数处理
    cn = True if all_cn else cn
    ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
    diff = diff if isinstance(diff, Difficulty) else DIFFICULTIES[diff]

    img = Image.new('RGBA', (ms.x(108) + 2, ms.x(26) + 2), color='#FFFFFF00')

    # 绘图单元
    du = DrawUnit(img, multiple=ms)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 108, 26), radius=ms.x(2.5), fill=diff.bg, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    # 标题栏
    du.draw.rectangle(ms.size(0, 2, 108, 5), fill=diff.title_bg)

    # 标题栏文字
    du.difficulty(2, 4.2, diff, all_cn=all_cn)

    # 谱面类型 (SD/DX)
    du.dx(64, 2, cn=cn) if cabinet_dx else du.sd(64, 2, cn=cn)

    # 等级 `LV`
    plus = round(level % 1 * 10) >= plus_level
    if diff is UTAGE:
        pass
    else:
        du.level(86, 7.4, diff, level, plus=plus, all_cn=all_cn)

    # 达成率
    du.ach(46, 10, diff, ach_percent=achievement, all_cn=all_cn)

    # # DXSCORE
    du.dxscore_lite(2, 21, score=dxscore[0], max_score=dxscore[1], star_count=dxscore[2],
                    diff=diff, cn=cn, all_cn=all_cn)

    # FC/FC+/AP/AP+
    if combo:
        c, t, tl, tc = COMBO_DICT[combo]
        du.evaluate(3, 12, text=tc if all_cn else t, color=c)
    # SYNC/FS/FS+/FDX/FDX+
    if sync:
        c, t, tl, tc = SYNC_DICT[sync]
        du.evaluate(3, 17, text=tc if all_cn else t, color=c)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 108, 26), radius=ms.x(2.5), fill=None, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    return img


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
    du_lite_1 = DrawUnit(img, multiple=int(ms_multiple_value/1.25))
    du_lite_2 = DrawUnit(img, multiple=int(ms_multiple_value/1.5))

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
        cn: bool = False,
        all_cn: bool = False,
        ms_multiple: int | MS = 10,
) -> Image.Image:
    cn = True if all_cn else cn
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
    limit_t = du.get_text_length('I' * 62, MIS_HE, 4.6, stroke_width=0.8)  # 实测结果
    du.difficulty(2, 4.2, diff, all_cn=all_cn, text=f'#{short_id}  {title}', limit_width=limit_t)

    # 曲绘
    du.bg_png(2, 9, 25, 25, radius=1.5, outline=diff.deep, outline_width=0.3, png=bg_path)

    # 谱面类型 (SD/DX) - 进行了额外的 MS 缩放
    tv = ms.multiple * 1
    ms.multiple = tv * 0.5
    tx, ty = MS(2).xy(1.25, 8.5)
    du.dx(tx, ty, cn=cn) if cabinet_dx else du.sd(tx, ty, cn=cn)
    ms.multiple = tv * 1

    # 达成率
    du.ach(29, 9, diff, ach_percent=achievement, all_cn=all_cn)

    # DXSCORE
    du.dxscore(65, 25, score=dxscore[0], max_score=dxscore[1], star_count=dxscore[2], diff=diff, cn=cn, all_cn=all_cn)

    offset = -0.5 if all_cn else 0
    # FC/FC+/AP/AP+
    if combo:
        c, t, tl, tc = COMBO_DICT[combo]
        du.evaluate(30, 27, text=tc if all_cn else tl, color=c, size_offset=offset)
    # SYNC/FS/FS+/FDX/FDX+
    if sync:
        c, t, tl, tc = SYNC_DICT[sync]
        du.evaluate(30, 32, text=tc if all_cn else tl, color=c, size_offset=offset)

    # INFO
    du.rounded_rect(43, 25, 20, 9, fill=bcm(diff.bg, '#0009'), radius=1.5)
    du.infos(44.5, 29.5, lines=[f'b{'1' if new_song else '3'}5#{index}', f'{level:.1f} > {ra}'], line_height=3.4,
             font=MIS_DB, size=2.5)

    # 外框
    du.draw.rounded_rectangle(ms.size(0, 0, 91, 36), radius=ms.x(2.5), fill=None, outline=diff.frame,
                              width=3, corners=(True,) * 4)

    return img


def info_board(
        mai: MaiData,
        cn: bool = False,
        all_cn: bool = False,
        plus_level: int = 6,
        ms_multiple: int | MS = 5,
) -> Image.Image:
    # 参数处理
    cn = True if all_cn else cn
    ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)

    img = Image.open(IMG_PATH / "bakamai.png").convert('RGBA')
    img = img.resize(ms.xy(240, 240), Image.Resampling.LANCZOS)
    du = DrawUnit(img, multiple=ms)

    # MIS_DB 字体大小参考
    font_mdb5 = MIS_DB.font_variant(size=ms.x(5))
    font_mdb6 = MIS_DB.font_variant(size=ms.x(6))

    # 曲绘
    du.bg_png(10, 10, 70, 70, radius=5, outline='#FFF', outline_width=1, png=mai.image)
    # 曲名
    du.text(86, 10, text=mai.title, fill='#FFF', anchor='la', font=MIS_DB, size=12)

    # 曲名标准数据
    # ShortID
    du.text(86, 28, text=f"id{mai.shortid}", fill='#FFF', anchor='la', font=font_mdb6)
    # BPM
    du.text(138, 28, text=f"BPM: {mai.bpm}", fill='#FFF', anchor='la', font=font_mdb6)
    # Artist
    du.text(86, 40, text=f"Artist: {mai.artist}", fill='#FFF', anchor='la', font=font_mdb6)
    # Genre
    du.text(86, 52, text=f"Genre:", fill='#FFF', anchor='la', font=font_mdb6)
    genre = mai.genre.replace('&', '&\n') if '&' in mai.genre else mai.genre
    genre = genre+'™' if 'nico' in mai.genre else genre
    # (86, 60) -> 340*180 img
    du.draw.multiline_text(ms.xy(103, 69), text=genre, fill='#FFF', anchor='mm',
                           font=font_mdb5, spacing=ms.x(1), align="center")
    # Version
    du.text(138, 52, text=f"Version:", fill='#FFF', anchor='la', font=font_mdb6)

    def ver_img_draw(ver_img_path: Path, img: Image.Image, la_xy: Tuple[int, int], mm_xy: Tuple[int, int],
                     replace_text: str) -> None:
        """将版本图标绘制到指定位置"""
        if ver_img_path.exists():
            # 版本图标存在，绘制图标
            v = Image.open(ver_img_path).convert('RGBA')
            original_width, original_height = v.size
            scale_ratio = min(ms.x(34)/original_width, ms.x(18)/original_height)
            v = v.resize((int(original_width * scale_ratio), int(original_height * scale_ratio)),
                           Image.Resampling.LANCZOS)
            r = Image.new('RGBA', ms.xy(34, 18), color='#00000000')
            r.paste(v, ((r.width - v.width) // 2, (r.height - v.height) // 2), v)
            img.paste(r, la_xy, r)
        else:
            # 版本图标不存在，绘制替代文字
            du.draw.multiline_text(mm_xy, text=replace_text, fill='#FFF', anchor='mm',
                                   font=font_mdb6, spacing=ms.x(1), align="center")

    config_yaml_path = Path.cwd() / "versions.yaml"

    with open(config_yaml_path, "r", encoding="utf-8") as f:
        ver_cfg: Dict[int, str] = yaml.safe_load(f)

    # JP
    ver_img_draw(VER_PATH / f"{mai.version}.png", img,
                 ms.xy(138, 60), ms.xy(154, 69), ver_cfg.get(mai.version, str(mai.version)))
    # CN
    if mai.version_cn is not None:
        ver_img_draw(VER_PATH / f"CN_{mai.version_cn}.png", img,
                     ms.xy(176, 60), ms.xy(192, 69), ver_cfg.get(mai.version_cn, str(mai.version_cn)))

    next_y = 87  # 记录下一个组件的起始 y 坐标
    aliases_max_width = du.get_text_length('A'*60, font=font_mdb5)
    # Aliases
    if mai.aliases:
        du.text(10, next_y, text="这首歌的别名包括： ", fill='#FFF', anchor='la', font=font_mdb5)
        lines = ['']
        for alias in mai.aliases:
            alias_text = ' '*4 + f"<{alias}>".strip()
            if du.get_text_length(lines[-1] + alias_text, font=font_mdb5) <= aliases_max_width:
                lines[-1] += alias_text
            else:
                lines.append(alias_text)
        next_y += 7  # font_mdb5 行高+间距
        for line in lines:
            du.text(10, next_y, text=line, fill='#FFF', anchor='la', font=font_mdb5)
            next_y += 7
    next_y += 4  # 与谱面数据间距

    # 核心谱面数据
    base_xy = (10, next_y)
    for i, chart in enumerate(mai.charts):
        if not chart.ach:
            chart.ach = MaiChartAch(-101, 0, 0, 0, 0)
        img_func = info_box if chart.difficulty >= 4 else info_box_lite

        # todo: 此处要 ms*5 后再缩小，改进显示效果
        chart_img = img_func(diff=chart.difficulty,
                             cabinet_dx=mai.is_cabinet_dx,
                             level=chart.lv,
                             achievement=chart.ach.achievement,
                             dxscore=chart.ach.dxscore_tuple,
                             combo=chart.ach.combo,
                             sync=chart.ach.sync,
                             note_designer=chart.des,
                             level_diving_fish=-1,  # 暂未进行获取计算
                             score_up={},  # 暂未进行获取计算
                             new_song=mai.is_b15,
                             cn=cn,
                             all_cn=all_cn,
                             plus_level=plus_level,
                             ms_multiple=ms)

        x, y = base_xy
        img.paste(chart_img, ms.xy(x, y), chart_img)
        next_y = base_xy[1] + (39 if chart.difficulty >= 4 else 29)  # 同时用于给下一个组件传递 y 起始值
        if (i+1) % 2 == 1:
            base_xy = (123, base_xy[1])  # 保持同行
        else:
            base_xy = (10, next_y)  # 使用下一行的 y 起始值
    next_y += 4

    # Other Info
    # 目前没有

    # Copyright Info
    CR_INFO = "    |    ".join([
        "Powered by LyraBot (@GoldSheep3)",
        f"Version: {MODEL_VERSION}",
        "Designer by Bakamai⑨'s Members",
        "Background Artist by @银色山雾"
    ])
    du.rounded_rect(0, next_y, 240, 6, fill='#313d7c', radius=0)  # 后续修改为遮罩渐变合成
    du.text(120, next_y + 3, text=CR_INFO, fill='#64d2ce', anchor='mm', font=MIS_DB, size=3.5)

    # 切除多余部分，同时转换回 RGB 模式
    img = img.crop((0, 0, ms.x(240), ms.x(next_y + 6)))
    img = img.convert('RGB')

    return img

# 示例用法
if __name__ == "__main__":
    mdt = MaiData(
        shortid=101,
        title="おちゃめ機能",
        bpm=150,
        artist="ゴジマジP",
        genre="niconico & VOCALOID",
        cabinet='DX',
        version=1,
        version_cn=1,
        converter="PreData",
        img_path=Path(r"C:\Users\sanji\AppData\Roaming\JetBrains\PyCharm2025.3\scratches\bg.png"),
        aliases=[
            "五月病"
        ]
    )

    mdt._chart2 = MaiChart(
        difficulty=2,
        lv=3.6,
    )

    mdt._chart3 = MaiChart(
        difficulty=3,
        lv=3.6,
    )

    mdt._chart4 = MaiChart(
        difficulty=4,
        lv=13.6,
        des="?",
        ach=MaiChartAch(
            achievement=74.1044,
            dxscore=1318,
            dxscore_max=1497,
            combo=Combo.FC,
            sync=Sync.FS_PLUS
        )
    )

    mdt._chart5 = MaiChart(
        difficulty=5,
        lv=13.6,
        des="mai-Star",
        ach=MaiChartAch(
            achievement=100.3177,
            dxscore=1318,
            dxscore_max=1497,
            combo=Combo.FC,
            sync=Sync.FS_PLUS
        )
    )

    # mdt._chart6 = MaiChart(
    #     difficulty=6,
    #     lv=13.6,
    #     des="mai-Star",
    #     ach=MaiChartAch(
    #         achievement=100.3177,
    #         dxscore=1318,
    #         dxscore_max=1497,
    #         combo=Combo.FC,
    #         sync=Sync.FS_PLUS
    #     )
    # )

    ib = info_board(mdt, False, True, ms_multiple=3)

    pif = info_box_lite(
        diff=3,
        cabinet_dx=False,
        level=13.6,
        achievement=100.3177,
        dxscore=(1318, 1497, 1),
        combo=1,
        sync=2,
        note_designer="mai-Star",
        level_diving_fish=13.9,
        score_up={"SSS+": 5},
        new_song=False,
        cn=True,
        all_cn=True,
        ms_multiple=10
    )

    pbb = b50_box(
        diff=5,
        cabinet_dx=False,
        short_id=101,
        title="おちゃめ機能",
        level=13.6,
        ra=306,
        achievement=100.3177,
        bg_path=Path(r"C:\Users\sanji\AppData\Roaming\JetBrains\PyCharm2025.3\scratches\bg.png"),
        dxscore=(1318, 1497, 1),
        combo=1,
        sync=2,
        new_song=False,
        index=5,
        cn=True,
        all_cn=True
    )

    ifm = info_box_mini(
        diff=5,
        level=13.6,
        achievement=100.3177,
        combo=1,
        sync=3,
        all_cn=True
    )

    from PIL import ImageTk
    import tkinter as tk

    root = tk.Tk()
    tk_image = ImageTk.PhotoImage(ib)
    label = tk.Label(root, image=tk_image)
    label.pack()
    label.image = tk_image
    root.mainloop()




