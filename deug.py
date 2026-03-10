from plugins.maib.image_gen import *


if __name__ == "__main__":
    maidata = MaiData(
        shortid=101,
        title="おちゃめ機能",
        bpm=150,
        artist="ゴジマジP",
        genre="niconicoボーカロイド",
        cabinet='SD',
        version=2,
        version_cn=2022,
        converter="PreData",
        img_path=Path(r"C:\Users\sanji\AppData\Roaming\JetBrains\PyCharm2025.3\scratches\bg.png"),
        aliases=[MaiAlias(101, a, 0, -1) for a in ["ochamekinou", "五月病", "天真浪漫机能", "天真烂漫机能", "机能"]]*5,
    )

    for i in range(2, 7):
        maidata.set_chart(MaiChart(
            difficulty=i,
            lv=3.6 + i * 1.8,
            des="chartDes",
            ach=MaiChartAch(
                achievement=70 + 2.63 ** (i/1.7),
                dxscore=200 + i * 100,
                dxscore_max=300 + i * 100,
                combo=Combo(i - 2),
                sync=Sync(i - 1)
            )
        ))

    config_yaml_path = Path.cwd() / "versions.yaml"
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        ver_cfg: Dict[int, str] = yaml.safe_load(f)

    # target = DrawInfo(maidata, ver_cfg, multiple=0.3, cn_level=1).get_image()
    # target = info_box_mini(diff=4, level=5.0, achievement=99.5, combo=Combo(2), sync=Sync(3), all_cn=True, ms_multiple=MS(10))

    target = b50_box(5,1,101,"おちゃめ機能",5.0,1000,99.5,Path(r"C:\Users\sanji\AppData\Roaming\JetBrains\PyCharm2025.3\scratches\bg.png"),(200,300,100),False,0)
        # diff,
        # cabinet_dx: bool,
        # short_id: int,
        # title: str,
        # level: float,
        # ra: int,
        # achievement: float,
        # bg_path: Path,
        # dxscore: Tuple[int, int, int],
        # new_song: bool,
        # index: int,
        # combo: Optional[Combo | int] = None,
        # sync: Optional[Sync | int] = None,
        # all_cn: bool = False,
        # ms_multiple: int | MS = 10,

    from PIL import ImageTk
    import tkinter as tk

    root = tk.Tk()
    tk_image = ImageTk.PhotoImage(target)
    label = tk.Label(root, image=tk_image)
    label.pack()
    root.mainloop()
