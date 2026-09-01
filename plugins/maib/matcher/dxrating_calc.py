import re
from typing import Optional

from nonebot import on_regex
from nonebot.params import RegexDict
from nonebot.internal.matcher import Matcher
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Event as OneBotV11Event
from nonebot.adapters.telegram import Event as TGEvent

from .. import services
from ..utils import get_dxrating_old
from ..utils.map import AchievementMap, Difficulties
from . import i18n_data, i18n, reply


ra_calc = on_regex(r"^ra\s+(?P<level>\S+)(?:\s+(?P<achievement>\S+))?\s*$", priority=5, block=True)

pattern = r"^id(?P<id>\d+)(?P<color>[蓝绿黄红紫白彩])$"

@ra_calc.handle()
async def ra_calc_handled(event: Event, matcher: Matcher, groups: dict[str, Optional[str]] = RegexDict(), _i18n = i18n):
    """处理命令: ra 13.2 100.1000"""
    i18n_data.set(_i18n)
    
    # 解析 achievement
    achievement: float | None
    raw_achievement: str = (groups.get("achievement") or "").rstrip("%")
    if raw_achievement == "":
        # 参数为空，输出多个
        achievement = None
    elif raw_achievement.replace('.', '', 1).isdigit():
        # 可解析为浮点数
        achievement = float(raw_achievement)
        # achievement = int(achievement * 10000)  -> 后续重构为 INT 1,010,000 存储格式
    else:
        # 按照别名解析
        achievement = AchievementMap.find_achievement(raw_achievement)
        if achievement is None:
            await matcher.finish(reply("rc.achievement_invalid", achievement=raw_achievement))
            return
        else:
            achievement = achievement / 10000  # AchievementRateInfo 中存储的是`1,010,000`格式的整数，除以 10000 得到浮点计算结果

    # 解析 level
    raw_level: str = groups.get("level") or ""
    if raw_level.lower() in ["help", "帮助"]:
        await matcher.finish(reply("rc.help"))
        return
    elif raw_level.replace('.', '', 1).isdigit():
        # 可解析为浮点数
        level = float(raw_level)
        if not 15 >= level >= 1:
            # 似乎是不支持的定数范围
            await matcher.finish(reply("rc.level_failed"))
            return
    elif match := re.match(pattern, raw_level):
        # 解析 `id11951紫` 形式
        shortid = int(match.group("id"))
        difficulty = Difficulties.find_id(match.group("color")) or 5  # MASTER

        mdt = await services.get_mdt.id(shortid)
        if mdt is None:
            await matcher.finish(reply("rc.maidata_invalid"))
            return
        
        # TODO 这里未来可以考虑获取一下用户的谱面成绩和对应版本地板，来确定能不能上分
        chart = mdt.to_utils(achs_user_id=None).get_chart(difficulty)
        if chart is None:
            await matcher.finish(reply("rc.maidata_invalid"))
            return
        level = chart.lv

    else:
        # 解析失败
        await matcher.finish(reply("rc.level_invalid"))
        return

    level = round(level, 1)
    
    if achievement is None:
        lines = [reply("rc.success.tip")]
        for rate, _achievement in (
            ("SSS+", 100.5),
            ("SSS", 100.0),
            ("SS+", 99.5),
            ("SS", 99.0),
            ("S+", 98.0),
            ("S", 97.0),
        ):
            ra = get_dxrating_old(_achievement, level, 0)
            lines.append(reply("rc.success.blur", level=level, rate=rate, ra=ra))
        lines.append(reply("rc.excluding_ap_bouns"))
        await matcher.finish("\n".join(lines))
        return
    else:
        ra = get_dxrating_old(achievement, level, 0)
        lines = [
            reply("rc.success.tip"),
            reply("rc.success.common", level=level, achievement=f"{achievement:.4f}", ra=ra),
            reply("rc.excluding_ap_bouns") if achievement >= 100.5 else ""
        ]
        await matcher.finish("\n".join(lines).strip('\n'))
        return

