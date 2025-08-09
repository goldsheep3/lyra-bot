from datetime import datetime
from hashlib import md5
from nonebot.plugin import on_fullmatch, PluginMetadata
from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

__plugin_meta__ = PluginMetadata(
    name="简单运势",
    description="一个简单的运势查询插件。",
    usage="发送「今日运势」「运势」「抽签」「签到」「打卡」即可获得今日专属运势。",
)

# 主要运势定义与权重分配，每个有多个描述
MAIN_FORTUNES = [
    {
        "title": "大吉",
        "desc": [
            "早安！小梨刚刚拨了一下青音，弦音像昨晚的梦一样灿烂——所以，今天一定是大吉！",
            "考试？抽卡？随便挑！青音替你奏起胜利的小步舞曲。",
            "莉莉丝阿姐给的草莓松饼！呐，送你一个，甜甜的，和你的大吉很配。",
        ]
    },
    {
        "title": "吉",
        "desc": [
            "今天的青音格外温柔，像午后微风拂过皇宫回廊。",
            "像是小梨可以在集市上买到最后一支香草冰淇淋一样幸运。",
            "今天是吉诶！要和小梨试试新东西去吗？",
        ]
    },
    {
        "title": "中吉",
        "desc": [
            "嗯……青音弹到这里就打个小小的呵欠，说明今天不会惊天动地，但也绝不会无聊。",
            "平凡里藏着小惊喜，记得抬头看天空哦。",
        ]
    },
    {
        "title": "小吉",
        "desc": [
            "嘿，签上闪着一点点银光，像青音最细的那根弦。",
            "小梨刚才在花园绊了一跤，结果捡到一枚四叶草！",
        ]
    },
    {
        "title": "平",
        "desc": [
            "今天的青音特别钟爱小行板，不快不慢。",
            "平是好兆头！莉莉丝阿姐说过——平安是福。",
        ]
    },
    {
        "title": "凶",
        "desc": [
            "欸？青音突然跑调了……小梨昨晚练习得太晚，琴弦有点抗议。",
            "今天可能会有点小波折，别担心，小梨和青音会帮你调整好。",
        ]
    },
    {
        "title": "大凶",
        "desc": [
            "今天大概诸事不宜，连莉莉丝阿姐都把蛋糕烤糊了。",
            "青音的弦音有点刺耳，像是预示着什么不好的事情。要小心哦。",
            "是大凶啊……来和小梨咸鱼一天吧ww",
        ]
    },
]
MAIN_FORTUNE_WEIGHTS = [2, 4, 5, 6, 3, 3, 1]
MAIN_FORTUNE_INDEX_POOL = [
    idx for idx, weight in enumerate(MAIN_FORTUNE_WEIGHTS) for _ in range(weight)
]

SPECIAL_FORTUNES = ["舞萌", "中二", "PJSK", "写谱", "雀魂", "MC"]
SPECIAL_RESULT_LABELS = ["吉", "平", "凶"]

today_fortune = on_fullmatch(
    ("今日运势", "运势", "抽签", "签到", "打卡"),
    rule=to_me(),
    priority=2,
    block=True,
)

def get_daily_seed(user_id: int, date_str: str) -> int:
    """生成每日唯一种子，保证同人同日一致，不同人或不同天不同。"""
    seed_source = f"{user_id}_{date_str}"
    return int(md5(seed_source.encode("utf-8")).hexdigest(), 16)

def get_main_fortune(user_id: int, date: datetime) -> tuple[dict, str]:
    """加权选择主要运势和唯一描述。"""
    date_str = date.strftime("%Y%m%d")
    seed = get_daily_seed(user_id, date_str)
    idx = MAIN_FORTUNE_INDEX_POOL[seed % len(MAIN_FORTUNE_INDEX_POOL)]
    fortune = MAIN_FORTUNES[idx]
    # 用 seed+index 保证同人同天描述唯一
    desc_seed = int(md5(f"{seed}_{idx}".encode("utf-8")).hexdigest(), 16)
    desc_idx = desc_seed % len(fortune["desc"])
    desc = fortune["desc"][desc_idx]
    return fortune, desc

def get_special_fortunes(user_id: int, date: datetime) -> list[str]:
    """为每个特别运势均匀分配【吉/平/凶】，保证每日一致。"""
    date_str = date.strftime("%Y%m%d")
    seed = get_daily_seed(user_id, date_str)
    results = []
    for i in range(len(SPECIAL_FORTUNES)):
        item_seed = md5(f"{seed}_{i}".encode("utf-8")).hexdigest()
        label_idx = int(item_seed, 16) % 3
        results.append(SPECIAL_RESULT_LABELS[label_idx])
    return results

@today_fortune.handle()
async def handle_today_fortune(matcher: Matcher, event: MessageEvent):
    user_id = event.user_id
    today = datetime.now()
    main_fortune, main_desc = get_main_fortune(user_id, today)
    special_results = get_special_fortunes(user_id, today)

    message_text = [
        MessageSegment.text(f"小梨来啦！你今天的运势是：【{main_fortune['title']}】！"),
        MessageSegment.text(main_desc),
        MessageSegment.text(""),
        MessageSegment.text("今日你的特别运势是："),
    ]
    for i in range(0, len(SPECIAL_FORTUNES), 2):
        left = f"{SPECIAL_FORTUNES[i]}  {special_results[i]}"
        if i + 1 < len(SPECIAL_FORTUNES):
            right = f"{SPECIAL_FORTUNES[i+1]}  {special_results[i+1]}"
        else:
            right = ""
        message_text.append(MessageSegment.text(f"{left}  |  {right}"))
    message_text.append(MessageSegment.text(""))
    message_text.append(MessageSegment.text("无论运势如何，小梨都在陪着你呢！"))
    # todo 持久化数据-打卡签到累计
    # message_text.append(MessageSegment.text(f"你已经在小梨这里打卡运势{day}天啦。"))
    await matcher.finish(Message(message_text))