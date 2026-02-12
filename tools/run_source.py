from pathlib import Path
from typing import List, Iterable

from tools.maidata import md5_check as md5ck


def filter_by_filename(dir_path: Path, extensions: List[str]) -> Iterable[Path]:
    """使用生成器表达式过滤文件，仅扫描当前目录，匹配后缀。"""
    ext_set = {s.lower() if s.startswith('.') else f".{s.lower()}" for s in extensions}
    return (p for p in dir_path.iterdir() if p.is_file() and p.suffix.lower() in ext_set)


if __name__ == "__main__":
    dir_path: Path = Path(r"E:\adx_download\Output_MilkBot_StrictDecimal_Zip_Manifest_JsonLog_NoBGA")
    output_path: Path = Path(r"E:\adx_download\md5.json")

    file_list = list(filter_by_filename(dir_path, [".zip", ".adx"]))

    if not file_list:
        print("未在该目录下找到指定的 .zip 或 .adx 文件。")
    else:
        md5_dict = md5ck.build_md5_dict(file_list)
        new_dict = md5ck.load_or_save_md5(output_path, md5_dict)

        # 优化 3: 检查返回结果
        if new_dict == md5_dict:
            print(f"MD5 文件已同步完成，路径为：\n{output_path}")
        else:
            print("MD5 校验文件内容不匹配，请检查写入权限或 maidata 逻辑。")
