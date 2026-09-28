from ._data import VersionID
from ...enums import Server


def mapping_jp_to_cn(version_id: VersionID) -> VersionID:
    """将 JP 版本号映射为 CN 版本号"""
    
    if version_id >= 2000:
        # CN 版本号，直接返回
        return version_id
    
    elif version_id < 13:
        # maimai ~ FiNALE
        return version_id
    
    elif 13 <= version_id < 24:
        # DX (JP) ~ PRiSM
        # 日服两代折算为国服一代，DX 无印和 PLUS 对应 2020，PRiSM 对应 2025
        return (version_id - 13) // 2 + 2020

    elif version_id == 24:
        # PRiSM PLUS
        # 国服 2026 归为了彩代 PRiSM PLUS，单独处理
        return 2026

    else:  # version_id >= 25:
        # CiRCLE ~ ...
        # **推测**后续回到原有的折算规则，CiRCLE/CiRCLE PLUS 按照同样规则折算为国服 2027 一代
        # 待 2027 更新后确定规则
        return (version_id - 13) // 2 + 2021


def b50_cut_version(version_id: VersionID) -> VersionID:
    """获取 B50 分段所需的 cut_version"""
    if version_id < 24:
        return version_id
    elif 2000 > version_id >= 24:
        return version_id - 1
    else:  # version_id >= 2000:
        return version_id


def get_server(version_id: VersionID) -> Server:
    return Server.CN if version_id >= 2000 else Server.JP

def is_finale_frame(version_id: VersionID) -> bool:
    """判断是否为旧框版本"""
    return version_id <= 12
