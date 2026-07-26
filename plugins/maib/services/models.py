"""services/models.py 数据库模型定义"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from nonebot_plugin_datastore import get_plugin_data
from nonebot_plugin_localstore import get_plugin_data_dir
from sqlalchemy import String, Integer, Float, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from .. import utils
from ..constants import DEFAULT_DATETIME, server


__all__ = [
    "MaiAlias",
    "MaiChartAch",
    "MaiChart",
    "MaiData",
    "MaiUser",
    "MaiIDMap",
]

Model = get_plugin_data().Model


def _as_datetime(value: datetime | int | float | None, *, default: datetime | None = None) -> datetime:
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
    if source is None:
        return default
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _dxra_from_source(source: object | Mapping[str, Any], prefix: server) -> utils.DXRatingData:
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


class MaiAlias(Model):
    """MaiData 曲目别名数据"""

    __tablename__ = "maib_maialiases"
    __table_args__ = (UniqueConstraint("shortid", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"), index=True)
    alias: Mapped[str] = mapped_column(index=True)

    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    create_qq: Mapped[int] = mapped_column(BigInteger)
    create_qq_group: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    maidata: Mapped["MaiData"] = relationship(back_populates="aliases", lazy="selectin")

    @validates("create_time")
    def _validate_create_time(self, _key: str, value: datetime | int | float | None) -> datetime:
        return _as_datetime(value)

    @classmethod
    def from_utils(cls, alias: utils.MaiAlias | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiAlias":
        source: object | Mapping[str, Any] = kwargs or alias or {}
        return cls(
            shortid=_get(source, "shortid"),
            alias=_get(source, "alias"),
            create_time=_as_datetime(_get(source, "create_time"), default=datetime.now()),
            create_qq=_get(source, "create_qq"),
            create_qq_group=_get(source, "create_qq_group"),
        )

    def to_utils(self) -> utils.MaiAlias:
        return utils.MaiAlias(
            shortid=self.shortid,
            alias=self.alias,
            create_time=self.create_time,
            create_qq=self.create_qq,
            create_qq_group=self.create_qq_group,
        )


class MaiChartAch(Model):
    """MaiChartAch 成绩数据"""

    __tablename__ = "maib_maichartachs"
    __table_args__ = (UniqueConstraint("user_id", "shortid", "difficulty", "server"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"))
    chart_id: Mapped[int] = mapped_column(ForeignKey("maib_maicharts.id", ondelete="CASCADE"))

    difficulty: Mapped[int]
    server: Mapped[server]
    achievement: Mapped[float]
    dxscore: Mapped[int] = mapped_column(default=0)
    combo: Mapped[int] = mapped_column(default=0)
    sync: Mapped[int] = mapped_column(default=0)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)
    dxrating: Mapped[int] = mapped_column(default=0)

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    chart: Mapped["MaiChart"] = relationship(back_populates="achs", lazy="selectin")

    @validates("update_time")
    def _validate_update_time(self, _key: str, value: datetime | int | float | None) -> datetime:
        return _as_datetime(value)

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
            achievement=_get(ach, "achievement"),
            dxscore=_get(ach, "dxscore", 0),
            combo=_get(ach, "combo", 0),
            sync=_get(ach, "sync", 0),
            update_time=_as_datetime(_get(ach, "update_time"), default=datetime.now()),
            dxrating=dxrating or 0,
            user_id=_get(ach, "user_id", -1),
        )

    def to_utils(self, dxscore_max: int | None = None) -> utils.MaiChartAch:
        if dxscore_max is None:
            dxscore_max = self.chart.dxscore_max if self.chart is not None else 0
        return utils.MaiChartAch(
            shortid=self.shortid,
            difficulty=self.difficulty,
            server=self.server,
            achievement=self.achievement,
            dxscore=self.dxscore,
            dxscore_max=dxscore_max,
            combo=self.combo,
            sync=self.sync,
            update_time=self.update_time,
            user_id=self.user_id if self.user_id is not None else -1,
        )

    def update(self, ach: utils.MaiChartAch) -> None:
        self.achievement = max(self.achievement, ach.achievement)
        self.dxscore = max(self.dxscore, ach.dxscore)
        self.combo = max(self.combo, ach.combo)
        self.sync = max(self.sync, ach.sync)
        self.update_time = datetime.now()


class MaiChart(Model):
    """MaiChart 谱面数据"""

    __tablename__ = "maib_maicharts"
    __table_args__ = (UniqueConstraint("shortid", "difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="CASCADE"))
    difficulty: Mapped[int]
    lv: Mapped[float] = mapped_column(index=True)
    lv_cn: Mapped[Optional[float]] = mapped_column(index=True, nullable=True)
    lv_synh: Mapped[Optional[float]] = mapped_column(index=True, nullable=True)
    des: Mapped[str] = mapped_column(default="")
    inote: Mapped[str] = mapped_column(default="")
    note_count_tap: Mapped[int] = mapped_column(default=0)
    note_count_hold: Mapped[int] = mapped_column(default=0)
    note_count_slide: Mapped[int] = mapped_column(default=0)
    note_count_touch: Mapped[int] = mapped_column(default=0)
    note_count_break: Mapped[int] = mapped_column(default=0)

    maidata: Mapped["MaiData"] = relationship(back_populates="charts", lazy="selectin")
    achs: Mapped[list["MaiChartAch"]] = relationship(
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
            lv=_get(source, "lv"),
            lv_cn=_get(source, "lv_cn"),
            lv_synh=_get(source, "lv_synh"),
            des=_get(source, "des", ""),
            inote=_get(source, "inote", ""),
            notes=notes,
        )

    def to_utils(self, achs_user_id: Optional[int] = None) -> utils.MaiChart:
        maichart = utils.MaiChart(
            shortid=self.shortid,
            difficulty=self.difficulty,
            lv=self.lv,
            lv_cn=self.lv_cn,
            lv_synh=self.lv_synh,
            des=self.des,
            inote=self.inote,
            notes=self.notes,
        )
        if achs_user_id is not None:
            for ach in self.achs:
                if ach.user_id == achs_user_id:
                    maichart.set_ach(ach.to_utils(dxscore_max=self.dxscore_max))
        return maichart


class MaiData(Model):
    """MaiData 曲目数据"""

    __tablename__ = "maib_maidatas"

    shortid: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(index=True)
    bpm: Mapped[int]
    artist: Mapped[Optional[str]] = mapped_column(nullable=True)
    genre: Mapped[int]
    cabinet: Mapped[Literal["SD", "DX"]]

    version: Mapped[int]
    version_cn: Mapped[Optional[int]] = mapped_column(nullable=True)
    jp_is_plate_required: Mapped[bool] = mapped_column(default=True)
    cn_is_plate_required: Mapped[bool] = mapped_column(default=True)

    converter: Mapped[Optional[str]] = mapped_column(nullable=True)
    zip_path: Mapped[str]
    tg_file_id_cache: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)

    is_utage: Mapped[bool] = mapped_column(default=False, index=True)
    utage_tag: Mapped[str] = mapped_column(default="")
    buddy: Mapped[bool] = mapped_column(default=False)

    charts: Mapped[list["MaiChart"]] = relationship(
        back_populates="maidata",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    aliases: Mapped[list["MaiAlias"]] = relationship(back_populates="maidata", lazy="selectin")

    @classmethod
    def from_utils(cls, maidata: utils.MaiData | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiData":
        source: object | Mapping[str, Any] = kwargs or maidata or {}
        zip_path = _get(source, "zip_path")
        mdt = cls(
            shortid=_get(source, "shortid"),
            title=_get(source, "title"),
            bpm=_get(source, "bpm"),
            artist=_get(source, "artist") or None,
            genre=_get(source, "genre"),
            cabinet=_get(source, "cabinet"),
            version=_get(source, "version"),
            version_cn=_get(source, "version_cn"),
            jp_is_plate_required=bool(_get(source, "jp_is_plate_required", True)),
            cn_is_plate_required=bool(_get(source, "cn_is_plate_required", True)),
            converter=_get(source, "converter") or None,
            zip_path=str(zip_path) if zip_path else "",
            tg_file_id_cache=_get(source, "tg_file_id_cache"),
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
            version=self.version,
            version_cn=self.version_cn,
            jp_is_plate_required=self.jp_is_plate_required,
            cn_is_plate_required=self.cn_is_plate_required,
            converter=self.converter or "",
            img_path=(zip_path / "bg.png") if zip_path else Path("bg.png"),
            zip_path=zip_path,
            tg_file_id_cache=self.tg_file_id_cache,
            is_utage=self.is_utage,
            utage_tag=self.utage_tag if self.is_utage and isinstance(self.utage_tag, str) else "",
            buddy=bool(self.buddy and self.is_utage),
            aliases=[alias.to_utils() for alias in self.aliases],
        )
        for chart in self.charts:
            maidata.set_chart(chart.to_utils(achs_user_id=achs_user_id))
        return maidata


class MaiUser(Model):
    """maimai 用户数据"""

    __tablename__ = "maib_maiusers"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=None,
        nullable=True,
        index=True,
        unique=True,
    )
    username: Mapped[str] = mapped_column(default="")
    default_server: Mapped[server] = mapped_column(default="CN")
    plate_version: Mapped[Optional[int]] = mapped_column(default=None, nullable=True)
    plate_code: Mapped[Optional[int]] = mapped_column(default=None, nullable=True)

    jp_current_version: Mapped[int] = mapped_column(default=0)
    jp_update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: DEFAULT_DATETIME)
    jp_dxra_total: Mapped[int] = mapped_column(default=0)
    jp_dxra_b35_total: Mapped[int] = mapped_column(default=0)
    jp_dxra_b35_max: Mapped[int] = mapped_column(default=0)
    jp_dxra_b35_min: Mapped[int] = mapped_column(default=0)
    jp_dxra_b15_total: Mapped[int] = mapped_column(default=0)
    jp_dxra_b15_max: Mapped[int] = mapped_column(default=0)
    jp_dxra_b15_min: Mapped[int] = mapped_column(default=0)

    cn_current_version: Mapped[int] = mapped_column(default=0)
    cn_update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: DEFAULT_DATETIME)
    cn_dxra_total: Mapped[int] = mapped_column(default=0)
    cn_dxra_b35_total: Mapped[int] = mapped_column(default=0)
    cn_dxra_b35_max: Mapped[int] = mapped_column(default=0)
    cn_dxra_b35_min: Mapped[int] = mapped_column(default=0)
    cn_dxra_b15_total: Mapped[int] = mapped_column(default=0)
    cn_dxra_b15_max: Mapped[int] = mapped_column(default=0)
    cn_dxra_b15_min: Mapped[int] = mapped_column(default=0)

    # lyra-sync 字段: 在可以使用 sync-hash 验证身份并同步成绩。
    maisync_hash: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)
    # Diving-Fish 字段: 通过水鱼获取到的数据的 hash 确认是否为最新数据，已经最新就直接跳过更新.
    last_sy_hash: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)

    @validates("jp_update_time", "cn_update_time")
    def _validate_update_time(self, _key: str, value: datetime | int | float | None) -> datetime:
        return _as_datetime(value, default=DEFAULT_DATETIME)

    @property
    def plate(self) -> tuple[int | None, int | None]:
        return self.plate_version, self.plate_code

    @classmethod
    def from_utils(cls, user: utils.MaiUser | Mapping[str, Any] | None = None, **kwargs: Any) -> "MaiUser":
        source: object | Mapping[str, Any] = kwargs or user or {}
        jp_data = _dxra_from_source(source, "JP")
        cn_data = _dxra_from_source(source, "CN")
        plate = _get(source, "plate", (None, None)) or (None, None)

        return cls(
            user_id=_get(source, "user_id"),
            user_telegram_id=_get(source, "user_telegram_id"),
            username=_get(source, "username", ""),
            default_server=_get(source, "default_server", "CN"),
            plate_version=plate[0],
            plate_code=plate[1],
            jp_current_version=_get(source, "jp_current_version", 0),
            jp_update_time=_as_datetime(_get(source, "jp_update_time"), default=DEFAULT_DATETIME),
            jp_dxra_total=jp_data.total,
            jp_dxra_b35_total=jp_data.b35.total,
            jp_dxra_b35_max=jp_data.b35.max,
            jp_dxra_b35_min=jp_data.b35.min,
            jp_dxra_b15_total=jp_data.b15.total,
            jp_dxra_b15_max=jp_data.b15.max,
            jp_dxra_b15_min=jp_data.b15.min,
            cn_current_version=_get(source, "cn_current_version", 0),
            cn_update_time=_as_datetime(_get(source, "cn_update_time"), default=DEFAULT_DATETIME),
            cn_dxra_total=cn_data.total,
            cn_dxra_b35_total=cn_data.b35.total,
            cn_dxra_b35_max=cn_data.b35.max,
            cn_dxra_b35_min=cn_data.b35.min,
            cn_dxra_b15_total=cn_data.b15.total,
            cn_dxra_b15_max=cn_data.b15.max,
            cn_dxra_b15_min=cn_data.b15.min,
            maisync_hash=_get(source, "maisync_hash"),
            last_sy_hash=_get(source, "last_sy_hash"),
        )

    def to_utils(self) -> utils.MaiUser:
        return utils.MaiUser(
            user_id=self.user_id,
            user_telegram_id=self.user_telegram_id,
            username=self.username,
            default_server=self.default_server,
            plate=self.plate,
            jp_current_version=self.jp_current_version,
            jp_update_time=self.jp_update_time,
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
            cn_update_time=self.cn_update_time,
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


class MaiRecord(Model):
    """maimai 成绩记录数据"""

    __tablename__ = "maib_mairecords"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    
    shortid: Mapped[int] = mapped_column(Integer, index=True, nullable=True)  # 可能会导入当前不存在的曲目 shortid，进行兼容操作
    title: Mapped[str] = mapped_column(String(256), default="")
    cabinet: Mapped[Literal["SD", "DX"]] = mapped_column(String(2), default="SD")
    difficulty: Mapped[int] = mapped_column(Integer)
    server: Mapped[server] = mapped_column(String(16))
    achievement: Mapped[float] = mapped_column(Float, default=0.0)
    dxscore: Mapped[int] = mapped_column(Integer, default=0)
    combo: Mapped[int] = mapped_column(Integer, default=0)
    sync: Mapped[int] = mapped_column(Integer, default=0)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    @validates("update_time")
    def _validate_update_time(self, _key: str, value: datetime | int | float | None) -> datetime:
        return _as_datetime(value)


class MaiIDMap(Model):
    """ID 映射检查表，用于临时记录 shortid 的重映射。"""

    __tablename__ = "maib_idchecks"

    original_id: Mapped[int] = mapped_column(primary_key=True)
    mapped_id: Mapped[Optional[int]] = mapped_column(default=None, nullable=True, index=True)
