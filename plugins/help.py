from typing import Dict, Tuple

from nonebot.plugin.on import on_regex
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher

__plugin_meta__ = PluginMetadata(
    name="Lyra Help",
    description="小梨的「帮助」信息",
    usage="发送 '帮助' 或 'Help' 获取小梨的帮助信息。",
)

# Help Contents: `模块名: (模块标题, 功能简介, 帮助内容)`
help_contents: Dict[str, Tuple[str, str, str]] = {
    "what_food": (
        "WhatFood (吃什么)",
        "“餐点”的随机抽选推荐(支持对“餐点”评分)",
        (
            "◎ 吃什么/喝什么\n"
            "  根据当前过滤条件随机推荐餐点，可在前面添加内容以修改小梨的回复内容\n"
            "◎ 吃这个 [餐点名称/ID] [*酒精状态=没有酒]/喝这个 [饮品名称/ID] [*酒精状态=没有酒]\n"
            "  添加新餐点或修改已有餐点酒精状态(有酒/没有酒)\n"
            "◎ 好吃吗/好喝吗 [餐点名称/ID] [*评分]\n"
            "  为餐点评分(1~5分，不填评分可查询当前分数)\n"
            "◎ 可以吃 [过滤条件]\n"
            "  设置餐点过滤(好的/能吃的/正常的/好玩的/猎奇的)\n"
            "◎ 吃什么排行榜/喝什么排行榜 [*页码=1]\n"
            "  查看餐点评分排行榜\n\n"
        )
    )
}
# Help Aliases: `别名: 模块名`
help_aliases = {
    "what_food": "what_food",
    "whatfood": "what_food",
    "吃什么": "what_food",
}


lyra_help = on_regex(pattern=r"帮助\s*(.*)", rule=to_me(), priority=1000, block=True)


@lyra_help.handle()
async def help_handler(matcher: Matcher):
    help_command = matcher.state["_matched"].group(1).lower().strip()
    help_text = "Lyra的帮助菜单 - "
    if not help_command:
        help_text += "主页\n在 帮助 后添加模块关键字获取详细信息（如：“帮助 whatfood”）。\n\n"
        for key, (title, desc, _) in help_contents.items():
            help_text += f"◎ {title} - {desc}\n"
    else:
        help_key = help_aliases.get(help_command)
        if not help_key:
            help_text = f"小梨没有找到与“{help_command}”对应的帮助模块哦，检查一下关键字是否正确吧！"
        else:
            title, _, content = help_contents[help_key]
            help_text += f"{title}\n\n{content}"
    await matcher.finish(help_text)
