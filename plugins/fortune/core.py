from datetime import datetime
from typing import List, Tuple
from hashlib import md5


FORTUNE_WEIGHTS: List[Tuple[int, str]] = [
    (400, "大吉"),
    (1000, "吉"),
    (1600, "中吉"),
    (2800, "小吉"),
    (3200, "平吉"),
    (3600, "小凶"),
    (3875, "凶"),
    (4096, "大凶"),
]


def _calc_fortune(
        user_id: str,
        date: str,
        fortune_name: str
) -> str:
    """
    使用 md5(user_id+date+fortune_name) 的第3~5位十六进制，转十进制后与权重列表判定运势。
    :param user_id: 用户ID（字符串类型）
    :param date: 日期字符串 (如"20241029")
    :param fortune_name: 运势名
    :return: 运势名字符串
    """
    weights = FORTUNE_WEIGHTS
    src = f"{user_id}_{date}_{fortune_name}".encode("utf-8")
    hash_hex = md5(src).hexdigest()
    val_hex = hash_hex[2:5]
    val_dec = int(val_hex, 16)
    for limit, name in weights:
        if val_dec < limit:
            return name
    return weights[-1][1]

def get_fortune(user_id: str, date: datetime, fortune_name: str = "main") -> str:
    """获取对应运势结果"""
    date_str = date.strftime("%Y%m%d")
    return _calc_fortune(user_id, date_str, fortune_name)

def get_fortunes(user_id: str, date: datetime, fortune_names: List[str, ...] | Tuple[str, ...]) -> list[tuple[str, str]]:
    """获取一组运势结果"""
    date_str = date.strftime("%Y%m%d")
    return [(title, _calc_fortune(user_id, date_str, title)) for title in fortune_names]

def get_text_index(user_id: str, date: datetime, text_count: int) -> int:
    """获取描述文本的随机索引"""
    date_str = date.strftime("%Y%m%d")
    src = f"{user_id}_{date_str}".encode("utf-8")
    hash_hex = md5(src).hexdigest()
    val_hex = hash_hex[2:5]
    val_dec = int(val_hex, 16)
    return val_dec % text_count