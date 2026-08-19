from dataclasses import dataclass


SyncID = int


@dataclass(frozen=True)
class SyncInfo:
    id: SyncID
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


_si = SyncInfo

raw_syncs: dict[SyncID, SyncInfo] = {
    0: _si(0, full="",              short="",     cn=""),
    1: _si(1, full="SYNC PLAY",     short="Sync", cn="同步游玩"),
    2: _si(2, full="FULL SYNC",     short="FS",   cn="全完同步"),  # SBGA 机台发包原文如此
    3: _si(3, full="FULL SYNC+",    short="FS+",  cn="全完同步+"),
    4: _si(4, full="FULL SYNC DX",  short="FDX",  cn="完全同步DX",  aliases=("FSD",)),
    5: _si(5, full="FULL SYNC DX+", short="FDX+", cn="完全同步DX+", aliases=("FSD+",)),
}
