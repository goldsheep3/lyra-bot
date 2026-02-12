import hashlib
import json
from typing import Dict, List, Optional
from pathlib import Path


MD5 = Dict[str, str]  # {filename: md5}


def calc_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """计算单个文件 MD5"""
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)  # type: ignore
    return md5.hexdigest()


def build_md5_dict(file_paths: List[Path]) -> MD5:
    """生成 MD5 字典"""
    result = {}
    for file in file_paths:
        result[file.name] = calc_md5(file)
    return result


def load_or_save_md5(filepath: Path, md5_dict: Optional[MD5] = None) -> MD5:
    """加载或存储 MD5 字典数据"""
    if md5_dict is not None:
        filepath.write_text(
            json.dumps(md5_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    # 对于保存的情况，写入后再读取，验证保存是否成功
    # 对于加载的情况，直接读取返回
    return json.loads(filepath.read_text(encoding="utf-8"))
