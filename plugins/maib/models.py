from pathlib import Path
from typing import List, Optional
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    # 尝试获取 driver 以确认是否为 NoneBot
    import nonebot
    nonebot.get_driver()
    from nonebot_plugin_datastore import get_plugin_data
    plugin_data = get_plugin_data()
    Model = plugin_data.Model
except (ImportError, ValueError):
    plugin_data = None

    class Model(DeclarativeBase):
        pass

from . import utils


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

    def get_charts(self):
        self.charts.sort(key=lambda c: c.difficulty)
        return self.charts

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
            img_path=Path(self.zip_path) / "bg.png",
            aliases=[alias.to_data() for alias in self.aliases],
            is_utage=self.is_utage,
            buddy=self.buddy if self.is_utage else False,
            utage_tag=self.utage_tag if self.is_utage else None,
        )
        # 添加谱面数据
        for chart in self.charts:
            maidata.set_chart(chart.to_data())
        # 添加别名数据
        maidata.add_aliases([a.to_data() for a in self.aliases])
        return maidata


class MaiChart(Model):
    """MaiChart 谱面数据"""
    __tablename__ = "charts"
    __table_args__ = (UniqueConstraint("shortid", "difficulty"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shortid: Mapped[int] = mapped_column(ForeignKey("maidata.shortid", ondelete="CASCADE"))
    difficulty: Mapped[int]  # 通常为 2~7
    lv: Mapped[float] = mapped_column(index=True)
    des: Mapped[str]

    # Note 统计数据
    note_count_tap: Mapped[int]
    note_count_hold: Mapped[int]
    note_count_slide: Mapped[int]
    note_count_touch: Mapped[int]
    note_count_break: Mapped[int]

    inote: Mapped[str]

    maidata: Mapped["MaiData"] = relationship(back_populates="charts")

    def to_data(self) -> utils.MaiChart:
        """转换为 utils.MaiChart 对象"""
        return utils.MaiChart(
            shortid=self.shortid,
            difficulty=self.difficulty,
            lv=self.lv,
            des=self.des,
            notes=(
                self.note_count_tap,
                self.note_count_hold,
                self.note_count_slide,
                self.note_count_touch,
                self.note_count_break
            ),
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

    def to_data(self):
        """转换为 utils.MaiAlias 对象"""
        return utils.MaiAlias(
            shortid=self.shortid,
            alias=self.alias,
            create_qq=self.create_qq,
            create_qq_group=self.create_qq_group,
            create_time=self.create_time
        )


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
            des=chart.des,
            inote=chart.inote,
            note_count_tap=chart.notes[0],
            note_count_hold=chart.notes[1],
            note_count_slide=chart.notes[2],
            note_count_touch=chart.notes[3],
            note_count_break=chart.notes[4]
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
