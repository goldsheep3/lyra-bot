from dataclasses import dataclass


@dataclass(frozen=True)
class GenreInfo:
    jp: str
    intl: str
    cn: str
    color: str
    
    def keys(self) -> tuple[str, ...]:
        return (
            self.jp,
            self.intl,
            self.cn,
        )


_gi = GenreInfo
GenreID = int


raw_genres: dict[GenreID, GenreInfo] = {
    0: _gi(jp="POPS＆アニメ", intl="POPS&ANIME", cn="流行&动漫", color="#ff972a"),
    1: _gi(jp="niconico＆\nボーカロイド", intl="niconico&\nVOCALOID™", cn="niconico&\nVOCALOID™", color="#02c8d3"),
    2: _gi(jp="東方Project", intl="東方Project", cn="东方Project", color="#ad59ee"),
    3: _gi(jp="ゲーム＆\nバラエティ", intl="GAME&VARIETY", cn="其他游戏", color="#4be070"),
    4: _gi(jp="maimai", intl="maimai", cn="舞萌", color="#f64849"),
    5: _gi(jp="オンゲキ＆\nCHUNITHM", intl="ONGEKI&\nCHUNITHM", cn="音击&中二节奏", color="#3584fe"),
    6: _gi(jp="宴会場", intl="宴会場", cn="宴会场", color="#dc39b8"),
}
