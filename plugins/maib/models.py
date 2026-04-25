import time
from pathlib import Path
from typing import Literal, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import utils
from .constants import SERVER_TAG
from .bot_registry import PluginRegistry

Model = PluginRegistry.get_model()


class MaiAlias(Model):
    """MaiData 曲目别名数据"""
    __tablename__ = "maib_maialiases"
    __table_args__ = (UniqueConstraint("shortid", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"), index=True)
    alias: Mapped[str] = mapped_column(index=True)

    create_time: Mapped[int] = mapped_column(default=lambda: int(time.time()))
    create_qq: Mapped[int] = mapped_column()
    create_qq_group: Mapped[Optional[int]] = mapped_column()

    # 关系映射
    maidata: Mapped["MaiData"] = relationship(back_populates="aliases", lazy="selectin")  # 不进行级联删除以避免在重建时丢失别名数据

    def to_data(self) -> utils.MaiAlias:
        """转换为 utils.MaiAlias 对象"""
        return utils.MaiAlias(
            shortid=self.shortid,
            alias=self.alias,
            create_qq=self.create_qq,
            create_qq_group=self.create_qq_group,
            create_time=self.create_time
        )


class MaiChartAch(Model):
    """MaiChartAch 成绩数据"""
    __tablename__ = "maib_maichartachs"
    __table_args__ = (UniqueConstraint("user_id", "shortid", "difficulty", "server"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="RESTRICT"))
    chart_id: Mapped[int] = mapped_column(ForeignKey("maib_maicharts.id", ondelete="CASCADE"))

    difficulty: Mapped[int]
    server: Mapped[Literal["JP", "CN"]]  # 服务器标识
    achievement: Mapped[float]  # 成就率
    dxscore: Mapped[int] = mapped_column(default=0)  # DX 分数
    combo: Mapped[int] = mapped_column(default=0)  # 连击
    sync: Mapped[int] = mapped_column(default=0)  # 同步游玩
    update_time: Mapped[int] = mapped_column(default=lambda: int(time.time()), onupdate=lambda: int(time.time()))  # 更新时间戳
    dxrating: Mapped[int] = mapped_column(default=0)  # DX Rating (Cache)

    user_id: Mapped[Optional[int]] = mapped_column()  # qq

    chart: Mapped["MaiChart"] = relationship(back_populates="achs", lazy="selectin")

    def update(self, other: 'MaiChartAch | utils.MaiChartAch'):
        """更新成绩"""
        if self.achievement < other.achievement:
            self.achievement = other.achievement
        if self.dxscore < other.dxscore:
            self.dxscore = other.dxscore
        if self.combo < other.combo:
            self.combo = other.combo
        if self.sync < other.sync:
            self.sync = other.sync
        self.update_time = int(time.time())

    def to_data(self) -> utils.MaiChartAch:
        """转换为 utils.MaiChartAch 对象"""
        return utils.MaiChartAch(
            shortid=self.shortid,
            difficulty=self.difficulty,
            server=self.server,
            achievement=self.achievement,
            dxscore=self.dxscore,
            combo=self.combo,
            sync=self.sync,
            update_time=self.update_time
        )


class MaiChart(Model):
    """MaiChart 谱面数据"""
    __tablename__ = "maib_maicharts"
    __table_args__ = (UniqueConstraint("shortid", "difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maib_maidatas.shortid", ondelete="CASCADE"))
    difficulty: Mapped[int]  # 通常为 2~7
    lv: Mapped[float] = mapped_column(index=True)
    lv_cn: Mapped[Optional[float]] = mapped_column(index=True)
    lv_synh: Mapped[Optional[float]] = mapped_column(index=True)  # 水鱼拟合定数
    des: Mapped[str]
    inote: Mapped[str]

    # Note 统计数据
    note_count_tap: Mapped[int]
    note_count_hold: Mapped[int]
    note_count_slide: Mapped[int]
    note_count_touch: Mapped[int]
    note_count_break: Mapped[int]

    maidata: Mapped["MaiData"] = relationship(back_populates="charts", lazy="selectin")
    achs: Mapped[list["MaiChartAch"]] = relationship(back_populates="chart", cascade="all, delete-orphan", lazy="selectin")

    def to_data(self, include_achs: bool = False) -> utils.MaiChart:
        """转换为 utils.MaiChart 对象"""
        maichart = utils.MaiChart(
            shortid=self.shortid,
            difficulty=self.difficulty,
            lv=self.lv,
            lv_cn=self.lv_cn,
            lv_synh=self.lv_synh,
            des=self.des,
            inote=self.inote,
            note_count_tap=self.note_count_tap,
            note_count_hold=self.note_count_hold,
            note_count_slide=self.note_count_slide,
            note_count_touch=self.note_count_touch,
            note_count_break=self.note_count_break
        )
        if include_achs:
            for ach in self.achs:
                maichart.set_ach(ach.to_data())
        return maichart


class MaiData(Model):
    """MaiData 曲目数据"""
    __tablename__ = "maib_maidatas"

    shortid: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(index=True)
    bpm: Mapped[int]
    artist: Mapped[Optional[str]]
    genre: Mapped[int]  # 重点重构
    cabinet: Mapped[Literal["SD", "DX"]]

    # 版本信息
    version: Mapped[int]
    version_cn: Mapped[Optional[int]]

    # 文件与来源
    converter: Mapped[Optional[str]]
    zip_path: Mapped[str]

    # Utage 特有字段 (常规曲目设为 None)
    is_utage: Mapped[bool] = mapped_column(default=False, index=True)  
    utage_tag: Mapped[str] = mapped_column(default='')
    buddy: Mapped[bool] = mapped_column(default=False)

    # 关系映射
    charts: Mapped[list["MaiChart"]] = relationship(back_populates="maidata", cascade="all, delete-orphan", lazy="selectin")
    aliases: Mapped[list["MaiAlias"]] = relationship(back_populates="maidata", lazy="selectin")

    def get_charts(self):
        self.charts.sort(key=lambda c: c.difficulty)
        return self.charts

    def to_data(self, include_achs: bool = False) -> utils.MaiData:
        """转换为 utils.MaiData 对象"""
        maidata = utils.MaiData(
            shortid=self.shortid,
            title=self.title,
            bpm=self.bpm,
            artist=self.artist if self.artist else '',
            genre=self.genre,
            cabinet=self.cabinet,
            version=self.version,
            version_cn=self.version_cn,
            converter=self.converter if self.converter else '',
            img_path=Path(self.zip_path) / "bg.png",
            zip_path=Path(self.zip_path) if self.zip_path else None,
            aliases=[alias.to_data() for alias in self.aliases],
            is_utage=self.is_utage,
            buddy=all((self.buddy, self.is_utage)),
            utage_tag=self.utage_tag if self.is_utage and isinstance(self.utage_tag, str) else '',
        )
        # 添加谱面数据
        for chart in self.charts:
            maidata.set_chart(chart.to_data(include_achs=include_achs))
        # 添加别名数据
        maidata.add_aliases([a.to_data() for a in self.aliases])
        return maidata


class MaiUser(Model):
    __tablename__ = "maib_maiusers"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(default='')
    default_server: Mapped[SERVER_TAG] = mapped_column(default='CN')
    plate_version: Mapped[int | None] = mapped_column(default=None)  # 牌子信息
    plate_code: Mapped[int | None] = mapped_column(default=None)

    jp_update_time: Mapped[int] = mapped_column(default=0)
    jp_dxrating: Mapped[int] = mapped_column(default=0)
    cn_update_time: Mapped[int] = mapped_column(default=0)
    cn_dxrating: Mapped[int] = mapped_column(default=0)

    # lyra-sync 字段: 在 sync_allow_time 有效期内，可以使用 sync-hash 验证身份并同步成绩
    sync_hash: Mapped[Optional[str]] = mapped_column(default=None)
    sync_allow_time: Mapped[Optional[int]] = mapped_column(default=None)

    def plate(self) -> tuple[int, int] | None:
        """返回牌子信息"""
        if self.plate_version is not None and self.plate_code is not None:
            return self.plate_version, self.plate_code
        return None

    def to_data(self):
        """转换为 utils.MaiUser 对象"""
        # lyra-sync 相关字段不包含在 utils.MaiUser
        return utils.MaiUser(
            user_id=self.user_id,
            username=self.username,
            default_server=self.default_server,
            plate=self.plate(),
            jp_update_time=self.jp_update_time,
            jp_dxrating=self.jp_dxrating,
            cn_update_time=self.cn_update_time,
            cn_dxrating=self.cn_dxrating
        )


# ====== 工厂函数 ======

class MaiDataModel:
    """模型工厂类，提供获取模型的接口"""

    @staticmethod
    def mdt(maidata: utils.MaiData):
        """根据 utils.MaiData 对象创建 MaiData 模型实例"""
        mdt = MaiData(
            shortid=maidata.shortid,
            title=maidata.title,
            bpm=maidata.bpm,
            artist=maidata.artist,
            genre=maidata.genre,
            cabinet=maidata.cabinet,
            version=maidata.version,
            version_cn=maidata.version_cn,
            converter=maidata.converter,
            zip_path=str(maidata.zip_path) if maidata.zip_path else None,
            is_utage=maidata.is_utage,
            utage_tag=maidata.utage_tag,
            buddy=maidata.buddy
        )
        # 添加谱面数据
        for chart in maidata.charts.values():
            mdt.charts.append(MaiDataModel.mct(chart, maidata.shortid))
        # 添加别名数据
        for alias in maidata.aliases:
            mdt.aliases.append(MaiDataModel.mal(alias))
        return mdt

    @staticmethod
    def mct(chart: utils.MaiChart, shortid: int):
        """根据 utils.MaiChart 对象创建 MaiChart 模型实例"""
        return MaiChart(
            shortid=shortid,
            difficulty=chart.difficulty,
            lv=chart.lv,
            lv_cn=chart.lv_cn,
            lv_synh=chart.lv_synh,
            des=chart.des,
            inote=chart.inote,
            note_count_tap=chart.note_count_tap,
            note_count_hold=chart.note_count_hold,
            note_count_slide=chart.note_count_slide,
            note_count_touch=chart.note_count_touch,
            note_count_break=chart.note_count_break
        )

    @staticmethod
    def mct_ach(ach: utils.MaiChartAch):
        """根据 utils.MaiChartAch 对象创建 MaiChartAch 模型实例"""
        return MaiChartAch(
            shortid=ach.shortid,
            difficulty=ach.difficulty,
            server=ach.server,
            achievement=ach.achievement,
            dxscore=ach.dxscore,
            combo=ach.combo,
            sync=ach.sync,
            update_time=ach.update_time
        )

    @staticmethod
    def mal(alias: utils.MaiAlias):
        """根据 utils.MaiAlias 对象创建 MaiAlias 模型实例"""
        return MaiAlias(
            shortid=alias.shortid,
            alias=alias.alias,
            create_qq=alias.create_qq,
            create_qq_group=alias.create_qq_group,
            create_time=alias.create_time
        )

    @staticmethod
    def mu(user: utils.MaiUser):
        """根据 utils.MaiUser 对象创建 MaiUser 模型实例"""
        return MaiUser(
            user_id=user.user_id,
            username=user.username,
            default_server=user.default_server,
            plate_version=user.plate[0] if user.plate else None,
            plate_code=user.plate[1] if user.plate else None,
            jp_update_time=user.jp_update_time,
            jp_dxrating=user.jp_dxrating,
            cn_update_time=user.cn_update_time,
            cn_dxrating=user.cn_dxrating
        )
