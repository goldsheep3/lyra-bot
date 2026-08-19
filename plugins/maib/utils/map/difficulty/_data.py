from dataclasses import dataclass


DifficultyID = int


@dataclass(frozen=True)
class DifficultyInfo:
    id: DifficultyID
    jp: str
    cn: str
    cn_short: str
    aliases: tuple[str, ...] = tuple()
    
    def keys(self) -> tuple[str, ...]:
        return (
            self.jp,
            self.cn,
            self.cn_short,
            *self.aliases,
        )


_di = DifficultyInfo

raw_difficulties: dict[DifficultyID, DifficultyInfo] = {
    0: _di(0, jp="UNKNOWN",   cn="未知",     cn_short="？",),
    1: _di(1, jp="EASY",      cn="简单",     cn_short="蓝",),
    2: _di(2, jp="BASIC",     cn="基础",     cn_short="绿",),
    3: _di(3, jp="ADVANCED",  cn="高级",     cn_short="黄",),
    4: _di(4, jp="EXPERT",    cn="专家",     cn_short="红",),
    5: _di(5, jp="MASTER",    cn="大师",     cn_short="紫",),
    6: _di(6, jp="Re:MASTER", cn="宗师",     cn_short="白", aliases=("REMASTER",)),
    7: _di(7, jp='U·TA·GE',   cn='宴·会·场', cn_short='宴', aliases=('宴会场', 'utage')),
}
