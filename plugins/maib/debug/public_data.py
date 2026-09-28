import os, sys

os.environ["MAIB_IMAGE_GEN_DEBUG"] = "1"
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ===============================

import random
from pathlib import Path
from datetime import datetime
    
    
def maidata(version: int = 18):
    from plugins.maib.utils import MaiData, MaiChart, MaiChartAch, MaiAlias
    from plugins.maib.utils.enums import Server
    
    datetime_now = datetime.now()
    
    aliases = ["小梨", "小梨酱", "小梨酱酱", "小梨酱酱酱", "小梨酱酱酱酱", "Lyra", "LyraBot", "DEBUG"]*2
    aliases.sort(key=lambda _: random.random())
    maidata = MaiData(shortid=11451, title="LyraTest", bpm=70, artist="GoldSheeeeeep3",
                      genre=1, cabinet="DX", version=version, version_cn=None, converter="Debug",
                      img_path=Path(project_root) / "temp" / "debug_cover.png", zip_path=None,
                      aliases=[MaiAlias(shortid=11451, alias=a, create_time=datetime_now, create_qq=-1, create_qq_group=None) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(shortid=11451, difficulty=i, lv=1 + i * 3)
        chart.set_ach(MaiChartAch(shortid=11451, difficulty=i, server=Server.JP, achievement=97.6 + i * 0.5,
                                  combo=random.randint(0, 4), sync=random.randint(0, 5)))
        maidata.set_chart(chart)

    return maidata


def maiuser():
    from plugins.maib.utils import MaiUser, DXRatingData
    from plugins.maib.utils.enums import Server

    return MaiUser(
        user_id=2940119626,
        username="GDSheep3",
        default_server=Server.JP,
        jp_current_version=26,
        jp_dxra_data=DXRatingData(15480, 10844, 319, 306, 4636, 317, 306),
        cn_current_version=2026,
        cn_dxra_data=DXRatingData(15480, 10844, 319, 306, 4636, 317, 306),
    )


def entries(number = 35, version = 18):
    return [(maidata(version), random.randint(2, 6)) for _ in range(number)]
