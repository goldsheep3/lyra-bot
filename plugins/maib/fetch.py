"""fetch.py 数据同步与谱面解析"""
import re
import time
import orjson
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeVar, overload, Literal, TypedDict, cast

from nonebot import logger
from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir
from nonebot_plugin_datastore.db import post_db_init
from sqlalchemy import select

from . import config, utils, services, network
from .utils.enums import Server, SLevelSource
from .utils.map import VersionID, Versions, Genres
from .utils.map.version import mapping_jp_to_cn


class ChartFileChangeBox(TypedDict):
    Cached: dict[str, str]
    Updated: dict[str, str]
    New: dict[str, str]

_T = TypeVar("_T")
_DefaultT = TypeVar("_DefaultT")



SUPPORTED_CHART_EXTS = {".zip", ".adx"}
STAT_CACHE_NAME = "chart_stat.json"


def get_file_stat_identity(file_path: Path) -> str:
    """获取文件的特征标识（修改时间 + 文件大小）"""
    stat = file_path.stat()
    return f"{stat.st_mtime}_{stat.st_size}"


def _load_chart_stat(stat_cache_file: Path) -> dict[str, str]:
    """加载谱面 stat 缓存"""
    if not stat_cache_file.exists():
        return dict()

    try:
        data = orjson.loads(stat_cache_file.read_bytes())
        if not data:
            return dict()
        elif "stats" in data and isinstance(data["stats"], dict):
            return cast(dict[str, str], data["stats"])
        else:
            return data
    except Exception:
        return dict()



def _save_chart_stat(stat_cache_file: Path, chart_stat: dict[str, str]) -> None:
    """保存谱面 stat 缓存"""
    stat_cache_file.parent.mkdir(parents=True, exist_ok=True)
    stat_cache_file.write_bytes(orjson.dumps(chart_stat))


def _iter_chart_files(data_dir: Path) -> list[Path]:
    """返回 data_dir 根层及 charts*/ 子目录下的谱面文件。"""
    candidates = list(data_dir.glob("*"))
    candidates.extend(data_dir.glob("charts*/*"))
    return sorted(
        p for p in candidates
        if p.is_file() and p.suffix.lower() in SUPPORTED_CHART_EXTS
    )



def _classify_chart_files(files: Sequence[Path], data_dir: Path, stats: dict[str, str]) -> ChartFileChangeBox:
    """依据相对目录文件列表进行缓存特征标识"""
    results = ChartFileChangeBox(Cached={}, Updated={}, New={})
    for file in files:
        file_key = str(file.relative_to(data_dir))
        identity = get_file_stat_identity(file)
        if file_key not in stats:
            results["New"][file_key] = identity
        elif stats[file_key] == identity:
            results["Cached"][file_key] = identity
        else:
            results["Updated"][file_key] = identity
    return results


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
    genre_id = Genres.find_id(genre_str, allow_fuzzy=True)
    if genre_id is None:
        logger.warning(f"[fetch 3/7] 无法解析流派名: {genre_str}")
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
        logger.warning(f"[fetch 3/7] 无法解析 shortid={short_id}, diff={chart_num} 的定数: {lv_str}")
        return None

    chart = utils.MaiChart(
        shortid=short_id,
        difficulty=chart_num,
        lv_jp=lv,
        des=str(raw_mdt.get(des_key, "")),
        inote=str(raw_mdt.get(inote_key, "")),
    )

    try:
        snc = utils.SimaiNoteCount(raw_mdt.get(inote_key, "")).process()
        chart.set_notes(*snc.to_tuple())
    except Exception as e:
        logger.warning(f"[fetch 3/7] shortid={short_id}, diff={chart_num} 的 Note 数解析失败: {e}")
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

    version: VersionID | Literal[-1] = Versions.find_id(_raw_get(raw_mdt, "version", default=""), default=-1)
    converter = _raw_get(raw_mdt, "ChartConvertTool", default="")

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


async def _apply_pending_id_mappings() -> bool:
    """[fetch 4/7] 应用待处理的 shortid 映射"""
    try:
        id_mappings = await services.get_pending_mappings()
    except Exception:
        logger.exception("[fetch 4/7] id_check 表异常")
        return False

    if not id_mappings:
        logger.info("[fetch 4/7] 无待处理的 shortid 映射")
        return False

    logger.info(f"[fetch 4/7] 处理 {len(id_mappings)} 条 shortid 映射规则")
    for original_id, mapped_id in id_mappings:
        try:
            await services.resolve_id_mapping(original_id, mapped_id)
            logger.info(f"[fetch 4/7] 应用映射 {original_id} -> {mapped_id}")
        except Exception:
            logger.exception(f"[fetch 4/7] 映射 {original_id}->{mapped_id} 失败")
    return True


async def _parse_changed_chart_files(
    data_dir: Path,
    change_files: dict[str, str],
) -> tuple[dict[int, utils.MaiData], list[dict[str, str]]]:
    """解析变更的谱面包，返回 shortid 映射的 MaiData 字典和解析统计"""
    
    maidata_dict: dict[int, utils.MaiData] = {}
    parsed_stats: list[dict[str, str]] = []

    for file_key, identity in change_files.items():
        chart_path = data_dir / file_key
        try:
            content = _read_maidata_text(chart_path)
            raw_mdt = _extract_metadata(content)
            if not raw_mdt:
                logger.warning(f"[fetch 3/7] {file_key} 未提取到 maidata 元数据")
                continue
            maidata = await parse_maidata(raw_mdt, file_key)
        except Exception as e:
            logger.error(f"[fetch 3/7] 无法解析 {file_key}，错误: {e}")
            continue

        maidata_dict[maidata.shortid] = maidata
        parsed_stats.append({"file_key": file_key, "identity": identity})

    return maidata_dict, parsed_stats


async def _sync_changed_charts(
    data_dir: Path,
    chart_stat: dict[str, str],
    change_files: dict[str, str],
) -> bool:
    """[fetch 3/7] 同步变更的谱面包"""
    logger.info(f"[fetch 3/7] 解析处理 ({len(change_files)} 个谱面包)")
    maidata_dict, parsed_stats = await _parse_changed_chart_files(data_dir, change_files)
    if not maidata_dict:
        logger.warning("[fetch 3/7] 解析异常，无有效谱面包")
        return False

    try:
        await services.sync_mdt_list([
            services.MaiData.from_utils(maidata)
            for maidata in maidata_dict.values()
        ])
    except Exception:
        logger.exception(f"[fetch 3/7] 数据库同步失败")
        return False

    for item in parsed_stats:
        chart_stat[item["file_key"]] = item["identity"]
    _save_chart_stat(get_plugin_cache_dir() / STAT_CACHE_NAME, chart_stat)
    logger.info(f"[fetch 3/7] 成功同步 {len(maidata_dict)} 个曲目")
    return True


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# TODO sy_data 采用带数据规范的 dict 以实现更精确的类型检查
async def _build_cn_update_lists(sy_data: Sequence[Any]) -> tuple[list[tuple[int, int]], list[dict[str, float]]]:
    """从水鱼数据中构建国服版本和定数更新列表"""
    version_update_list: list[tuple[int, int]] = []
    level_update_list: list[dict[str, float]] = []

    for sy_item in sy_data:
        if not isinstance(sy_item, Mapping):
            continue

        sid = _safe_int(sy_item.get("id"))
        if sid <= 0:
            continue

        basic_info = sy_item.get("basic_info", {})
        raw_version: str = basic_info.get("from", "") if isinstance(basic_info, Mapping) else ""
        version: VersionID | Literal[-1] = Versions.find_id(raw_version, default=-1)
        if version >= 0:
            cn_version = mapping_jp_to_cn(version)
            if cn_version is not None:
                version_update_list.append((sid, cn_version))
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
    """[fetch 5/7] 同步国服版本和定数数据"""
    music_data = await network.DivingFish.music_data(data_dir)
    if not music_data["data"]:
        logger.warning("[fetch 5/7] 从水鱼更新国服版本和定数数据失败，请检查服务状态")
        return

    if not (music_data["updated"] or force):
        logger.info("[fetch 5/7] 国服版本和定数数据无变化")
        return

    version_update_list, level_update_list = await _build_cn_update_lists(music_data["data"])
    if not version_update_list and not level_update_list:
        logger.warning("[fetch 5/7] 解析水鱼数据失败")
        return

    try:
        async with services.get_session() as session:
            if version_update_list:
                await services.set_mdt_version_batch(version_update_list, Server.CN, session=session)
            if level_update_list:
                await services.set_mct_level_batch(level_update_list, SLevelSource.CN, session=session)
                refresh_chart_keys = list(dict.fromkeys(
                    (int(item["shortid"]), int(item["difficulty"]))
                    for item in level_update_list
                ))
                await services.rfs_dxra_batch(refresh_chart_keys, Server.CN, session=session)
            await session.commit()
        logger.success(f"[fetch 5/7] 国服数据同步完成 (曲目:{len(version_update_list)}, 谱面:{len(level_update_list)})")
    except Exception:
        logger.exception(f"[fetch 5/7] 数据库同步失败")


async def _sync_synh_levels() -> None:
    """[fetch 6/7] 同步水鱼拟合定数"""

    chart_stats = await network.DivingFish.chart_stats()
    if not chart_stats:
        logger.info("[fetch 6/7] 未获取到水鱼拟合定数数据")
        return

    charts = chart_stats.get("charts", {}) if isinstance(chart_stats, Mapping) else {}
    if not isinstance(charts, Mapping):
        logger.info("[fetch 6/7] 水鱼拟合定数数据格式异常")
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
        logger.info("[fetch 6/7] 未解析到可同步的拟合定数")
        return

    try:
        await services.set_mct_level_batch(synh_list, source=SLevelSource.FIT)
        logger.info(f"[fetch 6/7] 已同步 {len(synh_list)} 条水鱼拟合定数")
    except Exception:
        logger.exception(f"[fetch 6/7] 更新水鱼拟合定数数据失败")


def _iter_alias_names(value: Any) -> Iterable[str]:
    """迭代别名名称兼容"""
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        values = value
    else:
        return []

    return (alias for raw in values if (alias := str(raw).strip()))


def _collect_yuzuchan_aliases(data: Mapping[str, Any] | None) -> list[tuple[int, str]]:
    """从 yuzuchan 别名数据中提取 (song_id, alias) 列表"""
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


def _collect_lxns_aliases(data: Mapping[str, Any] | None) -> list[tuple[int, str]]:
    """从 lxns 别名数据中提取 (song_id, alias) 列表"""
    if not data:
        return []
    
    def _map_lxns_shortid(shortid: int) -> int:
        """LXNS song_id 与本地 SD/DX shortid 互为 10000 偏移。"""
        return shortid % 10000 if shortid > 10000 else shortid + 10000

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
    """[fetch 7/7] 同步别名库数据"""
    yuzuchan_aliases = _collect_yuzuchan_aliases(await network.YuzuChaN.yuzuchan_alias_list())
    await services.add_ma_batch(yuzuchan_aliases, -101)
    logger.info(f"[fetch 7/7] 同步 yuzuchan 别名数据完成 ({len(yuzuchan_aliases)} 条)")

    lxns_aliases = _collect_lxns_aliases(await network.Lxns.lx_alias_list())
    await services.add_ma_batch(lxns_aliases, -102)
    logger.info(f"[fetch 7/7] 同步 lxns 别名数据完成 ({len(lxns_aliases)} 条)")


@post_db_init
async def maintenance_task():
    """数据重整主流程"""
    now_time = time.time()

    # [fetch 1/7] 获取谱面包列表
    logger.info("[fetch 1/7] 尝试获取谱面包")
    if config.CHART_DATA_DIR:
        data_dir = Path(config.CHART_DATA_DIR)
        if not data_dir.exists() or not data_dir.is_dir():
            logger.error(f"[fetch 1/7] 配置的谱面数据目录({data_dir})不存在或不是目录，请检查配置")
            return
    else:
        data_dir = get_plugin_data_dir()

    files = _iter_chart_files(data_dir)
    if not files:
        logger.error(f"[fetch 1/7] 谱面数据目录为空，请检查数据目录({data_dir})")
        return
    logger.info(f"[fetch 1/7] 成功在谱面数据目录 {data_dir} 获取到 {len(files)} 个谱面包")

    # [fetch 2/7] 解析 stat 缓存并分类文件
    _skip_db_exec: bool = False
    chart_stat_path = get_plugin_cache_dir() / STAT_CACHE_NAME
    chart_stat = _load_chart_stat(chart_stat_path)
    results = _classify_chart_files(files, data_dir, chart_stat)
    change_files = results["Updated"].copy()
    change_files.update(results["New"])
    if not change_files:
        # ------ refactoring ------        
        # 数据库被清空或首次迁移后，不能把旧 stat 缓存误当成曲库已入库。
        async with services.get_session() as session:
            has_maidata = (await session.execute(select(services.MaiData.shortid).limit(1))).scalar_one_or_none() is not None
        is_empty_library = not has_maidata
        # -------------------------
        if is_empty_library:
            logger.warning("[fetch 2/7] 谱面库为空，强制重建谱面库")
            change_files = {str(path.relative_to(data_dir)): get_file_stat_identity(path) for path in files}
            logger.info(f"[fetch 2/7] New={len(change_files)}")
        else:
            _skip_db_exec = True
            logger.info(f"[fetch 2/7] 谱面包 {len(results['Cached'])} 均已缓存，数据库无需更新")
    else:
        logger.info(f"[fetch 2/7] Cached={len(results['Cached'])}, Updated={len(results['Updated'])}, New={len(results['New'])}")

    # [fetch 3/7] 谱面包拆包解析和数据库同步
    if not _skip_db_exec:
        chart_synced = await _sync_changed_charts(data_dir, chart_stat, change_files)
    else:
        chart_synced = False
        logger.info("[fetch 3/7] 数据库无需更新，跳过谱面包拆包同步")

    # [fetch 4/7] 应用待处理的 shortid 映射
    if (await _apply_pending_id_mappings()) or chart_synced:
        logger.info("[fetch 4/7] 尝试回填成绩记录并刷新缓存")
        try:
            # ------ refactoring ------   
            affected_by_user = await services.backfill_record_shortids()
            for user_id, record_keys in affected_by_user.items():
                ach_list = await services.get_record_achs(user_id, list(record_keys))
                if ach_list:
                    await services.upd_ach_batch(user_id, ach_list)
            # -------------------------
        except Exception:
            logger.exception("[fetch 4/7] 回填成绩记录失败")

    # [fetch 5/7] 同步水鱼拟合定数
    await _sync_cn_metadata(get_plugin_cache_dir(), force=chart_synced)
    # [fetch 6/7] 同步水鱼拟合定数
    await _sync_synh_levels()
    # [fetch 7/7] 同步别名库数据
    await _sync_aliases()

    logger.info(f"[fetch 7/7] 流程结束，耗时:{(time.time() - now_time):.2f} 秒")
