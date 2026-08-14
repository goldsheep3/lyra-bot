def _debug_maidata(version: int):
    from pathlib import Path
    from datetime import datetime
    
    from ..utils import MaiData, MaiChart, MaiChartAch, MaiAlias
    
    datetime_now = datetime.now()
    
    aliases = ["transcend lights", "超越光", "九月的雨", "超超光光", "美瞳广告", "小女孩们的茶话会", "超越之光", "bright主题曲", "别急19", "音击的武士", "tl", "萝莉的雨", "音击妹妹", "114514", "音击的雨"]
    maidata = MaiData(11451, "Transcend Lights", 70, "曲：小高光太郎／歌：オンゲキシューターズ", 5, "DX", version, 2023, "debug",
                      Path(__name__).parent.parent.parent.parent / "temp" / "debug_cover.png", None,
                      aliases=[MaiAlias(11451, a, datetime_now, -1) for a in aliases])
    for i in range(2, 7):
        chart = MaiChart(11451, i, 1 + i * 3)
        chart.set_ach(MaiChartAch(11451, i, "JP", 97.6 + i * 0.5, combo=3, sync=2))
        maidata.set_chart(chart)

    return maidata
    
    
def _debug():
    from random import randint
    from ..image_gen.tools import get_image_bytes
    from ..image_gen.utils import MS
    
    def info_box():
        from ..image_gen.builder import draw_info_box
        maidata = _debug_maidata(26)
        return draw_info_box(
            maidata=maidata,
            server="JP",
            ms=MS(5),
            cn_level=1
        )

    def grid_b50_item():
        from ..image_gen.utils import ImageUnit
        maidata = _debug_maidata(26)
        maidata._charts[5]._achs["JP"].combo = 4  # type: ignore
        maidata._charts[5]._achs["JP"].sync = 5  # type: ignore
        return ImageUnit.b50_box(
            maidata=maidata,
            difficulty=5,
            server="JP",
            current_version=26,
            index=1,
            ms=MS(5),
            cn_level=1
        )

    def b50():
        from ..image_gen.builder import draw_b50
        b35_entries = [(_debug_maidata(18), randint(2, 6)) for _ in range(35)]
        b15_entries = [(_debug_maidata(26), randint(2, 6)) for _ in range(15)]
        return draw_b50(
            b35_entries=b35_entries,
            b15_entries=b15_entries,
            dxrating=15409,
            current_version=26,
            server='JP',
            user_name='测试用户',
            line_width=5,
            ms=MS(5),
            cn_level=1
        )

    def grid_list():
        from ..image_gen.builder import draw_grid_list
        entries = [(_debug_maidata(26), randint(2, 6)) for _ in range(randint(43, 80))]
        return draw_grid_list(
            entries=entries,
            dxrating=15409,
            server='JP',
            user_name='测试用户',
            ms=MS(5),
            cn_level=1
        )
    
    # ======== 选择要调试的函数 ========

    from PIL.Image import Image
    func_result: Image = grid_list()
    
    # ===============================
    
    return get_image_bytes(func_result) if func_result else None
