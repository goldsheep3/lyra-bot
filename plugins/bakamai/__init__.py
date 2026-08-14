from typing import Literal
import httpx

from nonebot import on_regex, require
from nonebot.params import RegexDict
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

require("nonebot_plugin_datastore")
from .manager import BakamaiManager
from .models import Whitelist
from nonebot_plugin_datastore import create_session
from sqlalchemy import delete

from .replies import say

bakamai_manager = BakamaiManager()

# --- 工具函数 ---
async def get_uuid_from_api(name: str, platform: Literal["java", "bedrock"]) -> str:
    url = f"https://mcprofile.io/api/v1/{'java/username' if platform == 'java' else 'bedrock/gamertag'}/{name}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("uuid") or data.get("floodgateuid")
    except Exception:
        pass
    return ''


# --- 响应器规则 ---
async def rule_is_bound(event: GroupMessageEvent) -> bool:
    return bakamai_manager.get_inst(event.group_id) is not None


# --- Matchers ---

cmd_wl = on_regex(
    r"^(?P<action>添加|删除)白名单\s+(?P<dot>\.?)(?P<name>[a-zA-Z0-9_-]+)(?:\s+(?P<target>\d+))?$",
    rule=rule_is_bound, priority=10, block=True
)

@cmd_wl.handle()
async def _(event: GroupMessageEvent, matcher, params: dict = RegexDict()):
    action, name = params["action"], params["name"]
    is_bedrock = bool(params["dot"])
    target_qq = int(params["target"]) if params.get("target") else event.user_id
    gid = event.group_id
    
    if target_qq != event.user_id:
        # 权限检查：只有管理员或群主可以指定其他人
        member_info = event.sender.role or ''
        if member_info not in ("owner", "admin"):
            return await matcher.finish(say("not_admin", name=name))

    try:
        if action == "添加":
            uuid = await get_uuid_from_api(name, "bedrock" if is_bedrock else "java")
            if not uuid:
                return await matcher.finish(say("add_fail_uuid", name=name))
            
            async with create_session() as session:
                session.add(Whitelist(user_id=target_qq, group_id=gid, username=name, uuid=uuid, platform="bedrock" if is_bedrock else "java"))
                await session.commit()
            await bakamai_manager.sync(gid)
            return await matcher.finish(say("add_success", name=name))
        
        elif action == "删除":
            async with create_session() as session:
                await session.execute(delete(Whitelist).where(Whitelist.username == name, Whitelist.group_id == gid))
                await session.commit()
            await bakamai_manager.sync(gid)
            return await matcher.finish(say("remove_success", name=name))
            
    except Exception:
        return await matcher.finish(say("add_error"))


cmd_status = on_regex(r"^(mc几|list)$", rule=rule_is_bound, priority=10, block=True)

@cmd_status.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    try:
        s = await bakamai_manager.get_status(event.group_id)
        if not s: return
        if int(s["cur"]) == 0: return await cmd_status.finish(say("status_empty"))
        
        lines = [say("status_header", current=s["cur"], max=s["max"])]
        for n in s["names"]:
            u = s["db_users"].get(n)
            if u:
                try:
                    m = await bot.get_group_member_info(group_id=event.group_id, user_id=u.user_id)
                    nick = m.get("card") or m.get("nickname")
                    lines.append(say("status_player_bound", name=n, nick=nick))
                except: lines.append(say("status_player_bound", name=n, nick=u.user_id))
            else: lines.append(say("status_player_unbound", name=n))
        await cmd_status.finish("\n".join(lines))
    except Exception: await cmd_status.finish(say("status_error"))
