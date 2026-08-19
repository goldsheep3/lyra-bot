import os, sys

os.environ["MAIB_IMAGE_GEN_DEBUG"] = "1"
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================


if __name__ == "__main__":
    # 绝对导入
    from plugins.maib.debug import public_data as pd

    from plugins.maib.image_gen.builder import draw_b50_board
    from plugins.maib.utils.enums import Server, UICode

    maiuser = pd.maiuser()
    result_img = draw_b50_board(
        b35_entries=pd.entries(35, 10), b15_entries=pd.entries(15, 12),
        dxrating_data=maiuser.jp_dxra_data, current_version=maiuser.jp_current_version,
        updated=maiuser.get_formated_time(Server.JP), server=Server.JP, ui_code=UICode.JP,
        username=maiuser.username, avatar=None, line_width=4,
    )
    
    result_img.show()
