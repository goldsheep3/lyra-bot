from pathlib import Path
from typing import Type, Optional, Callable
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import suppress

def get_nb2_driver():
    with suppress(Exception):
        from nonebot import get_driver
        return get_driver()
    return None

class PluginRegistry:
    # 初始化类属性，防止 AttributeError
    _plugin_data_dir: Optional[Path] = None
    _plugin_cache_dir: Optional[Path] = None
    _plugin_config_dir: Optional[Path] = None
    
    _Model: Optional[Type[DeclarativeBase]] = None
    _create_session_func: Optional[Callable[[], AsyncSession]] = None

    # --- Localstore 相关 ---

    @classmethod
    def _ensure_localstore(cls):
        """统一初始化路径信息"""
        if cls._plugin_data_dir is not None:
            return

        # 默认回退路径
        base_path = Path.cwd() / "data" / "maib"
        cls._plugin_data_dir = base_path / "data"
        cls._plugin_cache_dir = base_path / "cache"
        cls._plugin_config_dir = base_path / "config"

        # 尝试从 NoneBot 插件获取
        if get_nb2_driver():
            with suppress(ImportError, RuntimeError):
                from nonebot import require
                require("nonebot_plugin_localstore")
                from nonebot_plugin_localstore import (
                    get_plugin_data_dir, 
                    get_plugin_cache_dir, 
                    get_plugin_config_dir
                )
                cls._plugin_data_dir = get_plugin_data_dir()
                cls._plugin_cache_dir = get_plugin_cache_dir()
                cls._plugin_config_dir = get_plugin_config_dir()

    @classmethod
    def get_data_dir(cls) -> Path:
        cls._ensure_localstore()
        return cls._plugin_data_dir  # type: ignore

    @classmethod
    def get_cache_dir(cls) -> Path:
        cls._ensure_localstore()
        return cls._plugin_cache_dir  # type: ignore

    @classmethod
    def get_config_dir(cls) -> Path:
        cls._ensure_localstore()
        return cls._plugin_config_dir  # type: ignore

    # --- Datastore 相关 ---

    @classmethod
    def _ensure_datastore(cls):
        """统一初始化数据库配置"""
        if cls._Model is not None:
            return

        if get_nb2_driver():
            with suppress(ImportError, RuntimeError):
                from nonebot import require
                require("nonebot_plugin_datastore")
                from nonebot_plugin_datastore import get_plugin_data, create_session
                cls._Model = get_plugin_data().Model
                cls._create_session_func = create_session  #type: ignore
                return

        # Fallback: 定义本地模型基类
        class LocalModel(DeclarativeBase):
            pass
        
        cls._Model = LocalModel
        # 注意：此处未提供非 NB 环境下的 session 逻辑，如有需要需自行配置 engine

    @classmethod
    def get_model(cls) -> Type[DeclarativeBase]:
        cls._ensure_datastore()
        return cls._Model  # type: ignore

    @classmethod
    def get_session(cls) -> AsyncSession:
        cls._ensure_datastore()
        if cls._create_session_func:  #type: ignore
            return cls._create_session_func()  #type: ignore
        
        # 抛出明确错误，而不是返回一个无法使用的空 Session
        raise RuntimeError("AsyncSession is only available when nonebot_plugin_datastore is loaded.")