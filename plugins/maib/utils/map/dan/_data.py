from ._rule import DanLevelID
from ..version._data import VersionID
from ...enums import Difficulty
from ...type import ShortID



DanSongInfo = tuple[ShortID, Difficulty]
DanInfo = tuple[DanSongInfo, DanSongInfo, DanSongInfo, DanSongInfo]
DanVersionInfo = dict[DanLevelID, DanInfo]

D = Difficulty


# TODO 尚待获取
raw_dans: dict[VersionID, DanVersionInfo] = {
    # cir+
    26: {
        # 真七段
        17: ((11232, D.MASTER), (288, D.EXPERT), (11468, D.EXPERT), (11413, D.EXPERT)),
    },
}
