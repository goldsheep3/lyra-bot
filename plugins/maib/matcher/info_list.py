import re
from typing import Optional, Any, Sequence

from nonebot import logger, on_regex
from nonebot.params import RegexGroup, RegexDict
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event

# -- platform adapter --
from nonebot.adapters.onebot.v11 import (Event as OneBotV11Event,)

from nonebot.adapters.telegram import (Event as TGEvent,)

from .. import config, utils, services, image_gen, network
from ..utils.report import build_diff_report
from ..constants import server, VERSION_MAP
from . import i18n_data, i18n, reply,  sync
from .context import get_args
from .message import build_msg
from ..services import get_mct_list


# --- regex patterns ---

SCORELIST_PATTERN_ARG = re.compile(
    r"(?:(?:代|极|極|将|神|舞舞))?$",
    re.VERBOSE
)

SCORELIST_PATTERN_LEVEL = re.compile(
    r"^(\d+(?:\.\d+)?\+?)",
    re.VERBOSE
)

SCORELIST_PATTERN_VERSION = re.compile(
    r"^(?:[a-zA-Z]{1,6}(?:\+)?|dx\d{4}[一-龥]{1,2})",
    re.VERBOSE
)

SCORELIST_PATTERN_GENRE = re.compile(
    r"^(.+?)",
    re.VERBOSE
)



# --- matcher ---

scorelist = on_regex(r'^(?P<target>.+?)\s*(?:完成表|进度|列表)(?P<args>.*)', priority=5, block=True)

b50 = on_regex(r'^(?:b50|kkb)\s*(?P<args>.*)', priority=1, block=True)


@scorelist.handle()
async def scorelist_handled(event: Event, matcher: Matcher, groups: dict = RegexDict(), _i18n = i18n):
    """处理命令: xxx完成表/xxx进度/xxx列表"""
    i18n_data.set(_i18n)
    
    target = groups.get("target", "").strip()
    args_text = groups.get("args", "").strip()
    parsed_uid, target_server = get_args(args_text) if args_text else (None, None)
    parsed_uid = parsed_uid or int(event.get_user_id())
    server = target_server if (target_server and target_server != 'ALL') else 'CN'
    
    # 解析参数
    arg_match = SCORELIST_PATTERN_ARG.match(target)
    arg = arg_match.group(0) if arg_match and arg_match.group(0) else ""
    content = target[:-len(arg)].strip() if arg else target.strip()
    
    parser_status: bool = False
    mca_list: Sequence = []
    # 定数筛选
    level_matched = SCORELIST_PATTERN_LEVEL.match(content)
    if level_matched and parser_status is False:
        level = level_matched.group(1)
        # 13.6+  <- 会被匹配但不合法
        if level.endswith('+') and '.' in level:
            pass
        # 13.6  <- 定数筛选
        if level.endswith('.'):
            level_value = float(level[:-1])
            mca_list = await get_mct_list.level(level_value, server, achs_user_id=parsed_uid)
            parser_status = True
        # 13 或 13+  <- 定数范围筛选
        else:
            # 这里需要考虑 + 的分界线，当前先不考虑旧版按新版 .6 计算，后续增加判断
            plus = 6
            if level.endswith('+'):
                _l = int(level.rstrip('+'))
                level_range = (float(_l + plus * 0.1), float(_l + 0.9))
            else:
                _l = int(level)
                level_range = (float(_l), float(_l + (plus-1) * 0.1))
            mca_list = await get_mct_list.level(level_range, server, achs_user_id=parsed_uid) 
            parser_status = True
    
    # 版本筛选
    version_matched = SCORELIST_PATTERN_VERSION.match(content)
    if version_matched and parser_status is False:
        version = version_matched.group(0)
        pass
    
    # 流派筛选
    genre_matched = SCORELIST_PATTERN_GENRE.match(content)
    if genre_matched and parser_status is False:
        genre = genre_matched.group(1)
        pass
    
    # 解析失败
    if parser_status is False:
        await matcher.finish(reply("scorelist.invalid_format"))
        return
    
    # TODO: 处理 mca_list，生成完成表/进度/列表，并发送消息
    if not mca_list:
        await matcher.finish(reply("scorelist.no_data"))
        return
    
    # ...
    
    # 低内存模式，渲染 list_lite(还没写，先短路)，否则渲染完整成绩列表网格图片


@b50.handle()
async def b50_handled(event: Event, matcher: Matcher, groups: dict = RegexDict(), _i18n = i18n):
    """处理命令: xxxb50/xxxkkb xxx"""
    i18n_data.set(_i18n)

    # 低内存模式，短路拦截
    if config.LOW_MEMORY_MODE:
        if config.LOW_MEMORY_TIP:
            await matcher.finish(config.LOW_MEMORY_TIP)
        if config.LOW_MEMORY_TIP is None:
            await matcher.finish(reply("error.low_memory"))
        return

    args_text = groups.get("args", "").strip()
    sender_user_id = int(event.get_user_id())

    # 解析命令参数
    parsed_uid, target_server = get_args(args_text)
    server: server = target_server if (target_server and target_server != 'ALL') else 'CN'

    if target_server == 'ALL':
        await matcher.finish(reply("b50.all_not_supported"))
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
            return int(mu.user_id) if mu else None
        
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
        await matcher.finish(reply("b50.qq_parsing_failed"))
        return
    try:
        target_maiuser = (await services.check_mu(target_qq)).to_utils()
    except ValueError as e:
        await matcher.finish(str(e))
        return

    payload: list[tuple[str, Any]] = [("at", (sender_username, sender_user_id)), ("text", reply("b50.drawing"))]
    # extra. 查询内容含国服，强制刷新水鱼数据
    if server in ['CN', 'ALL']:
        try:
            report = await sync.get_sy_and_upload(target_qq, server)
            if report.has_changes:
                # 有变化，考虑查询者是否在查询自己，展示不同的报告细节
                if is_querying_self:
                    summary_text, diff_img = build_diff_report(report)
                    sync_payload: list[tuple[str, Any]] = [
                        ("text", f"已同步水鱼数据！以下是水鱼数据的同步详情：\n\n{summary_text}")
                    ]
                    if diff_img:
                        sync_payload.append(("image", image_gen.get_image_bytes(diff_img)))
                    await build_msg(matcher, event, sync_payload, tag='send')
                    await build_msg(matcher, event, payload, tag='send')
                else:
                    # 查询他人：简化提示
                    payload[1] = ("text", reply("b50.other_updated_drawing"))
                    await build_msg(matcher, event, payload, tag='send')
            else:
                await build_msg(matcher, event, payload, tag='send')
        except Exception as e:
            logger.warning(f"强制刷新水鱼数据失败: {e}")
        
        # 由于进行了更新，刷新 MaiUser 数据
        target_maiuser = (await services.check_mu(target_qq)).to_utils()
    else:
        await build_msg(matcher, event, payload, tag='send')


    # 确定版本并获取 achs 数据
    if server == 'ALL':
        # 目前不兼容 ALL 混合模式
        await matcher.finish(reply("b50.all_not_supported"))
        return
    current_version = VERSION_MAP.get_latest_version_id(server)
    cut_version = VERSION_MAP.get_cut_version(current_version)
    
    b35_achs, b15_achs = await services.get_b50(target_qq, server, cut_version)
    dxrating = sum([mca.dxrating for mca in (list(b35_achs) + list(b15_achs))])

    # 清洗谱面数据，构建绘图数据结构
    def _build_entries(achs: list[services.MaiChartAch]) -> list[tuple[utils.MaiData, int]]:
        entries = []
        for ach in achs:
            chart = ach.chart
            if not chart or not chart.maidata:
                continue
            maidata = chart.maidata.to_utils()
            maidata_chart = maidata.get_chart(chart.difficulty)
            if maidata_chart is None:
                continue
            maidata_chart.set_ach(ach.to_utils())
            entries.append((maidata, chart.difficulty))
        return entries

    b35_entries = _build_entries(list(b35_achs))
    b15_entries = _build_entries(list(b15_achs))

    if not (b35_entries or b15_entries):
        # 无谱面数据
        if server == 'CN':
            await build_msg(matcher, event, [("text", reply("b50.no_cn_data"))], tag='finish')
        elif server == 'JP':
            await build_msg(matcher, event, [("text", reply("b50.no_jp_data"))], tag='finish')
        return

    # 绘制 b50
    img = image_gen.draw_b50(
        b35_entries, b15_entries,
        current_version=current_version,
        server=server,
        user_name=target_maiuser.username,
        user_avatar=await utils.get_avatar(target_qq, spec=100),
        dxrating=dxrating,
        update_time=target_maiuser.get_formated_time(server),
        cn_level=1 if server == 'CN' else 0
    )
    img_bytes = image_gen.get_image_bytes(img)
    
    final_payload = [
        ("at", (sender_username, sender_user_id)),
        ("image", img_bytes)
    ]
    await build_msg(matcher, event, final_payload, tag='finish')

