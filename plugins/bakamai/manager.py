import json
import re
import asyncssh
from aiomcrcon import Client as RCONClient
from sqlalchemy import select
from nonebot import logger
from nonebot_plugin_datastore import create_session

from .config import cfg, ServerInstance
from .models import Whitelist

class BakamaiManager:
    def __init__(self):
        self._group_to_instance: dict[int, ServerInstance] = {}
        self._setup()

    def _setup(self):
        group_map = {}
        conflict_groups = set()
        for name, inst in cfg.bakamai_instances.items():
            for gid in inst.bound_groups:
                if gid in group_map:
                    logger.error(f"群 {gid} 存在多开冲突（{name} & {group_map[gid]}），已忽略该群。")
                    conflict_groups.add(gid)
                group_map[gid] = name
        
        self._group_to_instance = {
            gid: cfg.bakamai_instances[group_map[gid]] 
            for gid in group_map if gid not in conflict_groups
        }

    def get_inst(self, gid: int) -> ServerInstance | None:
        return self._group_to_instance.get(gid)

    async def sync(self, gid: int):
        inst = self.get_inst(gid)
        if not inst:
            logger.error(f"未找到群 {gid} 对应的服务器实例。")
            return

        async with create_session() as session:
            db_entries = (await session.execute(select(Whitelist).where(Whitelist.group_id == gid))).scalars().all()
        
        # SSH 推送
        wl_json = json.dumps([{"uuid": e.uuid, "name": e.username} for e in db_entries], indent=2)
        ssh_opts = {"host": inst.ssh_host, "port": inst.ssh_port, "username": inst.ssh_user, "known_hosts": None}
        if inst.ssh_key_path: ssh_opts["client_keys"] = [str(inst.ssh_key_path)]
        else: ssh_opts["password"] = inst.ssh_password

        async with asyncssh.connect(**ssh_opts) as conn:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(inst.whitelist_path, 'w') as f:
                    await f.write(wl_json)

        # RCON 重载
        rcon = RCONClient(host=inst.rcon_host, password=inst.rcon_password, port=inst.rcon_port)
        try:
            await rcon.connect()
            await rcon.command("whitelist reload")
        finally:
            await rcon.close()

    async def get_status(self, gid: int):
        inst = self.get_inst(gid)
        if not inst:
            logger.error(f"未找到群 {gid} 对应的服务器实例。")
            return

        rcon = RCONClient(host=inst.rcon_host, password=inst.rcon_password, port=inst.rcon_port)
        try:
            await rcon.connect()
            resp, _ = await rcon.command("list")
            # 简化版正则解析
            match = re.search(r"(\d+) of a max (\d+)", resp)
            cur, mx = (match.groups() if match else (0, 0))
            names = [n.strip() for n in resp.split(":")[-1].split(",") if n.strip()]
            
            async with create_session() as session:
                users = (await session.execute(select(Whitelist).where(Whitelist.username.in_(names), Whitelist.group_id == gid))).scalars().all()
            return {"cur": cur, "max": mx, "names": names, "db_users": {u.username: u for u in users}}
        finally:
            await rcon.close()
