import re
import time
import orjson
import zipfile
from pathlib import Path

from nonebot import logger, require
require("nonebot_plugin_datastore")
from nonebot_plugin_datastore.db import post_db_init

from . import utils, models, services, network
from .bot_registry import PluginRegistry
from .constants import GENRES_DATA


# Cache Time
CACHE_EXPIRATION_SECONDS = 3600 * 72  # 72小时


def _initialize_genres_data_rev():
    """初始化 `GENRES_DATA` 的反向映射，支持多语言模糊匹配"""
    genres_config_rev = {}
    for k, v in GENRES_DATA.items():
        if isinstance(v, dict):
            for lang in ['jp', 'intl', 'cn']:
                if lang_val := v.get(lang):
                    clean_key = lang_val.lower().replace('\n', '').strip()
                    genres_config_rev[clean_key] = k
    return genres_config_rev

_GENRES_DATA_REV = _initialize_genres_data_rev()


def _extract_metadata(content: str) -> dict[str, str]:
    """从 maidata.txt 内容提取键值元数据。"""
    metadata = {}
    # 预处理换行
    cleaned_content = content.replace('\r\n', '\n')
    for part in cleaned_content.split('&'):
        key, sep, value = part.partition('=')
        if sep:  # 只有存在 '=' 时才处理
            metadata[key.strip()] = value.strip()
    return metadata


async def get_chart(raw_mdt: dict, short_id: int, chart_num: int) -> utils.MaiChart | None:
    """获取谱面信息"""

    lv_key = f'lv_{chart_num}'
    des_key = f'des_{chart_num}'
    inote_key = f'inote_{chart_num}'
    if lv_key in raw_mdt:
        lv_str = raw_mdt.get(lv_key, '0').rstrip('?')
        if not lv_str:
            return None  # lv 为空，视为无该难度谱面
        chart = utils.MaiChart(
            shortid=short_id,
            difficulty=chart_num,
            lv=float(lv_str),
            des=str(raw_mdt.get(des_key, '')),
            inote=str(raw_mdt.get(inote_key, '')),
        )
        snc = await utils.SimaiNoteCount(raw_mdt.get(inote_key, '')).process()
        chart.set_notes_with_tuple(snc.to_tuple())
        return chart
    return None


async def parse_maidata(raw_mdt: dict[str, str], zip_path: Path | str) -> utils.MaiData:
    """通过 maidata.txt 元数据解析 MaiData"""
    global _GENRES_DATA_REV

    def raw_get(key_list, return_type: type = str, default = None):
        """从 raw_metadata 中获取数据的工具函数，支持多个候选 key 和类型转换"""
        if isinstance(key_list, str):
            key_list = [key_list]
        for key in key_list:
            if key in raw_mdt:
                if return_type:
                    try:
                        return return_type(raw_mdt[key])
                    except (ValueError, TypeError):
                        continue
        return default

    shortid = raw_get(['shortid', 'id'], int, 0)
    title = raw_get(['title'], default="")
    clean_title = re.sub(r'\[(宴|DX|SD)]$', '', title)  # title 处理：去掉`[XXXX]`
    bpm = raw_get(['wholebpm', 'bpm'], int, 0)
    artist = raw_get(['artist'], default="")
    genre = await utils.parse_genre(raw_get(['genre'], default=""), _GENRES_DATA_REV)
    _cabinet = raw_get(['cabinet'], default=None)
    if _cabinet is None:
        cabinet = "SD" if shortid < 10000 else "DX"
    else:
        cabinet = "DX" if any(k in _cabinet.lower() for k in ["dx", "でらっくす", "deluxe"]) else "SD"
    version_str = raw_get(['version'], default="")
    version = await utils.parse_version(version_str)
    converter = raw_get(['ChartConverter'], default="")

    # Utage Tag
    is_utage = shortid > 100000
    matched = re.match(r'\[(.)]', title)  # 取`[X]......`的`X`宴会场标签
    utage_tag = matched.group(1) if matched else "宴"

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
        zip_path=Path(zip_path),
        img_path=Path(zip_path) / 'bg.png',
        # utage 相关字段
        is_utage=is_utage,
        utage_tag=utage_tag if is_utage else '',
        buddy=not bool(raw_mdt.get('lv_7', '').strip()),
    )

    # 设置 2~7 的谱面数据
    for chart_num in range(2, 8):
        if chart := await get_chart(raw_mdt, shortid, chart_num):
            mai.set_chart(chart)

    return mai



@post_db_init
async def maintenance_task():
    """数据重整主流程"""
    now_time = time.time()


    # --- 1. 文件包的获取与 stat 判定 ---
    logger.info("maib-fetch Step 1/5: 获取谱面文件列表并进行 stat 判定")
    data_dir = PluginRegistry.get_data_dir()
    if not data_dir:
        logger.error("maib-fetch Step 1/5: 无法获取谱面目录")
        return
    files = [p for p in data_dir.glob("charts*/*") if p.suffix.lower() in {'.zip', '.adx'}]
    if not files:
        logger.warning("maib-fetch Step 1/5: 未找到任何谱面文件")
        return
    logger.debug(f"maib-fetch Step 1/5: 找到 {len(files)} 个谱面文件")
    # stat
    stat_cache_file = PluginRegistry.get_cache_dir() / "chart_stat.json"
    chart_stat = orjson.loads(stat_cache_file.read_bytes()) if stat_cache_file.exists() else {"timestamp": -1, "stats": {}}
    """
    # chart_stat.json 结构示例
    {
        timestamp: -1,
        stats: {
            "file_path": "stat_value",
             ...
        }
    }
    """
    results = {"Cached": [], "Updated": [], "New": []}
    for file in files:
        file_key = str(file.relative_to(data_dir))
        identity = utils.get_file_stat_identity(file)
        if file_key in chart_stat.get("stats", {}):
            if chart_stat["stats"][file_key] == identity:
                results["Cached"].append((file_key, identity))
            else:
                results["Updated"].append((file_key, identity))
        else:
            results["New"].append((file_key, identity))
    logger.info(f"maib-fetch Step 1/5: {len(results['Cached'])} 个文件未变更，{len(results['Updated'])} 个文件已更新，{len(results['New'])} 个文件为新增")
    if not results["Updated"] and not results["New"]:
        # 检查 stat timestamp
        if now_time - chart_stat.get("timestamp", -1) < CACHE_EXPIRATION_SECONDS:
            logger.info("maib-fetch Step 1/5: stat 数据较新，且无更新或新增文件，结束 fetch 流程")
            return
    change_files: list[tuple[str, str]] = results["Updated"] + results["New"]
    del results  # 简化列表结构


    # --- 2. 进行文件解析并更新数据库 ---
    if change_files:
        logger.info("maib-fetch Step 2/5: 拆包解析和数据库处理")
        maidata_dict: dict[int, utils.MaiData] = {}
        for file_key, identity in change_files:
            chart_path = data_dir / file_key  # 根据插件数据存储位置和 file_key 还原为绝对路径
            # 拆包！
            try:
                with zipfile.ZipFile(chart_path, 'r') as zip_ref:
                    with zip_ref.open("maidata.txt") as f:
                        content = f.read().decode('utf-8')
            except Exception as e:
                logger.error(f"maib-fetch Step 2/5: 无法解析 {file_key}，错误: {e}")
                continue
            raw_mdt = _extract_metadata(content)
            maidata = await parse_maidata(raw_mdt, file_key)
            maidata_dict[maidata.shortid] = maidata
            chart_stat["stats"][file_key] = identity  # 更新 stat_cache 信息

        if maidata_dict:
            try:
                await services.sync_mdt_list([models.MaiDataModel.mdt(maidata)
                                              for maidata in maidata_dict.values()])
                logger.info(f"maib-fetch Step 2/5: 成功同步 {len(maidata_dict)} 个曲目")
            except Exception as e:
                logger.error(f"maib-fetch Step 2/5: 数据库同步失败，原因：{e}")

    else:
        logger.info("maib-fetch Step 2/5: 无需拆包解析")

    # 更新 chart_stat
    chart_stat["timestamp"] = time.time()
    stat_cache_file.write_bytes(orjson.dumps(chart_stat))
    logger.info("maib-fetch Step 2/5: stat 缓存已更新")
    
    
    # --- 3. 获取水鱼版本数据，同步国服的版本信息和定数信息 ---
    sy_data, is_new = await network.sy_music_data_from_file(data_dir)
    if (is_new or change_files) and sy_data:
        # 如果拆过包，就强制刷新一下数据
        logger.info("maib-fetch Step 3/5: 准备更新国服版本和定数")
        
        version_update_list: list[tuple[int, int]] = []
        level_update_list: list[dict] = []

        # 1. 解析数据并构造批量列表
        for sy_item in sy_data:
            try:
                sid = int(sy_item.get("id", 0))
                # 转换版本号
                raw_ver = sy_item.get("basic_info", {}).get("from", "")
                ver_int = await utils.parse_diving_fish_version(raw_ver)
                version_update_list.append((sid, ver_int))

                # 转换定数列表 (ds)
                ds_list: list[float] = sy_item.get("ds", [])
                for diff, level in enumerate(ds_list, start=2):
                    level_update_list.append({
                        "shortid": sid, 
                        "difficulty": diff, 
                        "level": level
                    })
            except (ValueError, TypeError, KeyError) as e:
                continue # 容错处理
        
        if version_update_list or level_update_list:
            try:
                async with PluginRegistry.get_session() as session:
                    # 批量更新曲目版本
                    if version_update_list:
                        await services.set_mdt_version_batch(version_update_list, 'CN', session=session)
                    
                    # 批量更新谱面定数
                    if level_update_list:
                        await services.set_mct_level_batch(level_update_list, 'CN', session=session)
                    
                    await session.commit()
                    logger.success(f"maib-fetch Step 3/5: 同步完成 (曲目:{len(version_update_list)}, 谱面:{len(level_update_list)})")
            except Exception as e:
                logger.error(f"maib-fetch Step 3/5: 数据库同步失败: {e}")
        
    elif not sy_data:
        logger.warning("maib-fetch Step 3/5: 无法获取水鱼数据，跳过国服版本和定数更新")
    else:
        logger.info("maib-fetch Step 3/5: 水鱼数据未更新，无需同步调整")
    
    
    # --- 4. 尝试从水鱼获取拟合数据 ---
    sy_chart_stats = await network.sy_chart_stats()
    if sy_chart_stats:
        logger.info("maib-fetch Step 4/5: 更新水鱼的国服拟合定数数据")
        try:
            synh_list: list[dict] = []
            for shortid, sy_stats in sy_chart_stats.get("charts", {}).items():
                        shortid = int(shortid)
                        fit_diffs: list[float] = [s.get('fit_diff', 0) for s in sy_stats]
                        for diff, lv_synh in enumerate(fit_diffs, start=2):
                            synh_list.append({"shortid": shortid, "difficulty": diff, "level": lv_synh})
            await services.set_mct_level_batch(synh_list, server="synh")
        except Exception as e:
            logger.error(f"maib-fetch Step 4/5: 更新水鱼拟合定数数据失败，原因：{e}")
    else:
        logger.info("maib-fetch Step 4/5: 未获取到水鱼拟合定数数据")

    # --- 5. 从别名库更新别名 ---
    logger.info("maib-fetch Step 5/5: 同步别名库数据")
    
    async def yuzuchan():
        yuzuchan_data = await network.yuzuchan_alias_list()
        if not yuzuchan_data:
            return []
        aliases_set: set[tuple[int, str]] = set()
        for entry in yuzuchan_data.get("content", []):
            song_id = int(entry.get('SongID', 0))
            aliases: list[str] = entry.get('Alias', '')
            aliases_set.update((song_id, alias) for alias in aliases)
        return list(aliases_set)
    
    async def lxns():
        lxns_data = await network.lx_alias_list()
        if not lxns_data:
            return []
        aliases_set: set[tuple[int, str]] = set()
        for entry in lxns_data.get("aliases", []):
            song_id = int(entry.get('song_id', 0))
            aliases: list[str] = entry.get('aliases', [])
            aliases_set.update((song_id, alias) for alias in aliases)
        return list(aliases_set)
    
    
    await services.add_mdt_alias_batch(await yuzuchan(), -101)
    logger.info("maib-fetch Step 5/5: 同步 yuzuchan 别名数据完成")
    await services.add_mdt_alias_batch(await lxns(), -102)
    logger.info("maib-fetch Step 5/5: 同步 lxns 别名数据完成")
    
    
    # --- 6. 结束 ---
    logger.info(f"maib-fetch 同步完成，耗时: {(time.time() - now_time):.2f} 秒")

