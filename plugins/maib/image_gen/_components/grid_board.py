"""
image_gen.components.grid_board
GridList 看板构建器
"""
from typing import Optional, Union

from PIL import Image

from ...utils.map import DifficultyID
from ...utils.models import MaiData
from ...utils.enums import UICode, Server
from .. import color as Color
from ..utils import MS, ImageManager
from . import CopyrightBadge, MiniBoxBadge, UserHeaderBadge
from ..tools import image_grid_board


def draw_grid_board(
    entries: list[tuple[MaiData, DifficultyID]],
    *,
    dxrating: int, updated: str, server: Server, 
    username: str = 'maimai', avatar: Optional[Union[bytes, Image.Image]] = None,
    line_width: int = 6, ms: MS = MS(), ui_code: UICode = UICode.JP
) -> Image.Image:
    """绘制 grid 看板"""
    margin = 10
    box_w, _ = MiniBoxBadge.size()
    inner_width = line_width * box_w + (line_width - 1) * 5
    width = inner_width + margin * 2
    board_title = UserHeaderBadge.board(
        dxrating=dxrating, username=username, avatar=avatar,
        display_content=f"Update: [{server.value}] {updated}", dan=None, ms=MS(ms*0.6)
    )
    
    def generator(entries: list[tuple[MaiData, DifficultyID]]):
        for maidata, difficulty in entries:
            yield MiniBoxBadge.box(
                maidata=maidata, difficulty=difficulty, server=server,
                ms=ms, ui_code=ui_code
            )
        
    board_b35 = image_grid_board(
        image_iter=generator(entries),
        cols=line_width,
        gap_px=ms.x(5),
        total_count=len(entries),
        box_size_px=ms.xy(*MiniBoxBadge.size()),
    )
    board_last = CopyrightBadge.copyright_mpx(width, ms=ms)
    boards = [board for board in (board_title, board_b35) if board is not None]
    all_height_msed = ms.x(margin) * 2 + sum(b.height for b in boards) + ms.x(margin) * (len(boards) - 1) + board_last.height
    
    with Image.new("RGBA", (ms.x(width), all_height_msed), Color.THEME_CYAN) as result_img:
        if bg_img := ImageManager.background(size=result_img.size):
            result_img.paste(bg_img, (0, 0))
        curr_y = ms.x(margin)
        for board in boards:
            result_img.paste(board, (ms.x(margin), curr_y), board)
            curr_y += board.height + ms.x(margin)
            board.close()
        result_img.paste(board_last, (0, all_height_msed - board_last.height), board_last)
        board_last.close()

        final_img = result_img.convert("RGB")
        return final_img
