from dataclasses import dataclass


@dataclass(frozen=True)
class SyncInfo:
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


_si = SyncInfo
SyncID = int


raw_syncs: dict[SyncID, SyncInfo] = {
    0: _si(fullname="",              shortname="",     cn=""),
    1: _si(fullname="SYNC PLAY",     shortname="Sync", cn="同步游玩"),
    2: _si(fullname="FULL SYNC",     shortname="FS",   cn="全完同步"),  # SBGA 机台发包原文如此
    3: _si(fullname="FULL SYNC+",    shortname="FS+",  cn="全完同步+"),
    4: _si(fullname="FULL SYNC DX",  shortname="FDX",  cn="完全同步DX",  aliases=("FSD",)),
    5: _si(fullname="FULL SYNC DX+", shortname="FDX+", cn="完全同步DX+", aliases=("FSD+",)),
}
