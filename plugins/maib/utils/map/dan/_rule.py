from dataclasses import dataclass


@dataclass(frozen=True)
class DanRule:
    name: str
    hp: int
    great: int
    good: int
    miss: int
    clear: int


_dr = DanRule
DanLevelID = int


raw_dan_rules: dict[DanLevelID, DanRule] = {
    # 初心者
    0: _dr(name="初心者", hp=0, great=0, good=0, miss=0, clear=0),
    # 表段
    1: _dr(name="初段", hp=350, great=0, good=-2, miss=-5, clear=20),
    2: _dr(name="二段", hp=350, great=0, good=-2, miss=-5, clear=20),
    3: _dr(name="三段", hp=600, great=-1, good=-2, miss=-5, clear=50),
    4: _dr(name="四段", hp=700, great=-2, good=-2, miss=-5, clear=50),
    5: _dr(name="五段", hp=700, great=-2, good=-2, miss=-5, clear=50),
    6: _dr(name="六段", hp=700, great=-2, good=-2, miss=-5, clear=50),
    7: _dr(name="七段", hp=700, great=-2, good=-2, miss=-5, clear=50),
    8: _dr(name="八段", hp=700, great=-2, good=-2, miss=-5, clear=20),
    9: _dr(name="九段", hp=800, great=-2, good=-2, miss=-5, clear=30),
    10: _dr(name="十段", hp=900, great=-2, good=-2, miss=-5, clear=30),
    # 真段
    11: _dr(name="真初段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    12: _dr(name="真二段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    13: _dr(name="真三段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    14: _dr(name="真四段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    15: _dr(name="真五段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    16: _dr(name="真六段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    17: _dr(name="真七段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    18: _dr(name="真八段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    19: _dr(name="真九段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    20: _dr(name="真十段", hp=50, great=-2, good=-3, miss=-5, clear=10),
    # 真皆
    21: _dr(name="真皆伝", hp=50, great=-2, good=-3, miss=-5, clear=5),
    # 里皆
    22: _dr(name="裏皆伝", hp=10, great=-1, good=-3, miss=-10, clear=0),
}
