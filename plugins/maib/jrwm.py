import time

from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

from . import today_mai2, total_list


# 音游黄历事件表
fortune_items = ['拼机', '推分', '越级', '下埋', '夜勤', '练底力', '练手法', '打旧框', '干饭', '抓绝赞', '收歌']


def build_luck_seed(qq: int):
    """运气种子生成。采用水鱼方案"""
    days = int(time.strftime("%d", time.localtime(time.time()))) + 31 * int(
        time.strftime("%m", time.localtime(time.time()))) + 77
    return (days * qq) >> 8


def get_cover_len5_id(mid: int) -> str:
    """转化封面id格式"""
    return f'{(mid - 10000) if 10000 < mid <= 11000 else mid:05d}'


@today_mai2.handle()
async def _(event: MessageEvent):
    """`today_mai2` - 今日舞萌"""
    try:
        qq = int(event.get_user_id())
    except (ValueError, AttributeError):
        await today_mai2.finish("获取用户QQ失败，请报告bot主。")
        return

    luck_seed = build_luck_seed(qq)

    # 今日人品
    luck_value = luck_seed % 100
    messages = [MessageSegment.text(f"今日人品值：{luck_value}")]

    # 音游黄历
    for i in range(len(fortune_items)):
        val = luck_seed & 3
        if val == 3:
            messages.append(MessageSegment.text(f"宜 {fortune_items[i]}"))
        elif val == 0:
            messages.append(MessageSegment.text(f"忌 {fortune_items[i]}"))
        luck_seed >>= 2

    # 今日推歌
    music = total_list[luck_seed % len(total_list)]
    messages.extend([
        MessageSegment.text("今日推荐歌曲：\n"),
        MessageSegment.text(f"{music.id}. {music.title}\n"),
        MessageSegment.image(f"https://www.diving-fish.com/covers/{get_cover_len5_id(music.id)}.png"),
        MessageSegment.text(f"{'/'.join(music.level)}")
    ])

    await today_mai2.finish(Message(messages))
