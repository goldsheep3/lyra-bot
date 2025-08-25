from datetime import datetime

from nonebot import logger

from .utils import IDData, RadarData, mask_group_id, mask_user_name


async def cmd_query(group_id, jt_code):

    city_code = '""'
    try:
        city_code = IDData().is_whitelisted(group_id)
        jt = await RadarData().get_csjt(city_code, jt_code)
    except (KeyError, ValueError):
        logger.info(f"城市/机厅不存在。city_code: {city_code}, jt_code: {jt_code}")
        return None

    try:
        now_datetime = datetime.now()
        now_day = now_datetime.day
        from_group = mask_group_id(jt['from'].get('group'))
        from_user = mask_user_name(jt['from'].get('user'))
        if now_day == jt['day']:
            return f"Cryrin提醒您: {city_code}-{jt['name']} 可能 {jt['card']} 卡" + \
                f"(更新时间:{jt['time']}, 来自{from_group}的{from_user})。"
        else:
            return f"Cryrin提醒您: {city_code}-{jt['name']} 今日未更新。"
    except (KeyError, ValueError):
        logger.warning(f"发生Key/ValueError，信息有误。city_code: {city_code}, jt_code: {jt_code}, jt: {jt}")
        return "Cryrin好像出问题了……请帮小梨联系bot管理员吧qwq"

async def cmd_query_all(group_id):
    ...
