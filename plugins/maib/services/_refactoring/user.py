from ... import network
from ...utils import MaiUser, NoLinkQQError
from .._user import check_mu, set_mu_username
from .link import get_qq_from_tg


async def get_or_create_maiuser_from_qq(qq: int, *, without_name: bool = False) -> MaiUser:
    mu = await check_mu(qq)
    if mu is None:
        raise NoLinkQQError

    if (not mu.username) and (not without_name):
        data = await network.DivingFish.dev_player_records(qq=qq)
        username = data.get("nickname", "maimai") if isinstance(data, dict) else "maimai"
        await set_mu_username(qq, username)
        mu.username = username

    return mu.to_utils()


async def get_or_create_maiuser_from_tg(tg_id: int, *, without_name: bool = False) -> MaiUser:
    qq = await get_qq_from_tg(tg_id)
    if qq is None:
        raise NoLinkQQError 
    return await get_or_create_maiuser_from_qq(qq, without_name=without_name)

