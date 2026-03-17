import time
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any, Set

from PIL import Image
from loguru import logger


# 完成率别名映射
rate_alias: Dict[float, Tuple[str, ...]] = {
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
rate_alias_map: Dict[str, float] = {}
for rate_value, aliases in rate_alias.items():
    for alias in aliases:
        rate_alias_map[alias.lower()] = rate_value
del rate_alias  # 清理命名空间


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


def parse_status(target: str, mapping: Dict[str, int]) -> int:
    """通过映射表常量进行数值获取"""
    return mapping.get(target.lower(), 0)


@dataclass
class MaiAlias:
    """maimai 歌曲别名信息"""
    shortid: int  # 曲目 ID
    alias: str  # 别名字符串

    create_time: int  # 创建时间戳
    create_qq: int  # 创建者 QQ 号
    create_qq_group: Optional[int] = None  # 创建者 QQ 群号（若有）


@dataclass
class MaiChartAch:
    """maimai 谱面成就信息"""
    achievement: float  # 成就率
    dxscore: int = 0  # DX 分数
    dxscore_max: int = 0  # DX 分数最大值
    combo: int = 0  # 连击
    sync: int = 0  # 同步游玩
    server: str = "JP"  # 服务器标识 (JP/INTL/CN)
    update_time: int = 0  # 更新时间戳

    @property
    def dxscore_star_count(self) -> int:
        if self.dxscore_max == 0 or self.dxscore_max < self.dxscore:
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


@dataclass
class MaiChart:
    """maimai 谱面信息"""
    difficulty: int  # diff 难度编号
    lv: float  # level 等级
    lv_cn: Optional[float] = None  # 国服定数
    des: str = ""  # designer 谱师
    inote: str = ""  # note 音符数据
    # 音符数量 (tap, hold, slide, touch, break)
    notes: Tuple[int, int, int, int, int] = (-1, -1, -1, -1, -1)
    diving_fish_lv: Optional[int] = None  # 水鱼拟合难度

    _ach: Optional[MaiChartAch] = None  # 成就信息
    _ach_cn: Optional[MaiChartAch] = None  # 国服成就信息

    @property
    def note_count(self) -> int:
        c = sum(self.notes)
        return c if c >= 0 else -1

    @property
    def dxscore_max(self) -> int:
        return self.note_count * 3 if self.note_count >= 0 else 0

    @property
    def lv_str(self, plus: int = 6, server: str = "JP") -> str:
        """获取该谱面的等级字符串表示"""
        level = self.lv_cn if server == "CN" else self.lv
        if level is None:
            return "N/A"
        int_part = int(level)
        frac_part = level - int_part
        return f"{int_part}+" if frac_part * 10 >= plus else f"{level}"

    def get_dxrating(self, ap_bonus: bool = False, server: str = "JP") -> int:
        """获取谱面 DX Rating"""
        ach = self.get_achievement(server=server)
        if not ach:
            return 0

        # 使用 next() 找到第一个满足条件的因子
        factor = next(
            (f for threshold, f in RATE_FACTOR_TABLE if ach.achievement >= threshold),
            0.0  # 默认值
        )
        ra = int(self.lv * ach.achievement * factor)
        # AP 额外奖励
        if ap_bonus and ach.combo >= 3:  # 3 代表 All Perfect
            ra += 1
        return ra

    def get_achievement(self, server: str = "JP", prefer_non_empty: bool = False) -> Optional[MaiChartAch]:
        """获取谱面成绩"""
        if prefer_non_empty:
            # 优先返回非空成就信息
            if server == "CN" and self._ach_cn:
                return self._ach_cn
            elif server == "JP" and self._ach:
                return self._ach
        else:
            # 无优先级，直接返回对应服务器的成就信息
            if server == "CN":
                return self._ach_cn
            elif server == "JP":
                return self._ach
        return None

    def set_achievement(self, ach: MaiChartAch):
        """设置成就信息"""
        if ach.server == "CN":
            self._ach_cn = ach
        elif ach.server == "JP":
            self._ach = ach

@dataclass
class MaiData:
    """maimai 歌曲元数据"""

    shortid: int  # 曲目 ID
    title: str  # 曲名
    bpm: int  # BPM
    artist: str  # 艺术家
    genre: int  # 流派
    cabinet: str  # 谱面类型
    version: int  # 日服更新版本
    version_cn: Optional[int]  # 国服更新版本
    converter: str  # 谱面来源
    img_path: Path  # 图片文件路径
    zip_path: Optional[Path] = None  # 如果存在的话，ADX 谱面 ZIP 文件路径
    _cached_image: Optional[Image.Image] = None  # 缓存的封面图片对象

    current_version: int = -1  # 当前版本，判断是否为b15

    _chart1: Optional[MaiChart] = None  # Easy, 在 DX 版本中已废弃
    _chart2: Optional[MaiChart] = None  # Basic
    _chart3: Optional[MaiChart] = None  # Advanced
    _chart4: Optional[MaiChart] = None  # Expert
    _chart5: Optional[MaiChart] = None  # Master
    _chart6: Optional[MaiChart] = None  # Re: Master, 仅部分谱面追加

    # Utage 宴会场 专属字段
    is_utage: bool = True  # Utage: Utage 标志
    utage_tag: str = ""  # Utage: is_utage 标签
    buddy: bool = False  # Utage: 是否为 Buddy 谱面
    _chart7: Optional[MaiChart] = None  # Utage: Utage 谱面

    aliases: List[MaiAlias] = field(default_factory=list)  # 歌曲别名列表

    @property
    def is_cabinet_dx(self) -> bool:
        return self.cabinet.upper() == "DX"

    @property
    def is_b15(self) -> bool:
        version = self.version

        if self.current_version < 0:
            # 未绑定版本，直接返回 False
            return False
        elif self.current_version > 2000:
            # maiCN
            limit = 0
            version = self.version_cn if self.version_cn is not None else self.version
        elif self.current_version >= 25:
            # maiJP: 25(CiRCLE) 开始，B15 扩展到两个版本周期
            limit = 1
        else:
            # maiJP
            limit = 0
        return version >= self.current_version - limit

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
    def charts(self) -> List[MaiChart]:
        """获取所有谱面"""
        return [chart for chart in [self._chart1, self._chart2, self._chart3, self._chart4,
                                    self._chart5, self._chart6, self._chart7] if chart]

    def set_chart(self, chart: MaiChart):
        """设置对应谱面"""
        if not 1 <= chart.difficulty <= 7:
            raise ValueError("Difficulty must be between 1 and 7")
        elif chart.difficulty == 7:
            # 一定为非 Buddy 的 Utage 谱面
            self.is_utage = True
            self.buddy = False
        setattr(self, f"_chart{chart.difficulty}", chart)

    def set_chart_ach(self, diff: int, ach: MaiChartAch):
        """设置对应谱面的成就信息"""
        chart_obj = getattr(self, f"_chart{diff}", None)
        if chart_obj:
            chart_obj.ach = ach

    def from_diving_fish_json(self, data: Dict[str, List[Dict[str, Any]]], dxscore_max: int = 0) -> None:
        """解析来自水鱼查分器的响应体数据，填充 MaiChartAch 分数信息"""
        records: List[Dict[str, Any]] = data.get(str(self.shortid), [])
        for record in records:
            diff = record.get("level_index", 3) + 2  # 水鱼难度编号转换为 MaiChart 难度编号
            achievement = record.get("achievements", 0.0000)
            dxscore = 0 if dxscore_max == 0 else dxscore_max
            combo = parse_status(record.get("fc", ""), DF_FC_MAP)
            sync = parse_status(record.get("fs", ""), DF_FS_MAP)

            ach = MaiChartAch(
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


class MusicDataManager:
    """乐曲数据管理器（单例）"""
    _data: List[Dict[str, Any]] = []
    _ids: Set[int] = set()
    _last_update: float = 0
    _expire_seconds: int = 24 * 3600  # 24小时

    @classmethod
    async def get_all_data(cls, cache_path: Path) -> List[Dict[str, Any]]:
        """获取完整的乐曲列表（带内存缓存检查）"""
        current_time = time.time()

        # 1. 检查内存缓存是否有效
        if cls._data and (current_time - cls._last_update < cls._expire_seconds):
            return cls._data

        # 2. 内存失效，执行磁盘/API 加载逻辑
        data = await cls._load_data(cache_path)

        # 3. 更新内存状态并返回
        cls._update_memory_state(data)
        return cls._data

    @classmethod
    async def contains_id(cls, music_id: int, cache_path: Path) -> bool:
        """高性能判断 ID 是否在查分器列表中"""
        await cls.get_all_data(cache_path)
        return music_id in cls._ids

    @classmethod
    def _update_memory_state(cls, data: List[Dict[str, Any]]):
        """刷新内存缓存的时间戳和 ID 索引"""
        cls._data = data
        cls._ids = {
            int(d['id']) for d in data
            if d.get('id') is not None and str(d['id']).isdigit()
        }
        cls._last_update = time.time()
        logger.debug(f"MusicCache 内存已刷新: 记录数={len(cls._data)}, 索引数={len(cls._ids)}")

    @classmethod
    async def _load_data(cls, path: Path) -> List[Dict[str, Any]]:
        """内部逻辑：处理磁盘读取、API 更新及容错降级"""
        music_data: List[Dict[str, Any]] = []
        current_time = int(time.time())

        # 1. 检索本地文件
        json_files = sorted(
            list(path.glob("diving-fish-music-data_*.json")),
            key=lambda x: int(x.stem.split('_')[-1]) if x.stem.split('_')[-1].isdigit() else 0,
            reverse=True
        )

        latest_file = json_files[0] if json_files else None
        cache_is_valid = False

        # 2. 尝试读取本地有效缓存
        if latest_file:
            ts = int(latest_file.stem.split('_')[-1])
            if (current_time - ts) < cls._expire_seconds:
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        music_data = json.load(f)
                    cache_is_valid = True
                    logger.info(f"使用本地有效期内缓存: {latest_file.name}")
                except Exception as e:
                    logger.error(f"本地缓存读取失败: {e}")

        # 3. 缓存失效或缺失，尝试同步 API
        if not cache_is_valid:
            try:
                from .diving_fish import music_data as fetch_api_data
                logger.info("正在请求查分器 API 更新数据...")
                new_data = await fetch_api_data()
                if not new_data:
                    raise ValueError("API 返回数据为空")

                # API 成功：保存文件并准备清理旧缓存
                music_data = new_data
                new_file = path / f"diving-fish-music-data_{current_time}.json"
                with open(new_file, 'w', encoding='utf-8') as f:
                    json.dump(music_data, f, ensure_ascii=False, indent=4)
                logger.success(f"数据更新成功并保存至: {new_file.name}")

                # 清理旧文件
                for f in json_files:
                    try:
                        f.unlink()
                    except OSError:
                        pass

            except Exception as e:
                logger.error(f"API 更新失败: {e}")
                # 容错降级：API 挂了就去翻翻旧的能不能用
                if latest_file and not music_data:
                    try:
                        with open(latest_file, 'r', encoding='utf-8') as f:
                            music_data = json.load(f)
                        logger.warning(f"API 故障，已降级复用过期缓存: {latest_file.name}")
                    except Exception as e:
                        logger.critical(f"本地无任何可用数据！{e}")
                        raise FileNotFoundError("无法获取乐曲数据，API 及本地缓存均不可用。") from e

        return music_data
