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

from .default import REBIRTH_DATA_CN


__plugin_meta__ = PluginMetadata(
    name="自助投胎",
    description="一个 QQ 群的自助投胎小游戏插件。",
    usage="发送'投胎中国'即可参与"
)


rebirth_cn = on_regex(r"^投胎中国$", rule=to_me())

@rebirth_cn.handle()
async def _(event: MessageEvent, matcher: Matcher):
    # 获取基本信息
    user_id: int = event.user_id
    now_time: datetime = datetime.now()
    # 读取冷却配置
    rebirth_cd: int = 120  # 未接入 Config 机制，直接使用默认值
    # 读取用户数据
    user_data_path = get_data_file(f"rebirth_user_data_{str(user_id)}.yml")
    if not user_data_path.exists():
        with open(user_data_path, 'w', encoding='utf-8') as f:
            yaml.dump({"last_time": "20030101-0400", "history": {}}, f, allow_unicode=True)
    with open(user_data_path, 'r', encoding='utf-8') as f:
        try:
            user_data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"用户数据读取失败。{e}")
            user_data = {"last_time": "20030101-0400", "history": {}}

    # 处理投胎冷却
    try:
        last_time_str = user_data.get("last_time", "20030101-0400")
        last_time = datetime.strptime(last_time_str, "%Y%m%d-%H%M")
    except Exception as e:
        logger.error(f"解析 last_time 失败。{e}")
        last_time = datetime.strptime("20030101-0400", "%Y%m%d-%H%M")
    delta_seconds = (now_time - last_time).total_seconds()
    if delta_seconds < rebirth_cd:
        await matcher.finish(f"让小梨休息一下吧！请等待{int(rebirth_cd - delta_seconds)}秒后再玩吧")
        return
    # 读取区域数据
    rebirth_data_cn_path = get_data_file("rebirth_data_cn.yml")
    if not rebirth_data_cn_path.exists():
        with open(rebirth_data_cn_path, 'w', encoding='utf-8') as f:
            f.write(REBIRTH_DATA_CN)
    with open(rebirth_data_cn_path, 'r', encoding='utf-8') as f:
        try:
            rebirth_data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"区域数据读取失败。{e}")
            rebirth_data = {}
    region_city_ratio: float = rebirth_data.get('city_ratio', 0.7)
    region_datas = rebirth_data.get('country', [])
    region_names = [r['region'] for r in region_datas]
    region_populations = [r['population'] for r in region_datas]
    region_male_ratios = {r['region']: r['male_ratio'] for r in region_datas}

    # 投胎结果生成
    result_region = random.choices(region_names, weights=region_populations, k=1)[0]
    result_gender = "男" if random.random() < region_male_ratios.get(result_region, 1) else "女"
    result_location = "城市" if random.random() < region_city_ratio else "农村"
    # 更新用户数据
    history: dict = user_data.get("history", {})
    history[result_region] = history.get(result_region, 0) + 1
    user_data_update = {
        "last_time": now_time.strftime('%Y%m%d-%H%M'),
        "history": history
    }
    with open(user_data_path, 'w', encoding='utf-8') as f:
        yaml.dump(user_data_update, f, allow_unicode=True)

    # 绘制图片
    img = ""  # 暂不生成

    # 发送结果
    message = [
        MessageSegment.at(event.user_id),
        MessageSegment.text(f" 投胎成功！\n您投胎成了{result_region}{result_location}的{result_gender}孩。")
        ]
    if img: message.append(MessageSegment.image(img))
    await matcher.finish(Message(message))