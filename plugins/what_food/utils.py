import yaml
from pathlib import Path
from typing import Literal, List

from .default import FOODS, DRINKS, WINES


def content_cut(text: str) -> List[str]:
    """辅助拆分函数"""
    tags = [",", ".", ";", "，", "。", "；", "/", "、"]
    for tag in tags:
        text = text.replace(tag, " ")
    result = [f for f in text.split(" ") if f]
    return result


class Eatable:
    is_wine: bool = False
    category: Literal["Food", "Drink", "Wine"]
    def __init__(self, name: str):
        self.name = name

class Food(Eatable):
    is_wine = False
    category = "Food"

class Drink(Eatable):
    is_wine = False
    category = "Drink"

class Wine(Food):
    is_wine = True
    category = "Wine"


class Menu:
    foods: set[Food]
    drinks: set[Drink]  # Only non-wine drinks
    wines: set[Wine]

    foods_path: Path
    drinks_path: Path
    wines_path: Path
    history_path: Path

    def __init__(self, foods_path: Path, drinks_path: Path, wines_path: Path, history_path: Path):
        self.foods_path = foods_path
        self.drinks_path = drinks_path
        self.wines_path = wines_path
        self.history_path = history_path
        self._get_by_file()

    def _get_by_file(self):
        """从文件加载菜单数据"""
        def _init_set(fpath: Path, default_list: tuple[str, ...], cls) -> set[Food | Drink | Wine]:
            if not fpath.exists():
                with open(fpath, "w", encoding="utf-8") as file:
                    yaml.dump(list(default_list), file, allow_unicode=True)
            with open(fpath, "r", encoding="utf-8") as file:
                l = {cls(n) for n in yaml.safe_load(file)}
            return l

        self.foods = _init_set(self.foods_path, FOODS, Food)
        self.drinks = _init_set(self.drinks_path, DRINKS, Drink)
        self.wines = _init_set(self.wines_path, WINES, Wine)

    def get_foods(self) -> tuple[Food, ...]:
        """返回 Food 列表"""
        return tuple(self.foods)

    def get_drinks(self) -> tuple[Drink | Wine, ...]:
        """返回 Drink 列表，包含 Wine"""
        return tuple(self.drinks.union(self.wines))

    def add_food(self, item: Eatable, user_id, group_id=-1) -> bool:
        """添加食物或饮品到相应列表"""
        set_and_path_map = {
            "Food": {"set": self.foods, "path": self.foods_path, "tag": "Food"},
            "Drink": {"set": self.drinks, "path": self.drinks_path, "tag": "Drink"},
            "Wine": {"set": self.wines, "path": self.wines_path, "tag": "Wine"},
        }
        if isinstance(item, Food): target = set_and_path_map["Food"]
        elif isinstance(item, Wine): target = set_and_path_map["Wine"]  # Wine 属于 Drink 子类，需要优先处理
        elif isinstance(item, Drink): target = set_and_path_map["Drink"]
        else: return False # Unsupported type

        target_set = target["set"]
        old_count = len(target_set)
        target_set.add(item)
        is_new = len(target_set) > old_count
        if not is_new: return False  # Already exists

        # 保存到文件
        with open(target["path"], "w", encoding="utf-8") as file:
            yaml.dump([f.name for f in target_set], file, allow_unicode=True)
        with open(self.history_path, "a", encoding="utf-8") as file:
            from datetime import datetime
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            file.write(f"[{now}] {user_id} Add a {target["tag"]}: \"{item.name}\" (from group: {group_id})\n")
        return True  # Successfully added

    def add_foods(self, items: list[Eatable], user_id, group_id=-1) -> list[Eatable]:
        """批量添加食物或饮品，返回实际添加的项目列表"""
        added_items = []
        for item in items:
            if self.add_food(item, user_id, group_id):
                added_items.append(item)
        return added_items
