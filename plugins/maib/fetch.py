import re
import orjson
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import process
from nonebot import logger
from nonebot_plugin_datastore.db import post_db_init

from. import models, network, services
from .bot_registry import PluginRegistry
from .utils import MaiData, MaiChart, GENRES_DATA, VERSIONS_DATA
from .note_count import count_to_tuple


def initialize_genres_data_rev():
    genres_config_rev = {}
    for k, v in GENRES_DATA.items():
        if isinstance(v, dict):
            for lang in ['jp', 'intl', 'cn']:
                if lang_val := v.get(lang):
                    clean_key = lang_val.lower().replace('\n', '').strip()
                    genres_config_rev[clean_key] = k
    return genres_config_rev

GENRES_DATA_REV = initialize_genres_data_rev()


def get_file_stat_identity(file_path: Path) -> str:
    """获取文件的特征标识（修改时间 + 文件大小）"""
    stat = file_path.stat()
    # 使用 修改时间_文件大小 作为唯一标识
    return f"{stat.st_mtime}_{stat.st_size}"


async def parse_version(version_str: str) -> int:
    """辅助函数：解析版本号"""
    global VERSIONS_DATA

    v_str = version_str.lower().strip()
    if not v_str:
        return -1
    rd = {v.lower().strip(): k for k, v in VERSIONS_DATA.items()}
    # 1. 直接匹配
    v = rd.get(v_str, None)
    # 2. 尝试去掉前缀 "maimai "
    if not v:
        if v_str[:7] == "maimai ":
            v_str = v_str[7:].strip()
            v = rd.get(v_str, None)
    # 3. 尝试替换 DX -> でらっくす
    if not v:
        if 'dx' in v_str:
            v_str = v_str.replace('dx', 'でらっくす')
            v = rd.get(v_str, None)
    # 4. 尝试去掉前缀 "でらっくす "
    if not v:
        if v_str[:6] == "でらっくす ":
            v_str = v_str[6:].strip()
            v = rd.get(v_str, None)
    if v is None:
        logger.warning(f"无法解析版本号: {version_str}")
        return -1
    return v


async def parse_diving_fish_version(version_str: str) -> int:
    """辅助函数：解析国服版本号"""
    v_jp_result = await parse_version(version_str)
    if v_jp_result <= 12:
        # 旧框版本，一致
        return v_jp_result
    else:
        # 新框版本，转化
        v = (v_jp_result - 13) // 2 + 2020
        return v


async def parse_genre(genre_str: str, genre_dict_fixed: dict[str, int]) -> int:
    """辅助函数：解析流派名"""
    g_str = genre_str.lower().strip()
    if not g_str:
        return -1

    # 1. 精确匹配
    g = genre_dict_fixed.get(g_str, None)
    
    # 2. 模糊匹配 (容错几个字符)
    if g is None:
        try:
            # 提取相似度最高的一个，阈值设为 80 (可以根据实际效果调整)
            best_match = process.extractOne(g_str, list(genre_dict_fixed.keys()))
            if best_match and best_match[1] >= 80:
                g = genre_dict_fixed[best_match[0]]
                logger.debug(f"流派模糊匹配成功: '{genre_str}' -> '{best_match[0]}' (相似度: {best_match[1]})")
        except ImportError:
            logger.warning("未安装 thefuzz 库，跳过模糊匹配")

    if g is None:
        logger.warning(f"无法解析流派名: {genre_str}")
        return -1
    return g

async def get_chart(raw_metadata: dict, short_id: int, chart_num: int) -> MaiChart | None:
    """辅助函数：获取谱面信息"""

    lv_key = f'lv_{chart_num}'
    des_key = f'des_{chart_num}'
    inote_key = f'inote_{chart_num}'
    if lv_key in raw_metadata:
        lv_str = raw_metadata.get(lv_key, '0').rstrip('?')
        if not lv_str:
            return None  # lv 为空，视为无该难度谱面
        chart = MaiChart(
            shortid=short_id,
            difficulty=chart_num,
            lv=float(lv_str),
            des=str(raw_metadata.get(des_key, '')),
            inote=str(raw_metadata.get(inote_key, '')),
        )
        chart.set_notes_with_tuple(await count_to_tuple(raw_metadata.get(inote_key, '')))
        return chart
    return None

async def parse_maidata(raw_metadata: dict[str, str], zip_path: Path) -> MaiData:
    """通过 maidata.txt 元数据解析 MaiData"""
    global GENRES_DATA_REV

    def raw_get(key_list, return_type: type = str, default = None):
        """从 raw_metadata 中获取数据的工具函数，支持多个候选 key 和类型转换"""
        if isinstance(key_list, str):
            key_list = [key_list]
        for key in key_list:
            if key in raw_metadata:
                if return_type:
                    try:
                        return return_type(raw_metadata[key])
                    except (ValueError, TypeError):
                        continue
        return default

    shortid = raw_get(['shortid', 'id'], int, 0)
    title = raw_get(['title'], default="")
    bpm = raw_get(['wholebpm', 'bpm'], int, 0)
    artist = raw_get(['artist'], default="")
    genre = await parse_genre(raw_get(['genre'], default=""), GENRES_DATA_REV)
    _cabinet = raw_get(['cabinet'], default=None)
    if _cabinet is None:
        cabinet = "SD" if shortid < 10000 else "DX"
    else:
        cabinet = "DX" if any(k in _cabinet.lower() for k in ["dx", "でらっくす", "deluxe"]) else "SD"
    version_str = raw_get(['version'], default="")
    version = await parse_version(version_str)
    converter = raw_get(['ChartConverter'], default="")

    # title 处理：去掉`[XXXX]`
    title = re.sub(r'\[(宴|DX|SD)]$', '', title)

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
        zip_path=zip_path,
        img_path=zip_path / 'bg.png'
    )

    # Utage 宴会场 判断
    if mai.shortid > 100000:
        # Utage
        mai.is_utage = True
        matched = re.match(r'\[(.)]', mai.title)  # 取`[X]......`的`X`宴会场标签
        mai.utage_tag = matched.group(1) if matched else "宴"
        if raw_metadata.get('lv_7', '').strip():
            mai.buddy = False
            mai.set_chart(await get_chart(raw_metadata, shortid, 7))
        else:
            mai.buddy = True
            mai.set_chart(await get_chart(raw_metadata, shortid, 2))
            mai.set_chart(await get_chart(raw_metadata, shortid, 3))
    else:
        # 非 Utage 谱面
        for chart_num in range(2, 7):
            mai.set_chart(await get_chart(raw_metadata, shortid, chart_num))

    return mai

async def process_chart_files(chart_files: list[Path]) -> list[MaiData]:
    """处理文件夹中所有 zip 文件，提取 maidata.txt 中的元数据"""
    logger.info(f"数据同步-谱面处理开始：共 {len(chart_files)} 个 zip 文件")
    cache_path = PluginRegistry.get_cache_dir() / "stat_cache.json"
    if cache_path.exists():
        stat_cache = orjson.loads(cache_path.read_bytes())
    else:
        stat_cache = {}

    result = dict()
    for chart_path in chart_files:

        if not chart_path.exists():
            logger.warning(f"数据同步-谱面处理：{str(chart_path)} 不存在，跳过")
            continue
        chart_file_name = chart_path.stem

        # 文件状态校验，跳过未修改的文件
        file_identity = get_file_stat_identity(chart_path)
        if stat_cache.get(chart_file_name) == file_identity:
            logger.info(f"数据同步-谱面处理：{chart_path.name} 未修改，跳过")
            continue
        else:
            stat_cache[chart_file_name] = file_identity

        try:
            # 打开 zip 文件
            with zipfile.ZipFile(chart_path, 'r') as zip_ref:
                # 直接读取 maidata.txt 内容
                with zip_ref.open("maidata.txt") as f:
                    content = f.read().decode('utf-8')

            # 提取元数据
            parts = content.replace('\r\n', '\n').split('&')
            raw_metadata = {}

            for part in parts:
                if '=' in part:
                    # 只分割第一个 '='，防止注释或内容里有等号
                    k, v = part.split('=', 1)
                    # 去掉首尾空格和换行
                    raw_metadata[k.strip()] = v.strip()

            if not raw_metadata:
                # 未提取到元数据
                logger.warning(f"数据同步-谱面处理：未提取到 {chart_file_name} 的元数据")
                continue
            mai: MaiData = await parse_maidata(raw_metadata, chart_path)

            # 去重：以 shortid 为准，后处理的覆盖前处理的
            # 若前处理的含 Re:MASTER 谱面，优先保留有 Re:MASTER 谱面的版本
            if mai.shortid in result.keys():
                exist_remaster: bool = getattr(result[mai.shortid], '_chart6', None) is not None
                new_remaster: bool = getattr(mai, '_chart6', None) is not None
                if not (exist_remaster and not new_remaster):
                    result[mai.shortid] = mai
            else:
                result[mai.shortid] = mai

            logger.success(f"数据同步-谱面处理成功：{chart_file_name}({mai.title})")

        except Exception as e:
            logger.warning(f"数据同步-谱面处理失败 {chart_file_name}: {e}")
            raise e

    # 更新 stat 缓存
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(orjson.dumps(stat_cache))

    logger.success(f"数据同步-谱面处理完成：合计处理到 {len(result)} 条谱面数据")
    return list(result.values())


async def upsert_maidata(session: AsyncSession, data: MaiData):
    """插入或更新 MaiData 数据"""
    result = await session.execute(
        select(models.MaiData)
        .where(models.MaiData.shortid == data.shortid)
        .options(
            selectinload(models.MaiData.charts),
            selectinload(models.MaiData.aliases))
    )
    existing = result.scalar_one_or_none()
    if existing:
        # 更新基础信息
        for attr in ['title', 'bpm', 'artist', 'genre', 'cabinet', 'version', 
                     'version_cn', 'converter', 'is_utage', 'utage_tag', 'buddy']:
            setattr(existing, attr, getattr(data, attr))
        existing.zip_path = str(data.zip_path)
    else:
        # 创建新数据
        existing = models.MaiDataModelFactory.mai_data(data)
        session.add(existing)
        existing.charts = existing.charts or []
        existing.aliases = existing.aliases or []

    # 处理谱面数据
    changed_tasks = []
    existing_charts = {chart.difficulty: chart for chart in existing.charts}
    for chart in data.charts.values():
        if chart.difficulty in existing_charts:
            # 更新已有谱面
            ec = existing_charts[chart.difficulty]
            if ec.lv != chart.lv:
                changed_tasks.append((data.shortid, chart.difficulty, "JP"))
            if ec.lv_cn != chart.lv_cn:
                changed_tasks.append((data.shortid, chart.difficulty, "CN"))
            ec.lv = chart.lv
            ec.lv_cn = chart.lv_cn
            ec.lv_synh = chart.lv_synh
            ec.des = chart.des
            ec.inote = chart.inote
            (
                ec.note_count_tap,
                ec.note_count_hold,
                ec.note_count_slide,
                ec.note_count_touch,
                ec.note_count_break
                ) = chart.notes
        else:
            # 添加新谱面
            new_chart = models.MaiDataModelFactory.mai_chart(chart, data.shortid)
            existing.charts.append(new_chart)

    # 处理别名数据
    existing_alias_names = {a.alias for a in existing.aliases}
    for alias_obj in data.aliases:
        if alias_obj.alias not in existing_alias_names:
            new_alias = models.MaiDataModelFactory.mai_alias(alias_obj)
            existing.aliases.append(new_alias)
            existing_alias_names.add(alias_obj.alias)

    for shortid, diff, server_tag in changed_tasks:
        await services.refresh_dxrating_cache(shortid, diff, server_tag)
        


@post_db_init
async def maintenance_task():
    """每日重启后自动运行的数据重整理"""
    logger.info("maib 数据同步中")
    
    try:
        # 1. 准备路径和配置
        data_dir = PluginRegistry.get_data_dir()
        if not data_dir:
            logger.error("数据同步失败：无法获取谱面目录")
            return
        chart_dirs = [data_dir / "charts", data_dir / "charts2"]
        
        # 2. 收集文件
        charts_files = []
        for d in chart_dirs:
            if d.exists():
                charts_files.extend(d.glob("*.zip"))
        if not charts_files:
            logger.warning("数据同步结束：未找到任何谱面文件")
            return

        # 3. 处理数据
        maidata_dict: dict[int, MaiData] = {m.shortid: m for m in await process_chart_files(charts_files)}

        # 4. 同步国服难度和版本
        if sy_music_data := await network.sy_music_data_from_file(PluginRegistry.get_cache_dir() / "sy_music_data.json"):
            for sy_data in sy_music_data:
                shortid = int(sy_data.get('id', 0))
                # 国服难度表
                ds: list[int] = sy_data.get("ds", [])
                # 国服版本号
                ver = await parse_diving_fish_version(sy_data.get('basic_info', {}).get('from', ''))
            
                if shortid in maidata_dict:
                    maidata = maidata_dict[shortid]
                    # 同步版本号
                    maidata.version_cn = ver
                    # 同步难度
                    for diff, chart in maidata.charts.items():
                        lv_cn = ds[diff-2] if diff-2 < len(ds) else None
                        if lv_cn is not None:
                            chart.lv_cn = lv_cn
        else:
            logger.warning("数据同步-水鱼数据：music_data 加载失败，无法同步国服版本号")

        # 5. 存储到数据库
        get_session = PluginRegistry.get_session
        async with get_session() as session:
            total = len(maidata_dict)
            for idx, mai in enumerate(maidata_dict.values()):
                try:
                    await upsert_maidata(session, mai)
                    if (idx + 1) % 50 == 0:
                        await session.commit()
                        logger.info(f"数据同步进度: [{idx+1}/{total}]")
                except Exception as e:
                    logger.error(f"处理 {mai.shortid} ({mai.title}) 失败: {e}")
                    await session.rollback()
            
            # 最后统一 commit 剩余部分
            await session.commit()

        # 6. 同步拟合难度
        sy_lvnh = []
        if sy_chart_stats := await network.sy_chart_stats():
            for shortid, sy_stats in sy_chart_stats.get("charts", {}).items():
                shortid = int(shortid)
                fit_diffs: list[float] = [s.get('fit_diff', 0) for s in sy_stats]
                for diff, fit_diff in enumerate(fit_diffs, start=2):
                    sy_lvnh.append((shortid, diff, fit_diff))
            if sy_lvnh:
                await services.set_lv_synh_batch(sy_lvnh)
        else:
            logger.warning("数据同步-水鱼数据：chart_stats 加载失败，无法同步拟合难度")

        # 7. 独立获取别名数据
        from time import time
        
        now = int(time())
        # 处理 Yuzuchan 别名
        if yuzuchan_data := await network.yuzuchan_alias_list():
            aliases_set: set[tuple[int, str]] = set()
            for entry in yuzuchan_data.get("content", []):
                song_id = int(entry.get('SongID', 0))
                aliases: list[str] = entry.get('Alias', '')
                aliases_set.update((song_id, alias) for alias in aliases)
            # 存储别名数据
            await services.add_aliases(list(aliases_set), source_id=-101, add_time=now)
        # 处理 LXNS 别名
        if lxns_data := await network.lx_alias_list():
            aliases_set: set[tuple[int, str]] = set()
            for entry in lxns_data.get("aliases", []):
                song_id = int(entry.get('song_id', 0))
                aliases: list[str] = entry.get('aliases', [])
                aliases_set.update((song_id, alias) for alias in aliases)
            # 存储别名数据
            await services.add_aliases(list(aliases_set), source_id=-102, add_time=now)

        logger.success("maib 数据重整理完成！")
        
    except Exception as e:
        logger.error(f"数据重整理失败: {e}")

