import time
import httpx
from pathlib import Path

from loguru import logger


def _downloader(url: str, project_name: str, retries: int = 3, delay: int | float = 1) -> dict:
    """获取数据的辅助函数"""
    retries = retries if retries > 1 else 1
    for i in range(retries):
        logger.info(f"获取 {project_name} 数据，第{i+1}次尝试")
        try:
            # 谱面数据来自 GitHub 的 Neskol/Maichart-Converts 仓库
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            d = response.json()
            logger.success(f"成功获取 {project_name} 数据")
            return d
        except httpx.RequestError:
            logger.warning(f"获取 {project_name} 数据失败, 等待 {delay} 秒后重试...")
            time.sleep(delay)
    logger.warning(f"尝试获取 {project_name} 数据失败")
    return {}


def get_chart_index(retries: int = 3, delay: int | float = 1) -> dict:
    """获取 Maichart-Converts(maiJP) 数据"""
    CHART_INDEX_URL = "https://raw.githubusercontent.com/Neskol/Maichart-Converts/refs/heads/master/index.json"
    data = _downloader(CHART_INDEX_URL, project_name="Maichart-Converts (maiJP)", retries=retries, delay=delay)
    if data: return data

    logger.warning("获取 Maichart-Converts (maiJP) 数据失败，即将尝试通过 gh-proxy 重新获取")
    PROXY_URL = "https://gh-proxy.org/" + CHART_INDEX_URL
    data = _downloader(PROXY_URL, project_name="Maichart-Converts (maiJP) via gh-proxy", retries=retries, delay=delay)
    return data


def get_diving_fish_music_data(retries: int = 3, delay: int | float = 1):
    """获取水鱼查分器公开乐曲数据"""
    DIVING_FISH_API_URL = "https://www.diving-fish.com/api/maimaidxprober/music_data"
    data = _downloader(DIVING_FISH_API_URL, project_name="Diving-Fish 乐曲数据 (maiCN)", retries=retries, delay=delay)
    return data


if __name__ == "__main__":

    # Loguru 日志配置
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> <cyan>[{level}]</cyan> {message}\n",
        colorize=False,
    )

    logger.info("开始检查谱面完整性")

    # 谱面文件路径
    charts_path = Path.cwd() / "plugin_data" / "maib" / "charts"
    not_exist_chart_files = set()

    # 获取 Maichart-Converts (maiJP) 数据
    chart_index = get_chart_index()
    if chart_index:
        chart_filename_list = list(chart_index.keys())
        for filename in chart_filename_list:
            # 检查文件是否存在
            chart_file_path = charts_path / filename / ".zip"
            if not chart_file_path.exists():
                not_exist_chart_files.add(filename)
                logger.warning(f"缺少谱面文件: {chart_file_path}")

    if not_exist_chart_files:
        logger.info(f"总计缺少 {len(not_exist_chart_files)} 个谱面文件，请检查对应文件是否存在")
    else:
        logger.info("所有谱面文件均存在")


