import sys
import yaml
from pathlib import Path
from typing import List, Dict

from tools.maidata import downloader, md5_check, fetch, save


def check(charts_dir: Path, md5_file_path: Path) -> str | List[Path]:
    """检查 Neskol/Maichart-Converts 标准谱面集的完整性与 MD5"""
    missing, missing_in_md5, outdated = set(), set(), set()

    index = downloader.get_chart_index()
    if not index:
        return "无法获取 Neskol/Maichart-Converts 标准谱面集的 index.json"

    if not md5_file_path.exists():
        return "无法找到 Neskol/Maichart-Converts 标准谱面集的 md5.json"
    md5_dict = md5_check.load_or_save_md5(md5_file_path)

    filenames = [f"{name}.zip" for name in index.keys()]
    for filename in filenames:
        zip_path = charts_dir / filename

        if not zip_path.exists():
            missing.add(filename)
        elif (target_md5 := md5_dict.get(filename, None)) is None:
            missing_in_md5.add(filename)
        elif md5_check.calc_md5(zip_path) != target_md5:
            outdated.add(filename)
        # else: 校验通过

    if any([missing, missing_in_md5, outdated]):
        MESSAGE = "发现 Neskol/Maichart-Converts 标准谱面集未同步："
        if missing:
            MESSAGE += "MD5 缺少的谱面：\n" + ', '.join(sorted(missing)) if missing else ""
        if missing_in_md5:
            MESSAGE += "本地缺少的谱面：\n" + ', '.join(sorted(missing_in_md5)) if missing_in_md5 else ""
        if outdated:
            MESSAGE += "需要更新的谱面：\n" + ', '.join(sorted(outdated)) if outdated else ""
        return MESSAGE
    return [charts_dir / filename for filename in filenames]


if __name__ == "__main__":

    # ======================================================
    # 路径配置

    # Path.cwd() 的预设目标是根目录（`lyra-bot/~`）
    PLUGIN_CONFIG_PATH = Path.cwd() / "plugin_data/maib"
    # 标准谱面集：来自 `Neskol/Maichart-Converts`
    standard_chart_path: Path = PLUGIN_CONFIG_PATH / "charts"
    # 非标准谱面集
    other_chart_dir_paths: List[Path] = [
        PLUGIN_CONFIG_PATH / "charts2",
    ]
    # 标准谱面集的本地 MD5 预校验信息
    md5_file_path: Path = standard_chart_path / "md5.json"
    # 版本映射配置
    config_yaml_path = Path.cwd() / "versions.yaml"
    # .env 文件路径
    env_file_path = Path.cwd() / ".env.prod"

    # ======================================================
    # 业务逻辑

    # 标准谱面集校验
    result = check(standard_chart_path, md5_file_path)
    if isinstance(result, str):
        print(result)
        sys.exit(1)
    else:
        standard_chart_list: List[Path] = result

    # 从压缩包提取数据
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        versions_config: Dict[int, str] = yaml.safe_load(f)
    if not versions_config:
        print("无法加载版本映射配置")
        sys.exit(1)

    # 合并所有谱面集
    charts: List[Path] = standard_chart_list.copy()
    for chart_dir_path in other_chart_dir_paths:
        new_charts = chart_dir_path.glob("*.zip")
        charts.extend(new_charts)

    # 从谱面集提取 maidata 数据
    maidata_list = fetch.process_chart_folders(charts, versions_config)
    maidata_list = fetch.sync_diving_fish_version(maidata_list, versions_config)

    # 保存到数据库
    sql_alchemy = save.get_sql_alchemy_from_env(".env.prod")
    if sql_alchemy:
        import asyncio
        asyncio.run(save.run_import(sql_alchemy, maidata_list))
