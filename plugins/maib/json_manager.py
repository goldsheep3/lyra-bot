import orjson
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import OrderedDict

from nonebot import logger

from .diving_fish import dev_player_records


class MusicDataManager:
    """乐曲数据管理器（统一索引 + 高性能缓存）"""

    # 内存缓存：{ music_id: { "id": 1, "title": "...", "fit_diff": [...] } }
    _unified_map: Dict[int, Dict[str, Any]] = {}
    _last_update: float = 0
    _expire_seconds: int = 7 * 24 * 3600  # 有效期
    _is_loading: bool = False

    @classmethod
    async def get_unified_data(cls, cache_path: Path, force: bool = False) -> Dict[int, Dict[str, Any]]:
        """获取合并后的统一数据字典（带内存与磁盘双重缓存检查）"""
        current_time = time.time()

        # 1. 内存命中：非强制更新且在有效期内，直接返回
        if cls._unified_map and not force:
            if current_time - cls._last_update < cls._expire_seconds:
                return cls._unified_map

        # 2. 串行加载数据（尊重 API 频率限制）
        cls._is_loading = True
        try:
            # 动态导入 API 函数
            from .diving_fish import music_data as fetch_music, chart_stats as fetch_fit

            # 串行获取两个数据源
            logger.info("开始同步全局乐曲数据...")
            raw_music = await cls._load_single_source(
                cache_path, "diving-fish-music-data", fetch_music, force
            )

            logger.info("开始同步拟合难度数据...")
            raw_fit = await cls._load_single_source(
                cache_path, "diving-fish-fit-data", fetch_fit, force
            )

            if isinstance(raw_fit, str) or isinstance(raw_music, str):
                logger.error("API 返回错误信息而非数据，无法继续处理")
                raise ValueError("API 返回错误信息而非数据")

            # 3. 处理并合并数据
            cls._unified_map = cls._process_and_merge(raw_music, raw_fit)
            cls._last_update = time.time()
            logger.success(f"全局乐曲数据已刷新，共计 {len(cls._unified_map)} 条记录")

        finally:
            cls._is_loading = False

        return cls._unified_map

    @classmethod
    def _process_and_merge(cls, music_list: List[Dict], fit_data: Dict) -> Dict[int, Dict]:
        """
        合并逻辑实现
        :param music_list: 来自 music_data 的原始列表
        :param fit_data: 来自 chart_stats 的原始字典
        :return: 合并后的 Dict[int, Any]
        """
        merged = {}
        for music in music_list:
            shortid = music.get('id', None)
            if shortid is None:
                continue
            merged[shortid] = {
                "music_data": music,
                "chart_stats": fit_data.get(str(shortid), [])
            }
        return merged

    @classmethod
    async def _load_single_source(cls, path: Path, prefix: str, api_func, force: bool) -> Any:
        """内部逻辑：处理单个 JSON 源的磁盘读取、API 更新及容错"""
        current_ts = int(time.time())
        files = sorted(
            list(path.glob(f"{prefix}_*.json")),
            key=lambda x: int(x.stem.split('_')[-1]) if x.stem.split('_')[-1].isdigit() else 0,
            reverse=True
        )

        latest = files[0] if files else None
        data = None

        # 尝试读取本地有效缓存
        if latest and not force:
            ts = int(latest.stem.split('_')[-1])
            if (current_ts - ts) < cls._expire_seconds:
                try:
                    with open(latest, 'rb') as f:
                        data = orjson.loads(f.read())
                    logger.debug(f"加载磁盘缓存: {latest.name}")
                except Exception as e:
                    logger.error(f"读取缓存 {latest.name} 失败: {e}")

        # 缓存无效、文件缺失或强制更新 -> 请求 API
        if data is None:
            try:
                data = await api_func()
                if not data:
                    raise ValueError("API 返回数据为空")

                # 保存新缓存
                new_file = path / f"{prefix}_{current_ts}.json"
                with open(new_file, 'wb') as f:
                    f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))  # type: ignore

                # 清理旧文件
                for f in files:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                logger.success(f"数据源 {prefix} 已从 API 更新并缓存")
            except Exception as e:
                logger.error(f"API {prefix} 更新失败: {e}")
                if latest:
                    with open(latest, 'rb') as f:
                        data = orjson.loads(f.read())
                    logger.warning(f"由于 API 故障，降级使用旧缓存: {latest.name}")
                else:
                    raise FileNotFoundError(f"本地与 API 均无可用数据: {prefix}")

        return data

    @classmethod
    async def fit_level(cls, music_id: int, cache_path: Path) -> Tuple[float, ...]:
        """快捷获取乐曲的拟合难度列表"""
        data_map = await cls.get_unified_data(cache_path)
        music = data_map.get(music_id, {})
        fits = music.get('chart_stats', [])
        return tuple(f.get('fit_diff', 0.0) for f in fits) if isinstance(fits, list) else tuple()

    @classmethod
    async def contains_id(cls, music_id: int, cache_path: Path) -> bool:
        """高性能判断 ID 是否存在"""
        data_map = await cls.get_unified_data(cache_path)
        return music_id in data_map.keys()


class UserDataManager:
    """用户数据管理器（LRU 缓存 + 变更检测机制）"""

    # 限制内存缓存大小，防止内存溢出
    MAX_CACHE_SIZE = 128
    _expire_seconds: int = 3 * 24 * 3600  # 有效期

    # 内存缓存格式: { userid: {"data": {...}, "last_update": float} }
    _memory_cache: Dict[int, Any] = OrderedDict()

    @classmethod
    async def get_user_data(cls, userid: int, cache_path: Path, developer_token: str,
                            force: bool = False) -> Tuple[Dict[str, Any], bool]:
        """
        获取用户数据
        :return: (data_dict, has_changed)
        """
        current_time = time.time()

        # 1. 检查内存缓存 (LRU 命中)
        if userid in cls._memory_cache:
            # 移动到末尾表示最新活跃
            cached_item = cls._memory_cache.pop(userid)
            cls._memory_cache[userid] = cached_item

            old_data: Optional[Dict] = cached_item["data"]
            if not force and (current_time - cached_item["last_update"] < cls._expire_seconds):
                return old_data, False  # 命中，返回
        else:
            # 内存未命中，尝试读取磁盘历史记录作为比对基准
            old_data: Optional[Dict] = await cls._read_from_disk(userid, cache_path)

        # 2. 获取最新数据
        try:
            new_data = await dev_player_records(userid, developer_token=developer_token)
            if not new_data:
                raise ValueError(f"用户 {userid} 的 API 返回数据为空")

            # 3. 变更检测 (Deep Compare)
            if old_data is None or old_data != new_data:
                has_changed = True
                await cls._save_to_disk(userid, new_data, cache_path)
                logger.info(f"用户 {userid} 数据已更新并检测到变更")
            else:
                has_changed = False
                logger.debug(f"用户 {userid} 数据未发生变更")

            # 4. 更新 LRU 内存缓存
            cls._update_lru_cache(userid, new_data, current_time)
            return new_data, has_changed

        except Exception as e:
            logger.error(f"用户 {userid} 数据更新失败: {e}")
            if old_data:
                # 即使更新失败，也将旧数据重新放入 LRU 以便后续访问
                cls._update_lru_cache(userid, old_data, 0)
                return old_data, False
            raise e

    @classmethod
    def _update_lru_cache(cls, userid: int, data: Dict, timestamp: float):
        """维护 LRU 队列，确保内存占用恒定"""
        if userid in cls._memory_cache:
            cls._memory_cache.pop(userid)

        cls._memory_cache[userid] = {
            "data": data,
            "last_update": timestamp
        }

        # 超过上限时弹出最旧的
        if len(cls._memory_cache) > cls.MAX_CACHE_SIZE:
            cls._memory_cache.popitem()

    @classmethod
    async def _read_from_disk(cls, userid: int, path: Path) -> Optional[Dict]:
        """寻找并读取磁盘中的用户数据缓存"""
        files = sorted(
            list(path.glob(f"user-data_{userid}_*.json")),
            key=lambda x: int(x.stem.split('_')[-1]),
            reverse=True
        )
        if files:
            try:
                with open(files[0], 'rb') as f:
                    return orjson.loads(f.read())
            except OSError:
                pass
        return None

    @classmethod
    async def _save_to_disk(cls, userid: int, data: Dict, path: Path):
        """持久化存储并清理该用户的旧文件"""
        current_ts = int(time.time())
        # 清理旧文件（针对该用户）
        for f in path.glob(f"user-data_{userid}_*.json"):
            try:
                f.unlink()
            except OSError:
                pass

        new_file = path / f"user-data_{userid}_{current_ts}.json"
        with open(new_file, 'wb') as f:
            f.write(orjson.dumps(data))  # type: ignore

    @classmethod
    def clear_memory(cls):
        """完全清空内存缓存"""
        cls._memory_cache.clear()
        logger.info("用户数据内存缓存已清空")

    @classmethod
    async def get_user_music_data(cls, shortid: int, userid: int, cache_path: Path,
                                  developer_token: str) -> List[Dict[str, List[Dict[str, Any]]]]:
        """快捷获取用户特定乐曲数据（包含变更检测）"""
        user_data, _ = await cls.get_user_data(userid, cache_path, developer_token)
        if user_data:
            records = user_data.get("records", [])
            return [record for record in records if record["shortid"] == shortid]
        return []
