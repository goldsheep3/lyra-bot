import tempfile
import httpx
import os
import re
import zipfile

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event, Bot
from nonebot.exception import FinishedException


async def handle_download(bot: Bot, event: Event, matcher):
    """捕获消息，下载谱面文件并上传至群文件"""

    msg = str(event.get_message())
    logger.info(f"收到消息: {msg}")

    # 提取数字
    match = re.search(r"下载谱面\s*([0-9]+)", msg)
    if match:
        group_id = event.group_id if hasattr(event, "group_id") else None
        logger.debug(f"group_id: {group_id}")
        if not group_id:
            logger.debug("未检测到group_id，非群聊环境")
            await matcher.finish("现在lyra只能把谱面传到群文件喔qwq")

        song_id = match.group(1)
        logger.info(f"提取到song_id: {song_id}")
        url = f"https://api.milkbot.cn/server/api/nobga_download?id={song_id}"
        logger.debug(f"下载链接: {url}")
        await matcher.send(f"lyra正在帮你下载id{song_id}，不要急喔。")

        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"{song_id}.zip")
        logger.debug(f"临时文件路径: {tmp_path}")

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                logger.info(f"开始请求下载文件 {song_id}.zip")
                resp = await client.get(url)
                logger.info(f"{song_id}.zip HTTP状态码: {resp.status_code}")
                if resp.status_code == 404:
                    raise httpx.HTTPStatusError
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"下载完成: {tmp_path}({os.path.getsize(tmp_path)} bytes)")

            # 解压并读取maidata.txt第一行
            maidata_title = None
            logger.debug("开始解压zip文件")
            with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                logger.trace(f"zip内容: {zip_ref.namelist()}")
                for name in zip_ref.namelist():
                    if name.lower() == "maidata.txt":
                        logger.debug(f"找到maidata.txt: {name}")
                        with zip_ref.open(name) as maidata_file:
                            first_line = maidata_file.readline().decode("utf-8", errors="ignore").strip()
                            logger.debug(f"maidata.txt第一行: {first_line}")
                            title_match = re.search(r"&title=(.*)", first_line)
                            if title_match:
                                maidata_title = title_match.group(1)
                                logger.info(f"提取到曲目 {song_id} 标题: {maidata_title}")
                        break

            # 上传到QQ群文件
            logger.info(f"{song_id}.zip 开始上传群文件")
            await bot.call_api(
                "upload_group_file",
                group_id=group_id,
                file=tmp_path,
                name=f"{song_id}.zip"
            )
            logger.success(f"{song_id}.zip 上传成功")
            finish_message = f"{maidata_title}(id{song_id})" if maidata_title else f"id{song_id}"
            await matcher.finish(f"lyra已经帮你把 {finish_message} 的谱面传到群里啦！")
        except Exception as e:
            if isinstance(e, FinishedException):
                logger.info("发生 FinishedException 异常，可能是上传成功后触发的异常，无需特殊处理")
                raise
            if isinstance(e, httpx.ConnectTimeout):
                logger.info("发生 httpx.HTTPStatusError 异常，大概是谱面不存在")
                await matcher.finish(f"lyra没有成功下载到id{song_id}的谱面……真的有这首歌吗？")
            logger.warning(f"发生未知异常: {e}")
            await matcher.finish(f"小梨不知道怎么回事，下载不到id{song_id}的谱面……果咩纳塞QAQ")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    logger.debug(f"已删除临时文件: {tmp_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {e}")
    else:
        logger.info("未识别到谱面ID")
        await matcher.finish("lyra没看懂你想找哪首歌的谱面qwq")
