from nonebot.adapters.onebot.v11 import Event, Bot
from nonebot.params import CommandArg
import tempfile
import httpx
import os
import re
import zipfile

from . import adx_download


@adx_download.handle()
async def handle_download(bot: Bot, event: Event):
    msg = str(event.get_message())
    # 提取数字
    match = re.search(r"下载谱面\s*([0-9]+)", msg)
    if match:
        song_id = match.group(1)
        url = f"https://api.milkbot.cn/server/api/nobga_download?id={song_id}"
        await adx_download.send(f"正在下载曲目[{song_id}]，请稍候……")
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"{song_id}.zip")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
            # 解压并读取maidata.txt第一行
            maidata_title = None
            with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                for name in zip_ref.namelist():
                    if name.lower() == "maidata.txt":
                        with zip_ref.open(name) as maidata_file:
                            first_line = maidata_file.readline().decode("utf-8", errors="ignore").strip()
                            title_match = re.search(r"&title=(.*)", first_line)
                            if title_match:
                                maidata_title = title_match.group(1)
                        break
            # 上传到QQ群文件
            group_id = event.group_id if hasattr(event, "group_id") else None
            if not group_id:
                await adx_download.finish("只能在群聊中使用该命令。")
            await bot.call_api(
                "upload_group_file",
                group_id=group_id,
                file=tmp_path,
                name=f"{song_id}.zip"
            )
            if maidata_title:
                await adx_download.finish(f"曲目[{song_id}]({maidata_title}) 已上传到群文件：{song_id}.zip")
            else:
                await adx_download.finish(f"曲目[{song_id}]已上传到群文件：{song_id}.zip")
        except Exception as e:
            await adx_download.finish(f"下载或上传失败：{e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    else:
        await adx_download.finish("未识别到谱面ID，请检查格式。")
