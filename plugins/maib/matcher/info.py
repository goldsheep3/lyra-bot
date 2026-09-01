from typing import Optional

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Event as OneBotV11Event

from .. import services, image_gen
from ..utils import NoLinkQQError
from ..utils.enums import UICode, Server, ServerScope
from . import i18n_data, i18n, reply
from .context import get_args, get_maiuser
from .message import build_msg

mai_info = on_regex(r"^(id|info)(\d+)\s*(.*)$", priority=10, block=True)

mai_what_song = on_regex(r"^(.+?)是什么歌([?？]?)$", priority=10, block=True)


@mai_info.handle()
async def mai_info_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: id11451 / info11451"""
    i18n_data.set(_i18n)
    _, short_id, args = groups
    # shortid 判断
    if not short_id.isdigit():
        await matcher.finish(reply("info.invalid_id"))
        return
    shortid = int(short_id)

    try:
        maiuser = await get_maiuser(event)
        qq = int(maiuser.user_id)
        default_server = maiuser.default_server
    except NoLinkQQError as e:
        # 未绑定 QQ
        maiuser = None
        qq = None
        default_server = Server.JP  # 没有绑定 QQ 的用户默认展示日服数据
    except ValueError as e:
        await matcher.finish(str(e))
        return
    
    parsed_uid, scope = get_args(args)
    
    # 检查消息中的 at 提醒，优先级高于文本传参
    at_qq = None
    if isinstance(event, OneBotV11Event):
        for segment in event.get_message():
            if segment.type == "at":
                at_qq = int(segment.data["qq"])
                break
    if at_qq is not None:
        parsed_uid = at_qq


    # 如果传入了目标用户 ID，则覆盖当前查询用户
    if parsed_uid is not None:
        qq = parsed_uid
        # 同时获取目标用户的 MaiUser 信息
        try:
            maiuser = await get_maiuser(event, user_id=qq)
        except (NoLinkQQError, ValueError):
            maiuser = None
    # 查询乐曲信息
    mdt: Optional[services.MaiData] = await services.get_mdt.id(shortid, qq)
    if mdt is None:
        await matcher.finish(reply("info.maidata_not_found", short_id=shortid))
        return
    maidata = mdt.to_utils(achs_user_id=qq)
    
    if scope == ServerScope.ALL:
        # 暂不支持 ALL
        await matcher.finish(reply("info.all_server_not_supported"))
        return
    elif scope is None:
        server = default_server
    else:
        server = scope.to_server()
    if server == Server.CN and maidata.version_cn is None:
        server = Server.JP  # 如果乐曲没有国服版本，则展示日服数据
    uic = UICode.CN if server == Server.CN else UICode.JP

    info_box = image_gen.draw_info_board(maidata, server, maiuser=maiuser, ui_code=uic)
    info_box_bytes = image_gen.get_image_bytes(info_box)
    
    payload = [
        ("text", f"{mdt.shortid}. {mdt.title}"),
        ("image", info_box_bytes)
    ]
    if qq is None:
        payload.append(("text", reply("link.get_more_info")))
    await build_msg(matcher, event, payload, tag='finish')

@mai_what_song.handle()
async def mai_what_song_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: xxx是什么歌"""
    i18n_data.set(_i18n)
    keyword, all_tag = groups
    blur_search = bool(all_tag and all_tag.strip() in ['?', '？'])
    keyword = keyword.strip(' ')

    try:
        maiuser = await get_maiuser(event)
        qq = int(maiuser.user_id)
        server = maiuser.default_server
    except NoLinkQQError as e:
        # 未绑定 QQ
        maiuser = None
        qq = None
        server = Server.JP  # 没有绑定 QQ 的用户默认展示日服数据
    except ValueError as e:
        await matcher.finish(str(e))
        return

    try:
        # 搜索歌曲
        mdt_list = list(await services.get_mdt.title(keyword, achs_user_id=qq, way="blur" if blur_search else "smart"))
    except ValueError as exc:
        await matcher.finish(str(exc))
        return
    
    # 过滤宴会场 (shortid >= 100000)
    # mdt_list = [mdt for mdt in mdt_list if mdt.shortid < 100000]
    if not mdt_list:
        await matcher.finish(reply("info.found_none", keyword=keyword))
        return

    def _inject_matched_alias(mdt, keyword: str) -> str | None:
        """检查 ORM 对象的别名是否匹配关键词，返回匹配的别名或 None"""
        kw_lower = keyword.lower()
        if kw_lower == mdt.title.lower():
            return None  # 标题本身匹配，不是别名匹配
        for alias in mdt.aliases:
            if kw_lower in alias.alias.lower() or alias.alias.lower() == kw_lower:
                return alias.alias
        return None

    def generate_single_info_box(mdt, matched_alias: str | None = None) -> tuple[bytes, str | None]:
        """生成单首乐曲的 info box 图片字节，返回 (图片字节, 别名匹配提示)"""
        maidata = mdt.to_utils(achs_user_id=qq)
        if matched_alias:
            maidata._matched_alias = matched_alias
        uic = UICode.CN if server == Server.CN else UICode.JP
        info_box = image_gen.draw_info_board(maidata, server=server, maiuser=maiuser, ui_code=uic)
        info_bytes = image_gen.get_image_bytes(info_box)
        alias_hint = f"（别名: {matched_alias}）" if matched_alias else None
        return info_bytes, alias_hint

    # 输出结果
    payload = []
    
    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        matched_alias = _inject_matched_alias(mdt, keyword)
        payload.append(("text", reply("info.found_single", shortid=mdt.shortid, title=mdt.title)))
        img_bytes, alias_hint = generate_single_info_box(mdt, matched_alias)
        payload.append(("image", img_bytes))
        if alias_hint:
            payload.append(("text", alias_hint))

    elif len(mdt_list) <= 4:
        payload.append(("text", reply("info.found_multiple", count=len(mdt_list))))
        for mdt in mdt_list:
            matched_alias = _inject_matched_alias(mdt, keyword)
            img_bytes, alias_hint = generate_single_info_box(mdt, matched_alias)
            payload.append(("image", img_bytes))
            if alias_hint:
                payload.append(("text", alias_hint))

    elif len(mdt_list) <= 40:
        # 结果大于 4 首，采用简要列表图承载
        # TODO 创建独立的列表图生成函数
        lines = []
        for mdt in mdt_list:
            alias_hint = _inject_matched_alias(mdt, keyword)
            if alias_hint:
                lines.append(f"{mdt.shortid}.	{mdt.title} (别名: {alias_hint})")
            else:
                lines.append(f"{mdt.shortid}.	{mdt.title}")
        img = image_gen.draw_simple_board("\n".join(lines))
        
        img_bytes = image_gen.get_image_bytes(img)
        payload.append(("text", reply("info.found_many", count=len(mdt_list))))
        payload.append(("image", img_bytes))

    else:
        await matcher.finish(reply("info.found_too_many_abort"))
        return

    # 4. 统一发送消息
    await build_msg(matcher, event, payload, tag='finish')
