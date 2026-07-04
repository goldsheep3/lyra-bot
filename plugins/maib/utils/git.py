"""utils/git.py Git 工具函数"""
import subprocess

__all__ = ["get_git_head_hash"]


def get_git_head_hash() -> str:
    """获取当前 Git 仓库的 HEAD 提交的短哈希值"""
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except subprocess.CalledProcessError:
        return ""
