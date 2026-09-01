"""
image_gen.components.grid_board
GridList 看板构建器
"""
from typing import Optional, Union
from PIL import Image

from ...utils.models import MaiData
from ...utils.enums import UICode, Server
from ...utils.map import DifficultyID
from .. import color as Color
from ..utils import MS, ImageManager
from . import CopyrightBadge, MiniBoxBadge, UserHeaderBadge
from ..tools import image_grid_board


class GridListBoard:

    # TODO 待修整
    @staticmethod
    def draw_grid_board(entries: list[tuple[MaiData, DifficultyID]],
                    *,
                    dxrating: int, server: Server,
                    user_name: str, user_avatar: Optional[Union[bytes, Image.Image]] = None,
                    update_time: str = "Unknown", line_width: int = 6,
                    ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """绘制网格列表看板"""
        margin = 10
        box_w, _ = MiniBoxBadge.size()

        inner_width = line_width * box_w + (line_width - 1) * 5
        width = inner_width + margin * 2

        board_title = UserHeaderBadge.board(
            dxrating=dxrating, username=user_name, avatar=user_avatar,
            display_content=f"Update: [{server.value}] {update_time}", dan=None, ms=ms
        )

        def generator():
            for maidata, difficulty in entries:
                yield MiniBoxBadge.box(
                    maidata=maidata, difficulty=difficulty, server=server, ms=ms, ui_code=ui_code,
                    )

        box_size = MiniBoxBadge.size()
        entries_count = len(entries)
            
        board_grid = image_grid_board(
            image_iter=generator(),
            cols=line_width,
            gap_px=ms.x(5),
            total_count=entries_count,
            box_size_px=ms.xy(*box_size),
        )

        board_last = CopyrightBadge.copyright(width_px=width, ms=ms)

        boards = [board for board in (board_title, board_grid) if board is not None]
        all_height_msed = ms.x(margin) * 2 + sum(b.height for b in boards) + ms.x(margin) * (len(boards) - 1) + board_last.height
        result_img = Image.new("RGBA", (ms.x(width), all_height_msed), Color.THEME_CYAN)

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
        result_img.close()
        return final_img


draw_grid_board = GridListBoard.draw_grid_board
