"""
image_gen.components.evaluate
连击/同步类型组件

> FC / FS / ALL PERFECT +
"""
from typing import Literal
from PIL import Image
from functools import lru_cache

from ..utils import MS, FontCode, FontManager
from ...utils.enums import UICode
from ..style import _COMBO_TYPE, _SYNC_TYPE, get_combo_style, get_sync_style
from .base import TextDrawStyle, Drawer


_EVALUTATE_TYPE = _COMBO_TYPE | _SYNC_TYPE
_EVALUATE_INPUT_TYPE = Literal['combo', 'sync']
_EVALUATE_DISPLAY_TYPE = Literal['full', 'short', 'cn']


class EvaluateBadge:
    """FC/ FS 评价组件"""

    @classmethod
    @lru_cache(maxsize=8)
    def _evaluate_badge(cls, evaluate: _EVALUTATE_TYPE, evaluate_type: _EVALUATE_INPUT_TYPE,
                       display: _EVALUATE_DISPLAY_TYPE = 'full', ms: MS = MS()) -> Image.Image:
        if evaluate_type == 'combo' and isinstance(evaluate, _COMBO_TYPE):
            style = get_combo_style(combo=evaluate, short=(display == 'short'), is_cn_all=(display == 'cn'))
        elif evaluate_type == 'sync' and isinstance(evaluate, _SYNC_TYPE):
            style = get_sync_style(sync=evaluate, short=(display == 'short'), is_cn_all=(display == 'cn'))
        else:
            return Image.new('RGBA', (0, 0), "#FFFFFF00")

        font = FontManager.font(FontCode.MiSans_Heavy, ms.x(3))
        text_width = ms.rev(round(font.getlength(style.content)))
        img = Image.new('RGBA', ms.xy(text_width + 1, 4.5), "#FFFFFF00")
        drawer = Drawer(img, ms=ms)
        drawer.text(0.5, 2.25, text=style.content, tds=TextDrawStyle(
            fill=style.fill, anchor='lm', font=font,
            stroke=style.stroke, stroke_width=0.5,
            shadow=style.shadow, shadow_width=0.65
        ))
        return img

    @classmethod
    def _evaluate(cls, evaluate: _EVALUTATE_TYPE, evaluate_type: _EVALUATE_INPUT_TYPE,
                  mini: bool = False, ui_code: UICode = UICode.JP, ms: MS = MS()) -> Image.Image:
        display = 'short' if mini else 'full'
        display = 'cn' if ui_code.is_cn_all else display
        return cls._evaluate_badge(evaluate=evaluate, evaluate_type=evaluate_type, display=display, ms=ms).copy()

    @classmethod
    def combo(cls, combo: _COMBO_TYPE, mini: bool = False, ui_code: UICode = UICode.JP, ms: MS = MS()) -> Image.Image:
        """绘制连击徽章"""
        return cls._evaluate(evaluate=combo, evaluate_type='combo', mini=mini, ui_code=ui_code, ms=ms)

    @classmethod
    def sync(cls, sync: _SYNC_TYPE, mini: bool = False, ui_code: UICode = UICode.JP, ms: MS = MS()) -> Image.Image:
        """绘制同步徽章"""
        return cls._evaluate(evaluate=sync, evaluate_type='sync', mini=mini, ui_code=ui_code, ms=ms)
