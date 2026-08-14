from io import BytesIO
from nonebot import on_regex


debug = on_regex(r"^debug")

@debug.handle()
async def _debug_handle(event, matcher):
    from ..matcher.message import build_msg
    
    await matcher.send("please wait...")
    
    from .image_gen import _debug as debug_demo
    image = debug_demo()
    
    await build_msg(matcher, event, [("image", image)], "finish")
