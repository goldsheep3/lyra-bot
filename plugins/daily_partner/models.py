from enum import IntEnum
from typing import Optional
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, Integer, Boolean, Date, UniqueConstraint, String
from nonebot_plugin_datastore import get_plugin_data


class RelationType(IntEnum):
    WIFE = 0
    HUSBAND = 1


Model = get_plugin_data().Model


class Record(Model):
    __tablename__ = "daily_partner_record"
    __table_args__ = (
        # 联合唯一索引：确保每天、每个群、每个用户、针对同一种关系（娶/嫁），只能有一条活跃的基础记录
        UniqueConstraint('record_date', 'platform', 'group_id', 'user_id', 'relation_type', name='uq_daily_relation'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, default=date.today, index=True, comment="记录日期")
    platform: Mapped[str] = mapped_column(String(50), index=True, comment="平台标识")
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    relation_type: Mapped[RelationType] = mapped_column(Integer, comment="关系类型，0: 老婆, 1: 老公")
    swap_count: Mapped[int] = mapped_column(Integer, default=0, comment="独立记录 user_id 的换人次数")
    is_divorced: Mapped[bool] = mapped_column(Boolean, default=False, comment="离婚惩罚状态")


class User(Model):
    __tablename__ = "daily_partner_user"
    __table_args__ = (
        UniqueConstraint('platform', 'user_id', name='uq_user_platform_id'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), index=True, comment="平台标识)")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可使用插件，若为否则无法被其他人选中")
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为 bot")
    allow_bot: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否允许抽选选择 bot，是否为 bot 参照`is_bot`确定")
    hope_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="心愿单，记录抽选心选对象，抽选 wife 时抽到的概率更高")
