from ...type import Achievement

from dataclasses import dataclass


@dataclass(frozen=True)
class AchievementRateInfo:
    main_name: str
    aliases: tuple[str, ...] = tuple()

    def keys(self) -> tuple[str, ...]:
        """获取所有可用于查找的键"""
        return (self.main_name, *self.aliases)


_ari = AchievementRateInfo


raw_rates: dict[Achievement, AchievementRateInfo] = {
    1010000: _ari("AP+",  ("理论",)),
    1007500: _ari("AP",   ("完美无缺",)),
    1005000: _ari("SSS+", ("鸟家", "鸟加", "3S+")),
    1000000: _ari("SSS",  ("鸟S", "鸟", "3S")),
    995000:  _ari("SS+",  ("2S+",)),
    990000:  _ari("SS",   ("2S",)),
    980000:  _ari("S+",   ("1S+",)),
    970000:  _ari("S",    ("1S",)),
    940000:  _ari("AAA",  ("鸟A", "3A")),
    900000:  _ari("AA",   ("2A",)),
    800000:  _ari("A",    ("1A",)),
    750000:  _ari("BBB",  ("鸟B", "3B")),
    700000:  _ari("BB",   ("2B",)),
    600000:  _ari("B",    ("1B",)),
    500000:  _ari("C",    ("1C",)),
    0:       _ari("D",    ("1D",)),
}
