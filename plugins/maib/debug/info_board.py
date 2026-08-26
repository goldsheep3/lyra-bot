import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================

def _maidata(version: int = 18):
    from pathlib import Path
    from datetime import datetime
    
    from plugins.maib.utils import MaiData, MaiChart, MaiChartAch, MaiAlias
    from plugins.maib.utils.enums import Server
    
    datetime_now = datetime.now()
    
    aliases = ["transcend lights", "超越光", "九月的雨", "超超光光", "美瞳广告", "小女孩们的茶话会", "超越之光", "bright主题曲", "别急19", "音击的武士", "tl", "萝莉的雨", "音击妹妹", "114514", "音击的雨"]
    maidata = MaiData(shortid=11451, title="Transcend Lights", bpm=70, artist="曲：小高光太郎／歌：オンゲキシューターズ", genre=5, cabinet="DX", version=version, version_cn=2023, converter="debug",
                      img_path=Path(__name__).parent.parent.parent.parent / "temp" / "debug_cover.png", zip_path=None,
                      aliases=[MaiAlias(shortid=11451, alias=a, create_time=datetime_now, create_qq=-1, create_qq_group=None) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(shortid=11451, difficulty=i, lv=1 + i * 3)
        chart.set_ach(MaiChartAch(shortid=11451, difficulty=i, server=Server.JP, achievement=97.6 + i * 0.5, combo=3, sync=2))
        maidata.set_chart(chart)

    return maidata


def _maiuser():
    from plugins.maib.utils import MaiUser, DXRatingData
    from plugins.maib.utils.enums import Server

    return MaiUser(
        user_id=2940119626,
        username="GDSheep3",
        default_server=Server.JP,
        cn_dxra_data=DXRatingData(15480, 10844, 319, 306, 4636, 317, 306),
    )


if __name__ == "__main__":
    # 绝对导入
    from plugins.maib.image_gen.builder import draw_info_board
    
    from plugins.maib.utils.enums import Server
    
    result_img = draw_info_board(
        maidata=_maidata(), server=Server.JP, maiuser=_maiuser()
    )
    result_img.show()
