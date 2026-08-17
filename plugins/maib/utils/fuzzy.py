from typing import TypeVar, Optional

try:
    from thefuzz import process as thefuzz_process
except ImportError:
    thefuzz_process = None


K = TypeVar("K")

class _EMPTY:
    pass


def fuzzy_get(dict_: dict[str, K], key: str, *,
              threshold: Optional[int] = None) -> Optional[K]:
    """模糊匹配字典键，返回对应值"""
    
    value: K | _EMPTY = dict_.get(key, _EMPTY())
    if not isinstance(value, _EMPTY):
        return value

    if thefuzz_process:
        # 使用 thefuzz 库进行模糊匹配
        threshold = threshold or 85  # 默认阈值为 85
        
        match_result = thefuzz_process.extractOne(key, dict_.keys())
        if match_result and match_result[1] >= threshold:
            return dict_[match_result[0]]
    
    return None
