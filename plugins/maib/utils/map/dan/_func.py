from ..version._data import VersionID


def mapping_cn_to_jp(version_id: VersionID) -> VersionID:
    """将 CN 段位表版本号映射为 JP 段位表版本号"""
    if version_id < 15:
        raise ValueError("DXDan Starts from **Splash PLUS**")

    elif version_id < 2000:
        # jp -> jp
        return version_id
    
    elif version_id < 2023:
        raise ValueError("DXDan Starts from **DX 2023**")

    elif 2023 <= version_id < 2026:
        # dx2023 ~ dx2025
        return 2 * (version_id - 2014)
    
    elif version_id == 2026:
        # dx2026
        # 国服 2026 归为了彩代 PRiSM PLUS，单独处理
        return 23

    else:  # version_id >= 2027
        # dx2027 ~ ...
        # **推测**后续回到原有的折算规则，国服 2027 为 CiRCLE UI，折算为 CiRCLE PLUS 段位
        # 待 2027 更新后确定规则
        return 2 * (version_id - 2015)
