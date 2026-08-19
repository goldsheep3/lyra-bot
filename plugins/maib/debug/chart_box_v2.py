import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================


if __name__ == "__main__":
    # 绝对导入
    from plugins.maib.image_gen.components.chart_box import ChartBoxBadgeV2
    
    from plugins.maib.utils.models import MaiChart, MaiChartAch
    from plugins.maib.utils.enums import Server
    
    chart = MaiChart(shortid=11451, difficulty=7, lv=13.6, lv_synh=13.9, _achs={
        Server.JP: MaiChartAch(shortid=11451, difficulty=7, server=Server.JP, achievement=99.5, combo=3, sync=2, dxscore=799, dxscore_max=810)
    })
    result_img = ChartBoxBadgeV2._box(
        chart, 'DX', Server.JP, plus=True, utage=None, floor_rating=None,
    )
    result_img.show()
