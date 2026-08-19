from dataclasses import dataclass


VersionID = int


@dataclass(frozen=True)
class VersionInfo:
    id: VersionID
    name: str
    code: tuple[str, ...]
    plate: tuple[str, ...] = tuple()


_vi = VersionInfo

raw_versions: dict[VersionID, VersionInfo] = {
    # maimai
    0: _vi(0, name="maimai", code=('mai',), plate=('真',)),
    1: _vi(1, name="maimai PLUS", code=('mai+',), plate=('真',)),
    2: _vi(2, name="GreeN", code=('green',), plate=('超',)),
    3: _vi(3, name="GreeN PLUS", code=('green+',), plate=('檄',)),
    4: _vi(4, name="ORANGE", code=('orange',), plate=('橙',)),
    5: _vi(5, name="ORANGE PLUS", code=('orange+',), plate=('晓',)),
    6: _vi(6, name="PiNK", code=('pink',), plate=('桃',)),
    7: _vi(7, name="PiNK PLUS", code=('pink+',), plate=('樱',)),
    8: _vi(8, name="MURASAKi", code=('murasaki',), plate=('紫',)),
    9: _vi(9, name="MURASAKi PLUS", code=('murasaki+',), plate=('堇',)),
    10: _vi(10, name="MiLK", code=('milk',), plate=('白',)),
    11: _vi(11, name="MiLK PLUS", code=('milk+',), plate=('雪',)),
    12: _vi(12, name="FiNALE", code=('finale',), plate=('辉',)),
    
    # DX (JP)
    13: _vi(13, name="でらっくす", code=('dx',), plate=('熊',)),
    14: _vi(14, name="でらっくす PLUS", code=('dx+',), plate=('华',)),
    15: _vi(15, name="Splash", code=('splash',), plate=('爽',)),
    16: _vi(16, name="Splash PLUS", code=('splash+',), plate=('煌',)),
    17: _vi(17, name="UNiVERSE", code=('uni',), plate=('宙',)),
    18: _vi(18, name="UNiVERSE PLUS", code=('uni+',), plate=('星',)),
    19: _vi(19, name="FESTiVAL", code=('fes',), plate=('祭',)),
    20: _vi(20, name="FESTiVAL PLUS", code=('fes+',), plate=('祝',)),
    21: _vi(21, name="BUDDiES", code=('bud',), plate=('双',)),
    22: _vi(22, name="BUDDiES PLUS", code=('bud+',), plate=('宴',)),
    23: _vi(23, name="PRiSM", code=('pri',), plate=('镜',)),
    24: _vi(24, name="PRiSM PLUS", code=('pri+',), plate=('彩',)),
    25: _vi(25, name="CIRCLE", code=('cir',), plate=('丸',)),
    26: _vi(26, name="CIRCLE PLUS", code=('cir+',), plate=()),

    # DX (CN)
    2020: _vi(2020, name="舞萌DX", code=('dx2020',), plate=('熊华',)),
    2021: _vi(2021, name="舞萌DX 2021", code=('dx2021',), plate=('爽煌',)),
    2022: _vi(2022, name="舞萌DX 2022", code=('dx2022',), plate=('宙星',)),
    2023: _vi(2023, name="舞萌DX 2023", code=('dx2023',), plate=('祭祝',)),
    2024: _vi(2024, name="舞萌DX 2024", code=('dx2024',), plate=('双宴',)),
    2025: _vi(2025, name="舞萌DX 2025", code=('dx2025',), plate=('镜',)),
    2026: _vi(2026, name="舞萌DX 2026", code=('dx2026',), plate=('彩',)),
}
