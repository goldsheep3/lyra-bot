"""
image_gen.components.b50_board
B50 看板构建器
"""
from typing import Literal, Optional, Union

from PIL import Image

from ...utils.map import DifficultyID, VersionID
from ...utils.models import MaiData
from ...utils.enums import UICode, Server
from .. import color as Color
from ..utils import MS, ImageManager
from . import CopyrightBadge, B50BoxBadge, UserHeaderBadge
from ..tools import image_grid_board


class B50Board:

    # TODO 待修整
    @staticmethod
    def draw_b50(b35_entries: list[tuple[MaiData, DifficultyID]], b15_entries: list[tuple[MaiData, DifficultyID]],
                *,
                dxrating: int, current_version: VersionID, server: Server,
                user_name: str, user_avatar: Optional[Union[bytes, Image.Image]] = None,
                update_time: str = "Unknown Update Time", line_width: Literal[4, 5] = 5,
                ms: MS = MS(), ui_code: UICode = UICode.JP) -> Image.Image:
        """绘制 mai_b50 看板"""
        margin = 10
        box_w, _ = B50BoxBadge.size()

        inner_width = line_width * box_w + (line_width - 1) * 5
        width = inner_width + margin * 2

        board_title = UserHeaderBadge.board(
            dxrating=dxrating, username=user_name, avatar=user_avatar,
            display_content=f"Update: [{server.value}] {update_time}", dan=None, ms=ms
        )

        def generator(entries: list[tuple[MaiData, DifficultyID]], is_b15: bool):
            for index, (maidata, difficulty) in enumerate(entries, start=1):
                yield B50BoxBadge.b50_box(
                    maidata=maidata, difficulty=difficulty, server=server,
                    current_version=current_version, index=index,
                    is_b15=is_b15, ms=ms, ui_code=ui_code
                )
            
        box_size = B50BoxBadge.size()
        b35_count = len(b35_entries)
        b15_count = len(b15_entries)
            
        board_b35 = image_grid_board(
            image_iter=generator(b35_entries, is_b15=False),
            cols=line_width,
            gap_px=ms.x(5),
            total_count=b35_count,
            box_size_px=ms.xy(*box_size),
            first_img=None if line_width == 5 else Image.new("RGBA", (0, 0), Color.TRANSPARENT),
        )
        board_b15 = image_grid_board(
            image_iter=generator(b15_entries, is_b15=True),
            cols=line_width,
            gap_px=ms.x(5),
            total_count=b15_count,
            box_size_px=ms.xy(*box_size),
            first_img=None if line_width == 5 else Image.new("RGBA", (0, 0), Color.TRANSPARENT),
        )

        board_last = CopyrightBadge.copyright(width_px=width, ms=ms)

        boards = [board for board in (board_title, board_b35, board_b15) if board is not None]
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


draw_b50_board = B50Board.draw_b50
