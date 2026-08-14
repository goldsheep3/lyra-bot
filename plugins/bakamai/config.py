from pydantic import BaseModel
from pathlib import Path
from nonebot import get_plugin_config

class ServerInstance(BaseModel):
    ssh_host: str
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_password: str | None = None
    ssh_key_path: Path | None = None
    
    whitelist_path: str
    rcon_host: str
    rcon_port: int
    rcon_password: str
    
    bound_groups: list[int] = []  # 该实例对应的群号列表

class Config(BaseModel):
    bakamai_instances: dict[str, ServerInstance] = {}

cfg = get_plugin_config(Config)
