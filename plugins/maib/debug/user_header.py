import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================


if __name__ == "__main__":
    from PIL import Image

    # 绝对导入
    from plugins.maib.image_gen._components.user_header import UserHeaderBadge
    
    from plugins.maib.utils.models import MaiChart, MaiChartAch
    from plugins.maib.utils.enums import Server
    
    chart = MaiChart(shortid=11451, difficulty=7, lv=13.6, lv_synh=13.9, _achs={
        Server.JP: MaiChartAch(shortid=11451, difficulty=7, server=Server.JP, achievement=99.5, combo=3, sync=2, dxscore=799, dxscore_max=810)
    })
    avatar_path = os.path.join(project_root, "temp", "debug_cover.png")
    avatar = Image.open(avatar_path).convert("RGBA") if os.path.exists(avatar_path) else None
    
    result_img = UserHeaderBadge.board(
        dxrating=15480, username="GDSheep3", avatar=avatar,
        display_content="2024-06-01 12:00:00", dan=13
    )
    result_img.show()
