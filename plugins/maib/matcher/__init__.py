import time

from .. import services
from ..sync import link_cache, link_hash_index
from ..constants import ASSETS_PATH

from nonebot import on_regex, on_message, on_notice
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent)
from nonebot.adapters.telegram import Event as TGEvent
from nonebot.adapters.telegram.event import PrivateMessageEvent as TGPrivateMessageEvent


# --- i18n configs ---

from plugins.nonebot_plugin_i18n import use_i18n, reply, current_i18n_data as i18n_data
i18n_dir = ASSETS_PATH / "i18n"
i18n = use_i18n(i18n_dir)

from .context import get_args, get_maidata_with_ach, get_maiuser
from .message import build_msg

# --- rules ---

def file_received_enabled(event: Event) -> bool:
    if isinstance(event, OneBotV11PrivateMessageEvent):
        return True
    elif isinstance(event, TGPrivateMessageEvent):
        return True
    return False

# --- matcher ---

# 下载谱面
adx_download_matcher = on_regex(r"^下载[铺谱]面\s*(\d*)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (id / info)
mai_info = on_regex(r"^(id|info)(\d+)\s*(.*)$", priority=10, block=True)
# 查询乐曲信息 (是什么歌)
mai_what_song = on_regex(r"^(.+?)是什么歌([?？]?)$", priority=10, block=True)
# 设置乐曲别名
mai_alias = on_regex(r'^(添加|删除)别名\s+(?:id)?(\d+)\s+([^\s]+)$', priority=5, block=True)
# 列表查询（完成表/进度/列表）
# scorelist = on_regex(r'^(.*?)\s*(完成表|进度|列表)$', priority=5, block=True)
# 同步水鱼数据
sytb = on_regex(r'^sytb$', priority=5, block=True)
# b50 查询
b50 = on_regex(r'^(b50|kkb)\s*(.*)$', priority=1, block=True)
# ra 计算
ra_calc = on_regex(r"^ra\s+(?P<level>\S+)(?:\s+(?P<achievement>\S+))?$", priority=5, block=True)
# 上传 JSON 配置数据
file_receiver = on_message(priority=25, rule=file_received_enabled)
# 群文件上传 notice，用于处理 upload_group_file 超时但实际成功的场景
group_upload_notice = on_notice(priority=1, block=False)
# 获取同步码
get_sync_code = on_regex(r"^获取同步码$", priority=5, block=True)
# link 查询与绑定
link = on_regex(r"^(查询|获取|绑定|解除|解绑)?link(?:\s+(\S+))?$", priority=5, block=True)

# =================================
# 业务逻辑
# =================================

# --- link ---

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
