from nonebot import logger, on_regex
from nonebot.adapters import Event
from nonebot.internal.matcher import Matcher
from nonebot.params import RegexDict

from .. import services
from . import Reply, reply
from .context import get_maiuser


maime_link = on_regex(
    r"^绑定(?:aime|卡号|卡片)\s*(?P<access>\d{4}(?:[\s-]?\d{4}){4})\s*$",
    priority=5,
    block=True,
)
maime_unlink = on_regex(
    r"^解绑(?:aime|卡号|卡片)\s*(?P<access>\d{4}(?:[\s-]?\d{4}){4})\s*$",
    priority=5,
    block=True,
)
maime_lost = on_regex(
    r"^(?:挂失|捡到|拾获|查询)(?:aime|卡号|卡片)\s*"
    r"(?P<access>\d{4}(?:[\s-]?\d{4}){4}|\d{4})\s*$",
    priority=5,
    block=True,
)
maime_list = on_regex(r"^(查看卡片|查看完整卡片)\s*$", priority=5, block=True)


async def _resolve_qq(event: Event, matcher: Matcher) -> int:
    """在 AID 迁移前沿用现有的跨平台 QQ 解析。"""
    try:
        return (await get_maiuser(event)).user_id
    except ValueError as exc:
        await matcher.finish(str(exc))
        raise AssertionError("Matcher.finish() unexpectedly returned") from exc


@maime_link.handle()
async def aime_link(
    event: Event,
    matcher: Matcher,
    groups: dict = RegexDict(),
    reply: Reply = reply,
):
    """处理命令: 绑定(aime|卡号|卡片) <aime卡号>。"""
    access: str = groups.get("access", "")
    qq = await _resolve_qq(event, matcher)

    try:
        await services.refactoring.aime.link(access, qq=qq)
    except services.refactoring.aime.AimeAlreadyLinkedSelfError:
        await matcher.finish(await reply("maime.link.error.linked_self"))
    except services.refactoring.aime.AimeAlreadyLinkedError:
        await matcher.finish(await reply("maime.link.error.linked"))
    except Exception:
        logger.exception("Unexpected error when linking Aime")
        await matcher.finish(await reply("maime.link.error.unknown"))
    else:
        await matcher.finish(await reply("maime.link.success"))


@maime_unlink.handle()
async def aime_unlink(
    event: Event,
    matcher: Matcher,
    groups: dict = RegexDict(),
    reply: Reply = reply,
):
    """处理命令: 解绑(aime|卡号|卡片) <aime卡号>。"""
    access: str = groups.get("access", "")
    qq = await _resolve_qq(event, matcher)

    try:
        await services.refactoring.aime.unlink(access, qq=qq)
    except services.refactoring.aime.AimeNotFoundError:
        await matcher.finish(await reply("maime.unlink.error.not_found"))
    except services.refactoring.aime.AimeNotOwnerError:
        await matcher.finish(await reply("maime.unlink.error.not_owner"))
    except Exception:
        logger.exception("Unexpected error when unlinking Aime")
        await matcher.finish(await reply("maime.unlink.error.unknown"))
    else:
        await matcher.finish(await reply("maime.unlink.success"))


@maime_lost.handle()
async def aime_lost(
    event: Event,
    matcher: Matcher,
    groups: dict = RegexDict(),
    reply: Reply = reply,
):
    """处理命令: 拾获(aime|卡号|卡片) <aime卡号>。"""
    raw_access: str = groups.get("access", "")
    normalized = raw_access.replace(" ", "").replace("-", "")
    qq = await _resolve_qq(event, matcher)

    try:
        if len(normalized) == 20:
            aime = await services.refactoring.aime.find_aime(normalized)
        else:
            aime = await services.refactoring.aime.find_aime_by_access4(normalized)
    except services.refactoring.aime.AimeNotFoundError:
        await matcher.finish(await reply("maime.lost.error.not_found"))
    except services.refactoring.aime.AimeNotLinkedError:
        await matcher.finish(await reply("maime.lost.error.not_link"))
    except services.refactoring.aime.AimeMultipleFoundError:
        await matcher.finish(await reply("maime.lost.error.multiple_found"))
    except Exception:
        logger.exception("Unexpected error when finding Aime")
        await matcher.finish(await reply("maime.lost.error.unknown"))

    if aime is None:
        await matcher.finish(await reply("maime.lost.error.not_found"))
    if aime["qq"] == qq:
        await matcher.finish(await reply("maime.lost.error.self"))

    await matcher.finish(
        await reply("maime.lost.find", card=aime["access"], hint=aime["hint"])
    )


@maime_list.handle()
async def aime_list(event: Event, matcher: Matcher, reply: Reply = reply):
    """处理命令: 查看卡片。"""
    full = "完整卡片" in event.get_plaintext()
    qq = await _resolve_qq(event, matcher)
    aime_list = await services.refactoring.aime.get_aimes(qq=qq)

    if not aime_list:
        await matcher.finish(await reply("maime.list.empty"))

    lines = [await reply("maime.list.header")]
    for aime in aime_list:
        time_str = aime["create_at"].strftime(r"%Y-%m-%d")
        card_display = (
            aime["access"]
            if full
            else aime["access"][:4] + "*" * 12 + aime["access"][-4:]
        )
        lines.append(
            await reply("maime.list.item", access=card_display, create_at=time_str)
        )

    await matcher.finish("\n".join(lines))
