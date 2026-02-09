import argparse
import json
import sys
from pathlib import Path

from loguru import logger

from .downloader import get_chart_index
from .md5_check import load_md5_dict, calc_md5


def main():
    parser = argparse.ArgumentParser(description="谱面完整性与 MD5 校验")
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="以 JSON 格式输出结果（禁用日志）",
    )
    args = parser.parse_args()

    # -------- 日志配置 --------
    logger.remove()
    if not args.json_output:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> <cyan>[{level}]</cyan> {message}\n",
            colorize=False,
        )

    charts_dir = Path.cwd() / "plugin_data" / "maib" / "charts"
    md5_file = Path.cwd() / "charts_md5.json"

    missing_files: set[str] = set()
    need_update_files: set[str] = set()

    # -------- 获取 index --------
    index = get_chart_index()
    if not index:
        logger.error("无法获取 index.json")
        sys.exit(1)

    # -------- 读取 MD5 --------
    md5_data: dict[str, str] = {}
    if md5_file.exists():
        try:
            md5_data = load_md5_dict(md5_file)
        except Exception as e:
            logger.warning(f"MD5 文件解析失败：{e}")

    # -------- index 检查 --------
    for name in index.keys():
        zip_name = f"{name}.zip"
        zip_path = charts_dir / zip_name

        if not zip_path.exists():
            missing_files.add(zip_name)
            logger.warning(f"缺少谱面文件：{zip_name}")
            continue

        if zip_name not in md5_data:
            missing_files.add(zip_name)
            logger.warning(f"MD5 中缺少记录：{zip_name}")
            continue

        local_md5 = calc_md5(zip_path)
        if local_md5 != md5_data[zip_name]:
            need_update_files.add(zip_name)
            logger.warning(f"MD5 不一致：{zip_name}")

    result = {
        "missing": sorted(missing_files),
        "need_update": sorted(need_update_files),
    }

    # -------- 输出 --------
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False))
        return

    logger.info(f"需要上传的文件数量：{len(missing_files)}")
    logger.info(f"需要更新的文件数量：{len(need_update_files)}")
    if not missing_files and not need_update_files:
        logger.success("所有谱面文件均完整且校验通过")


if __name__ == "__main__":
    main()
