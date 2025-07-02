from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

from . import maib50
from .img import image_to_base64


# maib50 相关生成代码
# @maib50.handle()
async def maib50gen(event: MessageEvent, message: Message = CommandArg()):
    async def maib50_gen(_): return 0, 0

    username = str(message).strip()
    if username == "":
        payload = {'qq': str(event.get_user_id()), 'b50': True}
    else:
        payload = {'username': username, 'b50': True}

    img, success = await maib50_gen(payload)  # b50 图片生成函数

    if success == -1:
        await maib50.finish("出现未知错误。")
    elif success == 400:
        await maib50.finish("未找到此玩家，请确保此玩家的用户名和查分器中的用户名相同。")
    elif success == 403:
        await maib50.finish("该用户禁止了其他人获取数据。")
    else:
        await maib50.finish(Message([
            MessageSegment.image(f"base64://{str(image_to_base64(img), encoding='utf-8')}")
        ]))
