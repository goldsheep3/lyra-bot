# lyra-plugin-help
from random import choice

from nonebot import on_regex
from nonebot.rule import to_me

from nonebot.adapters.telegram.event import Event as TGEvent


# Special Message List / 小梨的特殊消息列表
SPECIAL_MESSAGE = [
    "小梨喜欢你！",
]

# Plugin Information / 插件信息，填写插件名和功能简介
PLUGIN_INFO = [
    {"maib": "小梨音游核心，提供围绕 maimai 的各种功能。"},
    {"fortune": "运势占卜，提供每日运势、抽签等功能。"},
    {"what_food": "「吃什么」，提供食物随机抽选和评分功能。"},
    {"daily_partner": "支持「一夫一妻制」的「今日老婆」。"},
]

_PLUGIN_TEXT = ""


def get_plugin_text():
    global _PLUGIN_TEXT
    if not _PLUGIN_TEXT:
        lines = []
        for index, item in enumerate(PLUGIN_INFO, start=1):
            for plugin_name, description in item.items():
                space = "  " if index < 10 else " "
                lines.append(f"{index}.{space}{plugin_name}")
                lines.append(f"   {description}")
        _PLUGIN_TEXT = "\n".join(lines)
    return _PLUGIN_TEXT


# ==============================================================

_help = on_regex(r"^/?(帮助|help)$", priority=10, rule=to_me(), block=True)

@_help.handle()
async def _():
    await _help.finish("""
{{special_message}}

帮助 | LyraBot
输入 /help [功能] 获取对应功能的帮助信息。

{{plugin_text}}
""".strip().format(special_message=choice(SPECIAL_MESSAGE), plugin_text=get_plugin_text()))



_start = on_regex(r"/start", block=True)

@_start.handle()
async def _(event):
    platform_tip = ""
    
    # 平台适配器判断
    if isinstance(event, TGEvent):  
        platform_tip = "\n此外，LyraBot 音游相关功能集中在 maib 插件中，该插件需要绑定 QQ 账号，可以通过 /help maib 获取帮助信息。\n"
        
    await _start.finish("""
欢迎使用 LyraBot ！{special_message}

小梨Bot（LyraBot）是一个基于 NoneBot2 的多功能机器人，提供了丰富的娱乐和音游相关实用功能。
可以输入 /help 获取帮助信息。
{platform_tip}
[WARNING] LyraBot 目前处于测试阶段，功能可能不稳定，欢迎反馈问题和建议！
""".strip().format(special_message=choice(SPECIAL_MESSAGE), platform_tip=platform_tip))
