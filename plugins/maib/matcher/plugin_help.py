"""plugin_help.py 帮助信息"""
from nonebot import on_regex
from nonebot.adapters import Event
from nonebot.internal.matcher import Matcher

from ..image_gen import draw_simple_board as simple_img
from . import Reply, reply
from .message import build_msg


plugin_help = on_regex(r"^(帮助|help)\s*(maib|舞萌|mai|maimai)$", priority=10, block=True)

@plugin_help.handle()
async def _(event: Event, matcher: Matcher, reply: Reply = reply):
    text = '\n'.join([
        await reply("help") + ": " + await reply("plugin_name"),  # 帮助标题
        "",
        await reply("ad.help"),
        await reply("b50.help"),
        await reply("rc.help"),
        await reply("sync.help"),
        await reply("info.help"),
        await reply("alias.help"),
        await reply("maime.help"),
    ])
    
    img = simple_img(text, ms=1)

    
    await build_msg(matcher, event, [("image", img)], tag="finish")
