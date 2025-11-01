from datetime import datetime
from typing import Dict, List

from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot import require, logger

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file

from .core import get_fortune, get_fortunes, get_text_index
from .msg import build_fortune_message
from .default import sub_fortune_default
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
            from .default import desc_yml_default
            with open(get_data_file("main_fortune_desc.yml"), 'w', encoding='utf-8') as f:
                f.write(desc_yml_default.strip())
            main_desc_data = load_yaml_data(get_data_file("main_fortune_desc.yml"), {}, logger)
        default_sub_titles = tuple([item.strip() for item in sub_fortune_default[4:].split(",")])
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
    history_path = get_data_file("fortune_history.csv")
    save_fortune_history(history_path, today, group_id, user_id, list(sub_titles), logger)
    # 发送消息
    await matcher.finish(MessageSegment.text(output))
