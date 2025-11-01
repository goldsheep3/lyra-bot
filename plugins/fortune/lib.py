import yaml
from typing import Optional


def load_yaml_data(file_path, default_data=None, logger_=None) -> Optional[dict]:
    """安全加载YAML数据文件"""
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            if logger_:
                logger_.warning(f"数据文件不存在: {file_path}")
            return default_data if default_data is not None else {}
    except Exception as e:
        if logger_:
            logger_.error(f"加载数据文件失败 {file_path}: {e}")
        return default_data if default_data is not None else {}