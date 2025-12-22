import csv
import json
import random
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Callable, Literal, List, Optional, Dict, Type, Tuple

from .init import get_default_foods, get_default_drinks


# Type 定义
MENU_JSON_DATA = Dict[int, Dict[str, bool | int | str]]

SUPERUSER_ID = -127
SUPERUSER_MULTIPLIER = 30


# noinspection DuplicatedCode
class BadLogger:
    """在无 nonebot2 日志记录器情况下的占位类"""
    @staticmethod
    def critical(msg: str): print("CRITICAL:", msg)
    @staticmethod
    def success(msg: str): print("SUCCESS:", msg)
    @staticmethod
    def trace(msg: str): print("TRACE:", msg)
    @staticmethod
    def debug(msg: str): print("DEBUG:", msg)
    @staticmethod
    def info(msg: str): print("INFO:", msg)
    @staticmethod
    def warning(msg: str): print("WARNING:", msg)
    @staticmethod
    def error(msg: str): print("ERROR:", msg)


def content_cut(text: str) -> List[str]:
    """辅助拆分函数"""
    tags = [",", ".", "，", "。", "；", "/", "、"]
    for tag in tags:
        text = text.replace(tag, ";")
    result = [f.strip() for f in text.split(";") if f]
    return result


class Score:

    def __init__(self, path: Path, nb_logger=None):
        self.logger = nb_logger
        self.npz_path = path

        self.data: np.ndarray
        self.item_id_index: Dict[int, int] = {}
        self.user_id_index: Dict[int, int] = {}
        self._score_cache: Dict[int, float] = {}

        self._load_from_file() if self.npz_path else self._init_data()

    @property
    def item_ids(self) -> Optional[List[int]]:
        return list(self.item_id_index.keys())

    @property
    def user_ids(self) -> Optional[List[int]]:
        return list(self.user_id_index.keys())

    def _init_data(self):
        """初始化空数据结构"""
        self.data = np.zeros((0, 0), dtype=int)
        self.item_id_index = {}
        self.user_id_index = {}

    def _load_from_file(self):
        """从.npz文件加载数据"""
        self._score_cache.clear()
        try:
            with np.load(self.npz_path) as npz_file:
                self.data = npz_file['data']
                self.item_id_index = {iid: idx for idx, iid in enumerate(npz_file['item_ids'].tolist())}
                self.user_id_index = {uid: idx for idx, uid in enumerate(npz_file['user_ids'].tolist())}
        except FileNotFoundError:
            self._init_data()
        except Exception as e:
            raise ValueError(f"加载文件失败: {e}")

    def _save_to_file(self):
        """保存数据到.npz文件"""
        try:
            self.npz_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.npz_path.parent / "temp_bcfa7f6.npz"
            temp_path.unlink(missing_ok=True)
            np.savez(temp_path, data=self.data, item_ids=np.array(self.item_ids), user_ids=np.array(self.user_ids))
            temp_path.replace(self.npz_path)
        except Exception as e:
            raise e

    def _ensure_capacity(self, item_id: int, user_id: int):
        """确保数组有足够的容量来存储指定的 item_id 和 user_id。"""
        need_resize = False

        if item_id not in self.item_id_index:
            new_item_index = len(self.item_ids)
            self.item_id_index[item_id] = new_item_index
            need_resize = True

        if user_id not in self.user_id_index:
            new_user_index = len(self.user_ids)
            self.user_id_index[user_id] = new_user_index
            need_resize = True

        if need_resize:
            new_shape = [len(self.item_ids), len(self.user_ids)]
            if self.data is None or self.data.size == 0:
                self.data = np.zeros(new_shape, dtype=int)
            else:
                new_data = np.zeros(new_shape, dtype=int)
                rows = min(self.data.shape[0], new_shape[0])
                cols = min(self.data.shape[1], new_shape[1])
                new_data[:rows, :cols] = self.data[:rows, :cols]
                self.data = new_data

    def get_score(self, item_id: int) -> float:
        """计算item_id对应的所有非0评分的平均值，-127用户有30倍权重"""
        if item_id not in self.item_id_index:
            return 0.0
        # 缓存命中
        if item_id in self._score_cache:
            return self._score_cache[item_id]

        item_index = self.item_id_index[item_id]
        scores = self.data[item_index, :]

        user_ids_np = np.array(self.user_ids)
        superuser_mask = user_ids_np == SUPERUSER_ID
        normal_mask = user_ids_np > 0

        superuser_scores = scores[superuser_mask]
        normal_scores = scores[normal_mask]

        total_sum = (np.sum(normal_scores[normal_scores != 0]) +
                     np.sum(superuser_scores[superuser_scores != 0]) * SUPERUSER_MULTIPLIER)
        total_count = np.count_nonzero(normal_scores) + np.count_nonzero(superuser_scores) * SUPERUSER_MULTIPLIER

        if total_count == 0:
            return 0.0
        final_score = round(total_sum / total_count, 2)
        self._score_cache[item_id] = final_score  # 缓存结果
        return final_score

    def set_score(self, item_id: int, score: int, user_id: int):
        """设置或更新用户评分"""
        self._score_cache.pop(item_id, None)  # 清除缓存
        self._ensure_capacity(item_id, user_id)
        item_index = self.item_id_index[item_id]
        user_index = self.user_id_index[user_id]
        self.data[item_index, user_index] = score
        self._save_to_file()


class Eatable:
    category: str = 'Eatable'

    def __init__(self, name: str, adder: int, score: Score, is_wine: bool = False,
                 enabled: bool = True, num: int = -10):
        # num < 0 意为未指定 ID，添加时由 Menu 类分配
        self.num: int = num
        self.name: str = name
        self.is_wine: bool = is_wine
        self.adder: int = adder  # -1 为默认添加
        self.enabled: bool = enabled

        # Score 规则: 喜欢的餐点(1), 不错的餐点(2), 也可以说成餐点(3), 不喜欢这个餐点(4), 不适合作为餐点(5)
        self._score: Score = score  # score 对象引用，外部不应直接操作该对象
        self._score_change_callbacks: List[Callable[['Eatable'], None]] = []

    def add_score_change_callback(self, callback: Callable[['Eatable'], None]):
        """添加评分变化回调函数"""
        if callback not in self._score_change_callbacks:
            self._score_change_callbacks.append(callback)

    def remove_score_change_callback(self, callback: Callable[['Eatable'], None]):
        """移除评分变化回调函数"""
        if callback in self._score_change_callbacks:
            self._score_change_callbacks.remove(callback)

    def get_score(self) -> float:
        """获取当前评分"""
        return self._score.get_score(self.num)

    def set_score(self, score_value: int, user_id: int):
        """设置普通用户评分"""
        self._score.set_score(self.num, score_value, user_id)
        for callback in self._score_change_callbacks:
            callback(self)

    def set_superuser_score(self, score_value: int):
        """设置 Superuser 的高权重评分"""
        self.set_score(score_value, SUPERUSER_ID)


class Food(Eatable):
    category = 'Food'


class Drink(Eatable):
    category = 'Drink'


class EatableMenu:
    """菜单数据类"""

    def __init__(self, cls: Type[Eatable], default_data: MENU_JSON_DATA,
                 dir_path: Path, cache_dir_path: Path, nb_logger=BadLogger()):
        self.logger = nb_logger
        self.cls: Type[Eatable] = cls

        self.menu: Dict[int, Eatable] = {}
        self._sorted_items_cache: List[Eatable] = []

        # path 初始化
        dir_path.mkdir(parents=True, exist_ok=True)
        cache_dir_path.mkdir(parents=True, exist_ok=True)
        self.cache_dir: Path = cache_dir_path  # 缓存目录路径
        self.data_path: Path = dir_path / f"{self.cls.category}.json"  # 菜单数据文件路径
        score_path = dir_path / f"{self.cls.category}_scores.npz"  # 评分数据文件路径
        self.score: Score = Score(score_path, nb_logger)  # 评分对象类

        self._load_from_file(default_data=default_data)

    def _on_item_score_changed(self, _item: Eatable):
        """当某个Eatable项的评分变化时的回调函数"""
        self._sorted_items_cache.clear()

    def _load_from_file(self, default_data: MENU_JSON_DATA) -> None:
        """加载菜单数据，返回 Food 或 Drink 实例的字典"""

        def _load_from_json(num: int = 0, ex: Optional[Exception] = None) -> Dict[int, Dict[str, bool | int | str]]:
            """从文件加载菜单数据，若文件不存在则创建默认数据，返回转 int 后的原始数据"""
            if num > 2:
                raise ex  # 递归次数过多
            if not self.data_path.exists():
                with open(self.data_path, "w", encoding="utf-8") as file:
                    json.dump(default_data, file, ensure_ascii=False, indent=2)

            try:
                with open(self.data_path, "r", encoding="utf-8") as file:
                    data: Dict[str, Dict[str, bool | int | str]] = json.load(file)
            except Exception as ex:
                return _load_from_json(num + 1, ex)  # 利用递归重新加载
            return {int(eid): e for eid, e in data.items()}

        # 如果 menu 已存在，先移除回调
        if self.menu:
            [item.add_score_change_callback(self._on_item_score_changed) for item in self.menu.values()]

        # 加载数据并创建回调
        items: Dict[int, Eatable] = {}
        for item_id, attrs in _load_from_json().items():
            item = self.cls(
                num=item_id,
                name=attrs.get("name", "Unknown Food"),
                adder=attrs.get("adder", -1),
                score=self.score,  # score 对象引用，用于直接操作评分
                is_wine=attrs.get("is_wine", False),
                enabled=attrs.get("enabled", False)  # 有意设计，保留 enabled 在内存中
            )
            items[item_id] = item
            item.add_score_change_callback(self._on_item_score_changed)

        self.menu = items
        self._sorted_items_cache.clear()

    def _save_to_file(self) -> None:
        """保存菜单数据到文件"""
        # 存储时，key 必须为 str
        items: Dict[str, Dict[str, bool | int | str]] = {
            str(item.num): {
                "name": item.name,
                "is_wine": item.is_wine,
                "adder": item.adder,
                "enabled": item.enabled
            }
            for item in self.menu.values()
        }

        with open(self.data_path, "w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)

    def _add_history(self, category: Literal['Add', 'Score', 'Wine', 'Ban', 'UnBan'],
                     item: Eatable, user_id: int, group_id: int = -1, score: Optional[int] = None,
                     superuser: bool = False) -> None:
        """添加历史记录"""
        now = datetime.now()
        now_date = now.strftime('%Y%m%d')
        now_time = now.strftime('%H:%M:%S')
        history_path = self.cache_dir / "logs" / f"menu_{category.lower()}_history_{now_date}.csv"
        if not history_path.parent.exists():
            history_path.parent.mkdir(parents=True, exist_ok=True)

        # 根据 category 确定第四列信息字段名
        info4_name = {
            "Add": "name",
            "Score": "score",
            "Wine": "is_wine",
            "Ban": "is_ban",
            "UnBan": "is_ban",
        }.get(category, "info")

        # 使用 csv 模块写入，保证 header 与每行列数一致
        write_header = not history_path.exists()
        with open(history_path, "a", encoding="utf-8", newline='') as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["time", "user_id", "category", "item_id", info4_name, "group_id"])

            # 选择 info4 的实际值
            if category == "Add":
                info4 = item.name
            elif category == "Score":
                # 若没有 score 参数则跳过写入（评分记录必须包含分数）
                if score is None:
                    return
                info4 = score
            elif category == "Wine":
                info4 = item.is_wine
            elif category == "Ban":
                info4 = item.enabled
            elif category == "UnBan":
                info4 = item.enabled
            else:
                info4 = "unknown"

            writer.writerow(
                [now_time, f"{user_id}{'*' if superuser else ''}", item.category, item.num, info4, group_id]
            )

    def _get_max_id(self) -> int:
        """获取最大 ID"""
        try:
            int_keys = [int(k) for k in self.menu.keys()]
        except Exception as e:
            self.logger.error(f"{e}")
            return -1
        if not int_keys:
            return 0
        return max(int_keys)

    def _refresh_sorted_items_cache(self):
        """刷新排序缓存"""
        items = list(self.menu.values())
        items.sort(key=lambda item: item.get_score(), reverse=True)
        self._sorted_items_cache = items

    def _add_item(self, item: Eatable, group_id=-1, score: Literal[1, 2, 3, 4, 5] = 3) -> bool:
        """仅内存操作：添加餐点到相应列表"""
        target_set = set([v.name for v in self.menu.values()])  # 转为集合以便判断重复
        old_count = len(target_set)
        target_set.add(item.name)
        if not len(target_set) > old_count:
            return False  # Already exists

        # 确认存在，分配 ID
        if item.num < 0:
            max_id = self._get_max_id()
            if max_id < 0:
                return False  # 获取最大 ID 失败
            item.num = max_id + 1
        item.add_score_change_callback(self._on_item_score_changed)
        self.menu.update({item.num: item})

        # 记录添加历史
        self._add_history('Add', item, item.adder, group_id, None)
        self.set_score(item.num, score, item.adder, group_id)  # 初始评分
        self._sorted_items_cache.clear()
        return True  # Successfully added

    def add_item(self, item: Eatable, group_id=-1, score: Literal[1, 2, 3, 4, 5] = 3) -> bool:
        """添加餐点到相应列表"""
        if self._add_item(item, group_id, score):
            self._save_to_file()
            return True
        return False

    def add_items(self, items: list[Eatable], group_id=-1, score: Literal[1, 2, 3, 4, 5] = 3) -> List[Eatable]:
        """批量添加餐点，返回实际添加的项目列表"""
        added_items = []
        for item in items:
            if self._add_item(item, group_id, score):
                added_items.append(item)
        self._save_to_file()
        return added_items

    def get_items(self, ignore_enabled: bool = False) -> List[Eatable]:
        """获取所有餐点列表"""
        if len(self._sorted_items_cache) == 0:
            # 缓存为空，刷新缓存
            self._refresh_sorted_items_cache()
        if ignore_enabled:
            return self._sorted_items_cache.copy()
        return [item for item in self._sorted_items_cache if item.enabled]

    def get_item(self, item_id: int) -> Optional[Eatable]:
        """获取指定 ID 的餐点"""
        return self.menu.get(item_id, None)

    def get_item_id_by_name(self, name: str) -> int:
        """根据名称查找餐点 ID"""
        for item in self.menu.values():
            if item.name == name:
                return item.num
        return -1  # Not found

    def get_item_by_name(self, name: str) -> Optional[Eatable]:
        """根据名称查找餐点"""
        item_id = self.get_item_id_by_name(name)
        if item_id >= 0:
            return self.get_item(item_id)
        return None

    def set_score(self, item_id: int, score_value: Literal[1, 2, 3, 4, 5], user_id: int, group_id: int = -1) -> bool:
        """设置指定 ID 餐点的评分"""
        item = self.get_item(item_id)
        if not item:
            return False
        item.set_score(score_value, user_id)
        self._add_history('Score', item, user_id, group_id, score_value)
        self._sorted_items_cache.clear()
        return True

    def set_score_from_super_user(self, data: Dict[int, int], user_id: int, group_id: int = -1) -> Tuple[int, int]:
        """Superuser 设置的餐点评分（支持批量），通过非1~5的评分实现特殊权重效果"""
        if len(data) < 1:
            return 0, 0  # 无 data 内容
        count = 0
        for item_id, score_value in data.items():
            item = self.get_item(item_id)
            if not item:
                break
            item.set_score(score_value, SUPERUSER_ID)
            self._add_history('Score', item, user_id, group_id, score_value, superuser=True)
            count += 1
        self._sorted_items_cache.clear()
        return count, len(data)

    def set_is_wine(self, item_id: int, is_wine: bool, user_id: int, group_id: int = -1) -> bool:
        """设置指定 ID 餐点的酒精状态"""
        item = self.get_item(item_id)
        if not item:
            return False
        item.is_wine = is_wine
        self._save_to_file()
        self._add_history('Wine', item, user_id, group_id, None)
        return True

    def get_items_if_no_score(self, user_id: int) -> List[Eatable]:
        """确认该用户未评分的食物及饮品列表"""
        if user_id not in self.score.user_id_index:
            # 根本未评分，直接返回
            return self.get_items()

        user_idx = self.score.user_id_index[user_id]
        result: List[Eatable] = []
        for item in self.get_items():
            if item.num not in self.score.item_id_index:
                result.append(item)
            else:
                item_idx = self.score.item_id_index[item.num]
                # 如果数据维度不足也认为未评分
                if item_idx >= self.score.data.shape[0] or user_idx >= self.score.data.shape[1]:
                    result.append(item)
                else:
                    if self.score.data[item_idx, user_idx] == 0:
                        result.append(item)
        return result

    def get_items_if_superuser_no_score(self) -> Optional[List[Eatable]]:
        return self.get_items_if_no_score(SUPERUSER_ID)

    def set_enabled(self, item_id: int, enabled: bool = False, user_id: int = -1) -> bool:
        """设置餐点禁用"""
        item = self.get_item(item_id)
        if not item:
            return False  # 不存在该餐点

        # 设置 enabled 状态并保存
        if item.enabled == enabled:
            return True  # 不需要修改
        item.enabled = enabled
        if enabled:
            self._add_history("UnBan", item, user_id)
        else:
            self._add_history("Ban", item, user_id)
        self._save_to_file()
        self._sorted_items_cache.clear()
        return True

    def choice(self, offset: float) -> Optional[Eatable]:
        """
        核心方法 - 餐点抽选
        餐点会按照评分作为抽选权重。

        :param offset: 为正时，不会抽选出低于offset的餐点；为负时，不会抽选出高于offset的餐点，且此时评分权重逆转。
        """
        # 确保缓存存在
        self._refresh_sorted_items_cache()

        threshold = abs(offset)

        sorted_items: List[Eatable]
        if offset >= 0:
            sorted_items = [item for item in self.get_items() if item.get_score() >= threshold]
            reverse_weights = False
        else:
            sorted_items = [item for item in self.get_items() if item.get_score() <= threshold]
            reverse_weights = True

        if not sorted_items:
            return None  # 评分范围内无餐点

        scores = [item.get_score() for item in sorted_items]
        weights = scores.copy() if not reverse_weights else [(max(scores) + min(scores)) - s for s in scores]
        if sum(weights) == 0:
            # 全部权重为 0，退化为均等权重
            weights = None
        if any([w <= 0 for w in weights]):
            # 存在非正权重，整体偏移为正值
            # offset = abs(min(weights)) + 1
            # weights = [w + offset for w in weights]
            # fix
            weights = None

        chosen = random.choices(list(sorted_items), weights=weights, k=1)[0]
        return chosen


class MenuManager:
    """总菜单管理类"""

    def __init__(self, data_dir_path: Path, cache_dir_path: Path, nb_logger=BadLogger()):
        self.food = EatableMenu(Food, get_default_foods(), data_dir_path, cache_dir_path, nb_logger)
        self.drink = EatableMenu(Drink, get_default_drinks(), data_dir_path, cache_dir_path, nb_logger)

        self.cache_dir_path = cache_dir_path
        self.offset_data_path: Path = data_dir_path / "offsets.json"
        self.offset_data = {}

    def _load_offset_data(self):
        """加载 offset 数据"""
        if not self.offset_data_path.exists():
            self._save_offset_data()
        with open(self.offset_data_path, "r", encoding="utf-8") as file:
            self.offset_data = json.load(file)

    def _save_offset_data(self):
        """存储 offset 数据"""
        with open(self.offset_data_path, "w", encoding="utf-8") as file:
            json.dump(self.offset_data, file, ensure_ascii=False, indent=2)

    def _add_history(self, content: str, user_id: int, group_id: int = -1) -> None:
        """添加历史记录"""
        now = datetime.now().strftime('%Y%m%d %H:%M:%S')
        history_path = self.cache_dir_path / "logs" / f"offset_history.log"
        if not history_path.parent.exists():
            history_path.parent.mkdir(parents=True, exist_ok=True)

        with open(history_path, "a", encoding="utf-8") as file:
            file.write(f"[{now}] {user_id}({group_id}): {content}\n")

    def get_menu(self, category: str) -> Optional[EatableMenu]:
        """获取指定 Menu 实例"""
        c = category.lower().strip()
        if c in ["food", "foods", "吃", "f", "foodlist", "food_list"]:
            return self.food
        elif c in ["drink", "drinks", "喝", "d", "drinklist", "drink_list"]:
            return self.drink
        return None

    def get_offset(self, user_id: int) -> float:
        """获取 offset 计算值"""
        return self.offset_data.get(user_id, 2.2)

    def set_offset(self, user_id: int, offset: float, group_id: int = -1) -> bool:
        """设置 offset 值，区间为[-5, 5]，超出则拒绝并返回 False"""
        if not (-5 <= offset <= 5):
            return False
        self.offset_data[user_id] = offset
        self._add_history(f"Offset -> {offset}", user_id, group_id)
        self._save_offset_data()
        return True
