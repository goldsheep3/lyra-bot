import time
from typing import Literal
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from nonebot_plugin_datastore import get_plugin_data

Model = get_plugin_data().Model

class EatableItem(Model):
    """餐点项模型"""
    __tablename__ = "whatfood_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)  # 某种物品一定是吃的或喝的，不能兼是
    category: Mapped[Literal['Food', 'Drink']] = mapped_column()
    is_wine: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    create_time: Mapped[int] = mapped_column(default=lambda: int(time.time()))
    create_qq: Mapped[int] = mapped_column()

    current_score: Mapped[float] = mapped_column(default=3.0)  # 当前平均分，冗余字段，方便查询
    total_weighted_sum: Mapped[int] = mapped_column(default=0)  # 计算权重的评分总和
    total_weight: Mapped[int] = mapped_column(default=0)  # 权重总和

    # 关联评分
    scores: Mapped[list["ScoreRecord"]] = relationship(back_populates="item", cascade="all, delete-orphan")

class ScoreRecord(Model):
    """评分记录模型"""
    __tablename__ = "whatfood_score"
    __table_args__ = (UniqueConstraint('item_id', 'user_id'),)  # 每人每项只能有一条评分记录

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("whatfood_item.id"))
    user_id: Mapped[int] = mapped_column()  # AI 设为 -200
    score: Mapped[int] = mapped_column()    # 1-5
    weight: Mapped[int] = mapped_column(default=1) # AI/SU 权重设为 30
    reason: Mapped[str | None] = mapped_column(default=None, nullable=True)  # AI 可返回理由
    create_time: Mapped[int] = mapped_column(default=lambda: int(time.time()))
    update_time: Mapped[int] = mapped_column(default=lambda: int(time.time()), onupdate=lambda: int(time.time()))

    item: Mapped["EatableItem"] = relationship(back_populates="scores")

class UserPreference(Model):
    """用户偏好模型"""
    __tablename__ = "whatfood_user_pref"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    offset: Mapped[float] = mapped_column(default=3.0)  # 目标分数，默认为3.0
