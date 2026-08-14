"""utils/exceptions.py 异常定义"""


__all__ = [
    "NoLinkQQError",
    "BlurSearchTooManyResultsError",
]


# decaption if refactor_locales
class NoLinkQQError(ValueError):
    """未绑定 QQ 号错误"""
    pass


class BlurSearchTooManyResultsError(ValueError):
    """模糊搜索结果过多错误"""
    pass