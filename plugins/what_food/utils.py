import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Literal, List, Optional, Dict, Set, Type, Union

import nonebot

nonebot.require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_dir as get_data_dir
from nonebot_plugin_localstore import get_plugin_cache_dir as get_cache_dir

from .default import FOODS, DRINKS, WINES


def content_cut(text: str) -> List[str]:
    """辅助拆分函数"""
    tags = [",", ".", ";", "，", "。", "；", "/", "、"]
    for tag in tags:
        text = text.replace(tag, " ")
    result = [f.strip() for f in text.split(" ") if f]
    return result


class Score:
    def __init__(self, path: Path):
        self.path = path
        self.data = None
        self.food_ids = []  # 存储food_id的映射
        self.user_ids = []  # 存储user_id的映射
        self.food_id_to_index = {}  # food_id到索引的映射
        self.user_id_to_index = {}  # user_id到索引的映射

        self.super_users: Set[int] = set()
        super_users_str = nonebot.get_driver().config.superusers
        for user_id_str in super_users_str:
            try:
                user_id = int(user_id_str)
                self.super_users.add(user_id)
            except ValueError:
                continue

        if path.exists():
            self._load_from_file()
        else:
            # 如果文件不存在，创建空数组
            self.data = np.zeros((0, 0), dtype=int)

        self._precompute_super_user_indices()

    def _precompute_super_user_indices(self):
        """预先计算超级用户索引"""
        self.super_user_indices = np.array([
            self.user_id_to_index[user_id] for user_id in self.super_users
            if user_id in self.user_id_to_index
        ])
        self.super_user_index_set = set(self.super_user_indices)

    def _load_from_file(self):
        """从.npz文件加载数据"""
        try:
            with np.load(self.path) as npz_file:
                self.data = npz_file['data']
                self.food_ids = npz_file['food_ids'].tolist()
                self.user_ids = npz_file['user_ids'].tolist()

                # 重建索引映射
                self.food_id_to_index = {fid: idx for idx, fid in enumerate(self.food_ids)}
                self.user_id_to_index = {uid: idx for idx, uid in enumerate(self.user_ids)}

        except Exception as e:
            raise ValueError(f"加载文件失败: {e}")

    def _ensure_capacity(self, food_id: int, user_id: int):
        """确保数组有足够的容量来存储指定的food_id和user_id"""
        need_resize = False
        new_shape = list(self.data.shape)

        # 检查是否需要扩展food_id维度
        if food_id not in self.food_id_to_index:
            new_food_index = len(self.food_ids)
            self.food_ids.append(food_id)
            self.food_id_to_index[food_id] = new_food_index
            new_shape[0] = len(self.food_ids)
            need_resize = True

        # 检查是否需要扩展user_id维度
        if user_id not in self.user_id_to_index:
            new_user_index = len(self.user_ids)
            self.user_ids.append(user_id)
            self.user_id_to_index[user_id] = new_user_index
            new_shape[1] = len(self.user_ids)
            need_resize = True

        # 如果需要调整大小，扩展数组
        if need_resize:
            if self.data.size == 0:
                self.data = np.zeros(new_shape, dtype=int)
            else:
                new_data = np.zeros(new_shape, dtype=int)
                # 复制旧数据到新数组
                rows = min(self.data.shape[0], new_shape[0])
                cols = min(self.data.shape[1], new_shape[1])
                new_data[:rows, :cols] = self.data[:rows, :cols]
                self.data = new_data

    def get_average(self, food_id: int) -> float:
        """计算food_id对应的所有非0评分的平均值"""
        if food_id not in self.food_id_to_index:
            return 0.0

        multiplier: int = 30

        food_index = self.food_id_to_index[food_id]
        scores = self.data[food_index, :]

        non_zero_mask = scores != 0
        non_zero_scores = scores[non_zero_mask]

        if len(non_zero_scores) == 0:
            return 0.0

        # 使用向量化操作处理超级用户
        super_mask = np.isin(np.arange(len(scores)), self.super_user_indices) & non_zero_mask
        super_scores = scores[super_mask]
        normal_scores = scores[non_zero_mask & ~super_mask]

        if len(super_scores) > 0:
            total_sum = np.sum(normal_scores) + np.sum(super_scores) * multiplier
            total_count = len(normal_scores) + len(super_scores) * multiplier
            avg_score = total_sum / total_count
        else:
            avg_score = np.mean(non_zero_scores)

        return round(avg_score, 2)

    def set_score(self, food_id: int, score: Literal[1, 2, 3, 4, 5], user_id: int):
        """设置或更新评分"""
        # 确保容量
        self._ensure_capacity(food_id, user_id)

        # 获取索引
        food_index = self.food_id_to_index[food_id]
        user_index = self.user_id_to_index[user_id]

        # 设置评分
        self.data[food_index, user_index] = score

    def save(self):
        """保存数据到.npz文件"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # 使用临时文件避免写入过程中出错
            temp_path = self.path.with_suffix('.tmp')
            np.savez(temp_path, data=self.data, food_ids=np.array(self.food_ids), user_ids=np.array(self.user_ids))
            temp_path.replace(self.path)  # 原子操作替换
        except Exception as e:
            # 记录日志
            raise e


class Eatable:
    def __init__(self, name: str, adder: int, score: Score, is_wine: bool = False,
                 enabled: bool = True, num: int = -10):
        # num = -10: 未指定 ID，添加时由 Menu 类分配
        self.num: int = num
        self.name: str = name
        self.is_wine: bool = is_wine
        self.adder: int = adder  # -1 为默认添加
        # Score 规则: 喜欢的餐点(1), 不错的餐点(2), 也可以说成餐点(3), 不喜欢这个餐点(4), 不适合作为餐点(5)
        self.score: Score = score
        self.enabled: bool = enabled
        self.category: str = 'Eatable'  # 子类中重写

    def average_score(self) -> float:
        """计算平均评分"""
        return self.score.get_average(self.num)

    def set_score(self, score_value: Literal[1, 2, 3, 4, 5], user_id: int):
        """设置评分"""
        self.score.set_score(self.num, score_value, user_id)


class Food(Eatable):
    category = 'Food'


class Drink(Eatable):
    category = 'Drink'


class Menu:
    """菜单数据类"""

    def __init__(self):
        dir_path = get_data_dir()
        dir_path.mkdir(parents=True, exist_ok=True)

        self.foods_path = dir_path / "foods.json"
        self.drinks_path = dir_path / "drinks.json"

        self.food_score = Score(dir_path / "foods_score.npz")
        self.drink_score = Score(dir_path / "drinks_score.npz")
        # 加载菜单数据
        self.foods: Dict[int, Food] = self._load_menu(Food, self.food_score)
        self.drinks: Dict[int, Drink] = self._load_menu(Drink, self.drink_score)

    @staticmethod
    def _add_history(category: Literal['Add', 'Score', 'Wine'], item: Eatable, score: Optional[int],
                     user_id: int, group_id: int = -1,) -> None:
        """添加历史记录"""
        now = datetime.now()
        now_date = now.strftime('%Y%m%d')
        now_time = now.strftime('%H:%M:%S')
        history_path = get_cache_dir() / "logs" / f"menu_{category.lower()}_history_{now_date}.csv"
        if not history_path.parent.exists():
            history_path.parent.mkdir(parents=True, exist_ok=True)
        if not history_path.exists():
            with open(history_path, "w", encoding="utf-8") as file:
                if category == 'Add':
                    file.write("time,user_id,category,food_id,name,group_id\n")
                elif category == 'Score':
                    file.write("time,user_id,category,food_id,score,group_id\n")
                elif category == 'Wine':
                    file.write("time,user_id,category,food_id,is_wine,group_id\n")

        with open(history_path, "a", encoding="utf-8") as file:
            if category == 'Add':
                file.write(f"{now_time},{user_id},{item.category},{item.num},\"{item.name}\",{group_id}\n")
            elif category == 'Score' and score is not None:
                file.write(f"{now_time},{user_id},{category},{item.num},{score},{group_id}\n")
            elif category == 'Wine':
                file.write(f"{now_time},{user_id},{category},{item.num},{item.is_wine},{group_id}\n")

    def _save_menu(self, cls: Optional[Type[Union[Food, Drink]]],
                   init_dict: Optional[Dict[int, Dict[str, bool | int | str]]] = None) -> None:
        """保存菜单数据到文件"""
        """
        Dict[int, Dict[str, bool | int | str]]
        { 1, {"name": "烤冷面", "is_wine": false, "adder": -1, "enabled": true} }
        """
        if not cls:
            # 无参 -> 保存所有类别
            self._save_menu(Food)
            self._save_menu(Drink)
            return

        fpath = {Food: self.foods_path, Drink: self.drinks_path}.get(cls)
        items = {Food: self.foods, Drink: self.drinks}.get(cls)
        foods: Dict[int, Dict[str, bool | int | str]] = {
            item.num: {
                "name": item.name,
                "is_wine": item.is_wine,
                "adder": item.adder,
                "enabled": True
            }
            for item in items.values()
        } if init_dict is None else init_dict

        with open(fpath, "w", encoding="utf-8") as file:
            json.dump(foods, file, ensure_ascii=False, indent=2)

        score = {Food: self.food_score, Drink: self.drink_score}.get(cls)
        score.save()

    def _load_json(self, cls) -> Dict[int, Dict[str, bool | int | str]]:
        """从文件加载菜单数据，若文件不存在则创建默认数据，返回原始数据"""
        """
        Dict[int, Dict[str, bool | int | str]]
        { 1, {"name": "烤冷面", "is_wine": false, "adder": -1, "enabled": true} }
        """
        fpath = self.foods_path if cls == Food else self.drinks_path
        if not fpath.exists():
            default: List[str] = FOODS if cls == Food else DRINKS
            d = dict()
            for i, name in enumerate(default):
                d[i+1] = {"name": name, "is_wine": False, "adder": -1, "enabled": True}
            if default == DRINKS:
                for j, name in enumerate(WINES):
                    d[len(default)+j+1] = {"name": name, "is_wine": True, "adder": -1, "enabled": True}
            self._save_menu(cls, d)
        with open(fpath, "r", encoding="utf-8") as file:
            try:
                data: Dict[int, Dict[str, bool | int | str]] = json.load(file)
            except json.JSONDecodeError:
                # 文件损坏，删除原有数据
                # logger.
                fpath.unlink()
                return self._load_json(cls)  # 利用递归重新加载
        return data

    def _load_menu(self, cls: Type[Union[Food, Drink]], score: Score) -> Dict[int, Food | Drink]:
        """加载菜单数据，返回 Food 或 Drink 实例的字典"""
        menu: Dict[int, Dict[str, bool | int | str]] = self._load_json(cls)

        foods: Dict[int, Food | Drink] = {}
        for food_id, attrs in menu.items():
            item = cls(
                num=food_id,
                name=attrs["name"],
                adder=attrs.get("adder", -1),
                score=score,
                is_wine=attrs.get("is_wine", False),
                enabled=attrs.get("enabled", False)
            )
            foods[food_id] = item

        return foods

    def _get_max_id(self, cls) -> int:
        """获取当前类别的最大 ID"""
        items = self.foods if cls == Food else self.drinks
        if not items: return 0
        return max(items.keys())

    def add_eatable(self, item: Food | Drink, user_id, group_id=-1) -> bool:
        """添加食物或饮品到相应列表"""
        if isinstance(item, Food):
            target_dict = self.foods
        elif isinstance(item, Drink):
            target_dict = self.drinks
        else: return False  # Unsupported type

        target_set = set([v.name for v in target_dict.values()])  # 转为集合以便判断重复
        old_count = len(target_set)
        target_set.add(item.name)
        if not len(target_set) > old_count:
            return False  # Already exists

        # 确认存在，分配 ID
        if item.num == -10:
            item.num = self._get_max_id(type(item)) + 1
        target_dict.update({item.num: item})

        # 保存到文件
        self._save_menu(type(item))
        # 记录添加历史
        self._add_history('Add', item, None, user_id, group_id)
        return True  # Successfully added

    def add_eatables(self, items: list[Food | Drink], user_id, group_id=-1) -> List[Food | Drink]:
        """批量添加食物或饮品，返回实际添加的项目列表"""
        added_items = []
        for item in items:
            if self.add_eatable(item, user_id, group_id):
                added_items.append(item)
        return added_items

    def get_foods(self) -> List[Food]:
        """获取所有食物列表"""
        return [food for food in self.foods.values() if food.enabled]

    def get_drinks(self) -> List[Drink]:
        """获取所有饮品列表"""
        return [drink for drink in self.drinks.values() if drink.enabled]

    def get_food(self, food_id: int) -> Optional[Food]:
        """获取指定 ID 的食物"""
        food = self.foods.get(food_id, None)
        return food

    def get_drink(self, drink_id: int) -> Optional[Drink]:
        """获取指定 ID 的饮品"""
        drink = self.drinks.get(drink_id, None)
        return drink

    def set_food_score(self, food_id: int, score_value: Literal[1, 2, 3, 4, 5], user_id: int) -> bool:
        """设置指定 ID 食物的评分"""
        food = self.get_food(food_id)
        if not food: return False
        food.set_score(score_value, user_id)
        self._add_history('Score', food, score_value, user_id)
        return True

    def set_drink_score(self, drink_id: int, score_value: Literal[1, 2, 3, 4, 5], user_id: int) -> bool:
        """设置指定 ID 饮品的评分"""
        drink = self.get_drink(drink_id)
        if not drink: return False
        drink.set_score(score_value, user_id)
        self._add_history('Score', drink, score_value, user_id)
        return True

    def set_food_wine(self, food_id: int, is_wine: bool, user_id: int, group_id: int = -1) -> bool:
        """设置指定 ID 食物是否为酒类"""
        food = self.get_food(food_id)
        if not food: return False
        food.is_wine = is_wine
        self._save_menu(Food)
        self._add_history('Wine', food, None, user_id, group_id)
        return True

    def set_drink_wine(self, drink_id: int, is_wine: bool, user_id: int, group_id: int = -1) -> bool:
        """设置指定 ID 饮品是否为酒类"""
        drink = self.get_drink(drink_id)
        if not drink: return False
        drink.is_wine = is_wine
        self._save_menu(Drink)
        self._add_history('Wine', drink, None, user_id, group_id)
        return True

    def find_by_name(self, category: Literal["Food", "Drink"], name: str) -> int:
        """根据名称查找食物或饮品"""
        items = self.foods if category == "Food" else self.drinks
        for item in items.values():
            if item.name == name:
                return item.num
        return -1  # Not found

    def get_no_score_list(self, user_id: int) -> Optional[List[Food | Drink]]:
        """确认该用户未评分的食物及饮品列表"""
        # todo: 从某些方面来讲实现了审核机制
        ...