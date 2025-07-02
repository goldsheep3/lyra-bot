import time
import random
from pathlib import Path

from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment


class Reincamate:
    """投胎基类"""

    # 最近投胎时间，用于处理投胎冷却
    last_time: int
    # 投胎冷却时间
    cd_time: int
    # 事件对象
    event: MessageEvent

    def __init__(self, event: MessageEvent, last_time: int = 0, cd_time: int = 120):
        self.event = event
        self.last_time = last_time
        self.cd_time = cd_time

    def _cd_calender(self) -> int:
        """计算投胎冷却"""
        current_time = int(time.time())
        cd_amount = self.cd_time - (current_time - self.last_time)
        if cd_amount > 0:
            return -cd_amount
        else:
            return self.last_time
    
    def _msg_output(self, text: str, img: Path | None = None) -> Message:
        """生成成功投胎的消息输出"""
        msg = [
            MessageSegment.at(self.event.user_id),
            MessageSegment.text(text)
        ]
        if img:
            msg.append(MessageSegment.image(img))
        return Message(msg)
        
    @staticmethod
    def _r100(a: str, b: str, a_percent: int | float) -> str:
        """根据`a_percent`百分比比重值，随机返回 a 或 b"""
        r100result = random.randint(0, 100)
        return a if r100result < a_percent else b