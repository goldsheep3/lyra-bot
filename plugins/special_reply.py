from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex
from nonebot.rule import Rule

# 仅匹配 OneBotV11 群消息中的纯文本「老吴」
on_laowu = on_regex(
    r"^老吴$",
    rule=Rule(lambda bot, event: isinstance(event, GroupMessageEvent)),
    block=True,
)


@on_laowu.handle()
async def _(matcher: Matcher):
    await matcher.finish("老吴~")
