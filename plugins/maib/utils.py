import time
import yaml
import bisect
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Literal

from PIL import Image
from loguru import logger


# 完成率别名映射
rate_alias_map: Dict[str, float] = {}
for rate_value, aliases in {
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
}.items():
    for alias in aliases:
        rate_alias_map[alias.lower()] = rate_value


# 完成率对应的评分因子表
RATE_FACTOR_TABLE: List[Tuple[float, float]] = [
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
DF_FC_MAP = {v: i + 1 for i, v in enumerate(['fc', 'fcp', 'ap', 'app'])}
DF_FS_MAP = {v: i + 1 for i, v in enumerate(['sync', 'fs', 'fsp', 'fsd', 'fsdp'])}
# 难度颜色字符串解析映射
DIFFS_MAP = {v: i + 1 for i, v in enumerate(["蓝", "绿", "黄", "红", "紫", "白"])}

# 服务器标识类型
SERVER_TAG = Literal["JP", "INTL", "CN"]

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

def parse_status(target: str, mapping: Dict[str, int]) -> int:
    """通过映射表常量进行数值获取"""
    return mapping.get(target.lower(), 0)

def get_current_versions():
    """从 VERSIONS_DATA 获取当前最新版本号"""
    jp_versions = [v for v in VERSIONS_DATA.keys() if v < 2000]
    cn_versions = [v for v in VERSIONS_DATA.keys() if v >= 2000]
    
    jp_current = max(jp_versions) if jp_versions else 0
    cn_current = max(cn_versions) if cn_versions else 0
    return jp_current, cn_current

@dataclass
class MaiAlias:
    """maimai 歌曲别名信息"""
    shortid: int  # 曲目 ID
    alias: str  # 别名字符串

    create_time: int  # 创建时间戳
    create_qq: int  # 创建者 QQ 号
    create_qq_group: Optional[int] = None  # 创建者 QQ 群号 (若有)


@dataclass
class MaiChartAch:
    """maimai 谱面成就信息"""

    shortid: int  # 曲目 ID
    difficulty: int  # 难度编号
    server: SERVER_TAG  # 服务器标识
    achievement: float  # 成就率
    dxscore: int = 0  # DX 分数
    dxscore_max: int = -1  # DX 分数上限
    combo: int = 0  # 连击
    sync: int = 0  # 同步游玩
    update_time: int = 0  # 更新时间戳

    user_id: int = -1 # 用户 ID (qq)

    @property
    def dxscore_star_count(self) -> int:
        if self.dxscore_max < self.dxscore:
            return 0
        dxs_percent = self.dxscore / self.dxscore_max * 100

        # 0~85: 0星, 85~90: 1星, 90~93: 2星, 93~95: 3星, 95~97: 4星, 97~100: 5星
        thresholds = [85, 90, 93, 95, 97, 100]
        for i, threshold in enumerate(thresholds):
            if dxs_percent < threshold:
                return i
        return 5

    @property
    def star(self) -> int:
        return self.dxscore_star_count

    @property
    def dxscore_tuple(self) -> tuple[int, int, int]:
        return self.dxscore, self.dxscore_max, self.dxscore_star_count

    def update(self, new_ach: 'MaiChartAch'):
        """
        合并成绩逻辑：取各项指标的最大值
        """
        self.achievement = max(self.achievement, new_ach.achievement)
        self.dxscore = max(self.dxscore, new_ach.dxscore)
        self.combo = max(self.combo, new_ach.combo)
        self.sync = max(self.sync, new_ach.sync)
        self.update_time = int(time.time())

@dataclass
class MaiChart:
    """maimai 谱面信息"""

    shortid: int  # 曲目 ID
    difficulty: int  # diff 难度编号
    lv: float  # level 等级
    lv_cn: Optional[float] = None  # 国服定数
    lv_synh: Optional[float] = None  # 水鱼拟合难度
    des: str = ""  # designer 谱师
    inote: str = ""  # note 音符数据

    # Note 统计数据
    note_count_tap: int = -1
    note_count_hold: int = -1
    note_count_slide: int = -1
    note_count_touch: int = -1
    note_count_break: int = -1

    # 成就信息，键为服务器标识
    _achs: dict[SERVER_TAG, MaiChartAch | None] = field(
            default_factory=lambda: {
                "JP": None,
                "INTL": None,
                "CN": None,
            }
        )

    @property
    def notes(self) -> Tuple[int, int, int, int, int]:
        """返回一个包含所有 Note 统计数据的元组"""
        return (
            self.note_count_tap,
            self.note_count_hold,
            self.note_count_slide,
            self.note_count_touch,
            self.note_count_break
        )

    @property
    def note_count(self) -> int:
        c = sum(self.notes)
        return c if c >= 0 else -1

    @property
    def dxscore_max(self) -> int:
        return self.note_count * 3 if self.note_count >= 0 else -1

    def get_lv_str(self, server: SERVER_TAG = "JP", plus: int = 6) -> str:
        """获取该谱面的等级字符串表示"""
        level = self.lv_cn if server == "CN" else self.lv
        if level is None:
            return "N/A"
        int_part = int(level)
        frac_part = level - int_part
        return f"{int_part}+" if frac_part * 10 >= plus else f"{level}"

    def get_ach(self, server: SERVER_TAG = "JP") -> MaiChartAch:
        """获取谱面成绩"""
        ach = self._achs.get(server, None)
        return ach if ach else MaiChartAch( shortid=self.shortid, difficulty=self.difficulty, server=server, achievement=-100)

    def set_ach(self, ach: MaiChartAch):
        """覆盖原有谱面成绩"""
        ach.dxscore_max = self.dxscore_max  # 同步 DX 分数上限
        self._achs[ach.server] = ach

    def update_ach(self, ach: MaiChartAch) -> MaiChartAch:
        """更新谱面成绩"""
        old_ach = self.get_ach(ach.server)
        old_ach.update(ach)
        self.set_ach(old_ach)
        return old_ach

    def get_dxrating(self, server: SERVER_TAG = "JP", ap_bonus: int = 0) -> int:
        """获取谱面 DX Rating"""
        ach = self.get_ach(server=server)
        if not ach or ach.achievement < 0:
            return 0
        factor = next((f for threshold, f in RATE_FACTOR_TABLE if ach.achievement >= threshold), 0.0)
        ra = int(self.lv * ach.achievement * factor)
        if ach.combo >= 3:
            ra += ap_bonus
        return ra

    def set_notes_with_tuple(self, notes: tuple[int, int, int, int, int]):
        """设置 Note 统计数据"""
        (
            self.note_count_tap,
            self.note_count_hold,
            self.note_count_slide,
            self.note_count_touch,
            self.note_count_break
        ) = notes

    def set_notes(self, tap: int, hold: int, slide: int, touch: int, break_note: int):
        """设置 Note 统计数据"""
        self.note_count_tap = tap
        self.note_count_hold = hold
        self.note_count_slide = slide
        self.note_count_touch = touch
        self.note_count_break = break_note

@dataclass
class MaiData:
    """maimai 歌曲元数据"""

    shortid: int  # 曲目 ID
    title: str  # 曲名
    bpm: int  # BPM
    artist: str  # 艺术家
    genre: int  # 流派
    cabinet: Literal['SD', 'DX']  # 谱面类型
    
    version: int  # 日服更新版本
    version_cn: Optional[int]  # 国服更新版本
    
    converter: str  # 谱面来源
    img_path: Path  # 图片文件路径
    zip_path: Optional[Path] = None  # 如果存在的话，ADX 谱面 ZIP 文件路径
    _cached_image: Optional[Image.Image] = None  # 缓存的封面图片对象

    # Utage 宴会场 专属字段
    is_utage: bool = False  # Utage: Utage 标志
    utage_tag: str = ""  # Utage: is_utage 标签
    buddy: bool = False  # Utage: 是否为 Buddy 谱面

    # 0~6 分别对应 Easy, Basic, Advanced, Expert, Master, Re: Master, Utage
    _charts: list[MaiChart | None] = field(default_factory=lambda: [None] * 7)

    aliases: List[MaiAlias] = field(default_factory=list)  # 歌曲别名列表

    @property
    def is_cabinet_dx(self) -> bool:
        return self.cabinet == "DX"

    @property
    def wholebpm(self) -> int: return self.bpm

    @property
    def image(self) -> Optional[Image.Image]:
        """获取封面图片对象"""
        path_str = str(self.img_path)

        # 场景 A: 路径包含 .zip/，说明是 ZIP 内部文件
        if ".zip" in path_str.lower():
            # 兼容 Win/Linux，寻找 .zip 结束位置
            # 假设格式为: /path/to/data.zip/image.png
            parts = path_str.split(".zip")
            zip_full_path = Path(parts[0] + ".zip")
            # 获取 ZIP 内部的相对路径 (去掉开头的斜杠)
            inner_path = parts[1].lstrip("\\/")

            if zip_full_path.exists():
                if not inner_path:
                    inner_path = 'bg.png'  # 默认文件名
                try:
                    with zipfile.ZipFile(zip_full_path, 'r') as z:
                        with z.open(inner_path) as f:
                            img = Image.open(f)
                            img.load()  # with 作用域外，强加载
                            self._cached_image = img
                            return self._cached_image
                except Exception as e:
                    logger.error(e)
                    return None

        # 场景 B: 普通物理路径
        p = Path(path_str)
        if p.exists() and p.is_file():
            self._cached_image = Image.open(p)
            self._cached_image.load()
            return self._cached_image

        return None

    @property
    def charts(self) -> dict[int, MaiChart]:
        """获取所有谱面"""
        return {chart.difficulty: chart for chart in self._charts if chart}

    def get_chart(self, diff: int) -> Optional[MaiChart]:
        """获取对应难度的谱面"""
        if not 1 <= diff <= 7:
            raise ValueError("Difficulty must be between 1 and 7")
        return self._charts[diff-1]  # diff 从 1 开始，列表索引从 0 开始

    def set_chart(self, chart: Optional[MaiChart]):
        """设置对应谱面"""
        if chart is None:
            return   # 兼容谱面返回 None 的情况，忽略而不设置
        if not 1 <= chart.difficulty <= 7:
            raise ValueError("Difficulty must be between 1 and 7")
        elif chart.difficulty == 7:
            # 一定为非 Buddy 的 Utage 谱面
            self.is_utage = True
            self.buddy = False
        elif chart.difficulty == 1 or 4 <= chart.difficulty <= 6:
            # 非 BASIC / ADVANCED 一定为非 Utage
            self.is_utage = False
            self.buddy = False
        self._charts[chart.difficulty - 1] = chart  # diff 从 1 开始，列表索引从 0 开始

    def is_b15(self, current_version: int) -> bool:
        version = self.version
        limit = 0

        if current_version < 0:
            # 未绑定版本，直接返回 False
            return False
        elif current_version > 2000:
            # maiCN
            version = self.version_cn if self.version_cn is not None else self.version
        elif current_version >= 25:
            # maiJP: 25(CiRCLE) 开始，B15 扩展到两个版本周期
            limit = 1

        return version >= current_version - limit

    def get_chart_dxrating(self, diff: int, server: SERVER_TAG, current_version: int = 0) -> Optional[int]:
        """获取对应难度的 DX Rating"""
        # maiJP: 25(CiRCLE) 开始，增加 AP+1 奖励分
        ap_bonus = 1 if 2000 > current_version >= 25 else 0
        chart = self.get_chart(diff)
        if chart:
            return chart.get_dxrating(server=server, ap_bonus=ap_bonus)
        return None

    def set_chart_ach(self, diff: int, ach: MaiChartAch):
        """设置对应谱面的成就信息"""
        # diff 从 1 开始，列表索引从 0 开始
        if chart_obj := self.get_chart(diff):
            chart_obj.set_ach(ach)

    def parse_sy_player_record(self, records: list, dxscore_max: int = 0) -> None:
        """解析来自水鱼查分器的响应体数据，填充 MaiChartAch 分数信息"""
        for record in records:
            diff = record.get("level_index", 3) + 2  # 水鱼难度编号转换为 MaiChart 难度编号
            achievement = record.get("achievements", 0.0000)
            dxscore = 0 if dxscore_max == 0 else dxscore_max
            combo = parse_status(record.get("fc", ""), DF_FC_MAP)
            sync = parse_status(record.get("fs", ""), DF_FS_MAP)
            shortid: int = record.get("song_id", self.shortid)

            ach = MaiChartAch(
                shortid=shortid,
                difficulty=diff,
                server="CN",
                achievement=achievement,
                dxscore=dxscore,
                dxscore_max=dxscore_max,
                combo=combo,
                sync=sync
            )
            self.set_chart_ach(diff, ach)

    def add_aliases(self, aliases: List[MaiAlias]):
        """添加多个别名"""
        existing_alias_names = {a.alias for a in self.aliases}
        for alias in aliases:
            if alias.shortid == self.shortid and alias.alias not in existing_alias_names:
                self.aliases.append(alias)
                existing_alias_names.add(alias.alias)


class MaiB50Manager:
    def __init__(self, current_version: int, server: SERVER_TAG):
        self.current_version = current_version
        self.server: SERVER_TAG = server
        # 存储格式: (rating, maidata, diff)
        self._b35: List[Tuple[int, 'MaiData', int]] = []
        self._b15: List[Tuple[int, 'MaiData', int]] = []

    @property
    def dxrating(self) -> int:
        """获取当前 B50 的总 Rating"""
        return sum(item[0] for item in self._b35 + self._b15)

    @property
    def dxrating_filename(self) -> str:
        """根据当前 DX Rating 获取对应的外框文件名"""
        ra = self.dxrating
        ver = self.current_version
        
        # 1. 确定使用的边界和前缀
        is_cirp = 26 <= ver < 2000
        bounds = BOUNDARIES_DX_RATING_NEW if is_cirp else BOUNDARIES_DX_RATING
        
        # 定位索引
        idx = max(0, bisect.bisect_right(bounds, ra) - 1)
        
        if idx < 8:
            # 金框之前不区分
            return f"JP_{idx}.png"
        if is_cirp:
            return f"JP_CIRP_{idx}.png"
        return f"JP_{idx}.png"

    def get_b35_list(self) -> list[tuple['MaiData', int]]:
        """获取当前 B35 的曲目列表"""
        return [(item[1], item[2]) for item in self._b35]

    def get_b15_list(self) -> list[tuple['MaiData', int]]:
        """获取当前 B15 的曲目列表"""
        return [(item[1], item[2]) for item in self._b15]

    def get_lists(self) -> tuple[list[tuple['MaiData', int]], list[tuple['MaiData', int]]]:
        """获取当前 B35 和 B15 的曲目列表"""
        return self.get_b35_list(), self.get_b15_list()

    def get_b50_list(self) -> list[tuple['MaiData', int]]:
        """获取当前 B50 的曲目列表，格式为 (MaiData, diff)"""
        b50 = self._b35 + self._b15
        b50.sort(key=lambda x: x[0], reverse=True)  # 按照 DX Rating 从高到低排序
        return [(item[1], item[2]) for item in b50]

    def _process_entry(self, maidata: 'MaiData', diff: int) -> Optional[Tuple[int, 'MaiData', int]]:
        ra = maidata.get_chart_dxrating(diff, server=self.server, current_version=self.current_version)
        return (ra, maidata, diff) if ra is not None else None

    def add_entry(self, maidata: 'MaiData', diff: int):
        """添加单个条目"""
        entry = self._process_entry(maidata, diff)
        if not entry:
            return

        is_new = maidata.is_b15(self.current_version)
        target = self._b15 if is_new else self._b35
        max_len = 15 if is_new else 35

        # 逻辑：如果没满直接加；如果满了且比最小值大，则替换最小值
        if len(target) < max_len:
            target.append(entry)
            target.sort(key=lambda x: x[0], reverse=True)
        else:
            # target[-1] 是当前最小值（因为已排序）
            if entry[0] > target[-1][0]:
                target[-1] = entry
                target.sort(key=lambda x: x[0], reverse=True)

    def add_entries(self, entries: List[Tuple['MaiData', int]]):
        """添加多个条目"""
        new_entries = []
        old_entries = []
        
        for md, diff in entries:
            entry = self._process_entry(md, diff)
            if not entry: continue
            if md.is_b15(self.current_version):
                new_entries.append(entry)
            else:
                old_entries.append(entry)

        # 合并当前数据与新数据，排序并截取前 N 个
        self._b15 = sorted(self._b15 + new_entries, key=lambda x: x[0], reverse=True)[:15]
        self._b35 = sorted(self._b35 + old_entries, key=lambda x: x[0], reverse=True)[:35]