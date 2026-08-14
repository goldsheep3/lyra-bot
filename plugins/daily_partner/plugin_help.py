# lyra-plugin-help 
# with i18n support
from pathlib import Path
from nonebot import on_regex
from plugins.nonebot_plugin_i18n import use_i18n, reply, current_i18n_data as i18n_data

i18n_dir = Path(__file__).parent / "assets" / "i18n"
i18n = use_i18n(i18n_dir)

_help = on_regex(r"^(帮助|help)\s*(今日老婆|jrlp)$", priority=10, block=True)

@_help.handle()
async def _(_i18n = i18n):
    i18n_data.set(_i18n)
    msg = f"Lyra's Help | {reply("plugin.code")}({reply("plugin.name")})\n\n{reply("plugin.help")}".strip()
    await _help.finish(msg)
