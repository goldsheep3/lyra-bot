import time

from .. import services
from ..constants import ASSETS_PATH

from nonebot import on_regex, on_message, on_notice
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent)
from nonebot.adapters.telegram import Event as TGEvent
from nonebot.adapters.telegram.event import (PrivateMessageEvent as TGPrivateMessageEvent,
                                             GroupMessageEvent as TGGroupMessageEvent)


# --- i18n configs ---

from plugins.nonebot_plugin_i18n import use_i18n, reply, current_i18n_data as i18n_data
i18n_dir = ASSETS_PATH / "i18n"
i18n = use_i18n(i18n_dir)


# --- rules ---

def rule_is_group(event: Event) -> bool:
    return isinstance(event, (
        OneBotV11GroupMessageEvent,
        TGGroupMessageEvent
    ))

def rule_is_private(event: Event) -> bool:
    return isinstance(event, (
        OneBotV11PrivateMessageEvent,
        TGPrivateMessageEvent
    ))

def rule_is_self(event: OneBotV11Event) -> bool:
    return event.get_user_id() == str(event.self_id)


# =================================


link = on_regex(r"^(查询|获取|绑定|解除|解绑)?link(?:\s+(\S+))?$", priority=5, block=True)


link_cache = {}
link_hash_index = {}

@link.handle()
async def link_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: link"""
    i18n_data.set(_i18n)
    action, args_text = groups
    global link_cache, link_hash_index

    # 预先的遍历过期检查
    current_time = int(time.time())
    expired_hashes = []
    for uid, (h, exp) in list(link_cache.items()):
        if current_time > exp:
            expired_hashes.append(h)
            del link_cache[uid]
    
    for h in expired_hashes:
        if h in link_hash_index:
            del link_hash_index[h]
    
    # 查询分支
    if action == "查询":
        await matcher.finish(reply("link.query_disabled"))
        return
    
    # 获取/绑定分支
    elif action in ("获取", "绑定"):
        # 检查是否为 Onebot (QQ) 平台
        if not isinstance(event, OneBotV11Event):
            await matcher.finish(reply("link.only_qq"))
            return
        
        # 生成随机 hash 并设置五分钟到期
        import secrets
        hash_value = secrets.token_hex(8)
        expiration_time = int(time.time()) + 300
        
        # 存储到缓存中
        user_id = int(event.get_user_id())
        _ = await services.check_mu(user_id)
        if old_link := link_cache.get(user_id):
            link_hash_index.pop(old_link[0], None)
        link_cache[user_id] = (hash_value, expiration_time)
        link_hash_index[hash_value] = user_id
        
        # 发送提示文案和绑定指令
        await matcher.send(reply("link.tip"))
        await matcher.finish(f"link {hash_value}")
        return
    
    # 解除/解绑分支
    elif action in ("解除", "解绑"):
        if isinstance(event, OneBotV11Event):
            # QQ 端解绑全部
            user_id = int(event.get_user_id())
            await services.del_mu_tgid(user_id)
            await matcher.finish(reply("link.unlink_success"))
            return
        elif isinstance(event, TGEvent):
            # TG 端解绑当前账号
            telegram_id = int(event.get_user_id())
            mu = await services.get_mu_from_tgid(telegram_id)
            if mu:
                await services.del_mu_tgid(mu.user_id)
            await matcher.finish(reply("link.unlink_success"))
            return
        await matcher.finish(reply("link.not_platform"))
    
    # 验证分支（action为空）
    else:
        if not args_text:
            await matcher.finish(reply("link.invalid_hash"))
            return
        
        provided_hash = args_text.strip()
        
        # 通过反向索引直接查找
        if provided_hash not in link_hash_index:
            await matcher.finish(reply("link.not_found"))
            return
        
        user_id = link_hash_index[provided_hash]
        cache_entry = link_cache.get(user_id)
        if cache_entry is None or cache_entry[0] != provided_hash:
            link_hash_index.pop(provided_hash, None)
            await matcher.finish(reply("link.not_found"))
            return
        
        # 验证成功，执行绑定逻辑
        if isinstance(event, OneBotV11Event):
            # 但 OneBotV11 不需要绑定 qq
            await matcher.finish(reply("link.onebot_no_bind"))
            return
        elif isinstance(event, TGEvent):
            await services.set_mu_tgid(user_id, telegram_id=int(event.get_user_id()))
            
            # 清理缓存
            del link_cache[user_id]
            del link_hash_index[provided_hash]
            await matcher.finish(reply("link.success"))
            return
        
        # 非支持平台（理论上不会到达）
        await matcher.finish(reply("link.not_platform"))
        return


# Import handler modules after matcher objects and shared helpers are ready.
from . import adx_download as _adx_download_handlers
from . import alias as _alias_handlers
from . import dxrating_calc as _dxrating_calc_handlers
from . import info as _info_handlers
from . import info_list as _info_list_handlers
from . import sync as _sync_handlers

# temp - 临时管理命令，可能随时移除
from . import temp as _temp_handlers
