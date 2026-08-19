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
    
    from plugins.maib.image_gen._components.mini_box import MiniBoxBadge
    from plugins.maib.image_gen._components.b50_box import B50BoxBadge
    from plugins.maib.utils.enums import Server, UICode
    from plugins.maib.image_gen.utils import MS
    
    # result_img = draw_info_board(
    #     maidata=_maidata(), server=Server.JP, maiuser=_maiuser()
    # )
    # result_img = MaiChartInfoBoard._metadata(maidata=_maidata())
    # result_img = MaiChartInfoBoard._alias_badge(aliases=[alias.alias for alias in _maidata().aliases], width=200)
    # result_img = MaiChartInfoBoard._charts(charts=list(_maidata().charts.values()), server=Server.JP, version=0, cabinet="DX",
                                        #    maiuser=_maiuser())
    # result_img = MiniBoxBadge.old_box(maidata=_maidata(), difficulty=5, server=Server.JP, ui_code=UICode.JP)
    # result_img = CopyrightBadge.copyright_mpx(2480)
    result_img = B50BoxBadge.b50_box(maidata=pd.maidata(), difficulty=5, server=Server.JP, ui_code=UICode.JP, ms=MS(10), current_version=0, index=12)
    result_img.show()
