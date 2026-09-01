"""utils/models.py 核心数据模型模块"""
from __future__ import annotations

import io
from datetime import datetime
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal
from contextlib import contextmanager, ExitStack, AbstractContextManager
from collections.abc import Generator
from PIL import Image
from loguru import logger

from .calculator import get_dxrating, get_dxscore_max, get_dxscore_star_count, get_level_plus_line
from ..utils.constants import DEFAULT_DATETIME
from ..utils.map import ComboID, SyncID, GenreID, DifficultyID, VersionID, Versions
from .enums import Server, SLevelSource
from .type import Achievement


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
    difficulty: DifficultyID
    server: Server
    achievement: float
    dxscore: int = 0
    dxscore_max: int = 0
    combo: ComboID = 0
    sync: SyncID = 0
    update_time: datetime = DEFAULT_DATETIME
    user_id: int = -1

    @property
    def dxscore_star_count(self) -> int:
        """根据 DXScore 和 DXScoreMax 计算星数"""
        return get_dxscore_star_count(self.dxscore, self.dxscore_max)

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
    difficulty: DifficultyID
    lv: float
    lv_cn: Optional[float] = None
    lv_synh: Optional[float] = None
    des: str = ""
    inote: str = ""
    notes: dict[str, int] = field(
        default_factory=lambda: {"tap": 0, "hold": 0, "slide": 0, "touch": 0, "break": 0}
    )
    _achs: dict[Server, Optional[MaiChartAch]] = field(
        default_factory=lambda: {server: None for server in Server}
    )

    @property
    def note_count(self) -> int:
        return sum(self.notes.values())

    @property
    def dxscore_max(self) -> int:
        return get_dxscore_max(self.note_count)

    def get_lv_str(self, source: SLevelSource = SLevelSource.JP, plus: int = 6) -> str:
        """获取谱面定数字符串表示，支持 JP/CN 服务器切换"""
        level = getattr(self, source.lv_field, None)
        if level is None:
            return "N/A"
        return f"{int(level)}+" if (level - int(level)) * 10 >= plus else f"{level}"

    def get_ach(self, server: Server = Server.JP) -> MaiChartAch:
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

    def get_dxrating(self, server: Server = Server.JP, ap_bonus: int = 0,
                     *, achievement: Optional[Achievement] = None, combo: Optional[ComboID] = None) -> int:
        """根据成就率和定数计算 DX Rating"""
        if achievement is None:
            ach_obj = self.get_ach(server)
            achievement = int(ach_obj.achievement * 10000)
            combo = ach_obj.combo
        else:
            combo = combo if combo is not None else 0
        level: float = getattr(self, SLevelSource.server(server).lv_field, -1)
        if level < 0:
            level = self.lv  # fallback
        return get_dxrating(achievement=achievement, level=level, ap_bonus=ap_bonus, combo=combo)

    def set_notes(self, tap: int, hold: int, slide: int, touch: int, break_note: int):
        """根据参数设置谱面 Note 数量"""
        self.notes["tap"] = tap
        self.notes["hold"] = hold
        self.notes["slide"] = slide
        self.notes["touch"] = touch
        self.notes["break"] = break_note

    def lv_is_plus(self, source: SLevelSource | Server = SLevelSource.JP, version: Optional[VersionID] = None,
                   plus: Optional[int] = None) -> bool:
        """判断谱面定数是否为加号定数"""
        if isinstance(source, Server):
            source = SLevelSource.server(source)
        if plus is None:
            if version is None:
                server = source.to_server() or Server.CN
                version = Versions.latest(server=server)
            plus = get_level_plus_line(version)
        level = getattr(self, source.lv_field, None)
        if level is None:
            return False
        return (level - int(level)) * 10 >= plus


@dataclass
class MaiData:
    """maimai 歌曲元数据"""
    shortid: int
    title: str
    bpm: int
    artist: str
    genre: GenreID
    cabinet: Literal['SD', 'DX']
    version: int
    version_cn: Optional[int]
    converter: str
    img_path: Path
    zip_path: Optional[Path] = None
    _cached_image: Optional[Image.Image] = None
    tg_file_id_cache: Optional[str] = None
    is_utage: bool = False
    utage_tag: str = ""
    buddy: bool = False
    jp_is_plate_required: bool = True
    cn_is_plate_required: bool = True
    _charts: dict[DifficultyID, Optional[MaiChart]] = field(
        default_factory=lambda: {i: None for i in range(1, 8)}
    )
    aliases: list[MaiAlias] = field(default_factory=list)

    # 特殊字段
    _matched_alias: Optional[str] = None  # 搜索时触发的别名缓存

    @property
    def is_cabinet_dx(self) -> bool:
        return self.cabinet == "DX"

    @property
    def wholebpm(self) -> int:
        return self.bpm

    def is_plate_required(self, server: Server) -> bool:
        """返回指定服务器是否要求牌子。"""
        if server == Server.JP:
            return self.jp_is_plate_required
        if server == Server.CN:
            return self.cn_is_plate_required
        raise KeyError(f"Invalid server: {server}")

    @contextmanager
    def image(self) -> Generator[Optional[Image.Image], None, None]:
        """
        上下文管理器：打开图片，使用后自动关闭底层资源。
        """
        path_str = str(self.img_path)
        lower = path_str.lower()
        zip_pos = lower.find(".zip")

        # 1. 处理 zip 内图片
        if zip_pos != -1:
            zip_end = zip_pos + len(".zip")
            zip_path = Path(path_str[:zip_end])
            inner_path = path_str[zip_end:].lstrip("/\\") or "bg.png"

            if zip_path.exists():
                stack = ExitStack()
                try:
                    zf = stack.enter_context(zipfile.ZipFile(zip_path))
                    raw_data = zf.read(inner_path)
                    buf = stack.enter_context(io.BytesIO(raw_data))
                    
                    img = Image.open(buf)
                    stack.callback(img.close)

                except Exception as exc:
                    stack.close()
                    logger.error(f"Failed to open image in zip: {exc}")
                    yield None
                    return

                with stack:
                    yield img
                return

        # 2. 处理普通文件图片
        p = Path(path_str)
        if not (p.exists() and p.is_file()):
            yield None
            return

        stack = ExitStack()
        try:
            img = Image.open(p)
            stack.callback(img.close)
        except Exception as exc:
            stack.close()
            logger.error(f"Failed to open image file: {exc}")
            yield None
            return

        with stack:
            yield img

    @property
    def charts(self) -> dict[DifficultyID, MaiChart]:
        return {c.difficulty: c for c in self._charts.values() if c}

    def get_chart(self, diff: DifficultyID) -> Optional[MaiChart]:
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

    def get_chart_dxrating(self, diff: DifficultyID, server: Server, current_version: int = 0) -> int:
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
    default_server: Server = Server.CN
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

    def get_dxrating_data(self, server: Optional[Server] = None) -> DXRatingData:
        """获取指定服务器的 DXRating 数据"""
        if server is None:
            server = self.default_server
        if server == Server.JP:
            data = self.jp_dxra_data
        elif server == Server.CN:
            data = self.cn_dxra_data
        else:
            raise KeyError(f"Invalid server: {server}")
        return data

    def get_update_time(self, server: Optional[Server] = None) -> datetime:
        """获取指定服务器的更新日期"""
        if server is None:
            server = self.default_server
        if server == Server.JP:
            dt = self.jp_update_time
        elif server == Server.CN:
            dt = self.cn_update_time
        else: raise KeyError(f"Invalid server: {server}")
        return dt

    def get_formated_time(self, server: Optional[Server] = None) -> str:
        """获取指定服务器的更新日期（格式化字符串）"""
        dt = self.get_update_time(server=server)
        if dt <= DEFAULT_DATETIME: return "Not Updated"
        return f"{dt:%Y.%m.%d %H:%M:%S}"
        
    def get_current_version(self, server: Server) -> int:
        """获取指定服务器的当前版本号"""
        if server == Server.JP:
            ver = self.jp_current_version
        elif server == Server.CN:
            ver = self.cn_current_version
        else:
            raise KeyError(f"Invalid server: {server}")
        return ver

    def set_current_version(self, server: Server, version: int):
        """设置指定服务器的当前版本号"""
        if server == Server.JP:
            self.jp_current_version = version
        elif server == Server.CN:
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
