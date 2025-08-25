from datetime import datetime
from hashlib import sha256


MAIN_FORTUNE_WEIGHTS = [
    ("大吉", 6),
    ("吉", 14),
    ("中吉", 12),
    ("小吉", 12),
    ("平吉", 12),
    ("小凶", 4),
    ("凶", 3),
    ("大凶", 1),
]
SUB_FORTUNE_WEIGHTS = [
    ("大吉", 2),
    ("小吉", 3),
    ("平吉", 2),
    ("小凶", 1),
]
MAX_SUB_FORTUNE_COUNT = 80


def _get_daily_seed(user_id: int, date_str: str) -> int:
    src = f"{user_id}_{date_str}".encode("utf-8")
    hash_bytes = sha256(src).digest()
    return int.from_bytes(hash_bytes, 'big')


def _fortune_by_weight(idx: int, weights: list[tuple[str, int]]) -> str:
    acc = 0
    for name, weight in weights:
        acc += weight
        if idx < acc:
            return name
    return weights[-1][0]


def get_main_fortune(user_id: int, date: datetime) -> str:
    date_str = date.strftime("%Y%m%d")
    seed = _get_daily_seed(user_id, date_str)
    main_idx = seed & 0x3F
    title = _fortune_by_weight(main_idx, MAIN_FORTUNE_WEIGHTS)
    return title


def get_sub_fortune(user_id: int, date: datetime, count: int = 6) -> list[str]:
    if count > MAX_SUB_FORTUNE_COUNT:
        raise ValueError(f"小运势数量最大为{MAX_SUB_FORTUNE_COUNT}，当前为{count}")
    date_str = date.strftime("%Y%m%d")
    seed = _get_daily_seed(user_id, date_str)
    small_weights_acc = []
    acc = 0
    for name, w in SUB_FORTUNE_WEIGHTS:
        small_weights_acc.append((name, range(acc, acc + w)))
        acc += w
    sub_hash = seed
    result = []
    for _ in range(count):
        idx = sub_hash & 0x7
        for name, r in small_weights_acc:
            if idx in r:
                result.append(name)
                break
        sub_hash >>= 3
    return result
