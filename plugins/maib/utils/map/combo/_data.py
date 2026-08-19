from dataclasses import dataclass


ComboID = int


@dataclass(frozen=True)
class ComboInfo:
    id: ComboID
    full: str
    short: str
    cn: str
    aliases: tuple[str, ...] = ()
    
    def keys(self) -> tuple[str, ...]:
        return (
            self.full,
            self.short,
            self.cn,
            *self.aliases,
        )
        

_ci = ComboInfo

raw_combos: dict[ComboID, ComboInfo] = {
    0: _ci(0, full="",             short="",    cn=""),
    1: _ci(1, full="FULL COMBO",   short="FC",  cn="全连击"),
    2: _ci(2, full="FULL COMBO+",  short="FC+", cn="全连击+"),
    3: _ci(3, full="ALL PERFECT",  short="AP",  cn="完美无缺"),
    4: _ci(4, full="ALL PERFECT+", short="AP+", cn="完美无缺+"),
}