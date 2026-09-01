"""
image_gen.components
图像组件库
"""
from .level import LevelBadge
from .difficulty import DifficultyBadge
from .cabinet import CabinetBadge
from .evaluate import EvaluateBadge
from .copyright import CopyrightBadge
from .achievement import AchievementBadge
from .dxscore import DXScoreBadge
from .user_header import UserHeaderBadge

from .chart_box import ChartBoxBadgeV2
from .mini_box import MiniBoxBadge
from .b50_box import B50BoxBadge

from .simple_list_board import SimpleListBoard, draw_simple_board
from .info_board import MaiChartInfoBoard, draw_info_board
from .grid_board import GridListBoard, draw_grid_board
from .b50_board import B50Board, draw_b50_board

__all__ = [    
    # 一级组件
    "LevelBadge",
    "DifficultyBadge",
    "CabinetBadge",
    "EvaluateBadge",
    "CopyrightBadge",
    "AchievementBadge",
    "DXScoreBadge",
    "UserHeaderBadge",

    # 二级组件
    "ChartBoxBadgeV2",
    "MiniBoxBadge",
    "B50BoxBadge",
    
    # 三级组件
    "SimpleListBoard", "draw_simple_board",
    "MaiChartInfoBoard", "draw_info_board",
    "GridListBoard", "draw_grid_board",
    "B50Board", "draw_b50_board",
]
