from pathlib import Path
from typing import List, Literal, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import utils
from .bot_registry import PluginRegistry

Model = PluginRegistry.get_model()


class MaiAlias(Model):
    """MaiData 曲目别名数据"""
    __tablename__ = "aliases"
    __table_args__ = (UniqueConstraint("shortid", "alias"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maidata.shortid", ondelete="RESTRICT"), index=True)
    alias: Mapped[str] = mapped_column(index=True)

    create_time: Mapped[int] = mapped_column()
    create_qq: Mapped[int] = mapped_column()
    create_qq_group: Mapped[Optional[int]] = mapped_column()

    # 关系映射
    maidata: Mapped["MaiData"] = relationship(back_populates="aliases")  # 不进行级联删除以避免在重建时丢失别名数据

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
    __tablename__ = "chart_achs"
    __table_args__ = (UniqueConstraint("shortid", "difficulty", "server"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maidata.shortid", ondelete="RESTRICT"))
    difficulty: Mapped[int]
    server: Mapped[Literal["JP", "INTL", "CN"]]  # 服务器标识
    achievement: Mapped[float]  # 成就率
    dxscore: Mapped[int] = mapped_column(default=0)  # DX 分数
    combo: Mapped[int] = mapped_column(default=0)  # 连击
    sync: Mapped[int] = mapped_column(default=0)  # 同步游玩
    update_time: Mapped[int] = mapped_column()  # 更新时间戳

    chart: Mapped["MaiChart"] = relationship(back_populates="chart_achs")

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
    __tablename__ = "charts"
    __table_args__ = (UniqueConstraint("shortid", "difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maidata.shortid", ondelete="CASCADE"))
    difficulty: Mapped[int]  # 通常为 2~7
    lv: Mapped[float] = mapped_column(index=True)
    lv_cn: Mapped[Optional[float]] = mapped_column(index=True)  # 重点重构
    lv_synh: Mapped[Optional[float]] = mapped_column(index=True)  # 水鱼拟合定数
    des: Mapped[str]
    inote: Mapped[str]

    # Note 统计数据
    note_count_tap: Mapped[int]
    note_count_hold: Mapped[int]
    note_count_slide: Mapped[int]
    note_count_touch: Mapped[int]
    note_count_break: Mapped[int]

    maidata: Mapped["MaiData"] = relationship(back_populates="charts")
    achs: Mapped[List["MaiChartAch"]] = relationship(back_populates="charts")

    def to_data(self) -> utils.MaiChart:
        """转换为 utils.MaiChart 对象"""
        return utils.MaiChart(
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


class MaiData(Model):
    """MaiData 曲目数据"""
    __tablename__ = "maidata"

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
    charts: Mapped[List["MaiChart"]] = relationship(back_populates="maidata", cascade="all, delete-orphan")
    aliases: Mapped[List["MaiAlias"]] = relationship(back_populates="maidata")

    def get_charts(self):
        self.charts.sort(key=lambda c: c.difficulty)
        return self.charts

    def to_data(self) -> utils.MaiData:
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
            maidata.set_chart(chart.to_data())
        # 添加别名数据
        maidata.add_aliases([a.to_data() for a in self.aliases])
        return maidata


# ====== 工厂函数 ======

class MaiDataModelFactory:
    """模型工厂类，提供获取模型的接口"""

    @staticmethod
    def mai_data(maidata: utils.MaiData):
        """根据 utils.MaiData 对象创建 MaiData 模型实例"""
        return MaiData(
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
            utage_tag=maidata.utage_tag if maidata.is_utage else None,
            buddy=maidata.buddy if maidata.is_utage else None
        )

    @staticmethod
    def mai_chart(chart: utils.MaiChart, shortid: int):
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
    def mai_alias(alias: utils.MaiAlias):
        """根据 utils.MaiAlias 对象创建 MaiAlias 模型实例"""
        return MaiAlias(
            shortid=alias.shortid,
            alias=alias.alias,
            create_qq=alias.create_qq,
            create_qq_group=alias.create_qq_group,
            create_time=alias.create_time
        )
