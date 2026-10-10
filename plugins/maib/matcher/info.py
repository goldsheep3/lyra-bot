from typing import Optional, Any

from nonebot import on_regex, logger
from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Event as OneBotV11Event
from nonebot.adapters.telegram import Event as TGEvent

from .. import services, image_gen
from ..utils.report import build_diff_report
from ..utils import NoLinkQQError
from ..utils.enums import ServerScope
from . import i18n_data, i18n, reply, sync
from .context import get_args, get_maiuser
from .message import build_msg

mai_info = on_regex(r"^(id|info)(\d+)\s*(.*)$", priority=10, block=True)

mai_what_song = on_regex(r"^(.+?)是什么歌([?？]?)$", priority=10, block=True)


@mai_info.handle()
async def mai_info_handled(event: Event, matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: id11451 / info11451"""
    i18n_data.set(_i18n)
    _, short_id, args_text = groups
    
    # shortid 判断
    if not short_id.isdigit():
        await matcher.finish(reply("info.invalid_id"))
        return
    shortid = int(short_id)

    # 解析命令参数
    parsed_uid, _scope = get_args(args_text)
    sender_user_id = int(event.get_user_id())
    scope: ServerScope = _scope or ServerScope.CN

    # 解析用户
    at_qq = None
    parsed_qq = None
    sender_qq = None
    sender_username = "maimai"

    if isinstance(event, OneBotV11Event):
        parsed_qq = parsed_uid if parsed_uid else None
        sender_qq = sender_user_id
        for segment in event.get_message():
            if segment.type == "at":
                at_qq = int(segment.data["qq"])
                break

    elif isinstance(event, TGEvent):
        async def get_qq_from_tg_uid(tg_uid: int) -> Optional[int]:
            if tg_uid is None:
                return None
            mu = await services.get_mu_from_tgid(tg_uid)
            return int(mu.user_id) if mu else None
        
        parsed_qq = None  # Telegram 目前不支持文本参数解析 QQ，预留接口但暂不启用
        sender_qq = await get_qq_from_tg_uid(sender_user_id)
        
        if from_ := getattr(event, "from_", None):
            sender_username = from_.username or from_.first_name or "maimai"
            
        at_qq = None  # Telegram 暂不支持 at

    # 确定最终被查询人 (优先级：at 目标 > 文本传参 > 发送者自己)
    target_qq = at_qq or parsed_qq or sender_qq
    is_querying_self = (target_qq is not None and target_qq == sender_qq)
    
    # 1. 先获取 mu
    target_mu = None
    if target_qq is not None:
        try:
            target_mu = await services.check_mu(target_qq)
        except ValueError:
            # 获取 MaiUser 失败（如未绑定或数据异常），降级为无成绩模式
            target_mu = None

    # 2. 同步水鱼数据 (仅当 target_mu 存在且 scope 为 CN 或 ALL 时)
    if target_mu and scope in [ServerScope.CN, ServerScope.ALL]:
        try:
            target_mu, report = await sync.check_sync_cn(target_mu, ignore_cache_expire=True)
            # 核心修改：只有当有更新时才发送提醒，否则静默
            if report and report.has_changes:
                if is_querying_self:
                    # 查询自己：展示详细的同步报告
                    summary_text, diff_img = build_diff_report(report)
                    sync_payload: list[tuple[str, Any]] = [
                        ("at", (sender_username, sender_user_id)),
                        ("text", f" 已同步水鱼数据！以下是水鱼数据的同步详情：\n\n{summary_text}")
                    ]
                    if diff_img:
                        sync_payload.append(("image", image_gen.get_image_bytes(diff_img)))
                    await build_msg(matcher, event, sync_payload, tag='send')
                else:
                    # 查询他人：简化提示
                    await build_msg(matcher, event, [
                        ("at", (sender_username, sender_user_id)), ("text", reply("b50.other_updated"))
                    ], tag='send')
        except Exception as e:
            logger.warning(f"强制刷新水鱼数据失败: {e}")

    # 3. 转化为 maiuser (使用同步后最新的 target_mu)
    target_maiuser = target_mu.to_utils() if target_mu else None

    # 查询乐曲信息
    mdt: Optional[services.MaiData] = await services.get_mdt.id(shortid, target_qq)
    if mdt is None:
        await matcher.finish(reply("info.maidata_not_found", short_id=shortid))
        return
    maidata = mdt.to_utils(achs_user_id=target_qq)

    info_box = image_gen.draw_info_board(maidata, maiuser=target_maiuser)
    info_box_bytes = image_gen.get_image_bytes(info_box)
    
    payload = [
        ("text", f"{mdt.shortid}. {mdt.title}"),
        ("image", info_box_bytes)
    ]
    
    # 如果未绑定或获取用户信息失败，提示绑定以获取更多信息
    if target_qq is None or target_maiuser is None:
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
    except NoLinkQQError as e:
        # 未绑定 QQ
        maiuser = None
        qq = None
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

    def generate_single_info_box(mdt, matched_alias: str | None = None) -> bytes:
        """生成单首乐曲的 info box 图片字节，返回 (图片字节, 别名匹配提示)"""
        maidata = mdt.to_utils(achs_user_id=qq)
        if matched_alias:
            maidata._matched_alias = matched_alias
        info_box = image_gen.draw_info_board(maidata, maiuser=maiuser, light_alias=matched_alias)
        info_bytes = image_gen.get_image_bytes(info_box)
        return info_bytes

    # 输出结果
    payload = []
    
    if len(mdt_list) == 1:
        mdt = mdt_list[0]
        matched_alias = _inject_matched_alias(mdt, keyword)
        payload.append(("text", reply("info.found_single", shortid=mdt.shortid, title=mdt.title)))
        img_bytes = generate_single_info_box(mdt, matched_alias)
        payload.append(("image", img_bytes))

    elif len(mdt_list) <= 4:
        payload.append(("text", reply("info.found_multiple", count=len(mdt_list))))
        for mdt in mdt_list:
            matched_alias = _inject_matched_alias(mdt, keyword)
            img_bytes = generate_single_info_box(mdt, matched_alias)
            payload.append(("image", img_bytes))

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
