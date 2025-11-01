import yaml
import random
from datetime import datetime

from nonebot import require, logger, on_regex
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, Message

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file as get_data_file
from nonebot_plugin_localstore import get_plugin_cache_dir as get_cache_dir

from .default import REBIRTH_DATA
from .history import RebirthHistory
from .map_build import map_build


__plugin_meta__ = PluginMetadata(
    name="自助投胎",
    description="一个 QQ 群的自助投胎小游戏插件。",
    usage="发送'投胎'即可参与"
)


rebirth_last_times: dict[int, datetime] = dict()


rebirth = on_regex(r"^投胎$", rule=to_me())

@rebirth.handle()
async def _(event: MessageEvent, matcher: Matcher):
    # 获取基本信息S
    user_id: int = event.user_id
    now_time: datetime = datetime.now()
    # 读取冷却配置
    rebirth_cd: int = 60  # todo: 接入 Nonebot2 Config
    # 读取用户数据
    user_data_path = get_data_file(f"rebirth_user_data_{str(user_id)}.npz")
    user_data = RebirthHistory(user_data_path)

    # 处理投胎冷却
    last_time: datetime = rebirth_last_times.get(user_id, datetime.min)
    delta_seconds = (now_time - last_time).total_seconds()
    if delta_seconds < rebirth_cd:
        await matcher.finish(f"让小梨休息一下吧！请等待{int(rebirth_cd - delta_seconds)}秒后再玩吧")
        return
    # 读取区域数据
    rebirth_data_path = get_data_file("rebirth_data.yml")
    if not rebirth_data_path.exists():
        # 初始化区域数据文件
        with open(rebirth_data_path, 'w', encoding='utf-8') as f:
            f.write(REBIRTH_DATA)
    with open(rebirth_data_path, 'r', encoding='utf-8') as f:
        try:
            rebirth_data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"区域数据读取失败。{e}")
            rebirth_data = yaml.safe_load(REBIRTH_DATA)
    region_city_ratio: float = rebirth_data.get('city_ratio', 0.7)
    region_datas: list[dict] = rebirth_data.get('country', [])
    region_names = [r['region'] for r in region_datas]
    region_populations = [r['population'] for r in region_datas]
    region_male_ratios = {r['region']: r['male_ratio'] for r in region_datas}

    # 投胎结果生成
    result_region = random.choices(region_names, weights=region_populations, k=1)[0]
    result_gender = "男" if random.random() < region_male_ratios.get(result_region, 1) else "女"
    result_location = "城市" if random.random() < region_city_ratio else "农村"
    # 更新用户数据
    user_data.add_record(result_region, result_location, result_gender)
    # 更新冷却时间
    rebirth_last_times[user_id] = now_time
    if llt := len(rebirth_last_times) > 100:
        # 清理超过60s的冷却记录，防止字典无限增长
        new = {u: t for u, t in rebirth_last_times.items() if (now_time - t).total_seconds() < rebirth_cd}
        rebirth_last_times.clear()
        rebirth_last_times.update(new)
        logger.info(f"清理了过期的投胎冷却记录：{str(llt)} -> {str(len(new))} (del {str(llt - len(new))}")
        del new

    # 绘制图片
    img = map_build(
        region_datas={n: user_data.get_count(n) for n in region_names},
        output_folder_path=get_cache_dir('rebirth_images')
    )

    # 发送结果
    result = f"""投胎成功！

第{user_data.get_total_count()}次投胎，您投胎成了{result_region}{result_location}的{result_gender}孩。"""

    message = [ MessageSegment.at(event.user_id), MessageSegment.text(result) ]
    if img: message.append(MessageSegment.image(img))
    await matcher.finish(Message(message))