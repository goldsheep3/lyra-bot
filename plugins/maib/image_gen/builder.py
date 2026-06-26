"""
image_gen 高级画布拼装层
负责将底层组件和资源拼装为完整图片。
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Literal, Optional, Tuple, List

from PIL import Image, ImageDraw

from ..constants import *
from ..utils import MaiChart, MaiData, MaiUser, parse_dxrating_filename
from .components import BaseDrawer, TextStyle
from .config import MODEL_VERSION
from .models import (
    AchColor,
    Combo,
    Diff,
    Difficulty,
    EvalInfo,
    Sync,
    COLOR_THEME,
    NO_COLOR,
)
from .resources import AssetsManager, FontManager
from .utils import MS, _MS_DEFAULT, bcm, get_full_width_text

# 这些对象由 image_gen.__init__ 初始化后回填到包级命名空间。
# builder 通过包级导入复用它们，避免重复初始化资源。
from . import ASSETS, FONT, IMU, DrawUnit, get_genre


__all__ = [
    "draw_info_box",
    "draw_b50",
    "simple_list",
    "simple_maidata_box",
    "get_image_bytes",
]


def _image_grid_board(
    image_list: list[Image.Image],
    cols: int = 4,
    gap: int = 0,
    skip_first: bool = True,
    auto_close: bool = False,
) -> Image.Image | None:
    """将图片列表排列成网格看板。"""
    if not image_list:
        return None

    box_w, box_h = image_list[0].size
    total_slots = len(image_list) + (1 if skip_first else 0)
    rows = (total_slots + cols - 1) // cols

    board_width = cols * box_w + (cols - 1) * gap
    board_height = rows * box_h + (rows - 1) * gap
    board = Image.new("RGBA", (round(board_width), round(board_height)), (0, 0, 0, 0))

    start_offset = 1 if skip_first else 0
    for index, img in enumerate(image_list):
        pos_idx = index + start_offset
        tx = (pos_idx % cols) * (box_w + gap)
        ty = (pos_idx // cols) * (box_h + gap)
        board.paste(img, (round(tx), round(ty)), img)
        if auto_close:
            img.close()

    return board


def _user_header_board(
    inner_width: int,
    dxrating: int,
    server: SERVER_TAG,
    user_name: str,
    user_avatar: bytes | Image.Image | None = None,
    update_time: str = "Unknown Time",
    dxra_cirp_frame: bool = True,
    ms: MS = _MS_DEFAULT,
    cn_level: Literal[0, 1, 2] = 0,
) -> Image.Image | None:
    header_h = 32
    board_title = Image.new("RGBA", ms.xy(inner_width, header_h), NO_COLOR)
    du1 = DrawUnit(board_title, multiple=ms, cn_level=cn_level)

    avatar_size = 32
    if user_avatar and isinstance(user_avatar, bytes):
        try:
            avatar = Image.open(io.BytesIO(user_avatar)).convert("RGBA")
        except Exception:
            avatar = None
    elif isinstance(user_avatar, Image.Image):
        avatar = user_avatar
    else:
        avatar = None
    avatar = avatar or Image.new("RGB", ms.xy(avatar_size, avatar_size), color="#CCC")
    if avatar.size != ms.xy(avatar_size, avatar_size):
        avatar = avatar.resize(ms.xy(avatar_size, avatar_size), Image.Resampling.LANCZOS)
    mask = IMU.get_mask(w=avatar_size, h=avatar_size, radius=5, ms=ms)
    board_title.paste(avatar, (0, 0), mask)
    avatar.close()
    du1.rounded_rect(0, 0, avatar_size, avatar_size, radius=5, fill=None, outline="#FFF", width=1)

    dx_ra_x, dx_ra_y = 36, 0
    dxra_frame_filename = parse_dxrating_filename(dxrating, cirp_frame=dxra_cirp_frame)
    if dxra_frame := ASSETS.dxrating_image(dxra_frame_filename, size=ms.xy(70, 14)):
        board_title.paste(dxra_frame, ms.xy(dx_ra_x, dx_ra_y), dxra_frame)

    ra_font = FONT.font("MIS_DB", size=ms.x(8))
    for i, digit in enumerate(str(dxrating)[::-1]):
        dx = 57.5 - 5.5 * i
        du1.text(
            dx_ra_x + dx,
            dx_ra_y + 7.1,
            text=digit,
            fill="#FCC916",
            anchor="mm",
            font=ra_font,
            stroke=(0.35, "#333"),
        )

    du1.rounded_rect(36, 15, 100, 17, fill="#333", radius=2)
    du1.text(36, 23.5, text=" " + get_full_width_text(user_name), fill="#FFF", anchor="lm", font=FONT.font("MIS_DB", size=ms.x(10)))

    record_info = f"Updated: [{server}] {update_time}"
    du1.text(inner_width - 2, 2, text=record_info, fill="#FFF", anchor="ra", font=FONT.font("MIS_DB", size=ms.x(5)))

    return board_title


def draw_info_box(
    maidata: MaiData,
    server: SERVER_TAG,
    maiuser: MaiUser | None = None,
    ms: MS = _MS_DEFAULT,
    cn_level: Literal[0, 1, 2] = 0,
) -> Image.Image:
    width, fw = 220, 10
    all_width = width + fw * 2

    cover_width = 54
    board1 = Image.new("RGBA", ms.xy(width, cover_width + 2), NO_COLOR)
    du1 = DrawUnit(board1, multiple=ms, cn_level=cn_level)

    img = maidata.image if maidata.image else Image.new("RGB", ms.xy(cover_width, cover_width), color="#999")
    mask = IMU.get_mask(w=cover_width, h=cover_width, radius=5, ms=ms)
    cover_img = img.resize(ms.xy(cover_width, cover_width), Image.Resampling.LANCZOS) if img.size != (cover_width, cover_width) else img
    board1.paste(cover_img, ms.xy(1, 1), mask)
    du1.rounded_rect(1, 1, cover_width, cover_width, radius=5, fill=None, outline="#FFF", width=1)

    dx = cover_width + 5
    du1.text(dx, 0, text=maidata.title, fill="#FFF", anchor="la", font=FONT.font("MIS_HE", size=ms.x(11)))
    du1.text(dx, 14, text=maidata.artist, fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(5)))
    du1.text(dx, 23, text=f"ID {maidata.shortid}", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(6)))
    du1.text(dx + 30, 23, text=f"BPM {maidata.bpm}", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(6)))
    du1.text(dx + 60, 23, text=f"谱面来源: {maidata.converter}", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(6)))

    margin = 5
    dy = 32
    im_y1, im_y1_5 = dy + 3, dy + 12
    genre_x, jpv_x, cnv_x, dv_x = dx, dx + 34 + margin, dx + 68 + margin * 2, dx + 102 + margin * 3
    du1.text(genre_x, dy, text="流派", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(4)))
    if maidata.genre:
        genre_text, genre_fill = get_genre(maidata.genre, cn_level=cn_level)
        du1.text(genre_x + 17, im_y1_5, text=genre_text, fill=genre_fill, anchor="mm", font=FONT.font("MIS_DB", size=ms.x(5)), shadow=(1.2, "#FFF"))

    du1.text(jpv_x, dy, text="JP", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(4)))
    if maidata.version:
        if ver_jp := ASSETS.version_image(maidata.version, size=ms.xy(34, 16)):
            board1.paste(ver_jp, ms.xy(jpv_x, im_y1), ver_jp)
        else:
            text = VERSIONS_DATA.get(maidata.version, str(maidata.version)).replace(" ", "\n")
            du1.text(jpv_x + 17, im_y1_5, text=text, fill="#FFF", anchor="mm", font=FONT.font("MIS_DB", size=ms.x(5)))

    du1.text(cnv_x, dy, text="CN", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(4)))
    if maidata.version_cn:
        if ver_cn := ASSETS.version_image(maidata.version_cn, size=ms.xy(34, 16)):
            board1.paste(ver_cn, ms.xy(cnv_x, im_y1), ver_cn)
        else:
            text = VERSIONS_DATA.get(maidata.version_cn, str(maidata.version_cn)).replace(" ", "\n")
            du1.text(cnv_x + 17, im_y1_5, text=text, fill="#FFF", anchor="mm", font=FONT.font("MIS_DB", size=ms.x(5)))
    else:
        du1.text(cnv_x + 17, im_y1_5, text="X\n", fill="#F00", anchor="mm", font=FONT.font("MIS_DB", size=ms.x(4)), stroke=(0.8, "#FFF"))
        du1.text(cnv_x + 17, im_y1_5, text="\n国服无此乐曲", fill="#FFF", anchor="mm", font=FONT.font("MIS_DB", size=ms.x(4)))

    if maiuser:
        du1.text(dv_x, dy, text="Record / 游玩记录", fill="#FFF", anchor="la", font=FONT.font("MIS_DB", size=ms.x(4)))
        username_text = get_full_width_text(maiuser.get_username()) + "\n\n"
        du1.text(dv_x, im_y1_5, text=username_text, fill="#FFF", anchor="lm", font=FONT.font("MIS_DB", size=ms.x(3)))
        records = [
            "",
            f"[CN({maiuser.cn_dxrating})] {maiuser.get_formated_time('CN').replace('0','O')}",
            f"[JP({maiuser.jp_dxrating})] {maiuser.get_formated_time('JP').replace('0','O')}",
        ]
        du1.text(dv_x, im_y1_5, text="\n".join(records), fill="#FFF", anchor="lm", font=FONT.font("JBM_BD", size=ms.x(2.2)))
        del du1

    if maidata.aliases:
        font_size = 4
        font = FONT.font("MIS_DB", size=ms.x(font_size))
        alias_width_list = [(alias.alias, font.getlength(alias.alias)) for alias in maidata.aliases]
        alias_cut: list[tuple[list[str], float]] = [([], 0)]
        for alias, alias_width in alias_width_list:
            if alias_cut[-1][1] + alias_width + font.getlength(" ") > ms.x(width):
                alias_cut.append(([alias], alias_width))
            else:
                alias_cut[-1][0].append(alias)
                alias_cut[-1] = (alias_cut[-1][0], alias_cut[-1][1] + alias_width + font.getlength("  "))
        aliases_height = (len(alias_cut) + 1) * font_size * 1.5
        board2 = Image.new("RGBA", ms.xy(width, aliases_height), NO_COLOR)
        du2 = DrawUnit(board2, multiple=ms, cn_level=cn_level)
        du2.text(0, 0, text="这首歌的别名包括：", fill="#FFF", anchor="la", font=font)
        for i, (alias_list, _) in enumerate(alias_cut):
            du2.text(0, (i + 1) * font_size * 1.5, text="  ".join(alias_list), fill="#FFF", anchor="la", font=font)
        del du2
    else:
        board2 = None

    chart_imgs = []
    for diff, chart in maidata.charts.items():
        func = IMU.chart_box if diff >= 4 else IMU.chart_box_lite
        chart_img = func(chart=chart, cabinet_dx=maidata.is_cabinet_dx, server=server, ms=ms, cn_level=cn_level)
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

    board3 = Image.new("RGBA", (ms.x(width), current_y), NO_COLOR)
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

    board_last = IMU.copyright_bar(width=all_width, ms=ms, cn_level=cn_level)

    margin = ms.x(fw) // 3
    boards = [board for board in (board1, board2, board3) if board is not None]
    all_height_msed = sum((sum(b.height for b in boards), board_last.height, ms.x(fw) * 2, (len(boards) - 1) * margin))
    all_width_msed = ms.x(all_width)
    result_img = Image.new("RGBA", (all_width_msed, all_height_msed), COLOR_THEME)
    bg_img = ASSETS.background((all_width_msed, round(all_width_msed)))
    if bg_img:
        result_img.paste(bg_img, (0, 0))
    current_y = ms.x(fw)
    for board in boards:
        result_img.paste(board, (ms.x(fw), current_y), board)
        current_y += board.height + margin
    footer_y = all_height_msed - board_last.height
    result_img.paste(board_last, (0, footer_y), board_last)
    return result_img.convert("RGB")


def draw_b50(
    b35_entries: list[tuple[MaiData, int]],
    b15_entries: list[tuple[MaiData, int]],
    *,
    dxrating: int,
    current_version: int,
    server: SERVER_TAG,
    user_name: str,
    user_avatar: bytes | Image.Image | None = None,
    update_time: str = "Unknown Update Time",
    line_width: Literal[4, 5] = 5,
    ms: MS = _MS_DEFAULT,
    cn_level: Literal[0, 1, 2] = 0,
) -> Image.Image:
    margin = 10
    temp_box = IMU.mini_box(None, 0, "JP", ms=ms, cn_level=cn_level)
    if isinstance(temp_box, tuple):
        box_w, _ = temp_box
    else:
        w, h = temp_box.size
        box_w, _ = round(ms.rev(w)), round(ms.rev(h))
        temp_box.close()

    inner_width = line_width * box_w + (line_width - 1) * 5
    width = inner_width + margin * 2

    board_title = _user_header_board(
        inner_width=inner_width,
        dxrating=dxrating,
        server=server,
        user_name=user_name,
        user_avatar=user_avatar,
        update_time=update_time,
        ms=ms,
        cn_level=cn_level,
    )

    shared_zip_handles: dict[Path, zipfile.ZipFile] = {}
    try:
        for maidata, _ in (*b35_entries, *b15_entries):
            zip_path = maidata.zip_path
            if zip_path and zip_path not in shared_zip_handles:
                shared_zip_handles[zip_path] = zipfile.ZipFile(zip_path, "r")

        b35_imgs = [
            IMU.b50_box(
                maidata,
                diff,
                server,
                current_version,
                index,
                False,
                ms,
                cn_level,
                shared_zip=shared_zip_handles.get(maidata.zip_path) if maidata.zip_path else None,
            )
            for index, (maidata, diff) in enumerate(b35_entries, start=1)
        ]
        b35_imgs = [img for img in b35_imgs if img is not None]
        board_b35 = _image_grid_board(b35_imgs, cols=line_width, gap=ms.x(5), skip_first=line_width == 4, auto_close=True)

        b15_imgs = [
            IMU.b50_box(
                maidata,
                diff,
                server,
                current_version,
                index,
                True,
                ms,
                cn_level,
                shared_zip=shared_zip_handles.get(maidata.zip_path) if maidata.zip_path else None,
            )
            for index, (maidata, diff) in enumerate(b15_entries, start=1)
        ]
        b15_imgs = [img for img in b15_imgs if img is not None]
        board_b15 = _image_grid_board(b15_imgs, cols=line_width, gap=ms.x(5), skip_first=line_width == 4, auto_close=True)
    finally:
        for zip_handle in shared_zip_handles.values():
            zip_handle.close()

    board_last = IMU.copyright_bar(width=width, ms=ms, cn_level=cn_level)

    boards = [board for board in (board_title, board_b35, board_b15) if board is not None]
    all_height_msed = ms.x(margin) * 2 + sum(b.height for b in boards) + ms.x(margin) * (len(boards) - 1) + board_last.height
    result_img = Image.new("RGBA", (ms.x(width), all_height_msed), COLOR_THEME)

    if bg_img := ASSETS.background(result_img.size):
        result_img.paste(bg_img, (0, 0))

    curr_y = ms.x(margin)
    for board in boards:
        result_img.paste(board, (ms.x(margin), curr_y), board)
        curr_y += board.height + ms.x(margin)
        board.close()

    result_img.paste(board_last, (0, all_height_msed - board_last.height), board_last)
    return result_img.convert("RGB")


def simple_list(text: str) -> Image.Image:
    """生成一个简单的文本列表图。"""
    font = FONT.font("MIS_DB", size=16)
    x1, y1, x2, y2 = ImageDraw.Draw(Image.new("RGB", (1, 1), color="#FFF")).multiline_textbbox((0, 0), text=text, font=font)
    width, height = int(x2 - x1 + 10), int(y2 - y1 + 10)
    img = Image.new("RGB", (width, height), color="#FFF")
    img_draw = ImageDraw.Draw(img)
    img_draw.text((2, 2), text, fill="#000", font=font)
    return img.convert("RGB")


def simple_maidata_box(maidata_list: List[MaiData]) -> Image.Image:
    """生成一个简单的文本列表图，展示多个曲目的信息。"""
    return simple_list("\n".join([f"{maidata.shortid}.\t{maidata.title}" for maidata in maidata_list]))


def get_image_bytes(img: Image.Image, format: str = "jpeg") -> bytes:
    """将 PIL Image 对象转换为字节流。"""
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


def _debug_demo() -> None:
    from random import randint

    from .. import utils

    aliases = ["transcend lights", "超越光", "九月的雨", "超超光光", "美瞳广告", "小女孩们的茶话会", "超越之光", "bright主题曲", "别急19", "音击的武士", "tl", "萝莉的雨", "音击妹妹", "114514", "音击的雨"]
    maidata = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, "DX", 18, 2023, "debug", Path(r"E:\Projects\PythonProjects\lyra-bot\temp\debug_cover.png"), None, aliases=[utils.MaiAlias(11451, a, 0, -1) for a in aliases])
    maidata2 = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, "DX", 25, 2023, "debug", Path(r"E:\Projects\PythonProjects\lyra-bot\temp\debug_cover.png"), None, aliases=[utils.MaiAlias(11451, a, 0, -1) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(11451, i, 1 + i * 3)
        chart.set_ach(utils.MaiChartAch(11451, i, "JP", 97.6 + i * 0.5, combo=3, sync=2))
        maidata.set_chart(chart)
        maidata2.set_chart(chart)

    b35_entries = [(maidata, randint(2, 6)) for _ in range(35)]
    b15_entries = [(maidata2, randint(2, 6)) for _ in range(15)]

    target = draw_info_box(maidata, server="JP", ms=MS(5), cn_level=1)
    # target = draw_b50(
    #     b35_entries=b35_entries,
    #     b15_entries=b15_entries,
    #     dxrating=15409,
    #     current_version=26,
    #     server='JP',
    #     user_name='测试用户',
    #     line_width=5,
    #     ms=MS(5), cn_level=1)
    target.show()


if __name__ == "__main__":
    _debug_demo()
