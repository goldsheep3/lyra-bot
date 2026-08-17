import re


def normalize_basic(text: str) -> str:
    """文本归一化函数"""
    text = re.sub(r"\s+", "", text.strip()).lower()
    return text
    

def normalize_eval(text: str) -> str:
    """文本归一化函数（用于 eval）"""
    if "_dummy" in text:
        # dummy 为空 eval，直接返回空字符串
        return ""
    text = normalize_basic(text)
    text = text.replace("deluxe", "dx")
    text = text.replace("plus", "p")
    text = text.replace("+", "p")
    return text


def normalize_version(text: str) -> str:
    """版本文本 归一化函数"""
    text = normalize_basic(text)
    text = text.replace("でらっくす", "dx")
    text = text.replace("+", "plus")
    
    is_dx = "dx" in text
    
    text = text[6:] if text.startswith("maimai") else text
    text = text[2:] if text.startswith("dx") else text
    
    if text == "":
        text = "dx" if is_dx else "maimai"
    if text.replace("plus", "") == "":
        text = ("dx" if is_dx else "maimai") + "plus"
    
    return text
