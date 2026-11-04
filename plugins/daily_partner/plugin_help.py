# lyra-plugin-help 
# with i18n support
from pathlib import Path
from nonebot import on_regex
from nonebot_plugin_locales import Reply, locales_init

i18n_dir = Path(__file__).parent / "assets" / "i18n"
reply = locales_init(i18n_dir)

_help = on_regex(r"^(帮助|help)\s*(今日老婆|jrlp)$", priority=10, block=True)

@_help.handle()
async def _(reply: Reply = reply):
    code = await reply("plugin.code")
    name = await reply("plugin.name")
    help_text = await reply("plugin.help")
    msg = f"Lyra's Help | {code}({name})\n\n{help_text}".strip()
    await _help.finish(msg)
