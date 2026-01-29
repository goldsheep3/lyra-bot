import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Optional, List, Any

from loguru import logger

# 导入 maib 插件中的 MaiData 相关类
sys.path.insert(0, Path.cwd().as_posix())
from plugins.maib.utils import MaiData, MaiChart


def get_by_list(dict_obj: dict, key_list: str | List[str], default: Any, return_type: Optional[type] = None):
    """辅助函数：从字典中按键列表获取值"""
    if isinstance(key_list, str):
        key_list = [key_list]
    for key in key_list:
        if key in dict_obj:
            if return_type:
                try:
                    return return_type(dict_obj[key])
                except (ValueError, TypeError):
                    continue
            # 未指定或转换失败，直接返回原值
            return dict_obj[key]
    return default


def get_chart(raw_metadata: dict, chart_num: int) -> Optional[MaiChart]:
    """辅助函数：获取谱面信息"""
    lv_key = f'lv_{chart_num}'
    des_key = f'des_{chart_num}'
    inote_key = f'inote_{chart_num}'
    if lv_key in raw_metadata:
        chart = MaiChart(
            difficulty=chart_num,
            lv=float(raw_metadata.get(lv_key, '0').rstrip('?')),
            des=str(raw_metadata.get(des_key, '')),
            inote=str(raw_metadata.get(inote_key, ''))
        )
        return chart
    return None


def parse_version(version_str: str, version_dict: Dict[int, str]) -> Optional[int]:
    """辅助函数：解析版本号"""
    v_str = version_str.lower().strip()
    if not v_str:
        return None
    rd = {v.lower().strip(): k for k, v in version_dict.items()}
    # 1. 直接匹配
    v = rd.get(v_str, None)
    # 2. 尝试去掉前缀 "maimai "
    if not v:
        if v_str[:7] == "maimai ":
            v_str = v_str[6:].strip()
            v = rd.get(v_str, None)
    # 3. 尝试替换 DX -> でらっくす
    if not v:
        if 'dx' in v_str:
            v_str = v_str.replace('dx', 'でらっくす')
            v = rd.get(v_str, None)
    # 4. 尝试去掉前缀 "でらっくす "
    if not v:
        if v_str[:6] == "でらっくす ":
            v_str = v_str[5:].strip()
            v = rd.get(v_str, None)
    if v is None:
        logger.warning(f"无法解析版本号: {version_str}")
    return v


def parse_diving_fish_version(version_str: str, version_dict: Dict[int, str]) -> Optional[int]:
    """辅助函数：解析国服版本号"""
    v_jp_result = parse_version(version_str, version_dict)
    if v_jp_result is None:
        return None
    elif v_jp_result <= 12:
        # 旧框版本，一致
        return v_jp_result
    else:
        # 新框版本，转化
        v = (v_jp_result - 13) // 2 + 2020
        return v


def parse_maidata(raw_metadata: Dict[str, str], versions_config: Dict[int, str], zip_path: Path) -> MaiData:
    """通过 maidata.txt 元数据解析 MaiData"""

    def raw_get(key_list, return_type: type = str, default: Any = ""):
        return get_by_list(raw_metadata, key_list, default, return_type)

    shortid = raw_get(['shortid', 'id'], int, 0)
    title = raw_get(['title'])
    bpm = raw_get(['wholebpm', 'bpm'], int, 0)
    artist = raw_get(['artist'])
    genre = raw_get(['genre'])
    cabinet = raw_get(['cabinet'], default="SD" if shortid < 10000 else "DX")
    version_str = raw_get(['version'])
    version = parse_version(version_str, versions_config)
    converter = raw_get(['ChartConverter'])

    mai = MaiData(
        shortid=shortid,
        title=title,
        bpm=bpm,
        artist=artist,
        genre=genre,
        cabinet=cabinet,
        version=version,
        version_cn=None,
        converter=converter,
        img_path=zip_path / "bg.png"
    )

#     # Utage 宴会场 专属字段
    #     utage: bool = True  # Utage: Utage 标志
    #     buddy: bool = False  # Utage: 是否为 Buddy 谱面
    #     utage_tag: str = ""  # Utage: utage 标签
    #     _chart7: Optional[MaiChart] = None  # Utage: Utage 谱面
    # Utage 宴会场 判断
    utage_levels = [int(k[3:]) if k[-1:] == '?' else False for k in raw_metadata.keys() if k.startswith('lv_')]
    if any(utage_levels):
        # 等级带 '?'，视为 Utage 谱面
        mai.utage = True
        mai.utage_tag = mai.title[1:2]  # 取`[X]......`的`X`宴会场标签
        if len(utage_levels) == 1:
            # Utage
            mai.buddy = False
            mai._chart7 = get_chart(raw_metadata, 7)
        elif len(utage_levels) == 2:
            # Utage Buddy
            mai.buddy = True
            mai._chart2 = get_chart(raw_metadata, 2)
            mai._chart3 = get_chart(raw_metadata, 3)
    else:
        # 非 Utage 谱面
        for chart_num in range(2, 7):
            chart = get_chart(raw_metadata, chart_num)
            setattr(mai, f'_chart{chart_num}', chart)

    return mai


def process_chart_files(chart_files: List[Path], versions_config: Dict[int, str]) -> List[MaiData]:
    """处理文件夹中所有 zip 文件，提取 maidata.txt 中的元数据"""
    logger.info(f"开始处理谱面文件，共 {len(chart_files)} 个")
    result = dict()
    for chart_path in chart_files:
        if not chart_path.exists():
            logger.warning(f"文件不存在: {str(chart_path)}")
            continue
        chart_file_name = chart_path.stem

        try:
            # 打开 zip 文件
            with zipfile.ZipFile(chart_path, 'r') as zip_ref:
                # 直接读取 maidata.txt 内容
                with zip_ref.open("maidata.txt") as f:
                    content = f.read().decode('utf-8')

            # 提取元数据
            raw_metadata = {}
            content = content.replace('\n', '').replace('\r', '')
            content = content.replace('&', '\n&')
            pattern = re.compile(r'^&(\w+)=(.+)$')
            # 逐行匹配
            for line in content.splitlines()[1:]:  # 跳过整理换行时多余的第一行空行
                match = pattern.match(line.strip())
                if match:
                    key, value = match.groups()
                    raw_metadata[key] = value.strip()

            if not raw_metadata:
                # 未提取到元数据
                logger.warning(f"未提取到 {chart_file_name} 的元数据")
                continue
            mai = parse_maidata(raw_metadata, versions_config, chart_path)
            result[mai.shortid] = mai

            logger.success(f"成功处理 {chart_file_name}: {mai.title}")

        except Exception as e:
            logger.warning(f"处理失败 {chart_file_name}: {e}")

    logger.success(f"处理完成，已覆盖提取到 {len(result)} 谱面数据")
    return list(result.values())


def process_chart_folders(folder_path_list: List[Path], versions_config: Dict[int, str]) -> List[MaiData]:
    """处理多个文件夹中的谱面文件"""
    files = []
    for folder_path in folder_path_list:
        if not folder_path.exists():
            logger.warning(f"文件夹不存在: {folder_path}")
            continue
        zip_files = list(folder_path.glob("*.zip"))
        if not zip_files:
            logger.warning(f"文件夹中没有找到 zip 文件: {folder_path}")
            continue
        files.extend(zip_files)
    files.reverse()
    return process_chart_files(files, versions_config)


def sync_diving_fish_version(maidata_list: List[MaiData], versions_config: Dict[int, str]):
    """使用水鱼查分器数据同步国服版本信息"""
    from downloader import get_diving_fish_music_data
    versions_cn_dict: Dict[int, Optional[int]] = {
        int(data.get('id', 0)): parse_diving_fish_version(data.get('basic_info', {}).get('from', ''), versions_config)
        for data in get_diving_fish_music_data()}
    for maidata in maidata_list:
        v_cn = versions_cn_dict.get(maidata.shortid, None)
        if v_cn:
            maidata.version_cn = v_cn
    return maidata_list


if __name__ == "__main__":

    # Loguru 日志配置
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> <cyan>[{level}]</cyan> {message}\n",
        colorize=False,
    )

    # 版本映射配置
    config_yaml_path = Path.cwd() / "versions.yaml"
    import yaml
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        versions_config: Dict[int, str] = yaml.safe_load(f)

    # 从 ZIP 获取 maidata 数据
    maidata_list = process_chart_folders([  # 排前的优先级更高
        Path.cwd() / "plugin_data" / "maib" / "charts"
    ], versions_config)
    maidata_list = sync_diving_fish_version(maidata_list, versions_config)

    logger.success(f"\n提取 {len(maidata_list)} 个谱面数据")
    logger.warning("提取到的数据未保存，请使用 save to db 脚本处理，而不是直接运行此脚本。")
