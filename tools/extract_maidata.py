import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Any

from loguru import logger


@dataclass
class MaiDataChart:
    """maimai 谱面信息"""
    lv: float  # level 等级
    des: str  # designer 谱师
    inote: str  # note 音符数据


@dataclass
class MaiData:
    """maimai 歌曲元数据"""

    shortid: int  # 曲目 ID
    title: str  # 曲名
    bpm: int  # BPM
    artist: str  # 艺术家
    genre: str  # 流派
    cabinet: str  # 谱面类型
    version: int  # 日服更新版本
    version_cn: Optional[int]  # 国服更新版本
    converter: str  # 谱面来源
    zip_path: str = ""  # zip 压缩包文件位置

    chart1: Optional[MaiDataChart] = None  # Easy
    chart2: Optional[MaiDataChart] = None  # Basic
    chart3: Optional[MaiDataChart] = None  # Advanced
    chart4: Optional[MaiDataChart] = None  # Expert
    chart5: Optional[MaiDataChart] = None  # Master
    chart6: Optional[MaiDataChart] = None  # Re: Master


@dataclass
class UtageMaiData(MaiData):
    """maimai 宴会场谱面"""
    utage: bool = True
    buddy: int = 0  # buddy 数量
    utage_tag: str = ""  # utage 标签

    chart7: Optional[MaiDataChart] = None  # Utage 谱面


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


def get_chart(raw_metadata: dict, chart_num: int) -> Optional[MaiDataChart]:
    """辅助函数：获取谱面信息"""
    lv_key = f'lv_{chart_num}'
    des_key = f'des_{chart_num}'
    inote_key = f'inote_{chart_num}'
    if lv_key in raw_metadata:
        chart = MaiDataChart(
            lv=float(raw_metadata.get(lv_key, "?")[:-1]),  # 去掉末尾的 '?' 符号
            des=str(raw_metadata.get(des_key, '')),
            inote=str(raw_metadata.get(inote_key, ''))
        )
        return chart
    return None


def parse_version(version_str: str, version_dict: Dict[int, str]) -> Optional[int]:
    """辅助函数：解析版本号"""
    v_str = version_str.lower().strip()
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


def extract_metadata_from_maidata(content: str) -> Dict[str, str]:
    """
    从 maidata. txt 内容中提取 &key=value 格式的元数据

    Args:
        content: maidata.txt 文件内容

    Returns:
        包含提取的键值对的字典
    """
    metadata = {}
    # 整理换行
    content = content.replace('\n', '').replace('\r', '')
    content = content.replace('&', '\n&')
    # 逐行匹配
    pattern = re.compile(r'^&(\w+)=(.+)$')
    for line in content.splitlines()[1:]:  # 跳过第一行
        match = pattern.match(line.strip())
        if match:
            key, value = match.groups()
            metadata[key] = value.strip()

    return metadata


def parse_normal_maidata(raw_metadata: Dict[str, str], versions_config: Dict[int, str], zip_path: str = "") -> MaiData:
    """
    解析普通 maimai 谱面

    Args:
        raw_metadata: 原始提取的键值对字典
        versions_config: 版本映射配置字典
        zip_path: zip 文件路径

    Returns:
        MaiData 对象
    """

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
        zip_path=zip_path
    )

    for chart_num in range(2, 7):
        chart = get_chart(raw_metadata, chart_num)
        setattr(mai, f'chart{chart_num}', chart)

    return mai


def parse_utage_maidata(raw_metadata: Dict[str, str], versions_config: Dict[int, str], zip_path: str = "") -> UtageMaiData:
    """
    解析宴会场 maimai 谱面

    Args:
        raw_metadata: 原始提取的键值对字典
        versions_config: 版本映射配置字典
        zip_path: zip 文件路径

    Returns:
        UtageMaiData 对象
    """

    def raw_get(key_list, return_type: type = str, default: Any = ""):
        return get_by_list(raw_metadata, key_list, default, return_type)

    shortid = raw_get(['shortid', 'id'], int, 0)
    title = raw_get(['title'])
    bpm = raw_get(['wholebpm', 'bpm'], int, 0)
    artist = raw_get(['artist'])
    genre = raw_get(['genre'])
    version_str = raw_get(['version'])
    version = parse_version(version_str, versions_config)
    converter = raw_get(['ChartConverter'])

    mai = UtageMaiData(
        shortid=shortid,
        title=title,
        bpm=bpm,
        artist=artist,
        genre=genre,
        cabinet="UTAGE",
        version=version,
        version_cn=None,
        converter=converter,
        zip_path=zip_path
    )

    match = re.match(r'^\[(.)]', title)
    mai.utage_tag = match.group(1) if match else ""

    buddy_count = 0
    if 'lv_7' in raw_metadata:
        chart = get_chart(raw_metadata, 7)
        mai.chart7 = chart
    else:
        for chart_num in range(2, 7):
            chart = get_chart(raw_metadata, chart_num)
            if chart:
                buddy_count += 1
                setattr(mai, f'chart{chart_num}', chart)
    mai.buddy = buddy_count

    return mai


def process_zip_files(zip_folder_path: Path, versions_config: Dict[int, str]) -> List[MaiData | UtageMaiData]:
    """
    处理文件夹中所有 zip 文件，提取 maidata. txt 中的元数据

    Args:
        zip_folder_path: 包含 zip 文件的文件夹路径
        versions_config: 版本映射配置字典

    Returns:
        解析后的 MaiData 或 UtageMaiData 对象
    """
    result = []
    if not zip_folder_path.exists():
        logger.info(f"❌ 文件夹不存在: {zip_folder_path}")
        return result

    zip_files = list(zip_folder_path.glob("*.zip"))
    if not zip_files:
        logger.info(f"⚠️ 文件夹中没有找到 zip 文件: {zip_folder_path}")
        return result

    logger.info(f"📦 找到 {len(zip_files)} 个 zip 文件")

    for zip_path in zip_files:
        zip_name = zip_path.stem

        try:
            # 打开 zip 文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 直接读取 maidata.txt 内容
                with zip_ref.open("maidata.txt") as f:
                    content = f.read().decode('utf-8')

            # 提取元数据
            raw_metadata = extract_metadata_from_maidata(content)

            if raw_metadata:
                # (Utage) or (Utage Buddy)
                if ('lv_7' in raw_metadata) or ('?' in raw_metadata.get('lv_2', "")):
                    mai = parse_utage_maidata(raw_metadata, versions_config, str(zip_path))
                else:
                    mai = parse_normal_maidata(raw_metadata, versions_config, str(zip_path))
                result.append(mai)

                # 根据类型显示不同信息
                if isinstance(mai, UtageMaiData):
                    if mai.chart7:
                        logger.info(f"✅ {zip_name}: U·TA·GE {mai.title}")
                    else:
                        logger.info(f"✅ {zip_name}: U·TA·GE(BUDDY) {mai.title}")
                else:
                    logger.info(f"✅ {zip_name}: {mai.title}")
            else:
                logger.info(f"⚠️ {zip_name}: 未提取到元数据")

        except zipfile.BadZipFile:
            logger.info(f"❌ {zip_name}: 无效的 zip 文件")
        except Exception as e:
            logger.info(f"❌ {zip_name}: 处理失败 - {e}")

    logger.info(f"🎉 处理完成，成功提取 {len(result)} 个文件的元数据")
    return result


if __name__ == "__main__":
    # 版本映射配置

    config_yaml_path = Path(input("CONFIG YAML PATH: "))
    import yaml
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        versions_config: Dict[int, str] = yaml.safe_load(f)
    zip_folder_path = Path(input("ZIP FOLDER: "))

    logger.info("🚀 开始处理 zip 文件")
    maidata_dict = process_zip_files(zip_folder_path, versions_config)

    # 分类统计
    normal_count = sum(1 for m in maidata_dict if isinstance(m, MaiData))
    utage_count = sum(1 for m in maidata_dict if isinstance(m, UtageMaiData))

    logger.info(f"\n📊 提取结果统计:")
    logger.info(f"  普通谱面:  {normal_count}")
    logger.info(f"  Utage 谱面: {utage_count}")
