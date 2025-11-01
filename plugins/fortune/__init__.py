import re
from datetime import datetime
from typing import Dict, List

from nonebot import require, logger
from nonebot.rule import to_me
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.internal.matcher import Matcher
from nonebot.internal.permission import Permission

from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file

from .core import get_fortune, get_fortunes, get_text_index
from .msg import build_fortune_message
from .default import SUB_FORTUNE_DEFAULT
from .history import save_fortune_history
from .lib import load_yaml_data


__plugin_meta__ = PluginMetadata(
    name="简单运势",
    description="一个基于MD5哈希的运势查询插件。",
    usage="发送「今日运势」「运势」「抽签」「签到」「打卡」即可获得今日专属运势。",
)


on_fortune = on_regex(r"^(今日运势|运势|抽签|签到|打卡)$", block=True)

@on_fortune.handle()
async def _(event: MessageEvent, matcher: Matcher):
    # 获取基本信息
    user_id: str = str(event.user_id)
    group_id: int = getattr(event, "group_id", -1)
    today: datetime = datetime.now()

    # 尝试根据群号获取运势规则
    try:
        main_desc_data = load_yaml_data(get_data_file("main_fortune_desc.yml"), {}, logger)
        if not main_desc_data:
            """覆写默认主运势描述数据"""
            from .default import DESC_DEFAULT
            with open(get_data_file("main_fortune_desc.yml"), 'w', encoding='utf-8') as f:
                f.write(DESC_DEFAULT.strip())
            main_desc_data = load_yaml_data(get_data_file("main_fortune_desc.yml"), {}, logger)
        default_sub_titles = [item.strip() for item in SUB_FORTUNE_DEFAULT[4:].split(",")]
        if group_id < 0:
            sub_titles = default_sub_titles
        else:
            sub_titles_data: Dict[int, List[str]] = load_yaml_data(get_data_file("sub_fortune_titles.yml"), {}, logger)
            sub_titles = sub_titles_data.get(group_id, default_sub_titles)
    except Exception as e:
        logger.error(f"获取本地运势数据时发生错误。{e}")
        return
    # 运势判定并生成消息
    try:
        main_title = get_fortune(user_id, today)
        sub_fortunes = get_fortunes(user_id, today, sub_titles)
        output = build_fortune_message(main_title, sub_fortunes, main_fortune_desc=main_desc_data)
    except Exception as e:
        logger.error(f"生成运势时发生错误。{e}")
        return
    # 保存运势数据
    history_path = get_data_file(f"fortune_history_data_{user_id}.csv")
    save_fortune_history(history_path, today, group_id, list(sub_titles), logger)
    # 发送消息
    await matcher.finish(MessageSegment.text(output))


on_fortune_setting = on_regex(r"^运势\s*(\S{2})(?:\s+(\S+))?$",
                              rule=to_me(), permission=Permission(GROUP_ADMIN, GROUP_OWNER), block=True)

@on_fortune_setting.handle()
async def _(event: MessageEvent, matcher: Matcher):
    def wlog(message: str, group: int, user: str, time: datetime):
        with open(get_data_file("op_edit.log"), 'a', encoding='utf-8') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{str(group)}] {message} (from {user})\n")
        logger.info(f"[{str(group)}] {message} (from {user})")

    # 获取基本信息
    user_id: str = str(event.user_id)
    group_id: int = getattr(event, "group_id", -1)
    today: datetime = datetime.now()

    sub_titles_data: Dict[int, List[str]] = load_yaml_data(get_data_file("sub_fortune_titles.yml"), {}, logger)

    match = re.search(r"^运势\s*(\S{2})(?:\s+(\S+))?$", str(event.get_message()))
    action = match.group(0)
    if action in ("配置","设置","查看"):
        sub_titles = sub_titles_data.get(group_id, [item.strip() for item in SUB_FORTUNE_DEFAULT[4:].split(",")])
        output = f"小梨来啦！现在 {str(group_id)} 的特别运势包含以下几个项目：\n" + ";".join(sub_titles) + ";"
        wlog(f"查看运势配置: {";".join(sub_titles)};", group_id, user_id, today)
        await matcher.finish(MessageSegment.text(output))

    elif action in ("添加","新增"):
        sub_titles = sub_titles_data.get(group_id, [item.strip() for item in SUB_FORTUNE_DEFAULT[4:].split(",")])
        new_title = match.group(1)
        if new_title in sub_titles:
            await matcher.finish(MessageSegment.text(f"小梨提醒你，「{new_title}」已经存在啦！不要重复添加哟。"))
            return
        sub_titles.append(new_title)
        sub_titles_data[group_id] = sub_titles
        with open(get_data_file("sub_fortune_titles.yml"), 'w', encoding='utf-8') as f:
            import yaml
            yaml.dump(sub_titles_data, f, allow_unicode=True)
        wlog(f"添加运势项目: {new_title};", group_id, user_id, today)
        await matcher.finish(MessageSegment.text(f"小梨已经帮你添加「{new_title}」到特别运势项目里啦！"))

    elif action in ("删除",):
        sub_titles = sub_titles_data.get(group_id, [item.strip() for item in SUB_FORTUNE_DEFAULT[4:].split(",")])
        new_title = match.group(1)
        if new_title not in sub_titles:
            await matcher.finish(MessageSegment.text(f"小梨提醒你，「{new_title}」本就不存在哦！"))
            return
        sub_titles.remove(new_title)
        sub_titles_data[group_id] = sub_titles
        with open(get_data_file("sub_fortune_titles.yml"), 'w', encoding='utf-8') as f:
            import yaml
            yaml.dump(sub_titles_data, f, allow_unicode=True)
        wlog(f"删除运势项目: {new_title};", group_id, user_id, today)
        await matcher.finish(MessageSegment.text(f"小梨已经帮你删除「{new_title}」啦！"))

    elif action in ("帮助",):
        await matcher.finish(MessageSegment.text("""想调整小梨的特别运势项目，请见：
查看配置：发送“运势 配置/设置/查看”
添加项目：发送“运势 添加/新增 <项目名称>”
删除项目：发送“运势 删除 <项目名称>”
不同群聊相同名称的运势项目结果相同哦。"""))

    else:
        return
