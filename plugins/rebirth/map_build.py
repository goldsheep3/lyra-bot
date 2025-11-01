from pathlib import Path
from typing import Optional, Literal


def map_build(region_datas: dict[str, int],
              output_folder_path: Path,
              color: Literal['red', 'blue', 'green'] = 'red',
              levels: tuple[int, int, int] = (1, 10, 50)
) -> Optional[Path]:
    """构建投胎地图图片"""
    if not region_datas:
        return None

    # todo: 实现地图绘制功能
    return None