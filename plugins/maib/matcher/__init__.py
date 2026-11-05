import time
from pathlib import Path

from .. import services
from ..utils.constants import ASSETS_PATH

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,
                                         MessageEvent as OneBotV11MessageEvent,
                                         PrivateMessageEvent as OneBotV11PrivateMessageEvent,
                                         GroupMessageEvent as OneBotV11GroupMessageEvent)
from nonebot.adapters.telegram import Event as TGEvent
from nonebot.adapters.telegram.event import (PrivateMessageEvent as TGPrivateMessageEvent,
                                             GroupMessageEvent as TGGroupMessageEvent)


# --- i18n configs ---

from nonebot_plugin_locales import Reply, locales_init
reply = locales_init(ASSETS_PATH / "i18n")


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

def rule_is_self(event: OneBotV11MessageEvent) -> bool:
    return event.get_user_id() == str(event.self_id)

# ======================================================


# 导入各模块以注册对应处理器
from . import adx_download as _adx_download_handlers
from . import alias as _alias_handlers
from . import dxrating_calc as _dxrating_calc_handlers
from . import info as _info_handlers
from . import info_list as _info_list_handlers
from . import sync as _sync_handlers
from . import maime as _maime_handlers
from . import plugin_help as _plugin_help_handlers

from . import temp_link as _temp_link_handlers