from nonebot.plugin.on import on_regex
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher

from libs.HelpContent import lyra_helper

__plugin_meta__ = PluginMetadata(
    name="Lyra Help",
    description="小梨的「帮助」信息",
    usage="发送 '帮助' 或 'Help' 获取小梨的帮助信息。",
)


lyra_help = on_regex(pattern=r"帮助\s*(.*)", rule=to_me(), priority=1000, block=True)


@lyra_help.handle()
async def help_handler(matcher: Matcher):
    help_command = matcher.state["_matched"].group(1).lower().strip()
    help_text = "Lyra的帮助菜单 - "

    if not help_command:
        help_text += "主页\n在 帮助 后添加模块关键字获取详细信息（如：“帮助 whatfood”）。\n\n"
        for helper in lyra_helper.get_all_help_contents():
            help_text += f"◎ {helper.title} - {helper.description}\n"
        await matcher.finish(help_text)
        return

    helper = lyra_helper.get_help_content(help_command)
    if not helper:
        await matcher.finish(F"小梨没有找到与“{help_command}”对应的帮助模块哦，检查一下关键字是否正确吧！")
        return
    help_text += f"{helper.title}\n\n"
    help_content = '\n'.join(helper.help_content)
    help_text += help_content
    await matcher.finish(help_text)
    return
