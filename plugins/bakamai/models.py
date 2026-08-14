from typing import Literal
from sqlalchemy import String, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_datastore import get_plugin_data


Model = get_plugin_data().Model


class Whitelist(Model):
    
    __tablename__ = "bakamai_whitelist"
    __table_args__ = (UniqueConstraint("user_id", "group_id", "platform"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)  # QQ
    group_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)  # QQ Group
    username: Mapped[str] = mapped_column(String(64), nullable=False)  # Minecraft Player Username
    uuid: Mapped[str] = mapped_column(String(64), nullable=False)  # Minecraft Player UUID
    platform: Mapped[Literal["java", "bedrock"]] = mapped_column(String(20), nullable=False)  # Java / Bedrock
