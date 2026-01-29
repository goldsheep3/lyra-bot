from typing import List, Optional
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nonebot_plugin_datastore import get_plugin_data

from . import utils

plugin_data = get_plugin_data()
Model = plugin_data.Model


class MaiData(Model):
    """MaiData 曲目数据"""
    __tablename__ = "maidata"

    shortid: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(index=True)
    bpm: Mapped[int]
    artist: Mapped[Optional[str]]
    genre: Mapped[str]
    cabinet: Mapped[str]

    # 版本信息
    version: Mapped[int]
    version_cn: Mapped[Optional[int]]

    # 文件与来源
    converter: Mapped[Optional[str]]
    zip_path: Mapped[Optional[str]]

    # Utage 特有字段 (常规曲目设为 None)
    is_utage: Mapped[bool] = mapped_column(default=False, index=True)  # Utage 区分标志
    utage_tag: Mapped[Optional[str]]
    buddy: Mapped[Optional[bool]]

    # 关系映射
    charts: Mapped[List["MaiChart"]] = relationship(back_populates="maidata", cascade="all, delete-orphan")
    aliases: Mapped[List["MaiAlias"]] = relationship(back_populates="maidata")

    def to_data(self) -> utils.MaiData:
        """转换为 utils.MaiData 对象"""
        maidata = utils.MaiData(
            shortid=self.shortid,
            title=self.title,
            bpm=self.bpm,
            artist=self.artist,
            genre=self.genre,
            cabinet=self.cabinet,
            version=self.version,
            version_cn=self.version_cn,
            converter=self.converter,
            img_path=plugin_data.data_dir / "bg.png",
            aliases=[a.alias for a in self.aliases],
            utage=self.is_utage,
            buddy=self.buddy if self.is_utage else False,
            utage_tag=self.utage_tag if self.is_utage else None,
        )
        # 添加谱面数据
        for chart in self.charts:
            maidata.set_chart(chart.to_data())
        return maidata


class MaiChart(Model):
    """MaiChart 谱面数据"""
    __tablename__ = "charts"
    __table_args__ = (UniqueConstraint("shortid", "chart_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maidata.shortid", ondelete="CASCADE"))
    chart_number: Mapped[int]
    lv: Mapped[float] = mapped_column(index=True)
    des: Mapped[str]
    inote: Mapped[str]

    maidata: Mapped["MaiData"] = relationship(back_populates="charts")

    def to_data(self) -> utils.MaiChart:
        """转换为 utils.MaiChart 对象"""
        return utils.MaiChart(
            difficulty=self.chart_number,
            lv=self.lv,
            des=self.des,
            inote=self.inote
        )


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
