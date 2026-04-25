# 常量集合
import yaml
from pathlib import Path
from typing import Literal, TypeVar, Mapping, Iterable


_T = TypeVar("_T")

# 使用 Mapping 和 Iterable 使函数更具通用性
def _get_map(origin_dict: Mapping[_T, Iterable[str]]) -> dict[str, _T]:
    """将原字典的 values (list[str]) 中的每个元素映射到其对应的 key"""
    result_map: dict[str, _T] = {}

    for key, aliases in origin_dict.items():
        for alias in aliases:
            result_map[alias] = key

    return result_map


RATE_ALIAS_DICT = {
    101.0000: ("ap+", "理论"),
    100.7500: ("ap",),
    100.5000: ("鸟加", "鸟家", "sss+", "3s+"),
    100.0000: ("鸟", "鸟s", "sss", "3s"),
    99.5000:  ("ss+", "2s+"),
    99.0000:  ("ss", "2s"),
    98.0000:  ("s+", "1s+"),
    97.0000:  ("s", "1s"),
    94.0000:  ("鸟a", "aaa", "3a"),
    90.0000:  ("aa", "2a"),
    80.0000:  ("a", "1a"),
    75.0000:  ("鸟b", "bbb", "3b"),
    70.0000:  ("bb", "2b"),
    60.0000:  ("b", "1b"),
    50.0000:  ("c", "1c"),
    0.0000:   ("d", "1d"),
}
RATE_ALIAS_MAP = _get_map(RATE_ALIAS_DICT)

# 完成率对应的评分因子表
RATE_FACTOR_TABLE: list[tuple[float, float]] = [
    (100.5000, 0.224),
    (100.4999, 0.222),
    (100.0000, 0.216),
    (99.9999, 0.214),
    (99.5000, 0.211),
    (99.0000, 0.208),
    (98.9999, 0.206),
    (98.0000, 0.203),
    (97.0000, 0.200),
    (96.9999, 0.176),
    (94.0000, 0.168),
    (90.0000, 0.152),
    (80.0000, 0.136),
    (79.9999, 0.128),
    (75.0000, 0.120),
    (70.0000, 0.112),
    (60.0000, 0.096),
    (50.0000, 0.080),
    (40.0000, 0.064),
    (30.0000, 0.048),
    (20.0000, 0.032),
    (10.0000, 0.016),
]

# Diving-Fish 的 FC/FS 解析映射
DF_FC_DICT = dict(enumerate([
    ('fc', 'full combo', 'fullcombo'),
    ('fcp', 'fc+', 'full combo +', 'fullcombo +', 'fullcombo+', 'full combo plus', 'fullcombo plus', 'fullcomboplus'),
    ('ap', 'all perfect', 'allperfect'),
    ('app', 'ap+', 'all perfect +', 'allperfect +', 'allperfect+', 'all perfect plus', 'allperfect plus', 'allperfectplus'),
    ], start=1))
DF_FC_MAP = _get_map(DF_FC_DICT)
DF_FS_DICT = dict(enumerate([
    ('sync', 'sync play', 'syncplay'),
    ('fs', 'full sync', 'fullsync'),
    ('fsp', 'fs+', 'full sync plus', 'fullsync plus', 'fullsync+', 'full sync+'),
    ('fsd', 'fdx', 'full sync deluxe', 'fullsync deluxe', 'fullsyncdeluxe', 'full sync deluxe'),
    ('fsdp', 'fsd+', 'fdxp', 'fdx+',  'full sync deluxe plus', 'fullsync deluxe plus', 'fullsyncdeluxe plus', 'fullsyncdeluxe+', 'full sync deluxe plus', 'full sync deluxe+'),
    ], start=1))
DF_FS_MAP = _get_map(DF_FS_DICT)

# 难度解析映射
DIFFS_DICT = dict(enumerate([
    ("蓝", 'easy'),
    ("绿", 'basic'),
    ("黄", 'advanced'),
    ("红", 'expert'),
    ("紫", 'master'),
    ("白", 'remaster', 're:master'),
    ('宴', '宴会场', '宴·会·场', 'utage', 'u·ta·ge'),
], start=1))
DIFFS_MAP = _get_map(DIFFS_DICT)

# 服务器标识类型
SERVER_TAG = Literal["JP", "CN"]

# 基础路径及 yml 数据
PLUGIN_BASE_PATH = Path(__file__).parent
ASSETS_PATH = PLUGIN_BASE_PATH / "assets"
GENRES_YAML_PATH = ASSETS_PATH / "genres.yaml"
GENRES_DATA = yaml.safe_load(GENRES_YAML_PATH.read_text(encoding="utf-8"))
VERSIONS_YAML_PATH = ASSETS_PATH / "versions.yaml"
VERSIONS_DATA = yaml.safe_load(VERSIONS_YAML_PATH.read_text(encoding="utf-8"))

# DXRating 版本分界线
BOUNDARIES_DX_RATING = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14500, 15000]
BOUNDARIES_DX_RATING_NEW = [0, 1000, 2000, 5000, 7000, 10000, 12000, 13000, 14000, 14250, 14500, 14750, 15000, 15250, 15500, 15750, 16000, 16250, 16500, 16750]
