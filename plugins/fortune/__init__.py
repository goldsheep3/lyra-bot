import yaml
from datetime import datetime
from typing import Dict, Tuple, Optional

from nonebot.internal.matcher import Matcher
from nonebot.plugin import on_regex, PluginMetadata
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot import require, logger

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file

from .core import get_fortune, get_fortunes, get_text_index
from .msg import build_fortune_message
from .default import sub_fortune_default


__plugin_meta__ = PluginMetadata(
    name="简单运势",
    description="一个基于MD5哈希的运势查询插件。",
    usage="发送「今日运势」「运势」「抽签」「签到」「打卡」即可获得今日专属运势。",
)


def load_yaml_data(file_path, default_data=None, logger_=None) -> Optional[dict]:
    """安全加载YAML数据文件"""
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            if logger_:
                logger_.warning(f"数据文件不存在: {file_path}")
            return default_data if default_data is not None else {}
    except Exception as e:
        if logger_:
            logger_.error(f"加载数据文件失败 {file_path}: {e}")
        return default_data if default_data is not None else {}


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
            sub_titles_data: Dict[int, Tuple[str]] = load_yaml_data(
                get_data_file("sub_fortune_titles.yml"), {}, logger)
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
    if not history_path.exists():
        with open(history_path, 'w', encoding='utf-8') as f:
            f.write("date,group_id,user_id,sub_fortunes\n")
    # todo
    with open(history_path, 'a', encoding='utf-8') as f:
        sub_fortunes_str = ";".join(sub_titles)
        f.write(f"{today.strftime('%Y%m%d')},{group_id},{user_id},{sub_fortunes_str}\n")
    # 发送消息
    await matcher.finish(MessageSegment.text(output))
