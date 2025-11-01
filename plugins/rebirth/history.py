import numpy as np
from pathlib import Path
from typing import Dict, Optional


class RebirthHistory:
    """基于 NumPy 三维数组的投胎历史记录管理类"""
    # 城市/农村、性别的映射
    CITY_RURAL_MAP = {"城市": 0, "农村": 1}
    GENDER_MAP = {"男": 0, "女": 1}

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.province_map: Dict[str, int] = {}
        self.data: np.ndarray = self._load() if self.file_path.exists() else self._init()

    def _init(self) -> np.ndarray:
        self.province_map = {}
        # 初始化为 (0, 2, 2) 空数组
        return np.zeros((0, 2, 2), dtype=int)

    def _load(self) -> np.ndarray:
        npz_file = np.load(self.file_path, allow_pickle=True)
        self.province_map = dict(npz_file["province_map"])
        return npz_file["data"]

    def _save(self):
        # 省份映射用 np.savez 的 dict存储特性保存
        np.savez(self.file_path,
                 data=self.data,
                 province_map=np.array(list(self.province_map.items()), dtype=object))

    def __repr__(self):
        return f"<RebirthHistory total={self.get_total_count()} provinces={self.get_province_list()}>"

    def _add_province(self, province: str):
        # 新增省份，扩容数组，更新映射
        new_index = len(self.province_map)
        self.province_map[province] = new_index
        # 扩展数组
        self.data = np.pad(self.data, ((0,1),(0,0),(0,0)), 'constant')

    def add_record(self, province: str, city_or_rural: str, gender: str):
        """新增投胎记录"""

        # 若省份不存在则自动扩容
        if province not in self.province_map:
            self._add_province(province)
        p_idx = self.province_map[province]
        c_idx = self.CITY_RURAL_MAP[city_or_rural]
        g_idx = self.GENDER_MAP[gender]
        self.data[p_idx, c_idx, g_idx] += 1
        self._save()

    def get_count(self, province: Optional[str]=None,
                  city_or_rural: Optional[str]=None,
                  gender: Optional[str]=None) -> int:
        """获取投胎次数，支持按省份、城市/农村、性别筛选统计"""
        try:
            p_idx = (self.province_map[province] if province else slice(None))
            c_idx = (self.CITY_RURAL_MAP[city_or_rural] if city_or_rural else slice(None))
            g_idx = (self.GENDER_MAP[gender] if gender else slice(None))
            return int(self.data[p_idx, c_idx, g_idx].sum())
        except KeyError:
            # 至少有一个键不存在，总次数一定为 0
            return 0

    def get_total_count(self) -> int:
        """获取总投胎次数"""
        return int(self.data.sum())

    def get_specific_count(self, province: str, city_or_rural: str, gender: str) -> int:
        """获取指定省份、城市/农村、性别的投胎次数"""
        if province not in self.province_map:
            return 0
        p_idx = self.province_map[province]
        c_idx = self.CITY_RURAL_MAP[city_or_rural]
        g_idx = self.GENDER_MAP[gender]
        return int(self.data[p_idx, c_idx, g_idx])

    def get_province_list(self):
        """返回所有省份列表"""
        return list(self.province_map.keys())

    def get_province_index(self, province: str) -> int:
        """返回省份对应的索引，若不存在则返回 -1"""
        return self.province_map.get(province)
