from nonebot import on_startswith
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

__plugin_meta__ = PluginMetadata(
    name="Beta Plugin",
    description="A plugin for testing new features.",
    usage="Send 'b' to trigger the beta feature.",
)

beta_pa = on_startswith("b", rule=to_me(), priority=2, block=True)

@beta_pa.handle()
async def rebirth_handler(matcher: Matcher, event: MessageEvent):
    await matcher.finish(Message([MessageSegment.text('啪！')]))
