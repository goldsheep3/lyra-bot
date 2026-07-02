from typing import Optional
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, Boolean, Date, UniqueConstraint, String
from nonebot_plugin_datastore import get_plugin_data


Model = get_plugin_data().Model


class Record(Model):
    __table_args__ = (
        # 联合唯一索引：确保每天、每个群、每个用户，只能有一条活跃的基础记录
        UniqueConstraint('record_date', 'platform', 'group_id', 'user_id', name='uq_daily_relation'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_date: Mapped[date] = mapped_column(Date, default=date.today, index=True, comment="记录日期")
    platform: Mapped[str] = mapped_column(String(50), index=True, comment="平台标识")
    group_id: Mapped[str] = mapped_column(String(50), index=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    wife_id: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    husband_id: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    swap_count: Mapped[int] = mapped_column(Integer, default=0, comment="更换 wife 或 husband 的次数")
    is_divorced: Mapped[bool] = mapped_column(Boolean, default=False, comment="主动 wife 离婚惩罚状态")


class User(Model):
    __table_args__ = (
        UniqueConstraint('platform', 'user_id', name='uq_user_platform_id'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), index=True, comment="平台标识)")
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否可使用插件，若为否则无法被其他人选中")
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为 bot")
    allow_bot: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否允许抽选选择 bot，是否为 bot 参照`is_bot`确定")
    hope_id: Mapped[Optional[str]] = mapped_column(String(50), default=None, comment="心愿单，记录抽选心选对象，抽选 wife 时抽到的概率更高")


# TODO: 群组配置功能 建议来自 LDxiaodiの粉丝老爷们@无名客晓枫
# class Group(Model):
#     __table_args__ = (
#         UniqueConstraint('platform', 'group_id', name='uq_group_platform_id'),
#     )
    
#     id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
#     platform: Mapped[str] = mapped_column(String(50), index=True, comment="平台标识)")
#     group_id: Mapped[str] = mapped_column(String(50), index=True)
#     filter_activate: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用活跃过滤器，若开启则根据配置文件筛选活跃用户")
