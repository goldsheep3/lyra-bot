import sys
import yaml
from pathlib import Path

from tools.maidata import fetch, save


if __name__ == "__main__":

    # ======================================================
    # 路径配置

    # Path.cwd() 的预设目标是根目录（`../lyra-bot $`）
    PLUGIN_CONFIG_PATH = Path.cwd() / "plugin_data/maib"
    # 谱面目录集
    chart_dir_paths: list[Path] = [
        PLUGIN_CONFIG_PATH / "charts",  # 标准谱面集：来自 `Neskol/Maichart-Converts`
        PLUGIN_CONFIG_PATH / "charts2",
    ]
    # 版本映射配置
    versions_yaml_path = Path.cwd() / "assets" / "versions.yaml"
    genre_yaml_path = Path.cwd() / "assets" / "genres.yaml"
    # .env 文件路径
    env_file_path = Path.cwd() / ".env.prod"

    # ======================================================
    # 业务逻辑

    # 从压缩包提取数据
    with open(versions_yaml_path, "r", encoding="utf-8") as f:
        versions_config: dict[int, str] = yaml.safe_load(f)
    with open(genre_yaml_path, "r", encoding="utf-8") as f:
        genre_config: dict[int, dict[str, str]] = yaml.safe_load(f)
    if not (versions_config and genre_config):
        print("加载配置失败")
        sys.exit(1)

    # 合并所有谱面集
    charts: list[Path] = []
    for chart_dir_path in chart_dir_paths:
        new_charts = chart_dir_path.glob("*.zip")
        charts.extend(new_charts)

    # 从谱面集提取 maidata 数据
    maidata_list = fetch.process_chart_files(charts, versions_config)
    maidata_list = fetch.sync_diving_fish_version(maidata_list, versions_config)
    maidata_list = fetch.sync_aliases(maidata_list)  # 同步 Lxns 和 YuzuChaN 别名数据

    # 保存到数据库
    sql_alchemy = save.get_sql_alchemy_from_env(".env.prod")
    if sql_alchemy:
        import asyncio
        asyncio.run(save.run_import(sql_alchemy, maidata_list))
