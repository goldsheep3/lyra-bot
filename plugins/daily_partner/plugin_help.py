# lyra-plugin-help
from nonebot import on_regex

_help = on_regex(r"^(帮助|help)\s*(今日老婆|jrlp)$", priority=10, block=True)


@_help.handle()
async def _():
    await _help.finish("""
LyraHELP | DailyPartner（今日老婆）

1. 今日老婆 / jrlp
   随机抽选一个「老婆」，每日一次，各群独立
2. 今日老公 / jrlg
   根据「今日老婆」的抽选结果，显示当前锚定的「老公」
3. 换老婆 / hlp
   重新抽选一个「老婆」（有次数限制）
4. 换老公 / hlg
   和当前的「老公」离婚（有次数限制）
5. 强娶 [QQ 或 at]
   尝试指定某个群友为你的「老婆」（有次数等限制）
6. 离婚 / lh
   和当前的「老婆」离婚（谨慎！后果自负）
7. 当老婆 / 不当老婆
   配置项：控制你是否可以参与抽选，以及是否可以被抽选
8. 娶bot / 不娶bot
   配置项：控制你是否可以娶该群的QQ官方机器人作为「老婆」

""".strip())
