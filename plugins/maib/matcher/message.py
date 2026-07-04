from typing import Any, Literal

from nonebot.adapters import Event
from nonebot.internal.matcher import Matcher

from nonebot.adapters.onebot.v11 import (
    Event as OneBotV11Event,
    Message as OneBotV11Message,
    MessageSegment as OneBotV11MessageSegment,
)
from nonebot.adapters.telegram import (
    Event as TGEvent,
    Message as TGMessage,
)
from nonebot.adapters.telegram.message import (
    Entity as TGMessageEntity,
    File as TGMessageFile,
)


MessagePayload = list[tuple[str, Any]]
MessageAction = Literal["send", "finish"]


async def build_msg(
    matcher: Matcher,
    event: Event,
    msg_segments: MessagePayload,
    tag: MessageAction = "send",
) -> None:
    """Build and send adapter-specific messages from a shared payload."""
    if isinstance(event, OneBotV11Event):
        onebotv11_msg = OneBotV11Message()
        for type_, content in msg_segments:
            if type_ == "text":
                onebotv11_msg += OneBotV11MessageSegment.text(content)
            elif type_ == "image":
                onebotv11_msg += OneBotV11MessageSegment.image(content)
            elif type_ == "at":
                uid = content[1] if isinstance(content, tuple) else content
                onebotv11_msg += OneBotV11MessageSegment.at(uid) + " "
            else:
                continue

        if not onebotv11_msg:
            return
        func = matcher.send if tag == "send" else matcher.finish
        await func(onebotv11_msg)

    elif isinstance(event, TGEvent):
        tg_msg = TGMessage()
        for type_, content in msg_segments:
            if type_ == "text":
                tg_msg += TGMessageEntity.text(content)
            elif type_ == "image":
                tg_msg += TGMessageFile.photo(content)
            elif type_ == "at" and isinstance(content, tuple) and len(content) == 2:
                username, tg_user_id = content
                tg_msg += TGMessageEntity.text_link(
                    f"{username}",
                    f"tg://user?id={tg_user_id}",
                ) + " "
            else:
                continue

        if not tg_msg:
            return
        func = matcher.send if tag == "send" else matcher.finish
        await func(tg_msg)
