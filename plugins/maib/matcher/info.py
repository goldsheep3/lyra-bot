from typing import Optional

from nonebot import on_regex
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

from .. import services, image_gen
from ..utils import NoLinkQQError
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
        default_server = 'JP'  # 没有绑定 QQ 的用户默认展示日服数据
    except ValueError as e:
        await matcher.finish(str(e))
        return
    
    _, server = get_args(args)
    
    server = server if (server != 'ALL' and server is not None) else default_server  # 暂不支持 ALL
    # 查询乐曲信息
    mdt: Optional[services.MaiData] = await services.get_mdt.id(shortid, qq)
    if mdt is None:
        await matcher.finish(reply("info.maidata_not_found", short_id=shortid))
        return
    maidata = mdt.to_utils(achs_user_id=qq)
    s = server if maidata.version_cn is not None else "JP"  # 如果乐曲没有国服版本，则展示日服数据
    
    info_box = image_gen.draw_info_box(maidata, s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
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
        server = 'JP'  # 没有绑定 QQ 的用户默认展示日服数据
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

    def generate_single_info_box(mdt) -> bytes:
        """生成单首乐曲的 info box 图片字节"""
        maidata = mdt.to_utils(achs_user_id=qq)
        s = server if maidata.version_cn is not None else "JP"
        info_box = image_gen.draw_info_box(maidata, server=s, maiuser=maiuser, cn_level=1 if s == 'CN' else 0)
        return image_gen.get_image_bytes(info_box)

    # 输出结果
    payload = []
    
    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        payload.append(("text", reply("info.found_single", shortid=mdt.shortid, title=mdt.title)))
        payload.append(("image", generate_single_info_box(mdt)))

    elif len(mdt_list) <= 4:
        payload.append(("text", reply("info.found_multiple", count=len(mdt_list))))
        for mdt in mdt_list:
            payload.append(("image", generate_single_info_box(mdt)))

    elif len(mdt_list) <= 40:
        # 结果大于 4 首，采用简要列表图承载
        # TODO 创建独立的列表图生成函数
        img = image_gen.simple_list("\n".join([f"{maidata.shortid}.\t{maidata.title}" for maidata in mdt_list]))
        
        img_bytes = image_gen.get_image_bytes(img)
        payload.append(("text", reply("info.found_many", count=len(mdt_list))))
        payload.append(("image", img_bytes))

    else:
        await matcher.finish(reply("info.found_too_many_abort"))
        return

    # 4. 统一发送消息
    await build_msg(matcher, event, payload, tag='finish')
