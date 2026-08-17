from typing import Literal
from dataclasses import dataclass


@dataclass(frozen=True)
class ComboInfo:
    fullname: str
    shortname: str
    cn: str
    aliases: tuple[str, ...] = ()
    
    def keys(self) -> tuple[str, ...]:
        return (
            self.fullname,
            self.shortname,
            self.cn,
            *self.aliases,
        )
        

_ci = ComboInfo
ComboID = int


raw_combos: dict[ComboID, ComboInfo] = {
    0: _ci(fullname="",             shortname="",    cn=""),
    1: _ci(fullname="FULL COMBO",   shortname="FC",  cn="全连击"),
    2: _ci(fullname="FULL COMBO+",  shortname="FC+", cn="全连击+"),
    3: _ci(fullname="ALL PERFECT",  shortname="AP",  cn="完美无缺"),
    4: _ci(fullname="ALL PERFECT+", shortname="AP+", cn="完美无缺+"),
}