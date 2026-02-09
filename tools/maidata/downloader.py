import time
import httpx
from loguru import logger


def _downloader(
        url: str,
        project_name: str,
        retries: int = 3,
        delay: int | float = 1,
) -> dict:
    """通用 JSON 下载函数"""
    retries = retries if retries > 1 else 1

    for i in range(retries):
        logger.info(f"获取 {project_name} 数据，第 {i + 1} 次尝试")
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.success(f"成功获取 {project_name} 数据")
            return data
        except httpx.RequestError:
            logger.warning(f"获取 {project_name} 数据失败，{delay} 秒后重试")
            time.sleep(delay)

    logger.warning(f"尝试获取 {project_name} 数据失败")
    return {}


def get_chart_index(retries: int = 3, delay: int | float = 1) -> dict:
    """获取 Maichart-Converts (maiJP) index.json"""
    url = (
        "https://raw.githubusercontent.com/"
        "Neskol/Maichart-Converts/refs/heads/master/index.json"
    )

    data = _downloader(
        url,
        project_name="Maichart-Converts (maiJP)",
        retries=retries,
        delay=delay,
    )
    if data:
        return data

    logger.warning("尝试通过 gh-proxy 重新获取 index.json")
    proxy_url = "https://gh-proxy.org/" + url
    return _downloader(
        proxy_url,
        project_name="Maichart-Converts (maiJP) via gh-proxy",
        retries=retries,
        delay=delay,
    )


def get_diving_fish_music_data(retries: int = 3, delay: int | float = 1) -> dict:
    """获取 Diving-Fish 乐曲数据（maiCN）"""
    url = "https://www.diving-fish.com/api/maimaidxprober/music_data"
    return _downloader(
        url,
        project_name="Diving-Fish 乐曲数据 (maiCN)",
        retries=retries,
        delay=delay,
    )
