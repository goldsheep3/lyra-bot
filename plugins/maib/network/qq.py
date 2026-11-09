from typing import Optional, Literal


from .tool import request_bytes


async def get_qq_avatar(qq: str | int, spec: Literal[1, 2, 3, 4, 5, 40, 100, 640] = 100) -> Optional[bytes]:
    avatar_url = f"http://q2.qlogo.cn/headimg_dl?dst_uin={qq}&spec={spec}"
    avatar = await request_bytes(avatar_url)
    return avatar