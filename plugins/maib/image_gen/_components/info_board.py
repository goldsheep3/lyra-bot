"""
image_gen.components.info
MaiChartInfo 看板构建器
"""
from typing import Optional

from PIL import Image

from ...utils.models import MaiData, MaiUser
from ...utils.enums import UICode, Server
from ...utils.map import Versions
from .. import color as Color
from ..utils import MS, FontCode, FontManager, ImageManager
from ..tools import FullWidthConverter
from ..style import get_genre_style
from .base import TextDrawStyle, Drawer
from . import CopyrightBadge, ChartBoxBadge


class MaiChartInfoBoard:
    
    # TODO 待修整
    @staticmethod
    def draw_info_box(maidata: MaiData, server: Server, maiuser: Optional[MaiUser] = None,
                  ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """绘制 mai_info 看板"""
        width, fw = 220, 10
        all_width = width + fw * 2

        cover_width = 54
        board1 = Image.new("RGBA", ms.xy(width, cover_width + 2), Color.TRANSPARENT)
        drawer1 = Drawer(board1, ms=ms)

        img = maidata.image if maidata.image else Image.new("RGB", ms.xy(cover_width, cover_width), color="#999")
        mask = Drawer.get_mask(w=cover_width, h=cover_width, radius=5, ms=ms)
        cover_img = img.resize(ms.xy(cover_width, cover_width), Image.Resampling.LANCZOS) if img.size != (cover_width, cover_width) else img
        board1.paste(cover_img, ms.xy(1, 1), mask)
        drawer1.rounded_rect(1, 1, cover_width, cover_width, radius=5, fill=None, outline="#FFF", width=1)

        dx = cover_width + 5
        drawer1.text(dx, 0, text=maidata.title, tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Heavy, size=ms.x(11))
        ))
        drawer1.text(dx, 14, text=maidata.artist, tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(5))
        ))
        drawer1.text(dx, 23, text=f"ID {maidata.shortid}", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(6))
        ))
        drawer1.text(dx + 30, 23, text=f"BPM {maidata.bpm}", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(6))
        ))
        drawer1.text(dx + 60, 23, text=f"谱面来源: {maidata.converter}", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(6))
        ))

        margin = 5
        dy = 32
        im_y1, im_y1_5 = dy + 3, dy + 12
        genre_x, jpv_x, cnv_x, dv_x = dx, dx + 34 + margin, dx + 68 + margin * 2, dx + 102 + margin * 3
        drawer1.text(genre_x, dy, text="流派", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4))
        ))
        if maidata.genre:
            gstyle = get_genre_style(maidata.genre, ui_code=ui_code)
            drawer1.text(genre_x + 17, im_y1_5, text=gstyle.content, tds=TextDrawStyle(
                fill=gstyle.fill, anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(5)),
                shadow=gstyle.shadow, shadow_width=1.2
            ))

        drawer1.text(jpv_x, dy, text="JP", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4))
        ))
        if maidata.version:
            if ver_jp := ImageManager.version_image(maidata.version, size=ms.xy(34, 16)):
                board1.paste(ver_jp, ms.xy(jpv_x, im_y1), ver_jp)
            else:
                text = Versions.text_name(maidata.version, default=str(maidata.version)).replace(" ", "\n")
                drawer1.text(jpv_x + 17, im_y1_5, text=text, tds=TextDrawStyle(
                    fill="#FFF", anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(5))
                ))

        drawer1.text(cnv_x, dy, text="CN", tds=TextDrawStyle(
            fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4))
        ))
        if maidata.version_cn:
            if ver_cn := ImageManager.version_image(maidata.version_cn, size=ms.xy(34, 16)):
                board1.paste(ver_cn, ms.xy(cnv_x, im_y1), ver_cn)
            else:
                text = Versions.text_name(maidata.version_cn, default=str(maidata.version_cn)).replace(" ", "\n")
                drawer1.text(cnv_x + 17, im_y1_5, text=text, tds=TextDrawStyle(
                    fill="#FFF", anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(5))
                ))
        else:
            drawer1.text(cnv_x + 17, im_y1_5, text="X\n", tds=TextDrawStyle(
                fill="#F00", anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4)),
                stroke="#FFFFFF", stroke_width=0.8
            ))
            drawer1.text(cnv_x + 17, im_y1_5, text="\n国服无此乐曲", tds=TextDrawStyle(
                fill="#FFF", anchor="mm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4))
            ))

        if maiuser:
            drawer1.text(dv_x, dy, text="Record / 游玩记录", tds=TextDrawStyle(
                fill="#FFF", anchor="la", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(4))
            ))
            username_text = FullWidthConverter.convert(maiuser.get_username()) + "\n\n"
            drawer1.text(dv_x, im_y1_5, text=username_text, tds=TextDrawStyle(
                fill="#FFF", anchor="lm", font=FontManager.font(FontCode.MiSans_Demibold, size=ms.x(3))
            ))
            records = [
                "",
                f'[CN({maiuser.get_dxrating_data(Server.CN).total})] {maiuser.get_formated_time(Server.CN).replace("0","O")}',
                f'[JP({maiuser.get_dxrating_data(Server.JP).total})] {maiuser.get_formated_time(Server.JP).replace("0","O")}',
            ]
            drawer1.text(dv_x, im_y1_5, text="\n".join(records), tds=TextDrawStyle(
                fill="#FFF", anchor="lm", font=FontManager.font(FontCode.JBMono_Bold, size=ms.x(2.2))
            ))
            del drawer1

        if maidata.aliases:
            font_size = 4
            font = FontManager.font(FontCode.MiSans_Demibold, size=ms.x(font_size))
            alias_width_list = [(alias.alias, font.getlength(alias.alias)) for alias in maidata.aliases]
            alias_cut: list[tuple[list[str], float]] = [([], 0)]
            for alias, alias_width in alias_width_list:
                if alias_cut[-1][1] + alias_width + font.getlength(" ") > ms.x(width):
                    alias_cut.append(([alias], alias_width))
                else:
                    alias_cut[-1][0].append(alias)
                    alias_cut[-1] = (alias_cut[-1][0], alias_cut[-1][1] + alias_width + font.getlength("  "))
            aliases_height = (len(alias_cut) + 1) * font_size * 1.5
            board2 = Image.new("RGBA", ms.xy(width, aliases_height), Color.TRANSPARENT)
            drawer2 = Drawer(board2, ms=ms)
            drawer2.text(0, 0, text="这首歌的别名包括：", tds=TextDrawStyle(fill="#FFF", anchor="la", font=font))
            for i, (alias_list, _) in enumerate(alias_cut):
                drawer2.text(0, (i + 1) * font_size * 1.5, text="  ".join(alias_list),
                            tds=TextDrawStyle(fill="#FFF", anchor="la", font=font))
            del drawer2
        else:
            board2 = None

        chart_imgs: list[Image.Image] = []
        for diff, chart in maidata.charts.items():
            chart_img = ChartBoxBadge.chart_box(chart=chart, is_cabinet_dx=maidata.is_cabinet_dx, server=server,
                                                ms=ms, ui_code=ui_code, lite=diff < 4)
            chart_imgs.append(chart_img)

        margin_msed = ms.x(2)
        rows_data = []
        current_y = 0
        for index in range(0, len(chart_imgs), 2):
            if index > 0:
                current_y += margin_msed
            chunk = chart_imgs[index:index + 2]
            row_height = max(img.size[1] for img in chunk)
            rows_data.append((chunk, current_y))
            current_y += row_height

        board3 = Image.new("RGBA", (ms.x(width), current_y), Color.TRANSPARENT) if chart_imgs else None
        if board3 is not None:
            canvas_width = ms.x(width)
            chart_w = chart_imgs[0].size[0]
            right_x = canvas_width - chart_w
            for chunk, y_offset in rows_data:
                board3.paste(chunk[0], (0, y_offset), chunk[0])
                chunk[0].close()
                if len(chunk) > 1:
                    board3.paste(chunk[1], (right_x, y_offset), chunk[1])
                    chunk[1].close()
        chart_imgs.clear()
        del chart_imgs

        board_last = CopyrightBadge.copyright(width_px=all_width, ms=ms)

        margin = ms.x(fw) // 3
        boards = [board for board in (board1, board2, board3) if board is not None]
        all_height_msed = sum((sum(b.height for b in boards), board_last.height, ms.x(fw) * 2, (len(boards) - 1) * margin))
        all_width_msed = ms.x(all_width)
        result_img = Image.new("RGBA", (all_width_msed, all_height_msed), Color.THEME_CYAN)
        bg_img = ImageManager.background(size=(all_width_msed, round(all_width_msed)))
        if bg_img:
            result_img.paste(bg_img, (0, 0))
        current_y = ms.x(fw)
        for board in boards:
            result_img.paste(board, (ms.x(fw), current_y), board)
            current_y += board.height + margin
        footer_y = all_height_msed - board_last.height
        result_img.paste(board_last, (0, footer_y), board_last)
        return result_img.convert("RGB")


draw_info_board = MaiChartInfoBoard.draw_info_box