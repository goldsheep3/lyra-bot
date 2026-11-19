from ... import network, services
from ...utils import MaiUser, NoLinkQQError


async def get_or_create_maiuser_qq(qq: int) -> MaiUser:
    mu = await services.check_mu(qq)
    if mu is None:
        raise NoLinkQQError

    if not mu.username:
        data = await network.DivingFish.dev_player_records(qq=qq)
        username = data.get("nickname", "maimai") if isinstance(data, dict) else "maimai"
        await services.set_mu_username(qq, username)
        mu.username = username

    return mu.to_utils()


async def get_or_create_maiuser_from_tg(tg_id: int) -> MaiUser:
    qq = await services.refactoring.link.get_qq_from_tg(tg_id)
    if qq is None:
        raise NoLinkQQError 
    return await get_or_create_maiuser_qq(qq)

