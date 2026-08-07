"""utils/models.py 核心数据模型模块"""
from __future__ import annotations

import io
from datetime import datetime
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

from PIL import Image
from loguru import logger

from .calculator import get_dxrating, get_dxscore_max
from ..constants import server, DEFAULT_DATETIME


__all__ = [
    "MaiAlias",
    "MaiChartAch",
    "MaiChart",
    "MaiData",
    "DXRatingData",
    "MaiUser",
]



@dataclass
class MaiAlias:
    """maimai 歌曲别名信息"""
    shortid: int
    alias: str
    create_time: datetime
    create_qq: int
    create_qq_group: Optional[int] = None


@dataclass
class MaiChartAch:
    """maimai 谱面成就信息"""
    shortid: int
    difficulty: int
    server: server
    achievement: float
    dxscore: int = 0
    dxscore_max: int = 0
    combo: int = 0
    sync: int = 0
    update_time: datetime = DEFAULT_DATETIME
    user_id: int = -1

    @property
    def dxscore_star_count(self) -> int:
        """根据 DXScore 和 DXScoreMax 计算星数"""
        if self.dxscore_max < self.dxscore or self.dxscore_max <= 0 or self.dxscore <= 0:
            return 0
        pct = self.dxscore / self.dxscore_max * 100
        thresholds = [85, 90, 93, 95, 97, 100]
        for i, t in enumerate(thresholds):
            if pct < t:
                return i
        return 5

    @property
    def star(self) -> int:
        return self.dxscore_star_count

    @property
    def dxscore_tuple(self) -> tuple[int, int, int]:
        """
        返回 DXScore 相关的数值
        
        :return: `dxscore`, `dxscore_max`, `dxscore_star_count`
        """
        return self.dxscore, self.dxscore_max, self.dxscore_star_count

    def _check_compatibility(self, other: MaiChartAch):
        """检查两个 MaiChartAch 对象是否兼容"""
        if not isinstance(other, MaiChartAch):
            raise TypeError("只能接受 MaiChartAch")
        if self.shortid != other.shortid or self.difficulty != other.difficulty:
            raise ValueError("只能操作相同谱面的成绩数据")
        if self.server != other.server:
            raise ValueError("只能操作相同服务器的成绩数据")

    def update(self, other: MaiChartAch):
        """合并更新成就数据到当前对象"""
        if not other > self:
            # 无任何提升，合并和不合并等效
            return
        
        self.achievement = max(self.achievement, other.achievement)
        self.dxscore = max(self.dxscore, other.dxscore)
        self.combo = max(self.combo, other.combo)
        self.sync = max(self.sync, other.sync)
        self.update_time = datetime.now()

    def __add__(self, other: MaiChartAch) -> MaiChartAch:
        """合并两个 MaiChartAch 对象，返回新的对象"""
        self._check_compatibility(other)
        return MaiChartAch(
            shortid=self.shortid,
            difficulty=self.difficulty,
            server=self.server,
            achievement=max(self.achievement, other.achievement),
            dxscore=max(self.dxscore, other.dxscore),
            dxscore_max=max(self.dxscore_max, other.dxscore_max),
            combo=max(self.combo, other.combo),
            sync=max(self.sync, other.sync),
            update_time=datetime.now(),
            user_id=self.user_id,
        )

    def __gt__(self, other: MaiChartAch) -> bool:
        """比较成就数据是否有任何提升"""
        self._check_compatibility(other)
        
        return (self.achievement > other.achievement
            or self.dxscore > other.dxscore
            or self.combo > other.combo
            or self.sync > other.sync)


@dataclass
class MaiChart:
    """maimai 谱面信息"""
    shortid: int
    difficulty: int
    lv: float
    lv_cn: Optional[float] = None
    lv_synh: Optional[float] = None
    des: str = ""
    inote: str = ""
    notes: dict[str, int] = field(
        default_factory=lambda: {"tap": 0, "hold": 0, "slide": 0, "touch": 0, "break": 0}
    )
    _achs: dict[server, Optional[MaiChartAch]] = field(
        default_factory=lambda: {"JP": None, "CN": None}
    )

    @property
    def note_count(self) -> int:
        return sum(self.notes.values())

    @property
    def dxscore_max(self) -> int:
        return get_dxscore_max(self.note_count)

    def get_lv_str(self, server: server = "JP", plus: int = 6) -> str:
        """获取谱面定数字符串表示，支持 JP/CN 服务器切换"""
        level = self.lv_cn if server == "CN" else self.lv
        if level is None: return "N/A"
        return f"{int(level)}+" if (level - int(level)) * 10 >= plus else f"{level}"

    def get_ach(self, server: server = "JP") -> MaiChartAch:
        """返回该谱面在指定服务器的成绩数据"""
        ach = self._achs.get(server, None)
        if ach is None:
            # 如果不存在成就数据，返回一个标记为未游玩的 MaiChartAch 对象
            ach = MaiChartAch(
                shortid=self.shortid,
                difficulty=self.difficulty,
                server=server,
                achievement=-100
            )
        return ach

    def set_ach(self, ach: MaiChartAch):
        """设置该谱面在指定服务器的成绩数据"""
        ach.dxscore_max = self.dxscore_max
        self._achs[ach.server] = ach

    def update_ach(self, ach: MaiChartAch):
        """更新该谱面在指定服务器的成绩数据"""
        current = self._achs.get(ach.server)
        if current is None:
            self.set_ach(ach)
            return
        current.update(ach)

    def get_dxrating(self, server: server = "JP", ap_bonus: int = 0) -> int:
        """根据成就率和定数计算 DX Rating"""
        ach = self.get_ach(server).achievement
        level = self.lv_cn if server == "CN" and self.lv_cn is not None else self.lv
        return get_dxrating(achievement=ach, level=level, ap_bonus=ap_bonus)

    def set_notes(self, tap: int, hold: int, slide: int, touch: int, break_note: int):
        """根据参数设置谱面 Note 数量"""
        self.notes["tap"] = tap
        self.notes["hold"] = hold
        self.notes["slide"] = slide
        self.notes["touch"] = touch
        self.notes["break"] = break_note


@dataclass
class MaiData:
    """maimai 歌曲元数据"""
    shortid: int
    title: str
    bpm: int
    artist: str
    genre: int
    cabinet: Literal['SD', 'DX']
    version: int
    version_cn: Optional[int]
    converter: str
    img_path: Path
    zip_path: Optional[Path] = None
    _cached_image: Optional[Image.Image] = None
    _matched_alias: Optional[str] = None  # 搜索时触发的别名缓存
    tg_file_id_cache: Optional[str] = None
    is_utage: bool = False
    utage_tag: str = ""
    buddy: bool = False
    jp_is_plate_required: bool = True
    cn_is_plate_required: bool = True
    _charts: dict[int, Optional[MaiChart]] = field(
        default_factory=lambda: {i: None for i in range(1, 8)}
    )
    aliases: list[MaiAlias] = field(default_factory=list)

    @property
    def is_cabinet_dx(self) -> bool:
        return self.cabinet == "DX"

    @property
    def wholebpm(self) -> int:
        return self.bpm

    def is_plate_required(self, server: server) -> bool:
        """返回指定服务器是否要求牌子。"""
        if server == "JP":
            return self.jp_is_plate_required
        if server == "CN":
            return self.cn_is_plate_required
        raise KeyError(f"Invalid server: {server}")

    def get_image(self, shared_zip: Optional[zipfile.ZipFile] = None) -> Optional[Image.Image]:
        path_str = str(self.img_path)
        if ".zip" in path_str.lower():
            parts = path_str.split(".zip")
            zip_full_path = Path(parts[0] + ".zip")
            inner_path = parts[1].lstrip("\\/")
            if zip_full_path.exists():
                if not inner_path: inner_path = 'bg.png'
                try:
                    if shared_zip:
                        with shared_zip.open(inner_path) as f:
                            img = Image.open(f)
                            img.load()
                            self._cached_image = img
                            return img
                    with zipfile.ZipFile(zip_full_path) as z:
                        with z.open(inner_path) as f:
                            img = Image.open(f)
                            img.load()
                            self._cached_image = img
                            return img
                except Exception as e:
                    logger.error(e)
                    return None
        p = Path(path_str)
        if p.exists() and p.is_file():
            self._cached_image = Image.open(p)
            self._cached_image.load()
            return self._cached_image
        return None

    @property
    def image(self) -> Optional[Image.Image]:
        return self.get_image()

    @property
    def charts(self) -> dict[int, MaiChart]:
        return {c.difficulty: c for c in self._charts.values() if c}

    def get_chart(self, diff: int) -> Optional[MaiChart]:
        """根据难度获取谱面对象"""
        if not 1 <= diff <= 7:
            raise ValueError("Difficulty must be between 1 and 7")
        return self._charts[diff]

    def set_chart(self, chart: MaiChart):
        """设置谱面对象"""
        if not 1 <= chart.difficulty <= 7:
            raise ValueError("Difficulty must be between 1 and 7")
        if chart.difficulty == 7:
            self.is_utage = True
            self.buddy = False
        elif chart.difficulty == 1 or 4 <= chart.difficulty <= 6:
            self.is_utage = False
            self.buddy = False
        self._charts[chart.difficulty] = chart

    def is_b15(self, version: int) -> bool:
        """判断该 MaiData 曲目是否属于对应版本 best15 部分（而不是 best35 部分）"""
        ver = self.version
        limit = 0
        if version < 0:
            return False
        if version > 2000:
            ver = self.version_cn
            if ver is None:
              return False  # cn 服务器无该歌曲，肯定不属于
        elif version >= 25:
            limit = 1
        return ver >= version - limit

    def get_chart_dxrating(self, diff: int, server: server, current_version: int = 0) -> int:
        """获取指定难度谱面的 DXRating"""
        ap = 1 if 2000 > current_version >= 25 else 0
        chart = self.get_chart(diff)
        if chart is None:
            return 0
        return chart.get_dxrating(server=server, ap_bonus=ap)

    def add_aliases(self, aliases: list[MaiAlias]):
        """添加别名列表（含去重逻辑）"""
        existing = {a.alias for a in self.aliases}
        for a in aliases:
            if a.shortid == self.shortid and a.alias not in existing:
                self.aliases.append(a)
                existing.add(a.alias)


@dataclass
class _StatMetrics:
    total: int = 0
    max: int = 0
    min: int = 0


class DXRatingData:
    total: int = 0
    b35: _StatMetrics = field(default_factory=_StatMetrics)
    b15: _StatMetrics = field(default_factory=_StatMetrics)

    def __init__(self, total: int = 0,
                 b35_total: int = 0, b35_max: int = 0, b35_min: int = 0,
                 b15_total: int = 0, b15_max: int = 0, b15_min: int = 0):
        self.total = total
        self.b35 = _StatMetrics(total=b35_total, max=b35_max, min=b35_min)
        self.b15 = _StatMetrics(total=b15_total, max=b15_max, min=b15_min)


@dataclass
class MaiUser:
    user_id: int
    user_telegram_id: Optional[int] = None
    username: str = ''
    default_server: server = 'CN'
    plate: tuple[int | None, int | None] = (None, None)

    jp_current_version: int = 0
    jp_update_time: datetime = DEFAULT_DATETIME
    jp_dxra_data: DXRatingData = field(default_factory=DXRatingData)
    cn_current_version: int = 0
    cn_update_time: datetime = DEFAULT_DATETIME
    cn_dxra_data: DXRatingData = field(default_factory=DXRatingData)

    @property
    def has_plate(self) -> bool:
        """若 plate 中的两个元素都是整数，则证明有牌子"""
        return all(isinstance(p, int) for p in self.plate)

    def get_username(self) -> str:
        """获取用户名，若未设置则返回 'maimai'"""
        return self.username or "maimai"

    def get_dxrating_data(self, server: Optional[server] = None) -> DXRatingData:
        """获取指定服务器的 DXRating 数据"""
        if server is None:
            server = self.default_server
        if server == 'JP':
            data = self.jp_dxra_data
        elif server == 'CN':
            data = self.cn_dxra_data
        else: raise KeyError(f"Invalid server: {server}")
        return data

    def get_update_time(self, server: Optional[server] = None) -> datetime:
        """获取指定服务器的更新日期"""
        if server is None:
            server = self.default_server
        if server == 'JP':
            dt = self.jp_update_time
        elif server == 'CN':
            dt = self.cn_update_time
        else: raise KeyError(f"Invalid server: {server}")
        return dt

    def get_formated_time(self, server: Optional[server] = None) -> str:
        """获取指定服务器的更新日期（格式化字符串）"""
        dt = self.get_update_time(server=server)
        if dt <= DEFAULT_DATETIME: return "Not Updated"
        return f"{dt:%Y.%m.%d %H:%M:%S}"
        
    def get_current_version(self, server: server) -> int:
        """获取指定服务器的当前版本号"""
        if server == 'JP':
            ver = self.jp_current_version
        elif server == 'CN':
            ver = self.cn_current_version
        else:
            raise KeyError(f"Invalid server: {server}")
        return ver

    def set_current_version(self, server: server, version: int):
        """设置指定服务器的当前版本号"""
        if server == 'JP':
            self.jp_current_version = version
        elif server == 'CN':
            self.cn_current_version = version

    def set_avatar(self, avatar: Image.Image | bytes):
        """设置用户头像，支持 PIL Image 对象或字节流"""
        if isinstance(avatar, Image.Image):
            self.avatar = avatar
        elif isinstance(avatar, bytes):
            try:
                self.avatar = Image.open(io.BytesIO(avatar)).convert('RGB')
            except Exception as e:
                logger.error(f"Failed to load avatar: {e}")
                self.avatar = None

    # --- refactor:locales 计划移除 ---
    def set_telegram_id(self, tid: int):
        """TG | 设置用户的 Telegram ID"""
        self.user_telegram_id = tid

    def remove_telegram_id(self):
        """TG | 移除用户的 Telegram ID"""
        self.user_telegram_id = None
