"""
image_gen.components.info
MaiChartInfo 看板构建器
"""
from typing import Optional, Literal
from dataclasses import dataclass

from PIL import Image

from ...utils.models import MaiData, MaiUser, MaiChart, MaiChartAch
from ...utils.enums import UICode, Server
from ...utils.map import Versions, DifficultyID, VersionID
from ...utils import get_level_plus_line
from ..color import TRANSPARENT, WHITE, BLACK, THEME_CYAN, GRAY, HALF_TRANSPARENT
from ..utils import MS, FontCode, FontManager, ImageManager
from ..tools import FullWidthConverter
from ..style import get_genre_style
from .base import TextDrawStyle, Drawer
from . import CopyrightBadge, ChartBoxBadgeV2
from ..tools import image_listed_to_rgb, image_grid_board


@dataclass
class _Alias:
    alias: str
    width: float
    line: int = 0
    x: float = 0

class MaiChartInfoBoard:
    
    width = 240
    ow = 4
    
    @classmethod
    def _alias_badge(cls, aliases: list[str], width: float, ms: MS = MS()) -> Image.Image:
        if not aliases:
            return Image.new("RGBA", (0, 0), TRANSPARENT)
        size = 4
        font = FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(size))
    
        alias_list = [_Alias(alias=alias, width=ms.rev(round(font.getlength(alias)))) for alias in aliases]
        line: int = 0
        x: float = width  # 保证第一个别名换行
        space_width = 2.5
        for alias in alias_list:
            if alias.width + x + space_width >= width:
                line += 1
                x = 0.0
            alias.line = line
            alias.x = x
            x += alias.width + space_width

        height = (line + 1) * (size * 2)
        img = Image.new("RGBA", ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        drawer.text(0, 0, text="这首歌的别名包括：", tds=TextDrawStyle(fill=WHITE, anchor="la", font=font))
        for alias in alias_list:
            drawer.text(x=alias.x, y=alias.line * size * 1.5, text=alias.alias,
                        tds=TextDrawStyle(fill=WHITE, anchor="la", font=font))
            line_y = (alias.line + 0.8) * size * 1.6
            drawer.line(x0=alias.x, y0=line_y, x1=alias.x + alias.width, y1=line_y, fill=WHITE, width=0.25)

        return img

    @classmethod
    def _metadata(cls, maidata: MaiData, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        width = cls.width

        image_size = 44
        image_outline_width = 1
        cap_margin = 1
        margin = 2.5
        half_size = image_size / 2
        cover_y = image_size + image_outline_width * 2 + cap_margin
        cap_width = half_size - margin
        cap_height = image_size*3.4/54 * 1.1
        alias_top = 36
        alias_img = cls._alias_badge(aliases=[alias.alias for alias in maidata.aliases], ms=ms, 
                                     width=width - image_size - image_outline_width * 2 - margin)
        
        height = max(
            cover_y + cap_height + cap_margin,  # 曲绘 + ID/BPM
            alias_top + ms.rev(alias_img.size[1]) + margin,  # 数据 + 别名
        )
        img = Image.new("RGBA", ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)

        # 曲绘
        with maidata.open_image() as cover_img:
            if cover_img is None:
                cover_img_now = Image.new("RGB", ms.xy(image_size, image_size), color=GRAY)
            elif cover_img.size != (image_size, image_size):
                cover_img_now = cover_img.resize(ms.xy(image_size, image_size), Image.Resampling.LANCZOS)
                cover_img.close()
            else:
                cover_img_now = cover_img
            mask = Drawer.get_mask(w=image_size, h=image_size, radius=5, ms=ms)
            img.paste(cover_img_now, ms.xy(image_outline_width, image_outline_width), mask)
            mask.close()
        drawer.rounded_rect(image_outline_width, image_outline_width, image_size, image_size,
                            radius=5, fill=None, outline=GRAY, width=image_outline_width)
        
        # 基础信息
        dx = image_size + image_outline_width * 2 + margin
        drawer.text(dx, 0, text=maidata.title, tds=TextDrawStyle(
            fill=WHITE, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Bold, size=ms.x(10.5))
        ))
        drawer.text(dx, 14, text=maidata.artist, tds=TextDrawStyle(
            fill=WHITE, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(5))
        ))
        
        genre_x, genre_y = dx + 50, 21.5
        genre_style = get_genre_style(maidata.genre, ui_code=ui_code)
        drawer.text(dx, genre_y, text="流派 / Genre: ", tds=TextDrawStyle(
            fill=WHITE, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(4))
        ))
        if genre_style.content.count('\n') == 1:
            content_left, content_right = genre_style.content.split('\n', 1)
            drawer.text(genre_x, genre_y, text=content_left, tds=TextDrawStyle(
                fill=genre_style.fill, anchor='ra', font=FontManager.font(FontCode.NotoSansSC_Bold, size=ms.x(4)),
                shadow=genre_style.shadow, shadow_width=1.2
            ))
            drawer.text(genre_x, genre_y, text=content_right, tds=TextDrawStyle(
                fill=genre_style.sub_fill, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Bold, size=ms.x(4)),
                shadow=genre_style.shadow, shadow_width=1.2
            ))
        else:
            content = genre_style.content.replace('\n', ' ')
            drawer.text(genre_x, genre_y, text=content, tds=TextDrawStyle(
                fill=genre_style.fill, anchor='ma', font=FontManager.font(FontCode.NotoSansSC_Bold, size=ms.x(4)),
                shadow=genre_style.shadow, shadow_width=1.2
            ))
        drawer.text(dx, 27, text=f"谱面来源 / Chart:  {maidata.converter}", tds=TextDrawStyle(
            fill=WHITE, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(4))
        ))
        
        cap_font = FontManager.font(FontCode.JBMono_Medium, size=ms.x(image_size*0.06))
        cap_tds = TextDrawStyle(fill=WHITE, anchor='mm', font=cap_font)
        cap_color = f"{genre_style.fill}77"  # 半透明
        drawer.capsule(margin, cover_y, cap_width, cap_height, fill=cap_color, outline=None, outline_width=0)
        drawer.text(margin + cap_width / 2, cover_y + cap_height / 2,
                    text=f"{"ID:":<4}{str(maidata.shortid).replace('0', 'O'):>6}", tds=cap_tds)
        drawer.capsule(margin + half_size, cover_y, cap_width, cap_height, fill=cap_color, outline=None, outline_width=0)
        drawer.text(margin + half_size + cap_width / 2, cover_y + cap_height / 2,
                    text=f"{"BPM:":<4}{str(maidata.bpm).replace('0', 'O'):>6}", tds=cap_tds)


        # 别名
        img.paste(alias_img, ms.xy(dx, alias_top), alias_img)
        alias_img.close()
        
        return img

    _charts_margin = 2
    _charts_font_size = 3.5

    @classmethod
    def _charts(cls, charts: list[MaiChart], server: Server, version: Optional[VersionID], cabinet: Literal['SD', 'DX'],
                maiuser: Optional[MaiUser] = None, is_b15: bool = False, ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        width = cls.width / 2
        margin = cls._charts_margin
        
        # 谱面列表
        if version is None:
            # 未上线谱面，绘制一个 UNKNOWN 谱面
            charts = [MaiChart(shortid=0, difficulty=0, lv=0, lv_cn=0)]

        if maiuser:
            dxrating_data = maiuser.get_dxrating_data(server)
            floor_rating = dxrating_data.b15.min if is_b15 else dxrating_data.b35.min
        else:
            floor_rating = None
        def generate():
            for chart in charts:
                plus = chart.lv * 10 % 10 >= get_level_plus_line(version=version) if version else False
                yield ChartBoxBadgeV2.box(
                    chart=chart, cabinet=cabinet, server=server, plus=plus, floor_rating=floor_rating,
                    ms=ms, ui_code=ui_code
                )
        chart_box_w, chart_box_h = ChartBoxBadgeV2.size()
        grid_img = image_grid_board(generate(), cols=1, gap_px=ms.x(margin/2), total_count=len(charts),
                                    box_size_px=ms.xy(chart_box_w, chart_box_h))
        if grid_img is None:
            return Image.new("RGBA", (0, 0), TRANSPARENT)

        font_size = cls._charts_font_size
        text_font = lambda m=1.0: FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(font_size*m))
        number_font = lambda m=1.0: FontManager.font(FontCode.JBMono_Medium, size=ms.x(font_size*m))
        font_h = font_size * 1.2
        version_w, version_h = 34, 16
        version_x, version_y = width - version_w, font_size

        grid_w, grid_h = chart_box_w, ms.rev(grid_img.size[1])
        grid_y = font_h * 5
        height = grid_y + grid_h
        x_margin = (width-grid_w)/2
        
        img = Image.new("RGBA", ms.xy(width, height), TRANSPARENT)
        drawer = Drawer(img, ms=ms)
        
        # 标题
        drawer.text(x_margin*2, 0, text=f"[{str(server)}] 谱面数据 / Chart Data",
                    tds=TextDrawStyle(fill=WHITE, anchor='la', font=text_font()))
        
        if maiuser:
            drawer.text(x_margin*2+font_h, font_h*1.2, text=FullWidthConverter.convert(maiuser.get_username()),
                        tds=TextDrawStyle(fill=WHITE, anchor='la', font=text_font()))
            user_name_width = ms.rev(round(text_font().getlength(FullWidthConverter.convert(maiuser.get_username()))))
            drawer.text(x_margin*2 + font_h + user_name_width + 2, font_h*2.2, text=f"({maiuser.get_dxrating_data(server).total})",
                        tds=TextDrawStyle(fill=WHITE, anchor='ls', font=number_font(0.9)))
            
            drawer.text(x_margin*2 + font_h, font_h*2.4, text=f"Update: {maiuser.get_formated_time(server)}",
                        tds=TextDrawStyle(fill=WHITE, anchor='la', font=number_font()))
            drawer.text(x_margin*2 + font_h, font_h*3.4, text=f"Provider: {'otogame' if server == Server.JP else 'diving-fish'}",
                        tds=TextDrawStyle(fill=WHITE, anchor='la', font=number_font()))
        # drawer.text(0, 0, text=content, tds=TextDrawStyle(
        #     fill=WHITE, anchor='la', font=FontManager.font(FontCode.NotoSansSC_Medium, size=ms.x(font_size))
        # ))
        
        # 版本
        drawer.text(version_x-x_margin, 0, text="版本 / Version", tds=TextDrawStyle(fill=WHITE, anchor='la', font=text_font(0.9)))
        if version is not None:
            version_img = ImageManager.version_image(version, size=ms.xy(version_w, version_h))
            if version_img:
                img.paste(version_img, ms.xy(version_x-x_margin, version_y), version_img)
            else:
                drawer.text(
                    version_x+version_w/2, version_y+version_h/2,
                    text=Versions.text_name(version, default=str(version)).replace(' ', '\n'),
                    tds=TextDrawStyle(fill="#771188", anchor='mm', font=text_font(), shadow=WHITE, shadow_width=0.5)
                )
        else:
            drawer.text(version_x+version_w/2, version_y+version_h/2, text="未上线\nNot Update",
                        tds=TextDrawStyle(fill="#881111", anchor='mm', font=text_font(),shadow=WHITE, shadow_width=0.5))
        
        # 谱面列表粘贴
        img.paste(grid_img, ms.xy(x_margin, grid_y), grid_img)
    
        return img

    @classmethod
    def _board(cls, maidata: MaiData, maiuser: Optional[MaiUser] = None, ms: MS = MS()) -> Image.Image:
        width = cls.width
        ow = cls.ow
        
        metadata_img = cls._metadata(maidata=maidata, ms=ms)
        chart_jp_img = cls._charts(
            charts=list(maidata.charts.values()), server=Server.JP, version=maidata.version, cabinet=maidata.cabinet,
            maiuser=maiuser, ms=ms)
        chart_cn_img = cls._charts(
            charts=list(maidata.charts.values()), server=Server.CN, version=maidata.version_cn, cabinet=maidata.cabinet,
            maiuser=maiuser, ms=ms)
        
        total_width = width + ow*2
        total_width_px = ms.x(total_width)
        copyright_img = CopyrightBadge.copyright_mpx(width_mpx=total_width, ms=ms)
    
        height = metadata_img.height + max(chart_jp_img.height, chart_cn_img.height)    
        total_height_px = height + ms.x(ow*1.5) + copyright_img.height
        img = Image.new("RGBA", (total_width_px, total_height_px), TRANSPARENT)
        
        bg_img = ImageManager.background(size=(total_width_px, total_height_px))
        if bg_img:
            img.paste(bg_img, (0, 0))
        img.paste(metadata_img, ms.xy(ow, ow), metadata_img)
        img.paste(chart_jp_img, (ms.x(ow), metadata_img.height + ms.x(ow/2)), chart_jp_img)
        img.paste(chart_cn_img, (ms.x(ow) + chart_jp_img.width, metadata_img.height + ms.x(ow/2)), chart_cn_img)
        img.paste(copyright_img,
                  (0, metadata_img.height + max(chart_jp_img.height, chart_cn_img.height) + ms.x(ow*1.5)),
                  copyright_img)
        
        return img

draw_info_board = MaiChartInfoBoard._board
