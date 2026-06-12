from pathlib import Path

from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot


async def get_group_root_files(bot: OneBotV11Bot, group_id: str | int, **kwargs) -> dict:
    return await bot.call_api(
        "get_group_root_files",
        group_id=str(group_id),
        **kwargs
    )


async def get_group_files_by_folder(bot: OneBotV11Bot, group_id: str | int, folder_id: str | int, **kwargs) -> dict:
    return await bot.call_api(
        "get_group_files_by_folder",
        group_id=str(group_id),
        folder_id=str(folder_id),
        **kwargs
    )


async def update_group_file(bot: OneBotV11Bot, group_id: str | int, file_path: Path, **kwargs) -> dict:
    file_name = kwargs.get("file_name", file_path.name)
    return await bot.call_api(
        "upload_group_file",
        group_id=str(group_id),
        file=file_path.resolve().as_posix(),
        name=file_name,
        **kwargs
    )

async def upload_private_file(bot: OneBotV11Bot, user_id: str | int, file_path: Path, **kwargs) -> dict:
    file_name = kwargs.get("file_name", file_path.name)
    return await bot.call_api(
        "upload_private_file",
        user_id=str(user_id),
        file=file_path.resolve().as_posix(),
        name=file_name,
        **kwargs
    )


async def create_group_file_folder(bot: OneBotV11Bot, group_id: str | int, folder_name: str, **kwargs) -> dict:
    return await bot.call_api(
        "create_group_file_folder",
        group_id=str(group_id),
        folder_name=folder_name,
        **kwargs
    )
