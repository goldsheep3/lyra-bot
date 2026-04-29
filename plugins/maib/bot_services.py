from pathlib import Path

from nonebot.adapters.onebot.v11 import Bot


async def get_group_root_files(bot: Bot, group_id: str | int, **kwargs) -> Exception | dict:
    try:
        return await bot.call_api(
            "get_group_root_files",
            group_id=str(group_id),
            **kwargs
        )
    except Exception as e:
        return e


async def get_group_files_by_folder(bot: Bot, group_id: str | int, folder_id: str | int, **kwargs) -> Exception | dict:
    try:
        return await bot.call_api(
            "get_group_files_by_folder",
            group_id=str(group_id),
            folder_id=str(folder_id),
            **kwargs
        )
    except Exception as e:
        return e


async def update_group_file(bot: Bot, group_id: str | int, file_path: Path, **kwargs) -> Exception | dict:
    file_name = kwargs.get("file_name", file_path.name)
    try:
        return await bot.call_api(
            "upload_group_file",
            group_id=str(group_id),
            file=file_path.resolve().as_posix(),
            name=file_name,
            **kwargs
        )
    except Exception as e:
        return e

async def upload_private_file(bot: Bot, user_id: str | int, file_path: Path, **kwargs) -> Exception | dict:
    file_name = kwargs.get("file_name", file_path.name)
    try:
        return await bot.call_api(
            "upload_private_file",
            user_id=str(user_id),
            file=file_path.resolve().as_posix(),
            name=file_name,
            **kwargs
        )
    except Exception as e:
        return e


async def create_group_file_folder(bot: Bot, group_id: str | int, folder_name: str, **kwargs) -> Exception | dict:
    try:
        return await bot.call_api(
            "create_group_file_folder",
            group_id=str(group_id),
            folder_name=folder_name,
            **kwargs
        )
    except Exception as e:
        return e
