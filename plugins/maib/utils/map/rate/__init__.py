from typing import Optional, Literal
from ...type import Achievement
from .._normalize import normalize_basic as normalize
from ._data import AchievementRateInfo, raw_rates


def _index_name_achievement(raw_rates: dict[Achievement, AchievementRateInfo]) -> dict[str, Achievement]:
    _dict: dict[str, Achievement] = {}
    
    for achievement, rate_info in raw_rates.items():
        for key in rate_info.keys():
            _dict[normalize(key)] = achievement

    return _dict


class AchievementMap:
    _raw: dict[Achievement, AchievementRateInfo] = raw_rates
    _index_name_achievement: dict[str, Achievement] = _index_name_achievement(raw_rates)

    # get: achievement -> info

    @classmethod
    def get(cls, achievement: Achievement) -> AchievementRateInfo:
        if achievement in cls._raw:
            return cls._raw[achievement]
        keys = [k for k in cls._raw if k <= achievement]
        if not keys:
            return cls.get(0)  # achievement < 0 的情况，返回最低称号信息
        return cls._raw[max(keys)]

    # text: achievement -> info.text

    @classmethod
    def _text(cls, achievement: Achievement, index: str, *, default: Optional[str] = None) -> Optional[str]:
        """根据 `Achievement` 获取 `AchievementRateInfo` 的指定文本属性"""
        info = cls.get(achievement)
        if info is None:
            return default
        return getattr(info, index, default)

    @classmethod
    def text_main_name(cls, achievement: Achievement, *, default: Optional[str] = None) -> Optional[str]:
        """根据 `Achievement` 获取 `AchievementRateInfo.main_name`"""
        return cls._text(achievement, index='main_name', default=default)

    # find: name -> achievement/info

    @classmethod
    def find_achievement(cls, name: str) -> Optional[Achievement]:
        """根据 称号名/别名 获取 `Achievement`"""
        return cls._index_name_achievement.get(normalize(name))

    @classmethod
    def find(cls, name: str) -> Optional[AchievementRateInfo]:
        """根据 称号名/别名 获取 `AchievementRateInfo`"""
        achievement = cls.find_achievement(name)
        return cls.get(achievement) if achievement is not None else None

    # 功能性方法
    
    @classmethod
    def rate(cls, achievement: Achievement | AchievementRateInfo) -> Literal['S', 'A', 'B']:
        """根据 `Achievement` 获取称号等级（S/A/B）"""
        info: AchievementRateInfo
        if isinstance(achievement, Achievement):
            info = cls.get(achievement)
        else:
            info = achievement

        achievement_value = cls.find_achievement(info.main_name)
        if achievement_value is None:
            achievement_value = 0

        if achievement_value >= 970000:
            return 'S'
        elif achievement_value >= 800000:
            return 'A'
        else:
            return 'B'
