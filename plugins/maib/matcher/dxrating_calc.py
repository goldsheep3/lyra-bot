import re

from nonebot.params import RegexGroup
from nonebot.internal.matcher import Matcher

from .. import utils, services
from ..utils import MaiChart, MaiChartAch
from ..constants import RATE_ALIAS, DIFFICULTY_MAP
from . import i18n_data, i18n, reply, ra_calc

# --- ra_calc ---

@ra_calc.handle()
async def ra_calc_handled(matcher: Matcher, groups: tuple = RegexGroup(), _i18n = i18n):
    """处理命令: ra 13.2 100.1000"""
    i18n_data.set(_i18n)

    info, rate = groups
    level: float = 0

    # 先解析 rate
    try:
        achievement = float(rate)
    except (ValueError, TypeError):
        achievement = RATE_ALIAS.key(rate.lower()) or -100

    # 1. 尝试以定数形式解析
    try:
        level = float(info)
    except (ValueError, TypeError):
        pass

    # 2. 判断定数是否越界，越界则解析为纯数字 id
    if level > 20:
        level = 0  # 大于 20 则一定不为定数，驳回上述解析
        try:
            shortid = int(info)
            mai = await services.get_mdt.id(shortid)
        except (ValueError, TypeError):
            mai = None
        if mai and mai.charts:
            level = mai.charts[-1].lv  # 取最高难度的定数

    # 3. 尝试以 id11451/info11451/id114514紫 形式解析
    if level == 0:
        # 通过正则提取 id
        match = re.search(r'\d+', info)
        diff_info = re.search('[绿黄红紫白]', info)
        if match and any([
            'id' in info.lower(),
            'info' in info.lower(),
            diff_info,
        ]):
            level_str = match.group(0)
            try:
                shortid = int(level_str)
                mai = await services.get_mdt.id(shortid)
            except (ValueError, TypeError):
                mai = None
            if mai:
                charts = mai.charts
                s = diff_info.group(0) if diff_info else ''
                diff = DIFFICULTY_MAP.key(s) or None
                if diff:
                    # 指定了难度颜色，尝试匹配
                    for c in charts:
                        if c.difficulty == diff:
                            level = c.lv
                            break
                level = level if level else charts[-1].lv

    # 4. 尝试解析 歌名/别名
    if level == 0:
        pass  # todo: 未实现 歌名/别名解析

    # 解析结束
    if level == 0:
        await matcher.finish(reply("rc.failed"))
        return

    # 调用 MaiChart 计算 DX Rating
    chart = MaiChart(shortid=0, difficulty=0, lv=level)
    chart.set_ach(MaiChartAch(shortid=0, difficulty=0, server="JP", achievement=achievement))
    ra = chart.get_dxrating()

    msg = reply("rc.success", level=level, achievement=f"{achievement:.4f}", ra=ra)
    if achievement >= 100.5:
        msg += '\n' + reply("rc.excluding_ap_bouns")
    await matcher.finish(msg)
