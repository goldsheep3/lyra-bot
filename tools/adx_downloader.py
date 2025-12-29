import time
import requests
from typing import Dict, List, Optional
from pathlib import Path

from loguru import logger


CHART_INDEX_URL = "https://raw.githubusercontent.com/Neskol/Maichart-Converts/refs/heads/master/index.json"
DIVING_FISH_API_URL = "https://www.diving-fish.com/api/maimaidxprober/music_data"
DIVING_FISH_AFDIAN_URL = "https://afdian.com/a/divingfish"
MILKBOT_URL = "https://astrodx.milkbot.cn/"


def milkbot_download_api_url(short_id: int, bga: bool = False) -> str:
    """生成 MilkBot 谱面下载 API URL"""
    return f"https://api.milkbot.cn/server/api/{'' if bga else 'nobga_'}download?id={short_id}"


class MergeChartCNVersionData:
    """合并 CNVersion (CNVer) 谱面数据的工具类"""

    def _downloader(self, url: str, retries: int = 3, delay: int | float = 1):
        """
        获取数据的辅助函数
        """
        for attempt in range(retries):
            try:
                logger.info(f"尝试从 \"{url}\" 获取JSON数据(尝试第{attempt+1}次/共尝试{retries}次)")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                logger.info(f"成功从 \"{url}\" 获取JSON数据")
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.warning(f"第 {attempt+1} 次尝试从 \"{url}\" 获取JSON数据失败: \"{e}\"")
                if attempt < retries - 1:
                    logger.debug(f"等待 {delay} 秒后第 {attempt+1} 次尝试从 \"{url}\" 获取JSON数据")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.warning(f"无法从 \"{url}\" 获取JSON数据: {e}")
                    raise requests.exceptions.RequestException(f"无法从 \"{url}\" 获取JSON数据") from e
        raise ValueError(f"无法从 \"{url}\" 获取JSON数据")

    def merge_chart_cnver_data(self) -> Optional[Dict[str, Optional[str]]]:
        """合并 song_id: CNVersion 谱面数据"""
        logger.info("准备合并 ChartData")

        chart_data: Dict[str, Optional[str]] = {}
        # 1. 获取 Converts(maiJP) 数据，以获取所有 song_id
        logger.debug("准备获取 Maichart-Converts(maiJP) 数据")
        maiJP_chart_data_url = CHART_INDEX_URL
        try:
            maiJP_data: dict = self._downloader(maiJP_chart_data_url)
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"获取 Maichart-Converts(maiJP) 数据失败: {str(e)}")
            raise Exception("获取 Maichart-Converts(maiJP) 数据失败") from e
        logger.debug(f"成功获取 Maichart-Converts(maiJP) 数据，数据包含 {len(maiJP_data)} 首歌曲。")
        logger.info("")
        logger.info("请考虑支持 Maichart-Converts 项目，在 GitHub 上给该项目一个 Star ⭐！")
        logger.info(CHART_INDEX_URL)
        logger.info("")
        song_ids: List[str] = [s for s in maiJP_data.keys()]
        song_ids.sort(key=lambda x: int(x))
        logger.debug(f"成功处理 Maichart-Converts(maiJP) 数据")
        # 2. 获取水鱼(maiCN)数据
        logger.debug("准备获取 水鱼(maiCN) 数据")
        maiCN_chart_data_url = DIVING_FISH_API_URL
        try:
            maiCN_data: list = self._downloader(maiCN_chart_data_url)
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"获取 水鱼(maiCN) 数据失败: {str(e)}")
            raise Exception("获取 水鱼(maiCN) 数据失败") from e
        logger.debug(f"成功获取 水鱼(maiCN) 数据，数据包含 {len(maiCN_data)} 首歌曲。")
        logger.info("")
        logger.info("请考虑支持 水鱼查分器 项目提供的国服乐曲公共 API 数据！")
        logger.info(f"水鱼查分器 的爱发电链接：{DIVING_FISH_AFDIAN_URL}")
        logger.info("")
        # V1 Data: 实质是 song_id: cn_ver
        cn_ver_data: Dict[str, Optional[str]] = {str(c.get("id")): c.get("basic_info", {}).get("from") for c in maiCN_data}
        logger.debug(f"成功处理 水鱼(maiCN) 数据")
        chart_data = {i: cn_ver_data.get(i, None) for i in song_ids}
        logger.info(f"成功合并 ChartData，数据包含 {len(chart_data)} 首歌曲")
        return chart_data



class ChartFileDownloader:
    """谱面文件下载工具类"""

    def _downloader(self, download_dir: Path, song_id: str | int, bga: bool = True, retries: int = 3, delay: int | float = 1) -> Dict[str, str | bool]:
        """
        **[内部]** 下载单个谱面文件的辅助函数

        :return: (file_path: str, download_tag: bool)
            其中 file_path 为下载成功或检测到相同文件时文件路径（若下载失败则为空字符串），download_tag 为是否发生下载动作的标志
        """
        log_prefix = f"下载谱面 {song_id}{'' if bga else '(nobga)'}"
        song_id = str(song_id)
        logger.info(f"{log_prefix}: 准备开始下载")
        download_dir.mkdir(parents=True, exist_ok=True)
        file_path = download_dir / f"{song_id}.zip"
        if file_path.exists():
            logger.info(f"{log_prefix}: 文件已存在，跳过下载")
            return {"file_path": str(file_path), "download_tag": False}
        download_url = milkbot_download_api_url(int(song_id), bga)
        # 下载尝试
        download_tag = False
        for attempt in range(retries):
            if attempt > 0:
                logger.debug(f"{log_prefix}: 等待 {delay} 秒后重试...")
                time.sleep(delay)
                delay *= 2
            try:
                logger.info(f"{log_prefix}: 尝试下载 (尝试第{attempt+1}次/共尝试{retries}次)")
                response = requests.get(download_url, timeout=10, stream=True)
                if response.status_code != 200:
                    logger.warning(f"{log_prefix}: 下载失败，HTTP 错误码：{response.status_code}")
                    continue
                with file_path.open('wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logger.debug(f"{log_prefix}: 文件下载完成，开始进行文件大小验证")
                downloaded_size = file_path.stat().st_size
                if downloaded_size < 1024:
                    logger.warning(f"{log_prefix}: 下载的文件字节数异常: {downloaded_size}字节，删除该文件并重新尝试")
                    file_path.unlink(missing_ok=True)
                    continue
                logger.info(f"{log_prefix}: 下载到 \"{file_path}\" 成功。大小: {downloaded_size//1024}KB")
                download_tag = True
                break
            except requests.exceptions.RequestException as e:
                logger.warning(f"{log_prefix}: 下载失败，未知 RequestException 错误: {str(e)}")
                continue
        if not download_tag:
            logger.error(f"{log_prefix}: 所有下载尝试均失败，已结束该谱面的下载尝试")
        return {"file_path": str(file_path) if download_tag else "", "download_tag": download_tag}

    def download_chart_batch(self, download_dir: Path, song_ids: List[str | int], bga: bool = True, delay: int | float = 0.5) -> tuple[int, int]:
        """批量下载谱面文件"""
        logger.info(f"准备批量下载 {len(song_ids)} 个{'' if bga else ' nobga '}谱面文件到目录 \"{download_dir}\"")
        logger.info("")
        logger.info("请考虑支持 MilkBot 项目，感谢 MilkBot 提供的 AstroDX 谱面下载服务！")
        logger.info(MILKBOT_URL)
        logger.info("")
        success_id_count: int = 0
        for i, song_id in enumerate(song_ids, start=1):
            song_id = str(song_id)
            logger.debug(f"批量下载: {song_id}(第{i}个/共{len(song_ids)}个) -> \"{download_dir}\"")
            success_path, download_tag = self._downloader(download_dir, song_id, bga)
            if success_path:
                success_id_count += 1
            logger.debug(f"批量下载: {song_id}(第{i}个/共{len(song_ids)}个) {'成功' if success_path else '失败'}，已完成 {i/len(song_ids)*100:.2f}%")
            if download_tag:
                time.sleep(delay)
        if success_id_count == len(song_ids):
            logger.info("批量下载全部成功")
        else:
            logger.warning("批量下载部分失败，请检查日志获取详细信息")
        return success_id_count, len(song_ids)


if __name__ == "__main__":
    working_dir = Path("/home/goldsheep3/lyra-bot/plugin_data/maib")

    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> <cyan>[{level}]</cyan> {message}\n",
        colorize=False,
    )

    merge_tool = MergeChartCNVersionData()
    cnver_data = merge_tool.merge_chart_cnver_data()
    downloader = ChartFileDownloader()
    downloads_dir = working_dir / "charts"
    if cnver_data:
        downloader.download_chart_batch(downloads_dir, list(cnver_data.keys()), bga=False)
