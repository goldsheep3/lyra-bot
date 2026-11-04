from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex

# 纯文本只有「喵」时才触发；想只匹配两个以上可以改成 r"^喵{2,}$"
on_meow = on_regex(r"^喵+$", block=False)


@on_meow.handle()
async def _(matcher: Matcher):
    await matcher.finish("喵喵 咕噜咕噜~")
