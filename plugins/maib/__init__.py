import requests

from nonebot import on_startswith, on_regex
from nonebot.plugin import PluginMetadata
from nonebot.rule import to_me

from .mai2_music import MusicList, Music

# from .config import Config

__plugin_meta__ = PluginMetadata(
    name="lyra-maib",
    description="一个QQ群的 舞萌DX 功能机器人。",
    usage="使用 help 查询使用方法",
    # config=Config,
)

# config = get_plugin_config(Config)

# 初始化歌曲数据库
obj = requests.get('https://www.diving-fish.com/api/maimaidxprober/music_data').json()
total_list: MusicList = MusicList(obj)
for __i in range(len(total_list)):
    total_list[__i] = Music(total_list[__i])
    # for __j in range(len(total_list[__i].charts)):
    #     total_list[__i].charts[__j] = Chart(total_list[__i].charts[__j])


# maib50 - 生成b50成绩图
maib50 = on_startswith(msg=("b50", "maib50"), rule=to_me(), priority=2, block=True)

# today_mai2 - 「今日舞萌」赛博卜算
today_mai2 = on_startswith(msg=("今日舞萌", "今日mai"), rule=to_me(), priority=2, block=True)

# id_search - id查歌
id_search = on_regex(r"id\s*(\d+)", priority=2, block=True)

# score_search - id查成绩
score_search = on_regex(r"score\s*(\d+)", priority=2, block=True)

# song_which - 模糊查歌
song_which = on_regex(r"(.+?)是什么歌", priority=2, block=True)
