import base64
import gzip
import json
import re
from typing import Any, Optional

# 定义头部匹配的正则模式
# ^ : 字符串开始
# lyra_maisync:json\.gz\.base64: : 固定前缀（点号需转义）
# v[0-9a-z.\-]+ : 版本号部分（连字符在字符组末尾无需转义，但显式转义更清晰）
# ; : 分隔符
# (.+) : 捕获组，匹配剩余的 Base64 内容
HEADER_PATTERN = re.compile(
    r'^lyra_maisync:json\.gz\.base64:v[0-9a-z.\-]+;(.+)$'
)

def parse_json_gz_b64_with_header(file_path: str) -> Any:
    """
    解析带有特定头部描述的 .json.gz.b64 文件。
    
    流程：
    1. 读取文件内容为文本字符串。
    2. 使用正则表达式剥离头部元数据。
    3. 对剩余内容进行 Base64 解码、Gzip 解压及 JSON 解析。
    
    参数:
        file_path (str): 目标文件路径。
        
    返回:
        Any: 解析后的 Python 数据结构。
        
    异常:
        ValueError: 当文件头部格式不符合预期时抛出。
        FileNotFoundError: 当文件不存在时抛出。
        Exception: 其他解码或解析错误。
    """
    try:
        # 1. 读取文件内容
        # 假设文件为 UTF-8 编码的文本流
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # 2. 正则匹配与头部剥离
        match = HEADER_PATTERN.match(raw_content.strip())
        if not match:
            raise ValueError(f"文件头部格式无效，不符合预期模式：{raw_content[:50]}...")
        
        # 获取捕获组中的 Base64 内容
        b64_payload = match.group(1)

        # 3. Base64 解码
        decoded_bytes = base64.b64decode(b64_payload)

        # 4. Gzip 解压
        json_bytes = gzip.decompress(decoded_bytes)

        # 5. JSON 解析
        json_str = json_bytes.decode('utf-8')
        data = json.loads(json_str)

        return data

    except FileNotFoundError:
        raise FileNotFoundError(f"未找到指定文件：{file_path}")
    except ValueError as ve:
        # 重新抛出自定义验证错误
        raise ve
    except Exception as e:
        raise RuntimeError(f"解析过程中发生错误：{type(e).__name__} - {str(e)}")

# 示例调用
if __name__ == "__main__":
    target_file = "temp/lyra-maisync-data-id1.json.gz.b64"
    try:
        result = parse_json_gz_b64_with_header(target_file)
        print("解析成功:")
        print(json.dumps(result, ensure_ascii=False))
    except Exception as err:
        print(f"解析失败：{err}")
