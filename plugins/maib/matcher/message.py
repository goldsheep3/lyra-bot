from typing import Any, Literal
from time import perf_counter

from nonebot import logger
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
    started_at = perf_counter()
    image_count = sum(type_ == "image" for type_, _ in msg_segments)
    if isinstance(event, OneBotV11Event):
        build_started_at = perf_counter()
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
        logger.info(
            f"maib message perf: build adapter=onebot_v11 tag={tag} segments={len(msg_segments)} "
            f"images={image_count} elapsed={perf_counter() - build_started_at:.3f}s"
        )
        func = matcher.send if tag == "send" else matcher.finish
        send_started_at = perf_counter()
        try:
            await func(onebotv11_msg)
        finally:
            logger.info(
                f"maib message perf: send adapter=onebot_v11 tag={tag} segments={len(msg_segments)} "
                f"images={image_count} elapsed={perf_counter() - send_started_at:.3f}s "
                f"total={perf_counter() - started_at:.3f}s"
            )

    elif isinstance(event, TGEvent):
        build_started_at = perf_counter()
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
        logger.info(
            f"maib message perf: build adapter=telegram tag={tag} segments={len(msg_segments)} "
            f"images={image_count} elapsed={perf_counter() - build_started_at:.3f}s"
        )
        func = matcher.send if tag == "send" else matcher.finish
        send_started_at = perf_counter()
        try:
            await func(tg_msg)
        finally:
            logger.info(
                f"maib message perf: send adapter=telegram tag={tag} segments={len(msg_segments)} "
                f"images={image_count} elapsed={perf_counter() - send_started_at:.3f}s "
                f"total={perf_counter() - started_at:.3f}s"
            )
