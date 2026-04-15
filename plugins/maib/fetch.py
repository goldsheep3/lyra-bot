import re
import orjson
import zipfile
from time import time
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import process
from nonebot import logger, require
require("nonebot_plugin_datastore")
from nonebot_plugin_datastore.db import post_db_init, get_engine

from. import models, network, services
from .bot_registry import PluginRegistry
from .utils import MaiData, MaiChart, SimaiNoteCount
from .constants import *


def get_sql_name() -> str:
    try:
        return get_engine().name
    except ValueError:
        return "no_sql"
    except Exception:
        return "unknown"
        

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


STAT_CACHE_META_KEY = "__meta__"
LAST_FETCH_TS_KEY = "last_fetch_ts"
FETCH_SKIP_WINDOW_SECONDS = 24 * 60 * 60


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
        # 版本号为 maib 自主定义，兼容水鱼版本号输出格式，不受官方版本号影响
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
        snc = await SimaiNoteCount(raw_metadata.get(inote_key, '')).process()
        chart.set_notes_with_tuple(snc.to_tuple())
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


def _extract_raw_metadata_from_content(content: str) -> dict[str, str]:
    """从 maidata.txt 内容提取键值元数据。"""
    parts = content.replace('\r\n', '\n').split('&')
    raw_metadata: dict[str, str] = {}
    for part in parts:
        if '=' in part:
            # 只分割第一个 '='，防止注释或内容里有等号
            k, v = part.split('=', 1)
            raw_metadata[k.strip()] = v.strip()
    return raw_metadata


async def read_chart_raw_metadata(chart_path: Path) -> dict[str, str] | None:
    """读取单个谱面 zip 的 maidata.txt 元数据。"""
    try:
        with zipfile.ZipFile(chart_path, 'r') as zip_ref:
            with zip_ref.open("maidata.txt") as f:
                content = f.read().decode('utf-8')
        raw_metadata = _extract_raw_metadata_from_content(content)
        return raw_metadata or None
    except Exception as e:
        logger.warning(f"数据同步-谱面处理失败 {chart_path.stem}: {e}")
        return None


def _parse_shortid_from_metadata(raw_metadata: dict[str, str]) -> int:
    """从元数据中提取 shortid。"""
    for key in ("shortid", "id"):
        v = raw_metadata.get(key)
        if v is None:
            continue
        try:
            return int(v)
        except (ValueError, TypeError):
            continue
    return 0


def _cache_key_for_path(chart_path: Path) -> str:
    """生成缓存 key，优先使用 data_dir 相对路径，保证文件名与 shortid 解耦。"""
    data_dir = PluginRegistry.get_data_dir()
    if data_dir:
        try:
            return chart_path.relative_to(data_dir).as_posix()
        except ValueError:
            pass
    return chart_path.as_posix()


def _normalize_cache_entry(raw_entry: object, fallback_shortid: int | None = None) -> dict[str, int | str] | None:
    """兼容旧缓存格式：str(identity) -> {identity, shortid?}。"""
    if isinstance(raw_entry, dict):
        identity = raw_entry.get("identity")
        shortid = raw_entry.get("shortid")
        normalized: dict[str, int | str] = {}
        if isinstance(identity, str):
            normalized["identity"] = identity
        if isinstance(shortid, int):
            normalized["shortid"] = shortid
        elif isinstance(shortid, str):
            try:
                normalized["shortid"] = int(shortid)
            except ValueError:
                pass
        elif fallback_shortid is not None:
            normalized["shortid"] = fallback_shortid
        return normalized if "identity" in normalized else None
    if isinstance(raw_entry, str):
        normalized = {"identity": raw_entry}
        if fallback_shortid is not None:
            normalized["shortid"] = fallback_shortid
        return normalized
    return None


def _load_stat_cache(cache_path: Path) -> tuple[dict[str, dict[str, int | str]], dict[str, int]]:
    """加载 stat 缓存，兼容旧版纯 entries 格式。"""
    if not cache_path.exists():
        return {}, {}

    try:
        raw = orjson.loads(cache_path.read_bytes())
    except Exception as e:
        logger.warning(f"数据同步-stat缓存读取失败，将视为空缓存: {e}")
        return {}, {}

    if not isinstance(raw, dict):
        return {}, {}

    raw_entries = raw.get("entries") if isinstance(raw.get("entries"), dict) else None
    raw_meta = raw.get(STAT_CACHE_META_KEY) if isinstance(raw.get(STAT_CACHE_META_KEY), dict) else None

    # 兼容旧格式：顶层就是 entries 映射。
    if raw_entries is None:
        raw_entries = {k: v for k, v in raw.items() if k != STAT_CACHE_META_KEY}

    entries: dict[str, dict[str, int | str]] = {}
    for k, v in raw_entries.items():
        if not isinstance(k, str):
            continue
        normalized = _normalize_cache_entry(v)
        if normalized is not None:
            entries[k] = normalized

    meta: dict[str, int] = {}
    if raw_meta is not None:
        ts = raw_meta.get(LAST_FETCH_TS_KEY)
        if isinstance(ts, int):
            meta[LAST_FETCH_TS_KEY] = ts
        elif isinstance(ts, str):
            try:
                meta[LAST_FETCH_TS_KEY] = int(ts)
            except ValueError:
                pass

    return entries, meta


def _save_stat_cache(
    cache_path: Path,
    entries: dict[str, dict[str, int | str]],
    meta: dict[str, int] | None = None,
):
    """写入 stat 缓存（entries + meta）。"""
    payload: dict[str, object] = {"entries": entries}
    if meta:
        payload[STAT_CACHE_META_KEY] = meta
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(orjson.dumps(payload))


def _classify_stat_change(
    chart_files: list[Path],
    stat_cache_entries: dict[str, dict[str, int | str]],
) -> tuple[int, int, int]:
    """基于 stat 缓存对文件做 A/B/C 分类，不开包。"""
    count_a = 0
    count_b = 0
    count_c = 0

    for chart_path in chart_files:
        if not chart_path.exists():
            continue

        cache_key = _cache_key_for_path(chart_path)
        chart_file_name = chart_path.stem
        file_identity = get_file_stat_identity(chart_path)

        legacy_entry = stat_cache_entries.get(chart_file_name)
        cache_entry = _normalize_cache_entry(stat_cache_entries.get(cache_key))
        if cache_entry is None and legacy_entry is not None:
            cache_entry = _normalize_cache_entry(legacy_entry)

        if cache_entry is None:
            count_c += 1
            continue

        raw_shortid = cache_entry.get("shortid")
        cached_shortid = raw_shortid if isinstance(raw_shortid, int) else None
        identity_match = (
            isinstance(cache_entry.get("identity"), str)
            and cache_entry["identity"] == file_identity
        )

        if identity_match and cached_shortid is not None:
            count_a += 1
        else:
            count_b += 1

    return count_a, count_b, count_c


def should_skip_fetch_by_stat(chart_files: list[Path]) -> bool:
    """当 B/C 均为 0 且最近一次完整抓取在 24h 内时，跳过本次 fetch。"""
    cache_path = PluginRegistry.get_cache_dir() / "stat_cache.json"
    stat_cache_entries, stat_cache_meta = _load_stat_cache(cache_path)
    count_a, count_b, count_c = _classify_stat_change(chart_files, stat_cache_entries)

    logger.info(f"数据同步-stat预检查：A={count_a}, B={count_b}, C={count_c}")

    if count_b != 0 or count_c != 0:
        return False

    last_fetch_ts = stat_cache_meta.get(LAST_FETCH_TS_KEY)
    if last_fetch_ts is None:
        return False

    now_ts = int(time())
    if now_ts - last_fetch_ts < FETCH_SKIP_WINDOW_SECONDS:
        logger.info(
            "数据同步-stat预检查命中：B/C 均为 0，且距上次完整抓取未超过 24 小时，跳过本次 fetch"
        )
        return True
    return False


def update_last_fetch_timestamp():
    """更新最近一次完整 fetch 的时间戳。"""
    cache_path = PluginRegistry.get_cache_dir() / "stat_cache.json"
    entries, meta = _load_stat_cache(cache_path)
    meta[LAST_FETCH_TS_KEY] = int(time())
    _save_stat_cache(cache_path, entries, meta)


def _merge_maidata_with_priority(existing: MaiData, new_data: MaiData) -> MaiData:
    """同 shortid 去重"""
    # 优先保留谱面数量更多的版本
    exist_charts = len(existing.charts)
    new_charts = len(new_data.charts)
    return existing if (exist_charts >= new_charts) else new_data

async def process_chart_files(chart_files: list[Path]) -> list[MaiData]:
    """按 shortid 增量处理 zip 文件，避免文件名与 shortid 绑定。"""
    logger.info(f"数据同步-谱面处理开始：共 {len(chart_files)} 个 zip 文件")
    cache_path = PluginRegistry.get_cache_dir() / "stat_cache.json"
    stat_cache_raw, stat_cache_meta = _load_stat_cache(cache_path)

    # 缓存候选项：首轮扫描收集，末尾按“是否成功重理”决定是否提交。
    pending_stat_cache: dict[str, dict[str, int | str]] = {}
    old_stat_cache: dict[str, dict[str, int | str]] = {}
    next_stat_cache: dict[str, dict[str, int | str]] = {}
    id_to_paths: dict[int, list[Path]] = {}
    needs_reprocess_ids: set[int] = set()
    preloaded_metadata: dict[str, dict[str, str]] = {}

    count_a = 0
    count_b = 0
    count_c = 0

    for chart_path in chart_files:
        if not chart_path.exists():
            logger.warning(f"数据同步-谱面处理：{str(chart_path)} 不存在，跳过")
            continue

        cache_key = _cache_key_for_path(chart_path)
        chart_file_name = chart_path.stem
        file_identity = get_file_stat_identity(chart_path)

        legacy_entry = stat_cache_raw.get(chart_file_name)
        cache_entry = _normalize_cache_entry(stat_cache_raw.get(cache_key))
        if cache_entry is None and legacy_entry is not None:
            cache_entry = _normalize_cache_entry(legacy_entry)
        if cache_entry is not None:
            old_stat_cache[cache_key] = cache_entry

        sid: int | None = None
        metadata: dict[str, str] | None = None
        cached_shortid: int | None = None
        if cache_entry is not None:
            raw_shortid = cache_entry.get("shortid")
            if isinstance(raw_shortid, int):
                cached_shortid = raw_shortid

        identity_match = (
            cache_entry is not None
            and isinstance(cache_entry.get("identity"), str)
            and cache_entry["identity"] == file_identity
        )

        if identity_match and cached_shortid is not None:
            # A 类：未变化，且缓存中已有 shortid。
            sid = cached_shortid
            count_a += 1
        else:
            # 非 A 类：只开包一次，先读元数据拿 shortid，并触发该 shortid 全组重理。
            metadata = await read_chart_raw_metadata(chart_path)
            if not metadata:
                logger.warning(f"数据同步-谱面处理：未提取到 {chart_file_name} 的元数据")
                continue
            sid = _parse_shortid_from_metadata(metadata)
            needs_reprocess_ids.add(sid)

            if cache_entry is None:
                count_c += 1
            else:
                count_b += 1

            preloaded_metadata[cache_key] = metadata

        if sid is None:
            logger.warning(f"数据同步-谱面处理：{chart_file_name} shortid 解析失败，跳过")
            continue

        pending_stat_cache[cache_key] = {"identity": file_identity, "shortid": sid}

        if sid not in id_to_paths:
            id_to_paths[sid] = []
        id_to_paths[sid].append(chart_path)

    logger.info(f"数据同步-谱面处理分类统计：A={count_a}, B={count_b}, C={count_c}")

    result: dict[int, MaiData] = {}
    parsed_success_cache_keys: set[str] = set()
    for sid in needs_reprocess_ids:
        paths = id_to_paths.get(sid, [])
        if not paths:
            continue

        sid_result: MaiData | None = None
        for chart_path in paths:
            chart_file_name = chart_path.stem
            cache_key = _cache_key_for_path(chart_path)
            raw_metadata = preloaded_metadata.get(cache_key)
            if raw_metadata is None:
                raw_metadata = await read_chart_raw_metadata(chart_path)
            if not raw_metadata:
                logger.warning(f"数据同步-谱面处理：未提取到 {chart_file_name} 的元数据")
                continue

            try:
                mai = await parse_maidata(raw_metadata, chart_path)
                sid_result = mai if sid_result is None else _merge_maidata_with_priority(sid_result, mai)
                parsed_success_cache_keys.add(cache_key)
                logger.success(f"数据同步-谱面处理成功：{chart_file_name}({mai.title})")
            except Exception as e:
                logger.warning(f"数据同步-谱面处理失败 {chart_file_name}: {e}")

        if sid_result is not None:
            result[sid] = sid_result

    # 仅在“文件成功参与解析”后提交重理组缓存；失败文件回退到旧缓存（若存在）。
    for cache_key, pending_entry in pending_stat_cache.items():
        sid_raw = pending_entry.get("shortid")
        sid = sid_raw if isinstance(sid_raw, int) else None
        if sid is None:
            continue

        if sid not in needs_reprocess_ids:
            next_stat_cache[cache_key] = pending_entry
            continue

        if cache_key in parsed_success_cache_keys:
            next_stat_cache[cache_key] = pending_entry
            continue

        old_entry = old_stat_cache.get(cache_key)
        if old_entry is not None:
            next_stat_cache[cache_key] = old_entry

    # 更新 stat 缓存
    _save_stat_cache(cache_path, next_stat_cache, stat_cache_meta)

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
        existing = models.MaiDataModel.mai_data(data)
        session.add(existing)
        existing.charts = existing.charts or []
        existing.aliases = existing.aliases or []

    # 处理谱面数据
    changed_tasks: list[tuple[int, int, SERVER_TAG]] = []
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
            new_chart = models.MaiDataModel.mai_chart(chart, data.shortid)
            existing.charts.append(new_chart)

    # 处理别名数据
    existing_alias_names = {a.alias for a in existing.aliases}
    for alias_obj in data.aliases:
        if alias_obj.alias not in existing_alias_names:
            new_alias = models.MaiDataModel.mai_alias(alias_obj)
            existing.aliases.append(new_alias)
            existing_alias_names.add(alias_obj.alias)

    for shortid, diff, server in changed_tasks:
        await services.refresh_dxrating_cache(shortid, diff, server)


async def process_upsert_all(session: AsyncSession, maidata_list: list[MaiData]):
    """
    全量内存比对处理：
    1. 一次性查出库中所有数据（含关联表）
    2. 在内存中完成 1804 条数据的 Diff
    3. 最后统一 commit
    """
    # --- 步骤 1: 预加载全量数据到内存 ---
    logger.info("正在预加载数据库全量数据以进行内存比对...")
    stmt = (
        select(models.MaiData)
        .options(
            selectinload(models.MaiData.charts),
            selectinload(models.MaiData.aliases)
        )
    )
    result = await session.execute(stmt)
    # 建立 shortid -> ORM 对象的映射
    db_cache: dict[int, models.MaiData] = {m.shortid: m for m in result.scalars().all()}
    
    changed_tasks: list[tuple[int, int, SERVER_TAG]] = []

    # --- 步骤 2: 内存比对循环 ---
    for data in maidata_list:
        existing = db_cache.get(data.shortid)
        
        if existing:
            # 更新基础信息 (已经在内存里的对象，修改属性会被 SQLAlchemy 追踪)
            for attr in ['title', 'bpm', 'artist', 'genre', 'cabinet', 'version', 
                         'version_cn', 'converter', 'is_utage', 'utage_tag', 'buddy']:
                setattr(existing, attr, getattr(data, attr))
            existing.zip_path = str(data.zip_path)
            
            # 处理谱面数据 (内存比对)
            existing_charts = {chart.difficulty: chart for chart in existing.charts}
            for chart in data.charts.values():
                if chart.difficulty in existing_charts:
                    ec = existing_charts[chart.difficulty]
                    # 记录需要刷新缓存的任务
                    if ec.lv != chart.lv: changed_tasks.append((data.shortid, chart.difficulty, "JP"))
                    if ec.lv_cn != chart.lv_cn: changed_tasks.append((data.shortid, chart.difficulty, "CN"))
                    
                    # 更新字段
                    ec.lv, ec.lv_cn, ec.lv_synh = chart.lv, chart.lv_cn, chart.lv_synh
                    ec.des, ec.inote = chart.des, chart.inote
                    (ec.note_count_tap, ec.note_count_hold, ec.note_count_slide, 
                     ec.note_count_touch, ec.note_count_break) = chart.notes
                else:
                    # 库里没有这个难度，新增
                    new_chart = models.MaiDataModel.mai_chart(chart, data.shortid)
                    existing.charts.append(new_chart)

            # 处理别名数据 (内存比)
            existing_alias_names = {a.alias for a in existing.aliases}
            for alias_obj in data.aliases:
                if alias_obj.alias not in existing_alias_names:
                    existing.aliases.append(models.MaiDataModel.mai_alias(alias_obj))
        
        else:
            # 库里完全没有这首歌，新增
            new_mai = models.MaiDataModel.mai_data(data)
            session.add(new_mai)

    return changed_tasks


@post_db_init
async def maintenance_task():
    """每日重启后自动运行的数据重整理"""
    logger.info("maib 数据同步中")
    
    try:
        # 1. 准备路径和配置
        logger.info(f"数据同步-步骤 1/5：获取谱面目录")
        data_dir = PluginRegistry.get_data_dir()
        if not data_dir:
            logger.error("数据同步失败：无法获取谱面目录")
            return
        chart_dirs = [data_dir / "charts", data_dir / "charts2"]
        charts_files = []
        for d in chart_dirs:
            if d.exists():
                charts_files.extend(d.glob("*.zip"))
        if not charts_files:
            logger.warning("数据同步结束：未找到任何谱面文件")
            return
        logger.success(f"数据同步-步骤 1/5：已找到 {len(charts_files)} 个谱面文件")

        if should_skip_fetch_by_stat(charts_files):
            logger.success("数据同步-提前结束：命中 stat + 24h 规则，本次 fetch 全流程跳过")
            return

        # 2. 处理本地 maidata 并存储到数据库
        logger.info(f"数据同步-步骤 2/5：开始处理本地谱面，共 {len(charts_files)} 个 zip 文件")
        maidata_list = await process_chart_files(charts_files)
        get_session = PluginRegistry.get_session
        async with get_session() as session:
            try:
                # 对于 SQLite，开启 WAL 模式提高并发稳定性
                if get_sql_name() == "sqlite":
                    await session.execute(text("PRAGMA journal_mode=WAL;"))
                
                # 执行全量内存比对
                changed_tasks = await process_upsert_all(session, maidata_list)
                
                # 一次性提交：此处才会产生真正的写入锁
                await session.commit()
                logger.success("本地谱面数据一次性原子提交成功")
                
                # 提交成功后再刷新 rating 缓存
                for shortid, diff, server in changed_tasks:
                    await services.refresh_dxrating_cache(shortid, diff, server)
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"数据同步-步骤 2/5：同步失败，已全量回滚: {e}")
            else:
                logger.success(f"数据同步-步骤 2/5：本地谱面同步完成，共写入 {len(maidata_list)} 条")

        # 4. 获取水鱼数据并逐条同步国服版本与定数
        logger.info("数据同步-步骤 3/5：开始同步水鱼国服版本与定数")
        if sy_music_data := await network.sy_music_data_from_file(PluginRegistry.get_cache_dir() / "sy_music_data"):
            total = len(sy_music_data)
            sync_data: list[tuple[int, int, list[float | int]]] = []
            for idx, sy_data in enumerate(sy_music_data):
                try:
                    shortid = int(sy_data.get("id", 0))
                    ds: list[float | int] = sy_data.get("ds", [])
                    ver = await parse_diving_fish_version(sy_data.get("basic_info", {}).get("from", ""))

                    sync_data.append((shortid, ver, ds))

                    if (idx + 1) % 200 == 0:
                        logger.info(f"水鱼数据解析进度: [{idx+1}/{total}]")
                except Exception as e:
                    logger.warning(f"水鱼数据同步失败 shortid={sy_data.get('id', 0)}: {e}")

            hit_song_count, changed_chart_count = await services.sync_cn_data_batch(sync_data, commit_every=200)
            logger.info(
                f"水鱼数据批量同步完成: 输入 {len(sync_data)} 条, 命中 {hit_song_count} 首, 更新谱面 {changed_chart_count} 条"
            )
            logger.success("数据同步-步骤 3/5：水鱼国服版本与定数同步完成")
        else:
            logger.warning("数据同步-水鱼数据：music_data 加载失败，无法同步国服版本号")

        # 4. 同步拟合难度
        logger.info("数据同步-步骤 4/5：开始同步拟合难度")
        sy_lvnh = []
        if sy_chart_stats := await network.sy_chart_stats():
            for shortid, sy_stats in sy_chart_stats.get("charts", {}).items():
                shortid = int(shortid)
                fit_diffs: list[float] = [s.get('fit_diff', 0) for s in sy_stats]
                for diff, fit_diff in enumerate(fit_diffs, start=2):
                    sy_lvnh.append((shortid, diff, fit_diff))
            if sy_lvnh:
                await services.set_lv_synh_batch(sy_lvnh)
            logger.success(f"数据同步-步骤 4/5：拟合难度同步完成，共 {len(sy_lvnh)} 条")
        else:
            logger.warning("数据同步-水鱼数据：chart_stats 加载失败，无法同步拟合难度")

        # 5. 独立获取别名数据
        logger.info("数据同步-步骤 5/5：开始同步别名数据")
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
            logger.success(f"数据同步-步骤 5/5：Yuzuchan 别名同步完成，共 {len(aliases_set)} 条")
        # 处理 LXNS 别名
        if lxns_data := await network.lx_alias_list():
            aliases_set: set[tuple[int, str]] = set()
            for entry in lxns_data.get("aliases", []):
                song_id = int(entry.get('song_id', 0))
                aliases: list[str] = entry.get('aliases', [])
                aliases_set.update((song_id, alias) for alias in aliases)
            # 存储别名数据
            await services.add_aliases(list(aliases_set), source_id=-102, add_time=now)
            logger.success(f"数据同步-步骤 5/5：LXNS 别名同步完成，共 {len(aliases_set)} 条")

        logger.success("maib 数据重整理完成！")
        update_last_fetch_timestamp()
        
    except Exception as e:
        logger.error(f"数据重整理失败: {e}")
