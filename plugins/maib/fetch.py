"""fetch.py 数据同步与谱面解析"""
import re
import time
import orjson
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar, overload

from nonebot import logger
from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir
from nonebot_plugin_datastore.db import post_db_init

from . import config, utils, services, network
from .constants import GENRE_MAP, VERSION_MAP


ChartFileChange = tuple[str, str]
ChartStat = dict[str, Any]
_T = TypeVar("_T")
_DefaultT = TypeVar("_DefaultT")

SUPPORTED_CHART_EXTS = {".zip", ".adx"}
STAT_CACHE_NAME = "chart_stat.json"


def get_file_stat_identity(file_path: Path) -> str:
    """获取文件的特征标识（修改时间 + 文件大小）"""
    stat = file_path.stat()
    return f"{stat.st_mtime}_{stat.st_size}"


def _new_chart_stat() -> ChartStat:
    return {"timestamp": -1, "stats": {}}


def _load_chart_stat(stat_cache_file: Path) -> ChartStat:
    if not stat_cache_file.exists():
        return _new_chart_stat()

    try:
        data = orjson.loads(stat_cache_file.read_bytes())
        stats = data.get("stats", {})
        if not isinstance(stats, dict):
            raise ValueError("chart_stat.stats is not a dict")
        return {
            "timestamp": float(data.get("timestamp", -1)),
            "stats": {str(k): str(v) for k, v in stats.items()},
        }
    except Exception as e:
        logger.warning(f"maib-fetch Step 1/6: stat 缓存读取失败，将重新生成: {e}")
        return _new_chart_stat()


def _save_chart_stat(stat_cache_file: Path, chart_stat: ChartStat) -> None:
    stat_cache_file.parent.mkdir(parents=True, exist_ok=True)
    stat_cache_file.write_bytes(orjson.dumps(chart_stat))


def _iter_chart_files(data_dir: Path) -> list[Path]:
    return sorted(
        p for p in data_dir.glob("charts*/*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_CHART_EXTS
    )


def _classify_chart_files(files: Sequence[Path], data_dir: Path, chart_stat: ChartStat) -> dict[str, list[ChartFileChange]]:
    stats = chart_stat.setdefault("stats", {})
    if not isinstance(stats, dict):
        stats = {}
        chart_stat["stats"] = stats

    results: dict[str, list[ChartFileChange]] = {"Cached": [], "Updated": [], "New": []}
    for file in files:
        file_key = str(file.relative_to(data_dir))
        identity = get_file_stat_identity(file)
        if file_key not in stats:
            results["New"].append((file_key, identity))
        elif stats[file_key] == identity:
            results["Cached"].append((file_key, identity))
        else:
            results["Updated"].append((file_key, identity))
    return results


def _has_fresh_stat_cache(chart_stat: ChartStat, now_time: float) -> bool:
    try:
        timestamp = float(chart_stat.get("timestamp", -1))
    except (TypeError, ValueError):
        return False
    return now_time - timestamp < (config.CACHE_EXPIRATION * 3600)


def _extract_metadata(content: str) -> dict[str, str]:
    """从 maidata.txt 内容提取键值元数据。"""
    metadata: dict[str, str] = {}
    for part in content.replace("\r\n", "\n").split("&"):
        key, sep, value = part.partition("=")
        if sep:
            metadata[key.strip()] = value.strip()
    return metadata


@overload
def _raw_get(raw_mdt: Mapping[str, str], key_list: str | Sequence[str]) -> str | None: ...


@overload
def _raw_get(raw_mdt: Mapping[str, str], key_list: str | Sequence[str], *, default: _DefaultT) -> str | _DefaultT: ...


@overload
def _raw_get(
    raw_mdt: Mapping[str, str],
    key_list: str | Sequence[str],
    return_type: None,
    default: _DefaultT,
) -> str | _DefaultT: ...


@overload
def _raw_get(
    raw_mdt: Mapping[str, str],
    key_list: str | Sequence[str],
    return_type: Callable[[str], _T],
    default: _DefaultT,
) -> _T | _DefaultT: ...


def _raw_get(
    raw_mdt: Mapping[str, str],
    key_list: str | Sequence[str],
    return_type: Callable[[str], Any] | None = str,
    default: Any = None,
) -> Any:
    """从 raw_metadata 中获取数据，支持多个候选 key 和类型转换。"""
    keys: tuple[str, ...] = (key_list,) if isinstance(key_list, str) else tuple(key_list)
    for key in keys:
        if key not in raw_mdt:
            continue
        value = raw_mdt[key]
        if return_type is None:
            return value
        try:
            return return_type(value)
        except (ValueError, TypeError):
            continue
    return default


def _parse_genre(genre_str: str) -> int:
    genre_id = GENRE_MAP.get_id_by_name(genre_str, fuzzy=True, threshold=80)
    if genre_id is None:
        logger.warning(f"maib-fetch: 无法解析流派名: {genre_str}")
        return -1
    return genre_id


async def get_chart(raw_mdt: Mapping[str, str], short_id: int, chart_num: int) -> utils.MaiChart | None:
    """获取谱面信息"""
    lv_key = f"lv_{chart_num}"
    des_key = f"des_{chart_num}"
    inote_key = f"inote_{chart_num}"
    if lv_key not in raw_mdt:
        return None

    lv_str = raw_mdt.get(lv_key, "0").rstrip("?")
    if not lv_str:
        return None

    try:
        lv = float(lv_str)
    except ValueError:
        logger.warning(f"maib-fetch: 无法解析 shortid={short_id}, diff={chart_num} 的定数: {lv_str}")
        return None

    chart = utils.MaiChart(
        shortid=short_id,
        difficulty=chart_num,
        lv=lv,
        des=str(raw_mdt.get(des_key, "")),
        inote=str(raw_mdt.get(inote_key, "")),
    )

    try:
        snc = utils.SimaiNoteCount(raw_mdt.get(inote_key, "")).process()
        chart.set_notes(*snc.to_tuple())
    except Exception as e:
        logger.warning(f"maib-fetch: shortid={short_id}, diff={chart_num} 的 Note 数解析失败: {e}")
    return chart


async def parse_maidata(raw_mdt: Mapping[str, str], zip_path: Path | str) -> utils.MaiData:
    """通过 maidata.txt 元数据解析 MaiData"""
    shortid = _raw_get(raw_mdt, ["shortid", "id"], int, 0)
    if shortid <= 0:
        raise ValueError("maidata.txt 缺少有效 shortid")

    title = _raw_get(raw_mdt, "title", default="")
    clean_title = re.sub(r"\[(宴|DX|SD)]$", "", title).strip()
    bpm = _raw_get(raw_mdt, ["wholebpm", "bpm"], int, 0)
    artist = _raw_get(raw_mdt, "artist", default="")
    genre = _parse_genre(_raw_get(raw_mdt, "genre", default=""))

    cabinet_raw = _raw_get(raw_mdt, "cabinet", default=None)
    if cabinet_raw is None:
        cabinet = "SD" if shortid < 10000 else "DX"
    else:
        cabinet = "DX" if any(k in cabinet_raw.lower() for k in ["dx", "でらっくす", "deluxe"]) else "SD"

    version = VERSION_MAP.get_id_by_text(_raw_get(raw_mdt, "version", default=""))
    version = version if version is not None else -1
    converter = _raw_get(raw_mdt, "ChartConverter", default="")

    is_utage = shortid > 100000
    has_utage_chart = bool(raw_mdt.get("lv_7", "").strip())
    matched = re.match(r"\[(.)]", title)
    utage_tag = matched.group(1) if matched else "宴"

    zip_path = Path(zip_path)
    mai = utils.MaiData(
        shortid=shortid,
        title=clean_title,
        bpm=bpm,
        artist=artist,
        genre=genre,
        cabinet=cabinet,
        version=version,
        version_cn=None,
        converter=converter,
        zip_path=zip_path,
        img_path=zip_path / "bg.png",
        is_utage=is_utage,
        utage_tag=utage_tag if is_utage else "",
        buddy=is_utage and not has_utage_chart,
    )

    for chart_num in range(2, 8):
        if chart := await get_chart(raw_mdt, shortid, chart_num):
            mai.set_chart(chart)

    if is_utage:
        mai.is_utage = True
        mai.utage_tag = utage_tag
        mai.buddy = not has_utage_chart

    return mai


def _read_maidata_text(chart_path: Path) -> str:
    with zipfile.ZipFile(chart_path, "r") as zip_ref:
        with zip_ref.open("maidata.txt") as f:
            return f.read().decode("utf-8-sig")


async def _apply_pending_id_mappings() -> None:
    try:
        id_mappings = await services.get_pending_mappings()
    except Exception as e:
        logger.error(f"maib-fetch Step 2/6: 读取 id_check 失败: {e}")
        return

    if not id_mappings:
        logger.debug("maib-fetch Step 2/6: 无待处理 shortid 映射")
        return

    logger.info(f"maib-fetch Step 2/6: 处理 {len(id_mappings)} 条 shortid 映射规则")
    for original_id, mapped_id in id_mappings:
        try:
            await services.resolve_id_mapping(original_id, mapped_id)
            logger.info(f"maib-fetch Step 2/6: 应用映射 {original_id} -> {mapped_id}")
        except Exception as e:
            logger.error(f"maib-fetch Step 2/6: 映射 {original_id}->{mapped_id} 失败: {e}")


async def _parse_changed_chart_files(
    data_dir: Path,
    change_files: Sequence[ChartFileChange],
) -> tuple[dict[int, utils.MaiData], list[ChartFileChange]]:
    maidata_dict: dict[int, utils.MaiData] = {}
    parsed_stats: list[ChartFileChange] = []

    for file_key, identity in change_files:
        chart_path = data_dir / file_key
        try:
            content = _read_maidata_text(chart_path)
            raw_mdt = _extract_metadata(content)
            if not raw_mdt:
                logger.warning(f"maib-fetch Step 3/6: {file_key} 未提取到 maidata 元数据")
                continue
            maidata = await parse_maidata(raw_mdt, file_key)
        except Exception as e:
            logger.error(f"maib-fetch Step 3/6: 无法解析 {file_key}，错误: {e}")
            continue

        maidata_dict[maidata.shortid] = maidata
        parsed_stats.append((file_key, identity))

    return maidata_dict, parsed_stats


async def _sync_changed_charts(
    data_dir: Path,
    chart_stat: ChartStat,
    change_files: Sequence[ChartFileChange],
) -> bool:
    if not change_files:
        logger.info("maib-fetch Step 3/6: 无需拆包解析")
        return False

    logger.info(f"maib-fetch Step 3/6: 拆包解析和数据库处理 ({len(change_files)} 个文件)")
    maidata_dict, parsed_stats = await _parse_changed_chart_files(data_dir, change_files)
    if not maidata_dict:
        logger.warning("maib-fetch Step 3/6: 未成功解析任何曲目，跳过数据库同步")
        return False

    try:
        await services.sync_mdt_list([
            services.MaiData.from_utils(maidata)
            for maidata in maidata_dict.values()
        ])
    except Exception as e:
        logger.error(f"maib-fetch Step 3/6: 数据库同步失败，原因: {e}")
        return False

    stats = chart_stat.setdefault("stats", {})
    for file_key, identity in parsed_stats:
        stats[file_key] = identity

    logger.info(f"maib-fetch Step 3/6: 成功同步 {len(maidata_dict)} 个曲目")
    return True


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _build_cn_update_lists(sy_data: Sequence[Any]) -> tuple[list[tuple[int, int]], list[dict[str, float]]]:
    version_update_list: list[tuple[int, int]] = []
    level_update_list: list[dict[str, float]] = []

    for sy_item in sy_data:
        if not isinstance(sy_item, Mapping):
            continue

        sid = _safe_int(sy_item.get("id"))
        if sid <= 0:
            continue

        basic_info = sy_item.get("basic_info", {})
        raw_version = basic_info.get("from", "") if isinstance(basic_info, Mapping) else ""
        version = VERSION_MAP.get_id_by_text(str(raw_version), cn=True)
        version = version if version is not None else -1
        if version >= 0:
            version_update_list.append((sid, version))

        ds_list = sy_item.get("ds", [])
        if not isinstance(ds_list, Iterable) or isinstance(ds_list, (str, bytes)):
            continue
        for diff, level in enumerate(ds_list, start=2):
            try:
                level_update_list.append({
                    "shortid": sid,
                    "difficulty": diff,
                    "level": float(level),
                })
            except (TypeError, ValueError):
                continue

    return version_update_list, level_update_list


async def _sync_cn_metadata(data_dir: Path, *, force: bool) -> None:
    music_data = await network.DivingFish.music_data(data_dir)
    if not music_data.data:
        logger.warning("maib-fetch Step 4/6: 无法获取水鱼数据，跳过国服版本和定数更新")
        return

    if not (music_data.updated or force):
        logger.info("maib-fetch Step 4/6: 水鱼数据未更新，无需同步调整")
        return

    logger.info("maib-fetch Step 4/6: 准备更新国服版本和定数")
    version_update_list, level_update_list = await _build_cn_update_lists(music_data.data)
    if not version_update_list and not level_update_list:
        logger.info("maib-fetch Step 4/6: 未解析到可同步的国服版本或定数")
        return

    try:
        async with services.get_session() as session:
            if version_update_list:
                await services.set_mdt_version_batch(version_update_list, "CN", session=session)
            if level_update_list:
                await services.set_mct_level_batch(level_update_list, "CN", session=session)
                refresh_chart_keys = list(dict.fromkeys(
                    (int(item["shortid"]), int(item["difficulty"]))
                    for item in level_update_list
                ))
                await services.rfs_dxra_batch(refresh_chart_keys, "CN", session=session)
            await session.commit()
        logger.success(f"maib-fetch Step 4/6: 同步完成 (曲目:{len(version_update_list)}, 谱面:{len(level_update_list)})")
    except Exception as e:
        logger.error(f"maib-fetch Step 4/6: 数据库同步失败: {e}")


async def _sync_synh_levels() -> None:
    chart_stats = await network.DivingFish.chart_stats()
    if not chart_stats:
        logger.info("maib-fetch Step 5/6: 未获取到水鱼拟合定数数据")
        return

    charts = chart_stats.get("charts", {}) if isinstance(chart_stats, Mapping) else {}
    if not isinstance(charts, Mapping):
        logger.info("maib-fetch Step 5/6: 水鱼拟合定数数据格式异常")
        return

    synh_list: list[dict[str, float]] = []
    for shortid, sy_stats in charts.items():
        sid = _safe_int(shortid)
        if sid <= 0 or not isinstance(sy_stats, Iterable) or isinstance(sy_stats, (str, bytes)):
            continue
        for diff, stat in enumerate(sy_stats, start=2):
            if not isinstance(stat, Mapping):
                continue
            try:
                synh_list.append({
                    "shortid": sid,
                    "difficulty": diff,
                    "level": float(stat.get("fit_diff", 0)),
                })
            except (TypeError, ValueError):
                continue

    if not synh_list:
        logger.info("maib-fetch Step 5/6: 未解析到可同步的拟合定数")
        return

    try:
        await services.set_mct_level_batch(synh_list, server="synh")
        logger.info(f"maib-fetch Step 5/6: 已同步 {len(synh_list)} 条水鱼拟合定数")
    except Exception as e:
        logger.error(f"maib-fetch Step 5/6: 更新水鱼拟合定数数据失败，原因: {e}")


def _iter_alias_names(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        values = value
    else:
        return []

    return (alias for raw in values if (alias := str(raw).strip()))


def _collect_yuzuchan_aliases(data: Mapping[str, Any] | None) -> list[tuple[int, str]]:
    if not data:
        return []

    aliases_set: set[tuple[int, str]] = set()
    for entry in data.get("content", []):
        if not isinstance(entry, Mapping):
            continue
        song_id = _safe_int(entry.get("SongID"))
        if song_id <= 0:
            continue
        aliases_set.update((song_id, alias) for alias in _iter_alias_names(entry.get("Alias", [])))
    return sorted(aliases_set)


def _map_lxns_shortid(shortid: int) -> int:
    """LXNS song_id 与本地 SD/DX shortid 互为 10000 偏移。"""
    return shortid % 10000 if shortid > 10000 else shortid + 10000


def _collect_lxns_aliases(data: Mapping[str, Any] | None) -> list[tuple[int, str]]:
    if not data:
        return []

    aliases_set: set[tuple[int, str]] = set()
    for entry in data.get("aliases", []):
        if not isinstance(entry, Mapping):
            continue
        song_id = _safe_int(entry.get("song_id"))
        if song_id <= 0:
            continue
        for alias in _iter_alias_names(entry.get("aliases", [])):
            aliases_set.add((song_id, alias))
            aliases_set.add((_map_lxns_shortid(song_id), alias))
    return sorted(aliases_set)


async def _sync_aliases() -> None:
    logger.info("maib-fetch Step 6/6: 同步别名库数据")

    yuzuchan_aliases = _collect_yuzuchan_aliases(await network.YuzuChaN.yuzuchan_alias_list())
    await services.add_ma_batch(yuzuchan_aliases, -101)
    logger.info(f"maib-fetch Step 6/6: 同步 yuzuchan 别名数据完成 ({len(yuzuchan_aliases)} 条)")

    lxns_aliases = _collect_lxns_aliases(await network.Lxns.lx_alias_list())
    await services.add_ma_batch(lxns_aliases, -102)
    logger.info(f"maib-fetch Step 6/6: 同步 lxns 别名数据完成 ({len(lxns_aliases)} 条)")


@post_db_init
async def maintenance_task():
    """数据重整主流程"""
    now_time = time.time()

    logger.info("maib-fetch Step 1/6: 获取谱面文件列表并进行 stat 判定")
    data_dir = get_plugin_data_dir()
    if not data_dir:
        logger.error("maib-fetch Step 1/6: 无法获取谱面目录")
        return

    files = _iter_chart_files(data_dir)
    if not files:
        logger.warning("maib-fetch Step 1/6: 未找到任何谱面文件")
        return

    stat_cache_file = get_plugin_cache_dir() / STAT_CACHE_NAME
    chart_stat = _load_chart_stat(stat_cache_file)
    results = _classify_chart_files(files, data_dir, chart_stat)
    change_files = results["Updated"] + results["New"]

    logger.debug(f"maib-fetch Step 1/6: 找到 {len(files)} 个谱面文件")
    logger.info(
        "maib-fetch Step 1/6: "
        f"{len(results['Cached'])} 个文件未变更，"
        f"{len(results['Updated'])} 个文件已更新，"
        f"{len(results['New'])} 个文件为新增"
    )

    await _apply_pending_id_mappings()

    if not change_files and _has_fresh_stat_cache(chart_stat, now_time):
        logger.info("maib-fetch Step 1/6: stat 数据较新，且无更新或新增文件，结束 fetch 流程")
        return

    chart_synced = await _sync_changed_charts(data_dir, chart_stat, change_files)
    chart_stat["timestamp"] = time.time()
    _save_chart_stat(stat_cache_file, chart_stat)
    logger.info("maib-fetch Step 3/6: stat 缓存已更新")

    await _sync_cn_metadata(data_dir, force=chart_synced)
    await _sync_synh_levels()
    await _sync_aliases()

    logger.info(f"maib-fetch 同步完成，耗时: {(time.time() - now_time):.2f} 秒")
