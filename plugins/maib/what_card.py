import re
import json
from datetime import datetime

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event, Bot
from nonebot import require

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store


def get_data(data, jt_code):
    jt = data.get(jt_code, {})
    if not jt:
        return None
    # 处理日重置逻辑
    now_day = datetime.now().day
    if now_day != jt.get('day', -1):
        jt['number'] = -114514
        jt['time'] = '今日未更新'
        jt['day'] = now_day
    return jt

def set_data(data, jt_code, number):
    jt = get_data(data, jt_code)
    if not jt:
        logger.warning(f"未找到 {jt_code} 的机厅数据")
        return None
    now = datetime.now()
    # 处理修改
    jt['number'] = number
    jt['time'] = f"{now.hour}:{now.minute}"
    jt['day'] = now.day
    data[jt_code] = jt
    return data


async def jtjk(event: Event, matcher):
    """排卡确定"""
    if str(event.group_id).strip() != "852330597":  # type: ignore
        return None

    # 指令解析逻辑
    # 支持格式如：.cc几、.百+1、万-2、北3、cc几、百几、万几、北几、cc2、百1、万3、北4
    msg = str(event.get_message()).strip()
    # 匹配指令
    m = re.match(r"[\.。]?\s*(cc|北|百|万)\s*(几|[+-]?\d+)?", msg)
    if m:
        in_code = m.group(1)
        in_num = m.group(2) if m.group(2) is not None else "几"
    else:
        return None  # 不提醒格式错误，直接忽略
    data_file = store.get_plugin_data_file("what_card-data.json")
    data_wr = None  # 标记是否需要覆写数据
    try:
        data = json.loads(data_file.read_text())
    except Exception:
        # 初始化数据
        data = dict()
        for c, n in [
            ('百', '黑B-百大6F快乐电堂'),
            ('万', '黑B-万达3F大玩家超乐场'),
            ('北', '黑B-北方新天地4F智栋电玩城'),
            ('cc', '黑B-华美家居1F CCPark')
            ]:
            data[c] = {
                "name": n,
                "number": -114514,
                "time": "今日未更新",
                "day": -1
            }
        data_wr = data.copy()  # 计划覆写初始化数据

    if (in_code in [".", "。"]) or (msg in [".all", "。all", "全部", "all"]):
        # 查看全部逻辑
        reply = "Cryrin提醒您, 当前各机厅卡数如下：\n"
        for c, jt in data.items():
            reply += f"黑B-{jt['name']}: {jt['number']} 卡 (更新时间:{jt['time']})\n"
        await matcher.finish(reply.strip())
    elif jt := get_data(data, in_code):
        # 验证 jt 数据
        try:
            if in_num == "几":
                await matcher.finish(f"Cryrin提醒您: 黑B-{jt['name']} 可能 {jt['number']} 卡(更新时间:{jt['time']})。")
            elif isinstance(in_num, int):
                data_wr = set_data(data, in_code, in_num)
            elif m_num := re.match(r"^([\+-]\d+)$", in_num):
                new_num = jt['number'] + int(m_num.group(1))  # 无论 m_num 是正负数都可以处理
                data_wr = set_data(data, in_code, new_num)
        except (ValueError, KeyError) as e:
            logger.error(f"处理输入 {in_code} {in_num} 时发生错误: {e}")
    # 判断是否需要回写
    if data_wr:
        # todo 计划验证data_wr格式
        data_file.write_text(json.dumps(data_wr, ensure_ascii=False, indent=2))
        jt = get_data(data_wr, in_code)
        if not jt:
            logger.error(f"覆写后未找到 {in_code} 的机厅数据！请检查数据文件！")
            return None
        await matcher.finish(f"Cryrin记住了: 黑B-{jt['name']} 当前为 {jt['number']} 卡。")

    # 不符合条件，忽略消息
    return None