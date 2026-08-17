from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyInfo:
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
DifficultyID = int


raw_difficulties: dict[DifficultyID, DifficultyInfo] = {
    0: _di(jp="UNKNOWN",   cn="未知",     cn_short="？",),
    1: _di(jp="EASY",      cn="简单",     cn_short="蓝",),
    2: _di(jp="BASIC",     cn="基础",     cn_short="绿",),
    3: _di(jp="ADVANCED",  cn="高级",     cn_short="黄",),
    4: _di(jp="EXPERT",    cn="专家",     cn_short="红",),
    5: _di(jp="MASTER",    cn="大师",     cn_short="紫",),
    6: _di(jp="Re:MASTER", cn="宗师",     cn_short="白", aliases=("REMASTER",)),
    7: _di(jp='U·TA·GE',   cn='宴·会·场', cn_short='宴', aliases=('宴会场', 'utage')),
}
