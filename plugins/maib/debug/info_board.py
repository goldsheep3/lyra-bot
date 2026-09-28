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

    from plugins.maib.image_gen.builder import draw_info_board
    from plugins.maib.image_gen._components.info_board import MaiChartInfoBoard
    from plugins.maib.image_gen._components.copyright import CopyrightBadge
    
    from plugins.maib.utils.enums import Server
    
    # result_img = draw_info_board(
    #     maidata=_maidata(), server=Server.JP, maiuser=_maiuser()
    # )
    # result_img = MaiChartInfoBoard._metadata(maidata=_maidata())
    # result_img = MaiChartInfoBoard._alias_badge(aliases=[alias.alias for alias in _maidata().aliases], width=200)
    # result_img = MaiChartInfoBoard._charts(charts=list(_maidata().charts.values()), server=Server.JP, version=0, cabinet="DX",
                                        #    maiuser=_maiuser())
    result_img = MaiChartInfoBoard.board(maidata=pd.maidata(), maiuser=pd.maiuser())
    # result_img = CopyrightBadge.copyright_mpx(2480)
    result_img.show()
