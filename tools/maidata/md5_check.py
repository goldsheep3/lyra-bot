import argparse
import hashlib
import json
from pathlib import Path


def calc_md5(file_path: Path, chunk_size: int = 8192) -> str:
    """计算单个文件 MD5"""
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            md5.update(chunk)  # type: ignore
    return md5.hexdigest()


def build_md5_dict(dir_path: Path) -> dict[str, str]:
    """
    扫描目录，生成 {filename: md5} 字典
    仅处理 .zip 文件
    """
    result = {}
    for file in dir_path.iterdir():
        if file.is_file() and file.suffix == ".zip":
            result[file.name] = calc_md5(file)
    return result


def save_md5_dict(md5_dict: dict, filepath: Path) -> None:
    """将 MD5 字典保存为 JSON 文件"""
    filepath.write_text(
        json.dumps(md5_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_md5_dict(filepath: Path) -> dict[str, str]:
    """从 JSON 文件加载 MD5 字典"""
    return json.loads(filepath.read_text(encoding="utf-8"))


def check_md5(
        current: dict[str, str],
        baseline: dict[str, str],
) -> tuple[set[str], set[str]]:
    """
    对比 MD5 字典

    返回：
    - missing：baseline 中存在，但 current 中不存在
    - outdated：current 中存在，但 MD5 与 baseline 不一致
    """
    missing = set()
    outdated = set()

    for name, md5 in baseline.items():
        if name not in current:
            missing.add(name)
        elif current[name] != md5:
            outdated.add(name)

    return missing, outdated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量计算并保存谱面 MD5")
    parser.add_argument("dir", type=Path, help="谱面文件目录")
    parser.add_argument("output", type=Path, help="输出 MD5 JSON 文件路径")
    args = parser.parse_args()

    md5_dict = build_md5_dict(args.dir)
    save_md5_dict(md5_dict, args.output)

    print(f"已生成 MD5 文件，共 {len(md5_dict)} 项：{args.output}")
