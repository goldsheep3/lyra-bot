from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex

on_ciallo = on_regex(r"[Cc]iallo", block=True)


@on_ciallo.handle()
async def _(matcher: Matcher):
    await matcher.finish("Ciallo~ (∠・ω< )⌒☆")

