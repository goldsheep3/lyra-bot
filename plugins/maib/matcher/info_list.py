from typing import Optional, Any

from nonebot import logger, on_regex
from nonebot.params import RegexDict
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import config, services, image_gen, network
from ..utils.report import build_diff_report
from ..utils.enums import ServerScope
from . import Reply, reply, sync
from .context import get_args
from .message import build_msg


# --- matcher ---

scorelist = on_regex(r'^(?P<target>.+?)\s*(?:完成表|进度|列表)(?P<args>.*)', priority=5, block=True)

b50 = on_regex(r'^(?:b50|kkb)\s*(?P<args>.*)', priority=1, block=True)


@scorelist.handle()
async def scorelist_handled(event: Event, matcher: Matcher, groups: dict = RegexDict(), reply: Reply = reply):
    """处理命令: xxx完成表/xxx进度/xxx列表"""
    return  # 暂未实现，暂时忽略


@b50.handle()
async def b50_handled(event: Event, matcher: Matcher, groups: dict = RegexDict(), reply: Reply = reply):
    """处理命令: xxxb50/xxxkkb xxx"""
    # 低内存模式，短路拦截
    if config.LOW_MEMORY_MODE:
        if config.LOW_MEMORY_TIP:
            await matcher.finish(config.LOW_MEMORY_TIP)
        if config.LOW_MEMORY_TIP is None:
            await matcher.finish(await reply("error.low_memory"))
        return

    args_text = groups.get("args", "").strip()
    sender_user_id = int(event.get_user_id())

    # 解析命令参数
    parsed_uid, target_server = get_args(args_text)
    scope: ServerScope = target_server or ServerScope.CN

    if scope == 'ALL':
        await matcher.finish(await reply("b50.all_not_supported"))
        return

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
            return int(mu.qq) if mu else None
        
        # parsed_qq = await get_qq_from_tg_uid(parsed_uid) if parsed_uid else None
        parsed_qq = None  # Telegram 目前不支持文本参数解析 QQ，预留接口但暂不启用
        sender_qq = await get_qq_from_tg_uid(sender_user_id)
        
        if from_ := getattr(event, "from_", None):
            sender_username = from_.username or from_.first_name or "maimai"
            
        # 预留给 TG 适配：从 entities 中提取 text_link 或 mention 的 user_id
        # at_uid = ...
        # at_username = ...
        at_qq = None  # Telegram 暂不支持 at
        pass

    # 确定最终被查询人 (优先级：at 目标 > 文本传参 > 发送者自己)
    target_qq = at_qq or parsed_qq or sender_qq
    is_querying_self = target_qq == sender_qq
    if target_qq is None:
        logger.warning(f"未能解析出目标 QQ，无法继续执行 b50 命令。平台：{type(event)}")
        await matcher.finish(await reply("b50.qq_parsing_failed"))
        return
    try:
        target_mu = await services.check_mu(target_qq)
    except ValueError as e:
        await matcher.finish(str(e))
        return
    
    if scope in [ServerScope.CN, ServerScope.ALL]:
        try:
            target_mu, report = await sync.check_sync_cn(target_mu, ignore_cache_expire=True)
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
                    sync_payload += [("text", await reply("b50.drawing"))]
                    await build_msg(matcher, event, sync_payload, tag='send')
                else:
                    # 查询他人：简化提示
                    await build_msg(matcher, event, [
                        ("at", (sender_username, sender_user_id)), ("text", await reply("b50.other_updated")), ("text", reply("b50.drawing"))
                    ], tag='send')
              
            else:
                await build_msg(matcher, event, [
                    ("at", (sender_username, sender_user_id)), ("text", await reply("b50.drawing"))
                ], tag='send')
                
        except Exception as e:
            logger.warning(f"强制刷新水鱼数据失败: {e}")

    target_maiuser = target_mu.to_utils()

    # 获取 services 内已完成 provider 过滤和 ORM 转换的 B50 DTO
    if scope == ServerScope.ALL:
        # 目前不兼容 ALL 混合模式
        await matcher.finish(await reply("b50.all_not_supported"))
        return
    b50_data = await services.refactoring.b50.get_b50_data(target_qq, scope)

    if not (b50_data.b35 or b50_data.b15):
        # 无谱面数据
        if scope == ServerScope.CN:
            await build_msg(matcher, event, [("text", await reply("b50.no_cn_data"))], tag='finish')
        elif scope == ServerScope.JP:
            await build_msg(matcher, event, [("text", await reply("b50.no_jp_data"))], tag='finish')
        return

    # 绘制 b50
    img = image_gen.draw_b50_data(
        b50_data,
        username=target_maiuser.username,
        avatar=await network.get_qq_avatar(target_qq, spec=100),
        line_width=4,
    )
    img_bytes = image_gen.get_image_bytes(img)
    
    final_payload = [
        ("at", (sender_username, sender_user_id)),
        ("image", img_bytes)
    ]
    await build_msg(matcher, event, final_payload, tag='finish')
