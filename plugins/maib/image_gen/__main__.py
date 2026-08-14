def _debug_demo() -> None:
    from random import randint
    from pathlib import Path
    from datetime import datetime
    
    from ..utils import MaiData, MaiChart, MaiChartAch, MaiAlias
    from .builder import draw_info_box, draw_b50
    from .utils import MS
    
    datetime_now = datetime.now()
    
    aliases = ["transcend lights", "超越光", "九月的雨", "超超光光", "美瞳广告", "小女孩们的茶话会", "超越之光", "bright主题曲", "别急19", "音击的武士", "tl", "萝莉的雨", "音击妹妹", "114514", "音击的雨"]
    maidata = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, "DX", 18, 2023, "debug",Path(r"E:\Projects\PythonProjects\lyra-bot\temp\debug_cover.png"), None, aliases=[MaiAlias(11451, a, datetime_now, -1) for a in aliases])
    maidata2 = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, "DX", 25, 2023, "debug", Path(r"E:\Projects\PythonProjects\lyra-bot\temp\debug_cover.png"), None, aliases=[MaiAlias(11451, a, datetime_now, -1) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(11451, i, 1 + i * 3)
        chart.set_ach(MaiChartAch(11451, i, "JP", 97.6 + i * 0.5, combo=3, sync=2))
        maidata.set_chart(chart)
        maidata2.set_chart(chart)

    b35_entries = [(maidata, randint(2, 6)) for _ in range(35)]
    b15_entries = [(maidata2, randint(2, 6)) for _ in range(15)]

    target = draw_info_box(maidata, server="JP", ms=MS(5), cn_level=1)
    # target = draw_b50(
    #     b35_entries=b35_entries,
    #     b15_entries=b15_entries,
    #     dxrating=15409,
    #     current_version=26,
    #     server='JP',
    #     user_name='测试用户',
    #     line_width=5,
    #     ms=MS(5), cn_level=1)
    target.show()


if __name__ == "__main__":
    _debug_demo()
