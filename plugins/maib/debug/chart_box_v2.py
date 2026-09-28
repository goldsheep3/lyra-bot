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
    
    from plugins.maib.image_gen._components.chart_box import ChartBoxBadge
    from plugins.maib.utils.enums import Server, UICode

    result_img = ChartBoxBadge._box(
        pd.maidata().charts[5], 'DX', Server.JP, plus=True, utage=None, floor_rating=263, ui_code=UICode.INTL,
    )
    result_img.show()
