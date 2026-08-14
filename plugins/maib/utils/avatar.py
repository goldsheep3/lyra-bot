from typing import Union, Literal, Optional
from ..network import request_image

async def get_qq_avatar(qq: Union[str, int], spec: Literal[1, 2, 3, 4, 5, 40, 100, 640] = 100) -> Optional[bytes]:
    avatar_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={qq}&spec={spec}"
    avatar = await request_image(avatar_url)
    return avatar
