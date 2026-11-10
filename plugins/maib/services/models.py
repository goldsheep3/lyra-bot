"""services/models.py 数据库模型定义"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from nonebot_plugin_datastore import get_plugin_data
from nonebot_plugin_localstore import get_plugin_data_dir
from sqlalchemy import String, Integer, Float, BigInteger, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped as M, mapped_column as col, relationship, validates

from .. import utils
from ..utils.constants import DEFAULT_DATETIME
from ..utils.enums import Server


D_T = datetime | int | float | None


__all__ = [
    "MaiAlias",     # 乐曲别名信息模型
    "MaiChartAch",  # 谱面游玩成绩信息模型
    "MaiChart",     # 谱面信息模型
    "MaiData",      # 乐曲信息模型
    "MaiUser",      # 用户信息模型
    "MaiSync",      # maisync 模型
    "MaiLxns",      # 落雪授权信息模型
    "MaiRecord",    # 谱面游玩成绩历史记录模型
    "Maime",        # Aime 绑定模型
    "MaiIDMap",     # ShortID 重映射模型
]

Model = get_plugin_data().Model


def _as_datetime(value: D_T, *, default: datetime | None = None) -> datetime:
    """转换为 datetime 对象"""
    if value is None:
        return default or datetime.now()
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        if value <= 0:
            return DEFAULT_DATETIME
        return datetime.fromtimestamp(value)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _get(source: object | Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    """从源对象中获取指定键的值"""
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


# ------ 数据库模型 ------

class MaiAlias(Model):
    """MaiData 曲目别名数据"""

    __tablename__ = "maib_maialiases"
    __table_args__ = (UniqueConstraint("shortid", "alias"),)

    id: M[int] = col(primary_key=True, autoincrement=True)
    shortid: M[int] = col(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"), index=True)
    alias: M[str] = col(index=True)

    create_by: M[Optional[int]] = col(Integer, nullable=True)
    create_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)
    create_qq: M[int] = col(BigInteger)

    maidata: M["MaiData"] = relationship(back_populates="aliases", lazy="selectin")

    @validates("create_at")
    def _validate(self, _key: str, value: D_T) -> datetime: return _as_datetime(value)

    @classmethod
    def from_utils(cls, alias: utils.MaiAlias | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiAlias":
        source: object | Mapping[str, Any] = kwargs or alias or {}
        return cls(
            shortid=_get(source, "shortid"),
            alias=_get(source, "alias"),
            create_by=_get(source, "create_by"),
            create_at=_as_datetime(_get(source, "create_at"), default=datetime.now()),
            create_qq=_get(source, "create_qq"),
        )

    def to_utils(self) -> utils.MaiAlias:
        return utils.MaiAlias(
            shortid=self.shortid,
            alias=self.alias,
            create_at=self.create_at,
            create_qq=self.create_qq,
        )


class MaiChartAch(Model):
    """MaiChartAch 成绩数据"""

    __tablename__ = "maib_maichartachs"
    __table_args__ = (UniqueConstraint("qq", "shortid", "difficulty", "provider", "server"),)

    id: M[int] = col(primary_key=True, autoincrement=True)
    shortid: M[int] = col(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"))
    chart_id: M[int] = col(ForeignKey("maib_maicharts.id", ondelete="CASCADE"))
    difficulty: M[int]

    # 成绩所属服务器
    server: M[Server] = col(String(4))
    # 成绩数据来源
    provider: M[str] = col(String(16), default="unknown")
    # 成绩所属用户 AID
    # user: M[int] = col(Integer)
    qq: M[int] = col(BigInteger, nullable=True)  # [Deprecated] 由 user_id 更名而来，后续被 AID 替代
    # 达成率
    achievement: M[int] = col(Integer, default=0)
    # DXScore
    dxscore: M[int] = col(Integer, default=0)
    # ComboID
    combo: M[int] = col(Integer, default=0)
    # SyncID
    sync: M[int] = col(Integer, default=0)
    # 更新时间
    update_at: M[datetime] = col(DateTime(timezone=True),
                                      default=datetime.now, onupdate=datetime.now)

    # [Cache] 谱面游玩成绩对应的 DXRating
    dxrating_cache: M[int] = col(default=0)

    chart: M["MaiChart"] = relationship(back_populates="achs", lazy="selectin")

    @validates("update_at")
    def _validate(self, _key: str, value: D_T) -> datetime: return _as_datetime(value)

    @classmethod
    def from_utils(
        cls,
        ach: utils.MaiChartAch | Mapping[str, Any],
        *,
        chart_id: int,
        dxrating: Optional[int] = None,
    ) -> "MaiChartAch":
        return cls(
            shortid=_get(ach, "shortid"),
            chart_id=chart_id,
            difficulty=_get(ach, "difficulty"),
            server=_get(ach, "server"),
            achievement=int(_get(ach, "achievement", 0) * 10000),
            dxscore=_get(ach, "dxscore", 0),
            combo=_get(ach, "combo", 0),
            sync=_get(ach, "sync", 0),
            update_at=_as_datetime(_get(ach, "update_at"), default=datetime.now()),
            dxrating_cache=dxrating or 0,
            qq=_get(ach, "user_id", -1),
        )

    def to_utils(self, dxscore_max: int | None = None) -> utils.MaiChartAch:
        if dxscore_max is None:
            dxscore_max = self.chart.dxscore_max if self.chart is not None else 0
        return utils.MaiChartAch(
            shortid=self.shortid,
            difficulty=self.difficulty,
            server=self.server,
            achievement=self.achievement/10000,
            dxscore=self.dxscore,
            dxscore_max=dxscore_max,
            combo=self.combo,
            sync=self.sync,
            update_at=self.update_at,
            user_id=self.qq if self.qq is not None else -1,
        )

    def update(self, ach: utils.MaiChartAch) -> None:
        # TODO float -> int
        self.achievement = max(self.achievement, int(ach.achievement*10000))
        self.dxscore = max(self.dxscore, ach.dxscore)
        self.combo = max(self.combo, ach.combo)
        self.sync = max(self.sync, ach.sync)
        self.update_at = datetime.now()


class MaiChart(Model):
    """MaiChart 谱面数据"""

    __tablename__ = "maib_maicharts"
    __table_args__ = (UniqueConstraint("shortid", "difficulty"),)

    # ChartID
    id: M[int] = col(Integer, primary_key=True, autoincrement=True)
    # MaiData ShortID
    shortid: M[int] = col(Integer, ForeignKey("maib_maidatas.shortid", ondelete="CASCADE"))
    # 谱面难度 (BASIC ~ Re:MASTER)
    difficulty: M[int] = col(Integer, index=True)
    # 谱面定数（JP 服务器）
    lv_jp: M[float] = col(Float, index=True)
    # 谱面定数（CN 服务器）
    lv_cn: M[Optional[float]] = col(Float, index=True, nullable=True)
    # 谱面定数（水鱼拟合数据）
    lv_fit: M[Optional[float]] = col(Float, index=True, nullable=True)
    # 谱师
    designer: M[str] = col(String, default="")
    # Simai 完整谱面数据
    inote: M[str] = col(String, default="")

    # 谱面 Note 数量统计
    note_count_tap: M[int] = col(default=0)
    note_count_hold: M[int] = col(default=0)
    note_count_slide: M[int] = col(default=0)
    note_count_touch: M[int] = col(default=0)
    note_count_break: M[int] = col(default=0)

    # FK 关系
    maidata: M["MaiData"] = relationship(
        back_populates="charts",
        lazy="selectin"
    )
    achs: M[list["MaiChartAch"]] = relationship(
        back_populates="chart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def notes(self) -> dict[str, int]:
        return {
            "tap": self.note_count_tap,
            "hold": self.note_count_hold,
            "slide": self.note_count_slide,
            "touch": self.note_count_touch,
            "break": self.note_count_break,
        }

    @notes.setter
    def notes(self, value: Mapping[str, int] | None) -> None:
        notes = value or {}
        self.note_count_tap = int(notes.get("tap", 0))
        self.note_count_hold = int(notes.get("hold", 0))
        self.note_count_slide = int(notes.get("slide", 0))
        self.note_count_touch = int(notes.get("touch", 0))
        self.note_count_break = int(notes.get("break", 0))

    @property
    def note_count(self) -> int:
        return sum(self.notes.values())

    @property
    def dxscore_max(self) -> int:
        return utils.get_dxscore_max(self.note_count)

    @classmethod
    def from_utils(
        cls,
        chart: utils.MaiChart | Mapping[str, Any] | None = None,
        *,
        shortid: Optional[int] = None,
        **kwargs: Any,
    ) -> "MaiChart":
        source: object | Mapping[str, Any] = kwargs or chart or {}
        notes = _get(source, "notes", {}) or {}
        return cls(
            shortid=shortid if shortid is not None else _get(source, "shortid"),
            difficulty=_get(source, "difficulty"),
            lv_jp=_get(source, "lv_jp"),
            lv_cn=_get(source, "lv_cn"),
            lv_fit=_get(source, "lv_fit"),
            designer=_get(source, "des", ""),
            inote=_get(source, "inote", ""),
            notes=notes,
        )

    def to_utils(self, qq: Optional[int] = None) -> utils.MaiChart:
        maichart = utils.MaiChart(
            shortid=self.shortid,
            difficulty=self.difficulty,
            lv_jp=self.lv_jp,
            lv_cn=self.lv_cn,
            lv_fit=self.lv_fit,
            des=self.designer,
            inote=self.inote,
            notes=self.notes,
        )
        if qq is not None:
            for ach in self.achs:
                if ach.qq == qq:
                    maichart.set_ach(ach.to_utils(dxscore_max=self.dxscore_max))
        return maichart


class MaiData(Model):
    """MaiData 曲目数据"""

    __tablename__ = "maib_maidatas"

    # MaiData 乐曲唯一 ShortID
    shortid: M[int] = col(Integer, primary_key=True)
    # 乐曲名
    title: M[str] = col(String, index=True)
    # 乐曲 BPM（速度）
    bpm: M[int] = col(Integer)
    # 乐曲艺术家
    artist: M[str] = col(String, default="")
    # 乐曲流派 ID
    genre: M[int] = col(Integer)
    # 乐曲谱面类型
    cabinet: M[Literal["SD", "DX"]]
    # 乐曲在 JP 服务器的版本 ID
    version_jp: M[int]
    # 乐曲在 CN 服务器的版本 ID
    version_cn: M[Optional[int]] = col(nullable=True)
    # 乐曲数据提供者
    provider: M[str] = col(default="unknown")
    # 乐曲封面图片路径，若为 zip 内图片则为 zip 文件路径 + 内部路径
    img_path: M[str] = col(String)
    # 乐曲数据压缩包路径
    zip_path: M[Optional[str]] = col(String, nullable=True)
    # 乐曲是否为 UTAGE 曲目
    is_utage: M[bool] = col(default=False, index=True)
    # UTAGE 曲目标签
    utage_tag: M[str] = col(String(1), default=" ")
    # 乐曲是否为 UTAGE/Buddy 曲目
    buddy: M[bool] = col(default=False)
    # JP 服务器对应版本获取牌子时是否需要该乐曲
    jp_is_plate_required: M[bool] = col(default=True)
    # CN 服务器对应版本获取牌子时是否需要该乐曲
    cn_is_plate_required: M[bool] = col(default=True)

    # [Cache] Telegram 文件 ID 缓存（ADX 格式）
    _tg_adx_id_cache: M[Optional[str]] = col(default=None, nullable=True)
    # [Cache] Telegram 文件 ID 缓存（ZIP 格式）
    _tg_zip_id_cache: M[Optional[str]] = col(default=None, nullable=True)

    charts: M[list["MaiChart"]] = relationship(
        back_populates="maidata",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    aliases: M[list["MaiAlias"]] = relationship(back_populates="maidata", lazy="selectin")

    @classmethod
    def from_utils(cls, maidata: utils.MaiData | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiData":
        source: object | Mapping[str, Any] = kwargs or maidata or {}
        zip_path = _get(source, "zip_path")
        img_path = _get(source, "img_path")
        mdt = cls(
            shortid=_get(source, "shortid"),
            title=_get(source, "title"),
            bpm=_get(source, "bpm"),
            artist=_get(source, "artist") or "",
            genre=_get(source, "genre"),
            cabinet=_get(source, "cabinet"),
            version_jp=_get(source, "version"),
            version_cn=_get(source, "version_cn"),
            jp_is_plate_required=bool(_get(source, "jp_is_plate_required", True)),
            cn_is_plate_required=bool(_get(source, "cn_is_plate_required", True)),
            provider=_get(source, "converter") or "unknown",
            img_path=str(img_path) if img_path else "",
            zip_path=str(zip_path) if zip_path else "",
            _tg_adx_id_cache=_get(source, "tg_file_id_cache"),
            is_utage=_get(source, "is_utage", False),
            utage_tag=_get(source, "utage_tag", ""),
            buddy=_get(source, "buddy", False),
        )
        charts = _get(source, "charts", {})
        if isinstance(charts, Mapping):
            charts = charts.values()
        for chart in charts or []:
            mdt.charts.append(MaiChart.from_utils(chart, shortid=mdt.shortid))

        for alias in _get(source, "aliases", []) or []:
            mdt.aliases.append(MaiAlias.from_utils(alias))

        return mdt

    def get_charts(self) -> list["MaiChart"]:
        self.charts.sort(key=lambda c: c.difficulty)
        return self.charts

    def to_utils(self, achs_user_id: Optional[int] = None) -> utils.MaiData:
        zip_path = Path(self.zip_path) if self.zip_path else None
        if zip_path is not None and not zip_path.is_absolute():
            zip_path = get_plugin_data_dir() / zip_path

        maidata = utils.MaiData(
            shortid=self.shortid,
            title=self.title,
            bpm=self.bpm,
            artist=self.artist or "",
            genre=self.genre,
            cabinet=self.cabinet,
            version=self.version_jp,
            version_cn=self.version_cn,
            jp_is_plate_required=self.jp_is_plate_required,
            cn_is_plate_required=self.cn_is_plate_required,
            converter=self.provider or "",
            img_path=(zip_path / "bg.png") if zip_path else Path("bg.png"),
            zip_path=zip_path,
            tg_file_id_cache=self._tg_adx_id_cache,
            is_utage=self.is_utage,
            utage_tag=self.utage_tag if self.is_utage and isinstance(self.utage_tag, str) else "",
            buddy=bool(self.buddy and self.is_utage),
            aliases=[alias.to_utils() for alias in self.aliases],
        )
        for chart in self.charts:
            maidata.set_chart(chart.to_utils(qq=achs_user_id))
        return maidata


class MaiUser(Model):
    """maimai 用户数据"""

    __tablename__ = "maib_maiusers"

    qq: M[int] = col(BigInteger, primary_key=True)
    tg: M[Optional[int]] = col(
        BigInteger,
        default=None,
        nullable=True,
        index=True,
        unique=True,
    )
    # 用户昵称
    username: M[str] = col(String, default="")
    # 默认服务器
    default_server: M[Server] = col(String(4), default=Server.CN)
    # 当前装备牌子的版本，None 为未装备，同时需要 code
    plate_version: M[Optional[int]] = col(default=None, nullable=True)
    # 当前装备牌子的等级代码，None 为未装备，同时需要 version
    plate_code: M[Optional[int]] = col(default=None, nullable=True)

    # JP 服务器当前版本及 DXRating 数据统计
    jp_current_version: M[int] = col(default=0)
    jp_update_at: M[datetime] = col(DateTime(timezone=True),
                                         default=lambda: DEFAULT_DATETIME)
    jp_dxra_total: M[int] = col(default=0)
    jp_dxra_b35_total: M[int] = col(default=0)
    jp_dxra_b35_max: M[int] = col(default=0)
    jp_dxra_b35_min: M[int] = col(default=0)
    jp_dxra_b15_total: M[int] = col(default=0)
    jp_dxra_b15_max: M[int] = col(default=0)
    jp_dxra_b15_min: M[int] = col(default=0)
    # CN 服务器当前版本及 DXRating 数据统计
    cn_current_version: M[int] = col(default=0)
    cn_update_at: M[datetime] = col(DateTime(timezone=True),
                                         default=lambda: DEFAULT_DATETIME)
    cn_dxra_total: M[int] = col(default=0)
    cn_dxra_b35_total: M[int] = col(default=0)
    cn_dxra_b35_max: M[int] = col(default=0)
    cn_dxra_b35_min: M[int] = col(default=0)
    cn_dxra_b15_total: M[int] = col(default=0)
    cn_dxra_b15_max: M[int] = col(default=0)
    cn_dxra_b15_min: M[int] = col(default=0)

    # 水鱼 sub ID
    diving_fish_sub: M[Optional[int]] = col(Integer, default=None, nullable=True)
    # [Cache] 水鱼查分器游玩成绩数据 hash 缓存值
    _diving_fish_records_hash_cache: M[Optional[str]] = col(String, default=None, nullable=True)

    @validates("jp_update_at", "cn_update_at")
    def _validate(self, _key: str, value: D_T) -> datetime: return _as_datetime(value, default=DEFAULT_DATETIME)

    @property
    def plate(self) -> tuple[int | None, int | None]:
        return self.plate_version, self.plate_code

    @classmethod
    def from_utils(cls, user: utils.MaiUser | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiUser":
        def _dxra_from_source(source: object | Mapping[str, Any], prefix: Server) -> utils.DXRatingData:
            """从 source 中获取 DXRatingData 数据"""
            key_prefix = prefix.lower()
            data = _get(source, f"{key_prefix}_dxra_data")
            if data is not None:
                return data
            return utils.DXRatingData(
                total=_get(source, f"{key_prefix}_dxra_total", 0),
                b35_total=_get(source, f"{key_prefix}_dxra_b35_total", 0),
                b35_max=_get(source, f"{key_prefix}_dxra_b35_max", 0),
                b35_min=_get(source, f"{key_prefix}_dxra_b35_min", 0),
                b15_total=_get(source, f"{key_prefix}_dxra_b15_total", 0),
                b15_max=_get(source, f"{key_prefix}_dxra_b15_max", 0),
                b15_min=_get(source, f"{key_prefix}_dxra_b15_min", 0),
            )

        source: object | Mapping[str, Any] = kwargs or user or {}
        jp_data = _dxra_from_source(source, Server.JP)
        cn_data = _dxra_from_source(source, Server.CN)
        plate = _get(source, "plate", (None, None)) or (None, None)

        return cls(
            qq=_get(source, "user_id"),
            tg=_get(source, "user_telegram_id"),
            username=_get(source, "username", ""),
            default_server=_get(source, "default_server", "CN"),
            plate_version=plate[0],
            plate_code=plate[1],
            jp_current_version=_get(source, "jp_current_version", 0),
            jp_update_at=_as_datetime(_get(source, "jp_update_time"), default=DEFAULT_DATETIME),
            jp_dxra_total=jp_data.total,
            jp_dxra_b35_total=jp_data.b35.total,
            jp_dxra_b35_max=jp_data.b35.max,
            jp_dxra_b35_min=jp_data.b35.min,
            jp_dxra_b15_total=jp_data.b15.total,
            jp_dxra_b15_max=jp_data.b15.max,
            jp_dxra_b15_min=jp_data.b15.min,
            cn_current_version=_get(source, "cn_current_version", 0),
            cn_update_at=_as_datetime(_get(source, "cn_update_time"), default=DEFAULT_DATETIME),
            cn_dxra_total=cn_data.total,
            cn_dxra_b35_total=cn_data.b35.total,
            cn_dxra_b35_max=cn_data.b35.max,
            cn_dxra_b35_min=cn_data.b35.min,
            cn_dxra_b15_total=cn_data.b15.total,
            cn_dxra_b15_max=cn_data.b15.max,
            cn_dxra_b15_min=cn_data.b15.min,
            _diving_fish_records_hash_cache=_get(source, "last_sy_hash"),
        )

    def to_utils(self) -> utils.MaiUser:
        return utils.MaiUser(
            user_id=self.qq,
            user_telegram_id=self.tg,
            username=self.username,
            default_server=self.default_server,
            plate=self.plate,
            jp_current_version=self.jp_current_version,
            jp_update_time=self.jp_update_at,
            jp_dxra_data=utils.DXRatingData(
                total=self.jp_dxra_total,
                b35_total=self.jp_dxra_b35_total,
                b35_max=self.jp_dxra_b35_max,
                b35_min=self.jp_dxra_b35_min,
                b15_total=self.jp_dxra_b15_total,
                b15_max=self.jp_dxra_b15_max,
                b15_min=self.jp_dxra_b15_min,
            ),
            cn_current_version=self.cn_current_version,
            cn_update_time=self.cn_update_at,
            cn_dxra_data=utils.DXRatingData(
                total=self.cn_dxra_total,
                b35_total=self.cn_dxra_b35_total,
                b35_max=self.cn_dxra_b35_max,
                b35_min=self.cn_dxra_b35_min,
                b15_total=self.cn_dxra_b15_total,
                b15_max=self.cn_dxra_b15_max,
                b15_min=self.cn_dxra_b15_min,
            ),
        )


class MaiSync(Model):
    """maisync 模型"""

    __tablename__ = "maib_maisync"

    # 配对 ID
    id: M[int] = col(Integer, primary_key=True, autoincrement=True)

    qq: M[int] = col(BigInteger, index=True, unique=True)

    # 临时校验码
    pairing_code: M[str] = col(String(64), index=True, unique=True)
    # 临时校验码创建时间
    pairing_created_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)
    # 临时校验码过期时间
    pairing_expires_at: M[datetime] = col(DateTime(timezone=True))
    # 临时校验码使用时间
    pairing_used_at: M[Optional[datetime]] = col(DateTime(timezone=True), default=None, nullable=True)

    # 长时配对码
    token: M[str] = col(String(64), index=True, unique=True)
    # 长时配对码创建时间
    token_created_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)
    # 长时配对码设备 ID
    device_id: M[str] = col(String(64), default="")
    # 长时配对码设备名称
    device_name: M[str] = col(String(128), default="")
    # 长时配对码上次使用时间
    token_last_used_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)
    # 长时配对码有效性
    token_revoked: M[bool] = col(Boolean, default=False)

    # 属性赋值验证
    @validates("pairing_created_at", "pairing_expires_at", "pairing_used_at",
               "token_created_at", "token_last_used_at")
    def _validate(self, _key: str, value: D_T) -> Optional[datetime]:
        if value is None:
            return None
        return _as_datetime(value)


class MaiLxns(Model):
    """落雪授权信息模型"""

    __tablename__ = "maib_mailxns"

    qq: M[int] = col(BigInteger, primary_key=True)

    # 落雪 refresh_token (hashed)
    refresh_token: M[str] = col(String(512), nullable=False)
    # 过期时间（30 天滚动，每次刷新更新）
    refresh_expires_at: M[datetime] = col(DateTime(timezone=True), nullable=False)
    # 授权范围（如 "read_user_profile read_player"）
    refresh_scope: M[str] = col(String(255), nullable=False, default="")
    # 授权有效性
    refresh_is_active: M[bool] = col(Boolean, nullable=False, default=True)
    # 创建时间
    refresh_created_at: M[datetime] = col(DateTime(timezone=True), nullable=False, default=datetime.now)
    # 更新时间
    refresh_updated_at: M[datetime] = col(DateTime(timezone=True), nullable=False, default=datetime.now)

    @validates("refresh_expires_at", "refresh_created_at", "refresh_updated_at")
    def _validate(self, _key: str, value: D_T) -> datetime: return _as_datetime(value, default=DEFAULT_DATETIME)


class MaiRecord(Model):
    """maimai 成绩记录数据"""

    __tablename__ = "maib_mairecords"

    id: M[int] = col(primary_key=True, autoincrement=True)
    user_id: M[int] = col(BigInteger, index=True)

    record_hash: M[str] = col(String(64), index=True, unique=True)
    shortid: M[Optional[int]] = col(Integer, index=True, nullable=True)  # 可能会导入当前不存在的曲目 shortid，进行兼容操作
    title: M[str] = col(String(256), default="")
    cabinet: M[Literal["SD", "DX"]] = col(String(2), default="SD")
    type: M[Literal["history", "best"]] = col(String(16), default="history")
    difficulty: M[int] = col(Integer)
    server: M[Server] = col(String(4))
    achievement: M[float] = col(Float, default=0.0)
    dxscore: M[int] = col(Integer, default=0)
    combo: M[int] = col(Integer, default=0)
    sync: M[int] = col(Integer, default=0)
    play_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)
    update_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    @validates("play_at", "update_at")
    def _validate(self, _key: str, value: D_T) -> datetime: return _as_datetime(value)


class Maime(Model):
    """maimai aime 绑定数据"""

    __tablename__ = "maib_maimes"

    access: M[str] = col(String(20), primary_key=True, comment="Aime卡号")
    user_id: M[Optional[int]] = col(BigInteger, index=True, comment="用户id")
    access4: M[str] = col(String(4), index=True, comment="Aime卡号后四位缓存")
    create_at: M[datetime] = col(DateTime(timezone=True), default=datetime.now)


class MaiIDMap(Model):
    """ID 映射检查表，用于临时记录 shortid 的重映射。"""

    __tablename__ = "maib_idchecks"

    original_id: M[int] = col(primary_key=True)
    mapped_id: M[Optional[int]] = col(default=None, nullable=True, index=True)
