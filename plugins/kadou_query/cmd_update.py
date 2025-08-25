from datetime import datetime

from nonebot import logger

from .utils import IDData, RadarData


async def _card_update(group_id, jt_code, card_number, sender_name, adjust: bool):

    city_code = '""'
    try:
        city_code = IDData().is_whitelisted(group_id)
        rd = await RadarData().get_data()
        cs = await RadarData().get_csjt(city_code)
        jt = await RadarData().get_csjt(city_code, jt_code)
    except (KeyError, ValueError):
        logger.info(f"城市/机厅不存在。city_code: {city_code}, jt_code: {jt_code}")
        return None

    now_datetime = datetime.now()
    now_day = now_datetime.day
    now_time = now_datetime.strftime("%H:%M")

    try:
        if adjust:
            # 调整数据
            current_card = jt.get('card', 0)
            if current_card < 0:
                current_card = 0
            new_card = current_card + card_number
        else:
            new_card = card_number
        if new_card < 0:
            return "Cryrin提醒您: 人一定要是人，不能是不是人（"

        # 更新数据
        jt['name'] = jt['name']  # 保持名称不变，但仍然进行一次写入
        jt['card'] = new_card
        jt['time'] = now_time
        jt['day'] = now_day
        jt['from'] = {"user": sender_name, "group": group_id}

        cs[jt_code] = jt
        rd[city_code] = cs
        logger.debug(f"更新数据成功。radar_data: {rd}")
        await RadarData().set_data(rd)

        jt_new: dict = await RadarData().get_csjt(city_code, jt_code)

    except (KeyError, ValueError):
        logger.info(f"发生Key/ValueError，信息有误。radar_data: {RadarData().get_data()}")
        return None

    return f"Cryrin收到啦! {city_code}-{jt_new['name']} 现在 {jt_new['card']} 卡。"


async def cmd_update(group_id, jt_code, card_number, sender_name):
    return await _card_update(group_id, jt_code, card_number, sender_name, adjust=False)


async def cmd_adjust(group_id, jt_code, card_number_adjust, sender_name):
    return await _card_update(group_id, jt_code, card_number_adjust, sender_name, adjust=True)

