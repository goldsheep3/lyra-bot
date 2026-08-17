from dataclasses import dataclass


@dataclass(frozen=True)
class VersionInfo:
    name: str
    code: tuple[str, ...]
    plate: tuple[str, ...] = tuple()


_vi = VersionInfo
VersionID = int


raw_versions: dict[VersionID, VersionInfo] = {
    # maimai
    0: _vi(name="maimai", code=('mai',), plate=('真',)),
    1: _vi(name="maimai PLUS", code=('mai+',), plate=('真',)),
    2: _vi(name="GreeN", code=('green',), plate=('超',)),
    3: _vi(name="GreeN PLUS", code=('green+',), plate=('檄',)),
    4: _vi(name="ORANGE", code=('orange',), plate=('橙',)),
    5: _vi(name="ORANGE PLUS", code=('orange+',), plate=('晓',)),
    6: _vi(name="PiNK", code=('pink',), plate=('桃',)),
    7: _vi(name="PiNK PLUS", code=('pink+',), plate=('樱',)),
    8: _vi(name="MURASAKi", code=('murasaki',), plate=('紫',)),
    9: _vi(name="MURASAKi PLUS", code=('murasaki+',), plate=('堇',)),
    10: _vi(name="MiLK", code=('milk',), plate=('白',)),
    11: _vi(name="MiLK PLUS", code=('milk+',), plate=('雪',)),
    12: _vi(name="FiNALE", code=('finale',), plate=('辉',)),
    
    # DX (JP)
    13: _vi(name="でらっくす", code=('dx',), plate=('熊',)),
    14: _vi(name="でらっくす PLUS", code=('dx+',), plate=('华',)),
    15: _vi(name="Splash", code=('splash',), plate=('爽',)),
    16: _vi(name="Splash PLUS", code=('splash+',), plate=('煌',)),
    17: _vi(name="UNiVERSE", code=('uni',), plate=('宙',)),
    18: _vi(name="UNiVERSE PLUS", code=('uni+',), plate=('星',)),
    19: _vi(name="FESTiVAL", code=('fes',), plate=('祭',)),
    20: _vi(name="FESTiVAL PLUS", code=('fes+',), plate=('祝',)),
    21: _vi(name="BUDDiES", code=('bud',), plate=('双',)),
    22: _vi(name="BUDDiES PLUS", code=('bud+',), plate=('宴',)),
    23: _vi(name="PRiSM", code=('pri',), plate=('镜',)),
    24: _vi(name="PRiSM PLUS", code=('pri+',), plate=('彩',)),
    25: _vi(name="CIRCLE", code=('cir',), plate=('丸',)),
    26: _vi(name="CIRCLE PLUS", code=('cir+',), plate=()),

    # DX (CN)
    2020: _vi(name="舞萌DX", code=('dx2020',), plate=('熊华',)),
    2021: _vi(name="舞萌DX 2021", code=('dx2021',), plate=('爽煌',)),
    2022: _vi(name="舞萌DX 2022", code=('dx2022',), plate=('宙星',)),
    2023: _vi(name="舞萌DX 2023", code=('dx2023',), plate=('祭祝',)),
    2024: _vi(name="舞萌DX 2024", code=('dx2024',), plate=('双宴',)),
    2025: _vi(name="舞萌DX 2025", code=('dx2025',), plate=('镜',)),
    2026: _vi(name="舞萌DX 2026", code=('dx2026',), plate=('彩',)),
}
