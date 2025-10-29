from typing import List, Tuple, Optional


RATE_FACTOR_TABLE: List[Tuple[float, float]] = [
    (100.5000, 0.224),
    (100.4999, 0.222),
    (100.0000, 0.216),
    (99.9999, 0.214),
    (99.5000, 0.211),
    (99.0000, 0.208),
    (98.9999, 0.206),
    (98.0000, 0.203),
    (97.0000, 0.200),
    (96.9999, 0.176),
    (94.0000, 0.168),
    (90.0000, 0.152),
    (80.0000, 0.136),
    (79.9999, 0.128),
    (75.0000, 0.120),
    (70.0000, 0.112),
    (60.0000, 0.096),
    (50.0000, 0.080),
    (40.0000, 0.064),
    (30.0000, 0.048),
    (20.0000, 0.032),
    (10.0000, 0.016),
]


class MusicInfo:
    
    name: str
    short_id: int  # <10000
    dx_chart: bool
    score: float
    difficulty: int  # EASY=0, BASIC=1, ADVANCED=2, EXPERT=3, MASTER=4, REMASTER=5
    level: float
    new: bool = False  # False=b35, True=b15
    combo: int = 0  # FC=1, FC+=2, AP=3, AP+=4
    sync: int = 0  # SYNC_PLAY=1, FS=2, FS+=3, FDX=4, FDX+=5
    dx_score: int = 0
    dx_score_max: int = 0
    dxrating: int = 0    
    CiRCLE_version: bool = False  # 影响 CiRCLE 新增的 AP 曲目可获得的 DXRating 1 分奖励
        
    def __init__(self, name: str, short_id: int, dx_chart: bool, score: float,
                 difficulty: int, level: float, new: bool, combo: int, sync: int,
                 dx_score: int, dx_score_max: int) -> None:
        # 初始化属性
        self.name = name
        self.short_id = short_id
        self.dx_chart = dx_chart
        self.score = score
        self.difficulty = difficulty
        self.level = level
        self.new = new if new else False
        self.combo = combo if combo else 0
        self.sync = sync if sync else 0
        self.dx_score = dx_score if dx_score else 0
        self.dx_score_max = dx_score_max if dx_score_max else 0
        
        # 计算 DX Rating
        factor: float = 0.0  # 因子
        for threshold, f in RATE_FACTOR_TABLE:
            if self.score >= threshold:
                factor = f
                break
        self.dxrating = int(self.difficulty * self.score * factor)
        # CiRCLE 版本 AP 曲目额外奖励
        if (self.CiRCLE_version and (self.combo >=3)):
            self.dxrating += 1
    
    def dict(self, style=None) -> dict:
        return {
            "name": self.name,
            "short_id": self.short_id,
            "dx_chart": self.dx_chart,
            "score": self.score,
            "difficulty": self.difficulty,
            "level": self.level,
            "new": self.new,
            "combo": self.combo,
            "sync": self.sync,
            "dx_score": self.dx_score,
            "dx_score_max": self.dx_score_max,
            "dxrating": self.dxrating
        }


class GenB50Info:

    _b35_music_infos: List[Tuple[MusicInfo, int]] = []
    _b15_music_infos: List[Tuple[MusicInfo, int]] = []
    name: str = ""
    
    dxrating: int = 0
    b35_ra: int = 0
    b15_ra: int = 0
    friend_rank: str = "B5"
    rank: str = "初心者"
    
    def __init__(self, name: str, friend_battle_rank: Optional[str], rank: Optional[str]) -> None:
        # 初始化属性
        self.name = name
        self.friend_rank = friend_battle_rank if friend_battle_rank else "B5"
        self.rank = rank if rank else "初心者"
    
    def add_music_info(self, music_info: MusicInfo) -> int:
        mi = music_info
        if mi.new:
            # 进入 b15 部分
            if len(self._b15_music_infos) < 15:
                self._b15_music_infos.append((mi, mi.dxrating))
                self.b15_ra += mi.dxrating
            else:
                # 替换 b15 部分最低分数曲目
                self._b15_music_infos.sort(key=lambda x: x[1])  # 按分数排序
                min_dxrating = self._b15_music_infos[14][1]  # 按序排列的最低 rating 曲目
                if mi.dxrating < min_dxrating:
                    return self.dxrating
                self._b15_music_infos[14] = (mi, mi.dxrating)
                self._b15_music_infos.sort(key=lambda x: x[1])  # 重新按分数排序
                self.b15_ra = sum(x[1] for x in self._b15_music_infos)  # 重新计算 b15 部分总分
        else:
            # 进入 b35 部分
            if len(self._b35_music_infos) < 35:
                self._b35_music_infos.append((mi, mi.dxrating))
                self.b35_ra += mi.dxrating
            else:
                # 替换 b35 部分最低分数曲目
                self._b35_music_infos.sort(key=lambda x: x[1])  # 按分数排序
                min_dxrating = self._b35_music_infos[34][1]  # 按序排列的最低 rating 曲目
                if mi.dxrating < min_dxrating:
                    return self.dxrating
                self._b35_music_infos[34] = (mi, mi.dxrating)
                self._b35_music_infos.sort(key=lambda x: x[1])  # 重新按分数排序
                self.b35_ra = sum(x[1] for x in self._b35_music_infos)  # 重新计算 b35 部分总分
        # 重新计算总 DX Rating
        self.dxrating = self.b35_ra + self.b15_ra
        return self.dxrating

    def get_music_infos(self) -> Tuple[List[MusicInfo], List[MusicInfo]]:
        b35_list = [x[0] for x in self._b35_music_infos]
        b15_list = [x[0] for x in self._b15_music_infos]
        return b35_list, b15_list

    def get_music_infos_dict(self) -> dict:
        b35_list = [x[0].dict() for x in self._b35_music_infos]
        b15_list = [x[0].dict() for x in self._b15_music_infos]
        return {
            "b35": b35_list,
            "b15": b15_list
        }