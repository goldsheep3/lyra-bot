import tempfile
import httpx
import os
import re
import zipfile

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event, Bot
from nonebot.params import CommandArg

from . import adx_download


async def handle_download(bot: Bot, event: Event, matcher):
    msg = str(event.get_message())
    logger.info(f"收到消息: {msg}")
    # 提取数字
    match = re.search(r"下载谱面\s*([0-9]+)", msg)
    if match:
        song_id = match.group(1)
        logger.info(f"提取到song_id: {song_id}")
        url = f"https://api.milkbot.cn/server/api/nobga_download?id={song_id}"
        logger.info(f"下载链接: {url}")
        await matcher.send(f"正在下载曲目[{song_id}]，请稍候……")
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"{song_id}.zip")
        logger.info(f"临时文件路径: {tmp_path}")
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                logger.info("开始请求下载文件")
                resp = await client.get(url)
                logger.info(f"HTTP状态码: {resp.status_code}")
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"文件已写��: {tmp_path}, 大小: {os.path.getsize(tmp_path)} bytes")
            # 解压并读取maidata.txt第一行
            maidata_title = None
            logger.info("开始解压zip文件")
            with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                logger.info(f"zip内容: {zip_ref.namelist()}")
                for name in zip_ref.namelist():
                    if name.lower() == "maidata.txt":
                        logger.info(f"找到maidata.txt: {name}")
                        with zip_ref.open(name) as maidata_file:
                            first_line = maidata_file.readline().decode("utf-8", errors="ignore").strip()
                            logger.info(f"maidata.txt第一行: {first_line}")
                            title_match = re.search(r"&title=(.*)", first_line)
                            if title_match:
                                maidata_title = title_match.group(1)
                                logger.info(f"提取到title: {maidata_title}")
                        break
            # 上传到QQ群文件
            group_id = event.group_id if hasattr(event, "group_id") else None
            logger.info(f"group_id: {group_id}")
            if not group_id:
                logger.info("未检测到group_id，非群聊环境")
                await matcher.finish("只能在群聊中使用该命令。")
            logger.info("开始上传群文件")
            await bot.call_api(
                "upload_group_file",
                group_id=group_id,
                file=tmp_path,
                name=f"{song_id}.zip"
            )
            logger.info("上传群文件成功")
            if maidata_title:
                await matcher.finish(f"曲目[{song_id}]({maidata_title}) 已上传到群文件：{song_id}.zip")
            else:
                await matcher.finish(f"曲目[{song_id}]已上传到群文件：{song_id}.zip")
        except Exception as e:
            logger.info(f"发生异常: {e}")
            await matcher.finish(f"下载或上传失败：{e}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    logger.info(f"已删除临时文件: {tmp_path}")
                except Exception as e:
                    logger.info(f"删除临时文件失败: {e}")
    else:
        logger.info("未识别到谱面ID")
        await matcher.finish("未识别到谱面ID，请检查格式。")
