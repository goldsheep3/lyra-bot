import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================


if __name__ == "__main__":
    # 绝对导入
    from plugins.maib.image_gen._components.chart_box import ChartBoxBadgeV2
    
    from plugins.maib.utils.models import MaiChart, MaiChartAch
    from plugins.maib.utils.enums import Server, UICode
    
    chart = MaiChart(shortid=11451, difficulty=5, lv=13.6, lv_synh=13.5833, _achs={
        Server.JP: MaiChartAch(shortid=11451, difficulty=7, server=Server.JP, achievement=101.0000, combo=4, sync=5, dxscore=799, dxscore_max=810)
    })
    result_img = ChartBoxBadgeV2._box(
        chart, 'DX', Server.JP, plus=True, utage=None, floor_rating=263, ui_code=UICode.INTL,
    )
    result_img.show()
