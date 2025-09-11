import json
import aiofiles

from nonebot import require, logger
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store


ID_DATA_FILENAME = "kd_id_data.json"
ID_DATA_DEFAULT = { 'group_whitelist': { 852330597: '黑B' }, 'group_blacklist': [] }

RADAR_DATA_FILENAME = "kd_radar_data.json"
RADAR_DATA_DEFAULT = { "黑B": {
    "万": { "name": "万达广场3F大玩家", "card": 0, "time": None, "day": -1, "from": { "user": "Bot", "group": 1234567890 } },
    "百": { "name": "百货大楼6F快乐电堂", "card": 0, "time": None, "day": -1, "from": { "user": "Bot", "group": 1234567890 } },
    "北": { "name": "北方新天地4F智栋电玩城", "card": 0, "time": None, "day": -1, "from": { "user": "Bot", "group": 1234567890 } },
    "cc": { "name": "华美家居1F CCPark", "card": 0, "time": None, "day": -1, "from": { "user": "Bot", "group": 1234567890 } },
}}


class _UtilsData:
    def __init__(self, filename: str, default_data=None):
        self.filename = filename
        self.default_data = default_data
        self.path = store.get_plugin_data_file(filename)
        self.data = None  # 初始化为空，需异步读取

    async def load(self):
        try:
            async with aiofiles.open(self.path, "r", encoding="utf-8") as f:
                content = await f.read()
                self.data = json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(f"{self.filename}异常，已初始化")
            await self.set_data(self.default_data)

    async def get_data(self):
        await self.load()
        return self.data

    async def set_data(self, data=None):
        self.data = data if data else self.data
        async with aiofiles.open(self.path, "w", encoding="utf-8") as f:
            # json.dumps 不支持 encoding 参数
            await f.write(json.dumps(self.data, ensure_ascii=False, indent=2))

    async def default(self):
        logger.warning(f"{self.filename}异常，已初始化")
        await self.set_data(self.default_data)


class IDData(_UtilsData):
    def __init__(self):
        super().__init__(ID_DATA_FILENAME, ID_DATA_DEFAULT)

    async def get_whitelist(self):
        data = await self.get_data()
        return data.get('group_whitelist', {})

    async def get_blacklist(self):
        data = await self.get_data()
        return data.get('group_blacklist', [])

    def is_whitelisted(self, group_id: int) -> str | None:
        wl = self.get_whitelist()
        return wl.get(group_id, None)

    def is_blacklisted(self, group_id: int) -> bool:
        bl = self.get_blacklist()
        return group_id in bl

    def add_whitelist(self, group_id: int, city_code: str):
        wl = self.get_whitelist()
        wl[group_id] = city_code
        self.data['group_whitelist'] = wl

    def del_whitelist(self, group_id: int):
        wl = self.get_whitelist()
        if group_id in wl:
            del wl[group_id]
        self.data['group_whitelist'] = wl

    def add_blacklist(self, group_id: int):
        bl = self.get_blacklist()
        if group_id not in bl:
            bl.append(group_id)
        self.data['group_blacklist'] = bl

    def del_blacklist(self, group_id: int):
        bl = self.get_blacklist()
        if group_id in bl:
            bl.remove(group_id)
        self.data['group_blacklist'] = bl


class RadarData(_UtilsData):
    def __init__(self):
        super().__init__(RADAR_DATA_FILENAME, RADAR_DATA_DEFAULT)

    async def get_csjt(self, city_code=None, jt_code=None):
        await self.load()
        if city_code and jt_code:
            return self.data.get(city_code, {}).get(jt_code, {})
        elif city_code:
            return self.data.get(city_code, {})
        else:
            return self.data


def mask_group_id(group_id: int) -> str:
    group_str = str(group_id)
    # 确保长度足够，否则用0填充
    prefix = group_str[:2] if len(group_str) >= 4 else group_str[:2].ljust(2, '0')
    suffix = group_str[-2:] if len(group_str) >= 4 else group_str[-2:].rjust(2, '0')
    return f"{prefix}**{suffix}"


def mask_user_name(user_id: str) -> str:
    # 确保长度足够，否则用X填充
    prefix = user_id[0] if len(user_id) >= 2 else (user_id[0] if user_id else 'X')
    suffix = user_id[-1] if len(user_id) >= 2 else (user_id[-1] if user_id else 'X')
    return f"{prefix}**{suffix}"
