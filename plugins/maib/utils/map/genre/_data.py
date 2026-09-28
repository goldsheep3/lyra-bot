from dataclasses import dataclass


GenreID = int


@dataclass(frozen=True)
class GenreInfo:
    id: GenreID
    jp: str
    intl: str
    cn: str
    
    def keys(self) -> tuple[str, ...]:
        return (
            self.jp,
            self.intl,
            self.cn,
        )


_gi = GenreInfo

raw_genres: dict[GenreID, GenreInfo] = {
    0: _gi(0, jp="POPS＆アニメ", intl="POPS&ANIME", cn="流行&动漫"),
    1: _gi(1, jp="niconico＆\nボーカロイド", intl="niconico&\nVOCALOID™", cn="niconico&\nVOCALOID™"),
    2: _gi(2, jp="東方Project", intl="東方Project", cn="东方Project"),
    3: _gi(3, jp="ゲーム＆\nバラエティ", intl="GAME&VARIETY", cn="其他游戏"),
    4: _gi(4, jp="maimai", intl="maimai", cn="舞萌"),
    5: _gi(5, jp="オンゲキ＆\nCHUNITHM", intl="ONGEKI&\nCHUNITHM", cn="音击&中二节奏"),
    6: _gi(6, jp="宴会場", intl="宴会場", cn="宴会场"),
}
