import bisect
from pathlib import Path
from enum import Enum
from typing import Optional, Tuple, Literal, List, Iterator, Any
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from .utils import MaiData, MaiChart, MaiChartAch, MaiAlias, MaiB50Manager
from .constants import *

# ========================================
# 基础常量
# ========================================

# 模块版本
MODEL_VERSION: str = "260330"

# 字体常量
class FontManager:
    _font_dict = {
        'MIS_DB': "MiSans-Demibold.otf",
        'MIS_HE': "MiSans-Heavy.otf",
        'JBM_BD': "JetBrainsMono-Bold.ttf",
        'JBM_EB': "JetBrainsMono-ExtraBold.ttf",
        'NCE_RG': 'NotoColorEmoji-Regular.ttf',
        'NSS_RG': "NotoSansSymbols2-Regular.ttf",
    }

    def __init__(self, font_path: Path):
        self._font_path = font_path

    @lru_cache(maxsize=128)
    def _get_font(self, font_file: Path, size: int) -> ImageFont.FreeTypeFont:
        if size <= 0:
            return ImageFont.truetype(str(font_file), 10000)
        return ImageFont.truetype(str(font_file), size)

    def font(self, font_code: str, size: float) -> ImageFont.FreeTypeFont:
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
FONT = FontManager(ASSETS_PATH / "fonts")

# 图片常量
class AssetsManager:
    def __init__(self, assets_path: Path):
        self._assets_path = assets_path
        self._pic_path = self._assets_path / "pic"
        self._dxrating_path = self._pic_path / "dxrating"
        self._plate_path = self._pic_path / "plate"
        self._ver_path = self._pic_path / "ver"

    @staticmethod
    @lru_cache(maxsize=64)
    def _get_image(path: Path, size: Tuple[int, int] | None = None) -> Image.Image | None:
        if not path.exists():
            raise FileNotFoundError(f"图片文件缺失: {path}")
        try:
            img = Image.open(path).convert('RGBA')
            if size is not None:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            return None

    def version_image(self, version: int, size: Tuple[int, int] | None = None) -> Image.Image | None:
        return self._get_image(self._ver_path / f"{version}.png", size)

    def dxrating_image(self, rating_filename: str, size: Tuple[int, int] | None = None) -> Image.Image | None:
        return self._get_image(self._dxrating_path / rating_filename, size)

    def background(self, size: Tuple[int, int] | None = None) -> Image.Image | None:
        return self._get_image(self._assets_path / "img" / "bakamai.png", size)
ASSETS = AssetsManager(ASSETS_PATH)

# 基础颜色常量
COLOR_DXSCORE_GN = '#0A5'
COLOR_DXSCORE_OR = '#C72'
COLOR_DXSCORE_GD = '#ED4'
COLOR_THEME = '#64d2ce'
NO_COLOR = '#FFFFFF00'  # 完全透明

# 难度
@dataclass(frozen=True)
class Diff:
    code: int
    text_title: str
    text_title_cn: str
    bg: str
    frame: str
    text: str
    deep: str
    title_bg: str
    _level_text: Optional[str] = None

    @property
    def level_text(self) -> str:
        return self._level_text if self._level_text else self.text

class Difficulty(Enum):
    NONE = Diff(0, "N/A", "N/A", bg='#FFF', frame='#FFF', text='#FFF', deep='#FFF', title_bg='#FFF')
    EASY = Diff(1, "EASY", "简单", bg='#FFF', frame='#FFF', text='#FFF', deep='#FFF', title_bg='#FFF')
    BASIC = Diff(2, "BASIC", "基础", bg='#7E6', frame='#053', text='#FFF', deep='#8D5', title_bg='#2B5')
    ADVANCED = Diff(3, "ADVANCED", "高级", bg='#FD3', frame='#B41', text='#FFF', deep='#FB1', title_bg='#F92')
    EXPERT = Diff(4, "EXPERT", "专家", bg='#F88', frame='#C23', text='#FFF', deep='#F9A', title_bg='#F46')
    MASTER = Diff(5, "MASTER", "大师", bg='#C7F', frame='#618', text='#FFF', deep='#B3D', title_bg='#94E')
    REMASTER = Diff(6, "Re:MASTER", "宗师", bg='#EDE', frame='#82D', text='#D5F', deep='#FFF', title_bg='#B6F', _level_text='#FFF')
    UTAGE = Diff(7, "U·TA·GE", "宴·会·场", bg='#E6E', frame='#D0B', text='#FFF', deep='#F6F', title_bg='#F4F')

    @classmethod
    def get(cls, code: int) -> Diff:
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value

COLOR_UTAGE_TAG_BG = '#236'
COLOR_UTAGE_TAG_FRAME = '#BEF'
COLOR_BUDDY_TAG_BG = '#411'
COLOR_BUDDY_TAG_FRAME = '#FEA'

# 达成率
@dataclass(frozen=True)
class AchColor:
    fill: str
    stroke: str
    shadow: str

class Achievement(Enum):
    S = AchColor(fill='#F93', stroke='#C00', shadow='#EB5')
    A = AchColor(fill='#D77', stroke='#834', shadow='#B77')
    B = AchColor(fill='#3AD', stroke='#239', shadow='#58B')

    @classmethod
    def get_by_percent(cls, percent: float) -> AchColor:
        if percent >= 97:
            return cls.S.value
        if percent >= 80:
            return cls.A.value
        return cls.B.value

# 评价类型
@dataclass(frozen=True)
class EvaluateColor:
    fill: str
    shadow: str

_EVAL_GN = EvaluateColor(fill='#7D5', shadow='#162')  # FC / FC+
_EVAL_GD = EvaluateColor(fill='#FE2', shadow='#A02')  # AP / AP+ / FDX / FDX+
_EVAL_BE = EvaluateColor(fill='#6DF', shadow='#038')  # FS / FS+
_EVAL_DB = EvaluateColor(fill='#038', shadow='#FFF')  # SYNC PLAY

@dataclass(frozen=True)
class EvalInfo:
    code: int
    color: EvaluateColor
    full_name: str
    short_name: str
    cn_name: str

    def __iter__(self) -> Iterator[Any]:
        # 使 EvalInfo 可以直接解包为 (color, full_name, short_name, cn_name)
        return iter((self.color, self.full_name, self.short_name, self.cn_name))

class Combo(Enum):
    NONE    = EvalInfo(0, _EVAL_GN, '', '', '')
    FC      = EvalInfo(1, _EVAL_GN, 'FULL COMBO', 'FC', '全连击')
    FC_PLUS = EvalInfo(2, _EVAL_GN, 'FULL COMBO +', 'FC+', '全连击+')
    AP      = EvalInfo(3, _EVAL_GD, 'ALL PERFECT', 'AP', '完美无缺')
    AP_PLUS = EvalInfo(4, _EVAL_GD, 'ALL PERFECT +', 'AP+', '完美无缺+')

    @classmethod
    def get(cls, code: int) -> EvalInfo:
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value

class Sync(Enum):
    NONE     = EvalInfo(0, _EVAL_DB, '', '', '')
    SYNC     = EvalInfo(1, _EVAL_DB, 'SYNC PLAY', 'SYNC', '同步游玩')
    FS       = EvalInfo(2, _EVAL_BE, 'FULL SYNC', 'FS', '全完同步')  # 原文如此
    FS_PLUS  = EvalInfo(3, _EVAL_BE, 'FULL SYNC +', 'FS+', '全完同步+')  # 原文如此
    FDX      = EvalInfo(4, _EVAL_GD, 'FULL SYNC DX', 'FDX', '完全同步DX')
    FDX_PLUS = EvalInfo(5, _EVAL_GD, 'FULL SYNC DX +', 'FDX+', '完全同步DX+')

    @classmethod
    def get(cls, code: int) -> EvalInfo:
        for item in cls:
            if item.value.code == code:
                return item.value
        return cls.NONE.value


# 全角映射
def _build_full_width_table():
    # 半角空格 (32) 对应全角空格 (12288)
    # 其他 ASCII 可打印字符 (33-126) 对应全角 (65281-65374)
    # 偏移量通常为 0xFEE0 (65248)
    half_width = "".join(chr(i) for i in range(32, 127))
    full_width = "　" + "".join(chr(i + 0xFEE0) for i in range(33, 127))
    return str.maketrans(half_width, full_width)

CHAR_FULL_WIDTH_TABLE = _build_full_width_table()

# DXRating 版本分界线
BOUNDARIES_DX_RATING = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14500, 15000]
BOUNDARIES_DX_RATING_NEW = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14250, 14500, 14750, 15000, 15250, 15500, 15750, 16000, 16250, 16500, 16750]


# ========================================
# 辅助函数
# ========================================


def get_image_from_path_or_weburl(path_or_url: str | Path) -> Optional[Image.Image]:
    """从本地路径或网络 URL 获取图片。对 str 识别为 URL，对 Path 识别为本地路径。"""
    # TODO: 最终要从这个模块中迁移出去
    if isinstance(path_or_url, str):
        # 从 URL 下载到临时目录
        import httpx
        import tempfile
        with httpx.Client(timeout=10.0) as client:
            response = client.get(path_or_url)
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(path_or_url).suffix) as tmp_file:
                tmp_file.write(response.content)
                path = Path(tmp_file.name)
        if not path.exists():
            return None
    elif isinstance(path_or_url, Path):
        path: Path = path_or_url
    if path.exists():
        try:
            return Image.open(path).convert('RGBA')
        except (FileNotFoundError, OSError):
            return None
    return None

def get_range_index_left_closed(boundaries, value):
    """
    根据左闭右开区间 [b[i], b[i+1]) 返回索引 i
    """
    # 如果值小于最小值，通常返回 -1 或处理异常
    if value < boundaries[0]:
        return -1

    idx = bisect.bisect_right(boundaries, value) - 1
    
    # 边界检查：如果值超出了最大边界
    if idx >= len(boundaries):
        return len(boundaries) - 1
        
    return idx

def bcm(t: str, f: str):
    """颜色混合函数 (背景色 t，前景色 f)"""
    # TODO: 最终要更换成 Pillow 的混合函数
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
    def __init__(self, multiple: float):
        self.multiple = multiple
        self._cache: dict[float, int] = {}  # 计算缓存

    def set_multiple(self, multiple: float):
        self.multiple = multiple
        self._cache = {}

    def x(self, val: int | float) -> int:
        val = float(val)
        if result := self._cache.get(val):
            return result
        self._cache[val] = round(val * self.multiple)
        return self._cache[val]

    def xy(self, x: int | float, y: int | float) -> tuple[int, int]:
        return self.x(x), self.x(y)

    def size(self, x: int | float, y: int | float, w: int | float, h: int | float) -> tuple[int, int, int, int]:
        return self.x(x), self.x(y), self.x(x + w), self.x(y + h)

    def rev(self, x: float) -> float:
        return x / self.multiple

    def __repr__(self):
        return f"MS(multiple={self.multiple})"

    def __mul__(self, other: int | float) -> 'MS':
        if not isinstance(other, (int, float)):
            return NotImplemented
        return MS(self.multiple * other)


_MS_DEFAULT = MS(8)  # 默认倍率


def get_full_width_text(text: str) -> str:
    """将文本中的半角 ASCII 字符转换为全角形式"""
    if not text:
        return ""
    return text.translate(CHAR_FULL_WIDTH_TABLE)


def get_genre(genre_id: int, cn_level: Literal[0, 1, 2]) -> Tuple[str, str]:
    """获取流派信息"""
    genre_info = GENRES_DATA.get(genre_id, {})
    target = {0: 'jp', 1: 'intl', 2: 'cn'}
    genre = genre_info.get(target.get(cn_level, 'jp'), 'N/A')
    color = genre_info.get('color', COLOR_THEME)
    return genre, color


# ========================================
# 元件方法
# ========================================

class DrawUnit:
    def __init__(self, img: Image.Image, multiple: MS | int = 8, cn_level: Literal[0, 1, 2] = 0):
        self.img: Image.Image = img
        self.draw: ImageDraw.ImageDraw = ImageDraw.Draw(self.img)
        self.ms: MS = multiple if isinstance(multiple, MS) else MS(multiple)

        self.cn_level: Literal[0, 1, 2] = cn_level

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

    def _text(self, x: float, y: float, text: Optional[str], fill: Optional[str], anchor: str, font: ImageFont.FreeTypeFont,
              stroke_fill: Optional[str] = None, stroke_width: float = 0):
        """text 绘制简化方法"""
        xy, sw = self.ms.xy(x, y), self.ms.x(stroke_width)
        text = text if text else ''
        self.draw.text(xy, text=text, fill=fill, anchor=anchor, font=font, stroke_width=sw, stroke_fill=stroke_fill)

    def text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str, font: ImageFont.FreeTypeFont,
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
        self._text(x, y, text=text, fill=fill, anchor=anchor, font=font, stroke_fill=stroke[1], stroke_width=stroke[0])

    def double_text(self, x: float, y: float, text: str, fill: Optional[str], anchor: str, font: ImageFont.FreeTypeFont,
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

    def difficulty(self, x: float, y: float, diff: Diff, text: Optional[str] = None, limit_width: float = -1):
        f = FONT.font('MIS_HE', self.ms.x(4.8))
        if all((not text, self.cn_level == 2)):
            fs = FONT.font('MIS_HE', self.ms.x(3.3))
            _x1, _y1, x2, y2 = f.getbbox(diff.text_title, anchor='lm', stroke_width=self.ms.x(0.8))
            mx2, my2 = self.ms.rev(x2), self.ms.rev(y2)
            self.text(x+mx2+0.5, y+my2, diff.text_title_cn, diff.text, 'ld',
                      fs, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))
        elif text and limit_width > -1:
            # 此处处理文字宽度限制
            text = self.limit_text(text, f, limit_width)
        text = text if text else diff.text_title
        self.text(x, y, text, diff.text, 'lm', f, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))

    def level(self, x: float, y: float, diff: Diff, level: float, plus: bool = False,
              ignore_decimal: bool = False):
        draw = self.draw
        ms = self.ms

        f = f"{str(int(level // 1)).replace('0', 'O'):>2}"  # 整数部分
        d = str(round(level % 1 * 10)).replace('0', 'O')  # 小数部分

        # 等级 `LV`
        if self.cn_level == 2:
            draw.text(ms.xy(x - 1, y), text="等级", fill=diff.frame, anchor='ls', font=FONT.font('MIS_DB', size=ms.x(3)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x - 1, y), text="等级", fill=diff.level_text, anchor='ls', font=FONT.font('MIS_DB', size=ms.x(3)))
        else:
            draw.text(ms.xy(x, y), text="LV", fill=diff.frame, anchor='ls', font=FONT.font('JBM_BD', size=ms.x(4)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x, y), text="LV", fill=diff.level_text, anchor='ls', font=FONT.font('JBM_BD', size=ms.x(4)))
        # 等级 `xx.x`
        draw.text(ms.xy(x + 6, y), text=f, fill=diff.frame, anchor='ls', font=FONT.font('JBM_BD', size=ms.x(6)),
                  stroke_width=ms.x(0.5), stroke_fill=diff.frame)
        draw.text(ms.xy(x + 6, y), text=f, fill=diff.level_text, anchor='ls', font=FONT.font('JBM_BD', size=ms.x(6)))
        if not ignore_decimal:
            draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.frame, anchor='ls',
                      font=FONT.font('JBM_BD', size=ms.x(5)), stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x + 13, y), text="." + d, fill=diff.level_text, anchor='ls',
                      font=FONT.font('JBM_BD', size=ms.x(5)))
        # 等级 `+`
        if plus:
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.frame, anchor='ls',
                      font=FONT.font('JBM_BD', size=ms.x(3.5)),
                      stroke_width=ms.x(0.5), stroke_fill=diff.frame)
            draw.text(ms.xy(x + 13.7, y - 2.8), text="+", fill=diff.level_text, anchor='ls',
                      font=FONT.font('JBM_BD', size=ms.x(3.5)))

    def ach_frame(self, x: float, y: float, diff: Diff):
        text = " 达成率" if self.cn_level == 2 else " ACHIEVEMENT"

        self.rounded_rect(x, y, 60, 14, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=text, fill=diff.frame, anchor='la', font=FONT.font('MIS_HE', size=self.ms.x(2)))

    def ach_value(self, x: float, y: float, ach_percent: float, color: Optional[AchColor] = None):
        if -100 < ach_percent < 1000:
            text = f"{ach_percent:.4f}%".replace('0', 'O').rjust(9)
            color = color or Achievement.get_by_percent(ach_percent)
        else:
            text = " --.----%"
            color = color or Achievement.B.value

        self.text(x, y, text=text, fill=color.fill, anchor='la', font=FONT.font('JBM_EB', size=self.ms.x(10)),
                  shadow=(0.4, color.shadow), stroke=(0.35, color.stroke))

    def ach(self, x: float, y: float, diff: Diff, ach_percent: float, color: Optional[AchColor] = None):
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

    def dxscore(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Diff):
        title, text, star_text, star_color = self._dxscore(cn_level=self.cn_level, score=score, max_score=max_score,
                                                           star_count=star_count)

        self.rounded_rect(x, y, 24, 9, fill=bcm(diff.bg, '#FFF9'), radius=1.5)
        self.text(x, y, text=title, fill=COLOR_DXSCORE_GN, anchor='la', font=FONT.font('MIS_HE', size=self.ms.x(2)))
        self.text(x + 12, y + 4.5, text=text, fill='#333', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(3)))
        self.text(x + 12, y + 6, text=star_text, fill=star_color, anchor='ma',
                  font=FONT.font('NSS_RG', size=self.ms.x(2.2)))

    def dxscore_lite(self, x: float, y: float, score: int, max_score: int, star_count: int, diff: Diff):
        title, text, star_text, star_color = self._dxscore(cn_level=self.cn_level, score=score, max_score=max_score,
                                                           star_count=star_count)

        self.rounded_rect(x, y, 42, 3, fill=bcm(diff.bg, '#FFF9'), radius=2)
        self.text(x + 0.5, y + 1.5, text=title, fill=COLOR_DXSCORE_GN, anchor='lm',
                  font=FONT.font('MIS_HE', size=self.ms.x(2)))
        self.text(x + 40, y + 1.5, text=text, fill='#333', anchor='rm', font=FONT.font('MIS_DB', size=self.ms.x(2.5)))
        self.text(x + 20, y + 1.8, text=star_text, fill=star_color, anchor='mm',
                  font=FONT.font('NSS_RG', size=self.ms.x(2.2)))

    def evaluate(self, x: float, y: float, text: str, color: EvaluateColor, offset: float = 0):
        self.text(x, y, text=text, fill=color.fill, anchor='lm', font=FONT.font('MIS_HE', size=self.ms.x(3 + offset)),
                  stroke=(0.65, color.shadow), shadow=(0.5, color.shadow))

    def infos(self, x: float, y: float, lines: list[str], font: ImageFont.FreeTypeFont, fill='#FFF',
              line_height: float = 3.4, limit_width: float = -1):
        lines_new = [self.limit_text(line, font, limit_width) for line in lines] if limit_width > -1 else lines
        offset = line_height / 2 if len(lines_new) % 2 == 0 else 0  # 偶数行偏移
        for i in range(len(lines_new)):
            dy = y + (i - len(lines_new) // 2) * line_height + offset
            self.text(x, dy, text=lines_new[i], fill=fill, anchor='lm', font=font)

class ImageUnit:

    # 获取圆角 L 遮罩
    @lru_cache(maxsize=8)
    def get_mask(self, w: int, h: int, radius: float,
                 ms: MS = _MS_DEFAULT) -> Image.Image:
        # 画布大小应包含完整的 w 和 h
        mask = Image.new('L', ms.xy(w, h), 0)
        draw = ImageDraw.Draw(mask)
        # 直接绘制充满画布的圆角矩形，坐标为 (0, 0, w, h)
        draw.rounded_rectangle(ms.size(0, 0, w, h), radius=ms.x(radius), fill=255)
        return mask

    # 难度式文本样式
    def diff_text(self, diff: Diff, text: Optional[str] = None, limit_width: float = -1, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0):
        # 处理文字长度并计算位置
        font = FONT.font('MIS_HE', ms.x(4.8))
        if text:
            # 自定义文本，需处理宽度顺序
            text = DrawUnit.limit_text(text, font, limit_width) if limit_width > 0 else text
            display_text = text
        else:
            display_text = diff.text_title

        x1, y1, x2, y2 = font.getbbox(display_text, anchor='lm', stroke_width=ms.x(0.8))
        if cn_level == 2 and not text:
            # 特殊处理中文默认难度标题的位置
            cn_font = FONT.font('MIS_HE', ms.x(3.3))
            cn_x1, _cn_y1, cn_x2, _cn_y2 = cn_font.getbbox(diff.text_title_cn, anchor='lm', stroke_width=ms.x(0.8))
            cn_width = ms.rev(cn_x2 - cn_x1)
        else:
            cn_width = 0
        width = (ms.rev(x2 - x1) + cn_width) * 1.2
        height = ms.rev(y2 - y1) * 1.2

        # 实际渲染逻辑
        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.text(1, height / 2, display_text, diff.text, 'lm', font, shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))
        if cn_width:
            du.text(ms.rev(x2 - x1) * 1.1, ms.rev(y2 - y1) * 1.1, diff.text_title_cn, diff.text, 'ld', FONT.font('MIS_HE', ms.x(3.3)),
                    shadow=(0.8, diff.deep), shadow2=(0.8, diff.frame, 0.7))

        return img

    # 难度文本
    @lru_cache(maxsize=10)
    def difficulty(self, diff: Diff, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return self.diff_text(diff=diff, text=None, limit_width=-1, ms=ms, cn_level=2)

    # FC / FS 评定文本
    @lru_cache(maxsize=18)
    def evaluate(self, eval: EvalInfo | None, mini: bool = False, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        size = ms.xy(20, 5) if mini else ms.xy(40, 5)
        img = Image.new('RGBA', size, "#FFFFFF00")
        if eval:
            du = DrawUnit(img, multiple=ms, cn_level=cn_level)
            text = eval.short_name if mini else (eval.cn_name if cn_level == 2 else eval.full_name)
            du.text(1, 2.5, text, eval.color.fill, 'lm', FONT.font('MIS_HE', ms.x(3)),
                stroke=(0.5, eval.color.shadow), shadow=(0.65, eval.color.shadow))
        return img

    # 谱面类型标记（标准）
    def draw_sd_badge(self, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_SD = '#4AF'
        du.rounded_rect(0, 0, 20, 5, fill=COLOR_SD, radius=5)
        offset = 0.6 if cn_level else 0
        font = FONT.font('MIS_HE', ms.x(3 + offset))
        text = "标 准" if cn_level else "スタンダード"
        du.text(10, 2.5, text, '#FFF', 'mm', font)
        return img

    # 谱面类型标记（DX）
    def draw_dx_badge(self, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        img = Image.new('RGBA', ms.xy(20, 5), "#FFFFFF00")
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        COLOR_DX = ('#FF7711', '#FFFFFF')
        COLOR_DELUXE = ('#FF4646', '#FFA02D', '#FFDC00', '#9AC948', '#00AAE6', '#2299EE')

        du.rounded_rect(0, 0, 20, 5, fill='#FFF', radius=5, outline=COLOR_DX[1] if cn_level else COLOR_DELUXE[-1], width=0.5)
        if cn_level:
            text = "DX"
            du.text(10, 2.5, text, COLOR_DX[0], 'mm', FONT.font('MIS_HE', ms.x(4.1)))
        else:
            font = FONT.font('MIS_HE', ms.x(3.2))
            text = "でらっくす"
            total_text_width = ms.rev(font.getlength(text))
            start_x = (10) - (total_text_width / 2)
            current_x = start_x
            center_y = 2.5
            for char, color in zip(text, COLOR_DELUXE):
                du.text(current_x, center_y, char, color, 'lm', font)
                char_width = ms.rev(font.getlength(char))
                current_x += char_width
        return img

    # 谱面类型标记
    @lru_cache(maxsize=4)
    def draw_badge(self, is_cabinet_dx: bool, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        return self.draw_dx_badge(ms=ms, cn_level=cn_level) if is_cabinet_dx else self.draw_sd_badge(ms=ms, cn_level=cn_level)

    # 版权信息栏
    @lru_cache(maxsize=4)
    def copyright_bar(self, width: int, lines: tuple[str, ...] | None = None,
                      ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        if lines is None:
            lines = (
                "Powered by LyraBot (@GoldSheep3)",
                "Version:" + MODEL_VERSION,
                "Designer by Bakamai⑨'s Members",
                "Background Artist by @银色山雾"
            )
        
        cr_info = "    |    ".join(lines)
        
        # 基准测量
        base_size = 5.0
        test_font = FONT.font('MIS_DB', size=ms.x(base_size))
        tx1, ty1, tx2, ty2 = test_font.getbbox(cr_info)
        raw_width = tx2 - tx1
        raw_height = ty2 - ty1

        target_content_width = width * 0.9  # 预留两侧各 5% 的空白边距
        # 缩放系数 = 目标宽度 / 原始宽度
        ratio = min(target_content_width / (raw_width / ms.multiple), 1.0)
        final_size = max(base_size * ratio, 1.2)
        
        font = FONT.font('MIS_DB', size=ms.x(final_size))
        # 预留上下各 20% 的空间，防止文字过于贴边
        bar_height = round(max((raw_height * ratio) * 1.4, ms.x(6)))

        # 实际渲染
        img = Image.new('RGBA', (ms.x(width), bar_height), '#313d7c')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)
        du.text(
            width // 2, 
            ms.rev(bar_height) // 2, 
            text=cr_info, 
            fill=COLOR_THEME, 
            anchor='mm',
            font=font
        )

        return img

    # -- 大型组件 --
    # 谱面信息框
    def chart_box(self, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6, is_utage: bool = False,
                  ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框"""
        w, h, ow = 108, 36, 1  # w, h, outline_width
        width, height = w + ow * 2, h + ow * 2
        diff = Difficulty.get(chart.difficulty)

        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, radius=4, fill=diff.bg)
        du.cut_line(ow, ow, w, h, radius=4, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        difficulty = IMU.difficulty(diff=diff, ms=ms, cn_level=cn_level)
        diff_height = ms.rev(difficulty.size[1])
        img.paste(difficulty, ms.xy(ow + 2.5, ow + 4.3 - diff_height / 2), difficulty)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 85, ow + 2), badge)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(ow + 64, ow + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(ow + 2, ow + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore(ow + 38, ow + 25, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = IMU.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 27-3), fc)
        fs = IMU.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 32-3), fs)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.lv_synh:.4f}" if chart.lv_synh else '',
        ]

        du.rounded_rect(ow + 64, ow + 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
        du.infos(ow + 65.5, ow + 21.65, lines=(info_line5 + [''] * 5)[:5], line_height=4.5, limit_width=-1,
                 font=FONT.font('MIS_DB', size=ms.x(3.2)))

        return img

    def chart_box_lite(self, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6, 
                       is_utage: bool = False, ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
        """组件：谱面信息框 Lite"""
        w, h, ow = 108, 25, 1  # w, h, outline_width
        width, height = w + ow * 2, h + ow * 2
        diff = Difficulty.get(chart.difficulty)

        img = Image.new('RGBA', ms.xy(width, height), '#FFFFFF00')
        du = DrawUnit(img, multiple=ms, cn_level=cn_level)

        du.rounded_rect(ow, ow, w, h, radius=4, fill=diff.bg)
        du.cut_line(ow, ow, w, h, radius=4, line_y=ow + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(ow, ow, w, h, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        difficulty = IMU.difficulty(diff=diff, ms=ms, cn_level=cn_level)
        diff_height = ms.rev(difficulty.size[1])
        img.paste(difficulty, ms.xy(ow + 2.5, ow + 4.3 - diff_height / 2), difficulty)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=ms, cn_level=cn_level)
        img.paste(badge, ms.xy(ow + 85, ow + 2), badge)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(ow + 64, ow + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(ow + 46, ow + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(ow + 2, ow + 20, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        # 评价图标
        fc = IMU.evaluate(Combo.get(ach.combo), ms=ms, cn_level=cn_level)
        img.paste(fc, ms.xy(ow + 3, ow + 12 - 3), fc)
        fs = IMU.evaluate(Sync.get(ach.sync), ms=ms, cn_level=cn_level)
        img.paste(fs, ms.xy(ow + 3, ow + 17 - 3), fs)
        return img

IMU = ImageUnit()  # 全局图像元件实例

# ========================================
# 组装工厂
# ========================================


class DrawFactory:

    def __init__(self, width: int, height: int, ms_multiple: int | MS = 10, cn_level: Literal[0, 1, 2] = 0):
        ms = ms_multiple if isinstance(ms_multiple, MS) else MS(ms_multiple)
        self.ms = ms  # 缩放倍率

        # 背景图片
        # TODO: 后续修改为分块和遮罩渐变合成的方式，减少内存占用和提高性能
        self.img: Image.Image = ASSETS.background(ms.xy(width, height)) or Image.new('RGBA', ms.xy(width, height), COLOR_THEME)
        self.img.convert('RGBA')

        # 绘图单元
        self.cn_level: Literal[0, 1, 2] = cn_level
        self.du = DrawUnit(self.img, multiple=ms, cn_level=cn_level)

    def get_image(self) -> Image.Image:
        """获取绘制完成的图像"""
        return self.img

    def chart_box(self, x, y, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6,
                  is_utage: bool = False) -> Tuple[int, int]:
        """组件：谱面信息框"""
        du = self.du
        diff = Difficulty.get(chart.difficulty)

        width, height = 108, 36
        # noinspection DuplicatedCode
        du.rounded_rect(x, y, width, height, radius=4, fill=diff.bg)
        du.cut_line(x, y, width, height, radius=4, line_y=y + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(x, y, width, height, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        du.difficulty(x + 2.5, y + 4.3, diff)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(badge, self.ms.xy(x + 85, y + 2), badge)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(x + 64, y + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(x + 2, y + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore(x + 38, y + 25, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        c, t, _tl, tc = Combo.get(ach.combo)
        du.evaluate(x + 3, y + 27, text=tc if self.du.cn_level == 2 else t, color=c)
        c, t, _tl, tc = Sync.get(ach.sync)
        du.evaluate(x + 3, y + 32, text=tc if self.du.cn_level == 2 else t, color=c)

        info_line5 = [
            f"谱师: {chart.des}",
            f"拟合定数: {chart.lv_synh:.4f}" if chart.lv_synh else '',
        ]

        du.rounded_rect(x + 64, y + 9, 42, 25, fill=bcm(diff.bg, '#0009'), radius=1.5)
        du.infos(x + 65.5, y + 21.65, lines=(info_line5 + [''] * 5)[:5], line_height=4.5, limit_width=-1,
                 font=FONT.font('MIS_DB', size=self.ms.x(3.2)))

        return width, height

    def chart_box_lite(self, x, y, chart: MaiChart, cabinet_dx: bool, server: SERVER_TAG, plus_level: int = 6,
                       is_utage: bool = False) -> Tuple[int, int]:
        """组件：谱面信息框 Lite"""
        du = self.du
        diff = Difficulty.get(chart.difficulty)

        width, height = 108, 25
        # noinspection DuplicatedCode
        du.rounded_rect(x, y, width, height, radius=4, fill=diff.bg)
        du.cut_line(x, y, width, height, radius=4, line_y=y + 2, line_h=5, fill=diff.title_bg)
        du.rounded_rect(x, y, width, height, radius=4, fill=None, outline=diff.frame, width=1)
        # 难度、DX
        du.difficulty(x + 2.5, y + 4.3, diff)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(badge, self.ms.xy(x + 85, y + 2), badge)
        # 等级 LV
        plus = round(chart.lv % 1 * 10) >= plus_level
        du.level(x + 64, y + 7.4, diff, chart.lv, plus=plus, ignore_decimal=is_utage)
        # 达成率
        ach = chart.get_ach(server=server)
        du.ach(x + 46, y + 9, diff, ach.achievement)
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(x + 2, y + 20, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)
        c, t, _tl, tc = Combo.get(ach.combo)
        du.evaluate(x + 3, y + 12, text=tc if self.du.cn_level == 2 else t, color=c)
        c, t, _tl, tc = Sync.get(ach.sync)
        du.evaluate(x + 3, y + 17, text=tc if self.du.cn_level == 2 else t, color=c)

        return width, height

    def chart_box_mini(self, x, y, chart: MaiChart, cabinet_dx: bool, plus_level: int = 6,
                       is_utage: bool = False, server: SERVER_TAG = "JP") -> Tuple[int, int]:
        """组件：谱面信息框 Mini (更紧凑的布局，适用于多行并列或背景填充)"""
        du = self.du
        diff = Difficulty.get(chart.difficulty)
        ach = chart.get_ach(server=server)

        # 定义 Mini 尺寸：宽度略窄，高度大幅度压缩 (从 25 降至 16)
        width, height = 86, 16 

        # 1. 绘制底色与装饰感边框
        # 背景填充
        du.rounded_rect(x, y, width, height, radius=2.5, fill=diff.bg)
        # 顶部切线装饰（保留 Lite 风格的视觉逻辑，但缩减高度）
        du.cut_line(x, y, width, height, radius=2.5, line_y=y + 1, line_h=3.5, fill=diff.title_bg)
        # 外边框（最后压一层确保清晰）
        du.rounded_rect(x, y, width, height, radius=2.5, fill=None, outline=diff.frame, width=1)

        # 2. 难度文本与 DX 标识 (左侧区域)
        du.difficulty(x + 2, y + 3.5, diff)
        badge = IMU.draw_badge(is_cabinet_dx=cabinet_dx, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(badge, self.ms.xy(x + 72, y + 1.5), badge)

        # 3. 等级 LV (紧跟在难度后面)
        plus = round(chart.lv % 1 * 10) >= plus_level
        # 坐标微调，使等级和难度文字在同一水平线附近
        du.level(x + 52, y + 6.5, diff, chart.lv, plus=plus, ignore_decimal=is_utage)

        # 4. 达成率 (居中偏右布局)
        du.ach(x + 36, y + 8, diff, ach.achievement)

        # 5. 状态 (FC/Sync) - 采用水平并列或极窄间距
        # 在 Mini 模式下，如果空间有限，FC 和 Sync 通常并排显示或缩小字体
        c_combo, t_combo, _tl, tc_combo = Combo.get(ach.combo)
        c_sync, t_sync, _tl, tc_sync = Sync.get(ach.sync)

        # 使用 self.du.cn 判定语言，2 为全中文
        text_combo = tc_combo if du.cn_level == 2 else t_combo
        text_sync = tc_sync if du.cn_level == 2 else t_sync

        # 绘制：水平排列在底部
        du.evaluate(x + 2, y + 11.5, text=text_combo, color=c_combo)
        du.evaluate(x + 22, y + 11.5, text=text_sync, color=c_sync)

        # 6. DX 分数
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(x + 48, y + 11.5, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)

        return width, height

    def mini_box(self, x: int, y: int, data: MaiData, diff_number: int, server: SERVER_TAG) -> Tuple[int, int]:
        """组件：Mini 成绩框"""
        du = self.du
        ms = self.ms
        diff = Difficulty.get(diff_number)
        chart = data.get_chart(diff_number)
        if not chart:
            return 0, 0  # 未绘制
        ach = chart.get_ach(server=server)
        
        width, height = 97, 36

        # 外框背景
        du.draw.rounded_rectangle(
            ms.size(x, y, width, height), 
            radius=ms.x(2.5), 
            fill=diff.bg, 
            outline=diff.frame,
            width=3, 
            corners=(True, True, True, True)
        )

        # 标题栏
        du.draw.rectangle(ms.size(x, y + 2, width, 5), fill=diff.title_bg)

        # 标题栏文字
        limit_t = FONT.font('MIS_HE', size=ms.x(4.6)).getlength('I' * 62)
        du.difficulty(x + 36, y + 4.2, diff, text=f'#{data.shortid}', limit_width=limit_t)

        # 曲绘
        if data.image:
            mask = IMU.get_mask(w=32, h=32, radius=1.5, ms=self.ms)
            cover_img = data.image.resize(self.ms.xy(32, 32), Image.Resampling.LANCZOS)
            self.img.paste(cover_img, self.ms.xy(x + 2, y + 2), mask)
            
            

        # 谱面类型 (SD/DX)
        badge = IMU.draw_badge(is_cabinet_dx=data.is_cabinet_dx, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(badge, self.ms.xy(x + 75, y + 2), badge)

        # 达成率
        du.ach(x + 35, y + 9, diff, ach_percent=ach.achievement)

        offset = 1 if self.cn_level == 2 else 0
        # FC/FC+/AP/AP+
        if ach.combo:
            c, _t, tl, tc = Combo.get(ach.combo)
            du.evaluate(x + 36, y + 27, text=tc if self.cn_level == 2 else tl, color=c)
            
        # SYNC/FS/FS+/FDX/FDX+
        if ach.sync:
            c, _t, tl, tc = Sync.get(ach.sync)
            du.evaluate(x + 36, y + 32, text=tc if self.cn_level == 2 else tl, color=c, offset=offset)

        # INFO
        # 留空 (x+53, y+25, w=42, h=5) 可供自定义

        # DXSCORE
        dxs, dxs_max, dxs_star = ach.dxscore_tuple
        du.dxscore_lite(x + 53, y + 31, score=dxs, max_score=dxs_max, star_count=dxs_star, diff=diff)

        # 外框边框
        du.draw.rounded_rectangle(
            ms.size(x, y, width, height), 
            radius=ms.x(2.5), 
            fill=None, 
            outline=diff.frame,
            width=3, 
            corners=(True, True, True, True)
        )

        return width, height

    def b50_box(self, x: int, y: int, data: MaiData, diff_number: int, server: SERVER_TAG, current_version: int,
                index: int, is_b15: Optional[bool] = None) -> tuple[int, int]:
        """组件：B50 成绩框"""
        du = self.du
        ms = self.ms
        diff = Difficulty.get(diff_number)
        chart = data.get_chart(diff_number)
        if not chart:
            return 0, 0  # 未绘制

        w, h = self.mini_box(x, y, data, diff_number, server=server)

        du.rounded_rect(x + 53, y + 25, 42, 5, fill=bcm(diff.bg, '#0009'), radius=2)
        du.rounded_rect(x + 53, y + 25, 16, 5, fill='#006', radius=2)
        b_type = '15' if is_b15 else '35'
        du.text(x+61, y+27.5, f"b{b_type} #{index}", fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=ms.x(3)))
        du.text(x+70, y+27.5, f"{chart.lv:.1f} > {data.get_chart_dxrating(diff_number, server, current_version)}", fill='#FFF', anchor='lm', font=FONT.font('MIS_DB', size=ms.x(3)))

        return w, h


def draw_info_box(maidata: MaiData, server: SERVER_TAG, user_info: dict | None = None,
                  ms: MS = _MS_DEFAULT, cn_level: Literal[0, 1, 2] = 0) -> Image.Image:
    width, fw = 220, 10  # width, frame_width
    all_width = width + fw * 2

    # Board 1: 曲绘和基本信息
    cover_width = 54
    board1 = Image.new('RGBA', ms.xy(width, cover_width + 2), NO_COLOR)
    du1 = DrawUnit(board1, multiple=ms, cn_level=cn_level)
    # 曲绘
    img = maidata.image if maidata.image else Image.new('RGB', ms.xy(cover_width, cover_width), color='#999')
    mask = IMU.get_mask(w=cover_width, h=cover_width, radius=5, ms=ms)
    if img.size != (cover_width, cover_width):
        cover_img = img.resize(ms.xy(cover_width, cover_width), Image.Resampling.LANCZOS)
    else:
        cover_img = img  # 避免不必要的复制
    board1.paste(cover_img, ms.xy(1, 1), mask)
    du1.rounded_rect(1, 1, cover_width, cover_width, radius=5, fill=None, outline='#FFF', width=1)
    # 标题、艺术家、ID、BPM、来源
    dx = cover_width + 5
    du1.text(dx, 0, text=maidata.title, fill='#FFF', anchor='la', font=FONT.font('MIS_HE', size=ms.x(11)))
    du1.text(dx, 14, text=maidata.artist, fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(5)))
    du1.text(dx, 23, text=f"ID {maidata.shortid}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(6)))
    du1.text(dx+30, 23, text=f"BPM {maidata.bpm}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(6)))
    du1.text(dx+60, 23, text=f"谱面来源: {maidata.converter}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(6)))
    # 流派、JP/CN 版本
    margin = 5
    dy = 32
    im_y1, im_y1_5 = dy+3, dy+12  # (标题高 5，图片高 18：5 + 18/2 = 14) 再整体向上 y-2 和上方文本微调
    genre_x, jpv_x, cnv_x, dv_x = dx, dx+34+margin, dx+68+margin*2, dx+102+margin*3
    du1.text(genre_x, dy, text="流派", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(4)))
    if maidata.genre:
        genre_text, genre_fill = get_genre(maidata.genre, cn_level=cn_level)
        genre_text = genre_text.replace('\\n', '\n')
        du1.text(genre_x+17, im_y1_5, text=genre_text, fill=genre_fill, anchor='mm', font=FONT.font('MIS_DB', size=ms.x(5)),
                shadow=(1.2, '#FFF'))

    du1.text(jpv_x, dy, text="JP", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(4)))
    if maidata.version:
        if ver_jp := ASSETS.version_image(maidata.version, size=ms.xy(34, 16)):
            board1.paste(ver_jp, ms.xy(jpv_x, im_y1), ver_jp)
        else:
            text = VERSIONS_DATA.get(maidata.version, str(maidata.version)).replace(' ', '\n')
            du1.text(jpv_x+17, im_y1_5, text=text, fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=ms.x(5)))
     
    du1.text(cnv_x, dy, text="CN", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(4)))
    if maidata.version_cn:
        if ver_cn := ASSETS.version_image(maidata.version_cn, size=ms.xy(34, 16)):
            board1.paste(ver_cn, ms.xy(cnv_x, im_y1), ver_cn)
        else:
            text = VERSIONS_DATA.get(maidata.version_cn, str(maidata.version_cn)).replace(' ', '\n')
            du1.text(cnv_x+17, im_y1_5, text=text, fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=ms.x(5)))
    else:
        du1.text(cnv_x+17, im_y1_5, text="X\n", fill='#F00', anchor='mm', font=FONT.font('MIS_DB', size=ms.x(4)),
                stroke=(0.8, '#FFF'))
        du1.text(cnv_x+17, im_y1_5, text="\n国服无此乐曲", fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=ms.x(4)))
    # 游玩记录信息
    if user_info:
        # TODO 获取实际数据
        record_info = '\n'.join([
            f"{get_full_width_text(user_info.get('nickname', 'maimai'))} (Ra {user_info.get('rating', '---')})",
            "Updated:",
            f"  [CN] {user_info.get('updated_cn', 'Now (from diving-fish)')}",
            f"  [JP] {user_info.get('updated_jp', 'Not Updated')}",
        ])
        du1.text(dv_x, dy, text="游玩数据", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=ms.x(4)))
        du1.text(dv_x, im_y1_5, text=record_info, fill='#FFF', anchor='lm', font=FONT.font('MIS_DB', size=ms.x(2.8)))
    del du1  # 释放绘图单元资源

    # Board 2: 别名信息
    if maidata.aliases:
        font_size = 4
        font = FONT.font('MIS_DB', size=ms.x(font_size))
        alias_width_list = [(alias.alias, font.getlength(alias.alias)) for alias in maidata.aliases]
        # 划定别名每行的分割
        alias_cut: list[tuple[list[str], float]] = [([], 0)]  # [(alias_list, total_width), ...]
        for alias, alias_width in alias_width_list:
            # TODO 将空格更换为 ms.x(1.2) 宽度
            if alias_cut[-1][1] + alias_width + font.getlength(' ') > ms.x(width):
                alias_cut.append(([alias], alias_width))
            else:
                alias_cut[-1][0].append(alias)
                alias_cut[-1] = (alias_cut[-1][0], alias_cut[-1][1] + alias_width + font.getlength('  '))
        aliases_height = (len(alias_cut) + 1) * font_size * 1.5  # 带上标题行的高度
        board2 = Image.new('RGBA', ms.xy(width, aliases_height), NO_COLOR)
        du2 = DrawUnit(board2, multiple=ms, cn_level=cn_level)
        du2.text(0, 0, text="这首歌的别名包括：", fill='#FFF', anchor='la', font=font)
        for i, (alias_list, _) in enumerate(alias_cut):
            # TODO 后续修改为逐词绘制，并手动绘制下划线
            du2.text(0, (i+1)*font_size*1.5, text='  '.join(alias_list), fill='#FFF', anchor='la', font=font)
        del du2  # 释放绘图单元资源
    else:
        board2 = None

    # Board 3: 谱面数据
    chart_imgs = []
    for diff, chart in maidata.charts.items():
        # 对于难度较高的谱面使用完整版信息框，对于难度较低的谱面使用精简版信息框
        func = IMU.chart_box if diff >= 4 else IMU.chart_box_lite
        chart_img = func(chart=chart, cabinet_dx=maidata.is_cabinet_dx, server=server, ms=ms, cn_level=cn_level)
        chart_imgs.append(chart_img)

    # 计算谱面信息框的总高度
    margin_msed = ms.x(2)
    rows_data = [] # 存储 (chunk, y_offset)
    current_y = 0

    for i in range(0, len(chart_imgs), 2):
        if i > 0:
            current_y += margin_msed
        chunk = chart_imgs[i:i+2]
        row_height = max(img.size[1] for img in chunk)
        rows_data.append((chunk, current_y))
        current_y += row_height

    board3 = Image.new('RGBA', (ms.x(width), current_y), NO_COLOR)
    # 将谱面信息框 paste mark 到 board3 上，粘贴后释放资源
    canvas_width = ms.x(width)
    chart_w = chart_imgs[0].size[0] 
    right_x = canvas_width - chart_w
    for chunk, y_offset in rows_data:
        # 粘贴左侧图片
        board3.paste(chunk[0], (0, y_offset), chunk[0])
        chunk[0].close()
        # 可能存在的右侧图片
        if len(chunk) > 1:
            board3.paste(chunk[1], (right_x, y_offset), chunk[1])
            chunk[1].close()
    # 确保释放
    chart_imgs.clear()
    del chart_imgs

    # Board 4: 版权底条
    board_last = IMU.copyright_bar(width=all_width, ms=ms, cn_level=cn_level)

    # BoardCraft
    margin = ms.x(fw) // 3
    boards = [board for board in (board1, board2, board3) if board is not None]
    all_height_msed = sum((
        sum(b.height for b in boards),  # 主要内容板块高度
        board_last.height,  # 版权底条高度
        ms.x(fw) * 2,  # 上下外边距
        (len(boards) - 1) * margin  # 板块间距 (1/3 外边距的内距)
    ))
    all_width_msed = ms.x(all_width)
    result_img = Image.new('RGBA', (all_width_msed, all_height_msed), COLOR_THEME)
    bg_img = ASSETS.background((all_width_msed, round(all_width_msed)))
    result_img.paste(bg_img, (0, 0)) if bg_img else None  # 直接粘贴，短会清除多余，长会保留底边
    current_y = ms.x(fw)
    for board in boards:
        result_img.paste(board, (ms.x(fw), current_y), board)
        current_y += board.height + margin
    # 最后贴上版权底条
    footer_y = all_height_msed - board_last.height
    result_img.paste(board_last, (0, footer_y), board_last)
    return result_img

    # self.img: Image.Image = ASSETS.background(ms.xy(width, height)) or Image.new('RGBA', ms.xy(width, height), COLOR_THEME)
    # self.img.convert('RGBA')
    



class DrawInfo(DrawFactory):
    """实现 `info11951` 图像的绘制"""

    def __init__(self, maidata: MaiData, server: SERVER_TAG, multiple: float = 1, cn_level: Literal[0, 1, 2] = 0):
        super().__init__(width=240, height=240, ms_multiple=int(10 * multiple), cn_level=cn_level)
        self._info(maidata, server)

    def _info(self, maidata: MaiData, server: SERVER_TAG):
        """实现 `info11951` 图像的绘制"""
        x, y = 10, 10
        width = 220
        margin = 5
        du = self.du

        # ========== Module.1 曲绘和基本信息 ==========
        # 曲绘
        cover_size = 54
        img = maidata.image if maidata.image else Image.new('RGB', (10, 10), color='#999')
        # du.image(x, y, cover_size, cover_size, radius=5, outline='#FFF', outline_width=1, png=img)
        
        mask = IMU.get_mask(w=cover_size, h=cover_size, radius=5, ms=self.ms)
        cover_img = img.resize(self.ms.xy(cover_size, cover_size), Image.Resampling.LANCZOS)
        self.img.paste(cover_img, self.ms.xy(x + 2, y + 2), mask)
        du.rounded_rect(x+2, y+2, cover_size, cover_size, radius=5, fill=None, outline='#FFF', width=1)
        
        t = cover_size + margin
        # 标题
        du.text(x + t, y, text=maidata.title, fill='#FFF', anchor='la',
                font=FONT.font('MIS_HE', size=self.ms.x(11)))
        # 艺术家
        du.text(x + t, y + 14, text=maidata.artist, fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(5)))
        # ShortID, BPM
        du.text(x + t, y + 23, text=f"ID {maidata.shortid}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(6)))
        du.text(x + t + 30, y + 23, text=f"BPM {maidata.bpm}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(6)))
        du.text(x + t + 60, y + 23, text=f"数据来源: {maidata.converter}", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(6)))
        # Genre, Version
        gvv_title = y + 34
        gvv_la = gvv_title + 5
        gvv_mm = gvv_la + 9

        p = 34 + margin
        du.text(x+t, gvv_title, text="流派", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(4)))
        du.text(x+t+p, gvv_title, text="JP", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(4)))
        du.text(x+t+p*2, gvv_title, text="CN", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(4)))

        # Genre
        genre_text, genre_fill = get_genre(maidata.genre, cn_level=self.cn_level)
        genre_text = genre_text.replace('\\n', '\n')
        du.text(x+t+17, gvv_mm, text=genre_text, fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(5)),
                shadow=(1.5, '#FFF'))
        du.text(x+t+17, gvv_mm, text=genre_text, fill=genre_fill, anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(5)),
                shadow=(1, '#FFF'))
        # JP
        if ver_jp := ASSETS.version_image(maidata.version, size=self.ms.xy(34, 16)):
            self.img.paste(ver_jp, self.ms.xy(x+t+p, gvv_la), ver_jp)
        else:
            text = VERSIONS_DATA.get(maidata.version, str(maidata.version))
            text = text.replace(' ', '\n')
            du.text(x+t+p+17, gvv_mm, text=text,
                    fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(5)))
        # CN: 需要考虑不存在
        if maidata.version_cn:
            if ver_cn := ASSETS.version_image(maidata.version_cn, size=self.ms.xy(34, 16)):
                self.img.paste(ver_cn, self.ms.xy(x+t+p*2, gvv_la), ver_cn)
            else:
                text = VERSIONS_DATA.get(maidata.version_cn, str(maidata.version_cn))
                text = text.replace(' ', '\n')
                du.text(x+t+p*2+17, gvv_mm, text=text,
                        fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(5)))
        else:
            du.text(x+t+p*2+17, gvv_mm, text="X\n", fill='#F00', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(4)),
                    stroke=(0.8, '#FFF'))
            du.text(x+t+p*2+17, gvv_mm, text="\n国服无此乐曲", fill='#FFF', anchor='mm', font=FONT.font('MIS_DB', size=self.ms.x(4)))

        y += cover_size + margin

        # ========== Module.2 乐曲别名数据 ==========
        if maidata.aliases:
            line_height = 7
            padding = 5

            # 绘制标题
            du.text(x, y, text="这首歌的别名包括：", fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(5)))
            y += line_height
            current_x_offset = 0

            for alias in maidata.aliases:
                alias_width = self.ms.rev(FONT.font('MIS_DB', size=self.ms.x(5)).getlength(alias.alias))
                if current_x_offset + alias_width > width:
                    y += line_height
                    current_x_offset = 0

                # TODO: 增加下划线分辨别名
                du.text(x + current_x_offset, y, text=alias.alias, fill='#FFF', anchor='la', font=FONT.font('MIS_DB', size=self.ms.x(5)))
                current_x_offset += alias_width + padding

            y += line_height + margin

        # ========== Module.3 详细谱面数据 ==========
        now_x = x
        for i, chart in enumerate(maidata.charts.values()):
            if chart.difficulty >= 4:
                cb = IMU.chart_box(chart, cabinet_dx=maidata.is_cabinet_dx, server=server, ms=self.ms, cn_level=self.cn_level)
                self.img.paste(cb, self.ms.xy(now_x, y), cb)
                _w, ht = cb.size
                h = self.ms.rev(ht)
                # _w, h = self.chart_box(now_x, y, chart, cabinet_dx=maidata.is_cabinet_dx, server=server)
            else:
                _w, h = self.chart_box_lite(now_x, y, chart, cabinet_dx=maidata.is_cabinet_dx, server=server)
            if (i + 1) % 2 == 1:
                now_x = 123
                if len(maidata.charts) - i == 1:
                    y += h + margin  # 向下传递
            else:
                now_x = 10
                y += h + margin

        # ========== Module.4 版权信息 ==========
        cb = IMU.copyright_bar(240, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(cb, (0, self.ms.x(y)), cb)
        _w, h = cb.size
        # 切割
        self.img = self.img.crop((0, 0, self.ms.x(240), self.ms.x(y + h)))
        self.img = self.img.convert('RGB')


class DrawB50Boxex(DrawFactory):
    """实现 `b50` 图像的绘制"""

    def __init__(self, b50manager: MaiB50Manager, user_name: str, user_avatar: Optional[Image.Image] = None,
                 multiple: float = 1, cn_level: Literal[0, 1, 2] = 0):
        super().__init__(width=411, height=580, ms_multiple=int(10 * multiple), cn_level=cn_level)
        self._b50(b50manager, user_name, user_avatar)

    def _b50(self, b50manager: MaiB50Manager, user_name: str, user_avatar: Optional[Image.Image]):
        """实现 `b50` 图像的绘制"""
        x, y = 7, 7
        margin = 3
        du = self.du

        # 头像
        user_avatar = user_avatar if user_avatar else Image.new('RGB', (10, 10), color='#CCC')
        # i, m = IMU.radius_image(image=user_avatar, w=32, h=32, radius=5, outline=(1, '#FFF'), ms=self.ms)
        # self.img.paste(i, self.ms.xy(x, y), m)
        # Username
        du.rounded_rect(x+36, y+15, 100, 17, fill='#333', radius=2)
        du.text(x+36, y+23.5, text=' ' + get_full_width_text(user_name), fill='#FFF', anchor='lm',
                font=FONT.font('MIS_DB', size=self.ms.x(10)))
        # DX Rating
        if dxra_frame := ASSETS.dxrating_image(b50manager.dxrating_filename, size=self.ms.xy(70, 14)):
            self.img.paste(dxra_frame, self.ms.xy(x+36, y), dxra_frame)
        # Rating Number
        font = FONT.font('MIS_DB', size=self.ms.x(8))
        for i, digit in enumerate(str(b50manager.dxrating)[::-1]):
            dx = 57.5 - 5.5 * i
            du.text(x+36+dx, y+7.1, text=digit, fill='#FCC916', anchor='mm', font=font,
                    stroke=(0.35, '#333'))

        y += 32 + margin * 2

        b35, b15 = b50manager.get_lists()

        for i, (maidata, diff) in enumerate(b35, start=1):
            tx = x + i % 4 * (97 + 3)
            ty = y + i // 4 * (36 + 3)
            _w, _h = self.b50_box(tx, ty, maidata, diff_number=diff, server=b50manager.server, current_version=b50manager.current_version, index=i, is_b15=False)
        y += (len(b35) + 3) // 4 * (36 + 3) + margin

        for i, (maidata, diff) in enumerate(b15, start=1):
            tx = x + i % 4 * (97 + 3)
            ty = y + i // 4 * (36 + 3)
            _w, _h = self.b50_box(tx, ty, maidata, diff_number=diff, server=b50manager.server, current_version=b50manager.current_version, index=i, is_b15=True)
        y += (len(b15) + 3) // 4 * (36 + 3)

        cb = IMU.copyright_bar(411, ms=self.ms, cn_level=self.cn_level)
        self.img.paste(cb, (0, self.ms.x(y)), cb)
        _w, h = cb.size
        # 切割
        self.img = self.img.crop((0, 0, self.ms.x(411), self.ms.x(y + h)))
        self.img = self.img.convert('RGB')


def simple_list(maidata_list: List[MaiData]) -> Image.Image:
    """生成一个简单的文本列表图，展示多个曲目的信息"""
    text = '\n'.join([f"{maidata.shortid}.\t{maidata.title}"
                      for maidata in maidata_list])
    font = FONT.font('MIS_DB', size=16)

    x1, y1, x2, y2 = ImageDraw.Draw(Image.new('RGB', (1, 1), color='#FFF')).multiline_textbbox((0, 0), text=text, font=font)
    width, height = int(x2 - x1 + 10), int(y2 - y1 + 10)
    img = Image.new('RGB', (width, height), color='#FFF')
    img_draw = ImageDraw.Draw(img)
    img_draw.text((2, 2), text, fill='#000', font=font)

    return img


if __name__ == "__main__":
    # 绘图调试
    aliases = ["transcend lights","超越光","九月的雨","超超光光","美瞳广告","小女孩们的茶话会","超越之光","bright主题曲","别急19","音击的武士","tl","萝莉的雨","音击妹妹","114514","音击的雨"]
    maidata = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, 'DX', 18, 2023, 'debug', Path(r"E:\Projects\PythonProjects\lyra-bot\temp\debug_cover.png"), None,
                      aliases=[MaiAlias(11451, a, 0, -1) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(11451, i, 1+i*3)
        chart.set_ach(MaiChartAch(11451, i, 'JP', 97.6+i*0.5, combo=3, sync=2))
        maidata.set_chart(chart)
    
    # target = DrawInfo(maidata, server='JP').get_image()
    target = draw_info_box(maidata, server='JP', cn_level=2)

    #     target = DrawB50Boxex([(maidata, randint(2, 6)) for _ in range(35)], [(maidata, randint(2, 6)) for _ in range(15)], multiple=1, cn_level=1, user_name="NameWCNM", user_avatar=None,
    #                       current_version=25, ra=15254).get_image()

    target.save(r"E:\UserFile\Desktop\debug2.png")
