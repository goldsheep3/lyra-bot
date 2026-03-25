from pathlib import Path

from nonebot.adapters.onebot.v11 import Bot


async def update_group_file(bot: Bot, group_id: str | int, file_path: Path, **kwargs) -> Exception | None:
    file_name = kwargs.get("file_name", file_path.name)
    try:
        await bot.call_api(
            "upload_group_file",
            group_id=str(group_id),
            file=file_path.resolve().as_posix(),
            name=file_name
        )
        return None
    except Exception as e:
        return e

async def upload_private_file(bot: Bot, user_id: str | int, file_path: Path, **kwargs) -> Exception | None:
    file_name = kwargs.get("file_name", file_path.name)
    try:
        await bot.call_api(
            "upload_private_file",
            user_id=str(user_id),
            file=file_path.resolve().as_posix(),
            name=file_name
        )
        return None
    except Exception as e:
        return e
