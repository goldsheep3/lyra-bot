from pathlib import Path
from typing import Type, Optional, Any
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio.session import AsyncSession
from contextlib import suppress


_driver = None


def get_nb2_driver():
    global _driver
    if _driver is not None:
        return _driver
    from nonebot import get_driver
    try:
        _driver = get_driver()
    except ValueError:
        pass
    return _driver


class PluginRegistry:
    # =================================
    # localstore 相关
    # =================================

    _plugin_data_dir: Optional[Path] = None
    _plugin_cache_dir: Optional[Path] = None
    _plugin_config_dir: Optional[Path] = None

    @classmethod
    def get_data_dir(cls) -> Optional[Path]:
        if cls._plugin_data_dir is None:
            cls.get_localstore()
        return cls._plugin_data_dir

    @classmethod
    def get_cache_dir(cls) -> Optional[Path]:
        if cls._plugin_cache_dir is None:
            cls.get_localstore()
        return cls._plugin_cache_dir

    @classmethod
    def get_config_dir(cls) -> Optional[Path]:
        if cls._plugin_config_dir is None:
            cls.get_localstore()
        return cls._plugin_config_dir

    @classmethod
    def get_localstore(cls):
        if not get_nb2_driver():
            return
        with suppress(ImportError, RuntimeError, AttributeError):
            from nonebot import require
            require("nonebot_plugin_localstore")
            from nonebot_plugin_localstore import get_plugin_data_dir, get_plugin_cache_dir, get_plugin_config_dir
    
            cls._plugin_data_dir = get_plugin_data_dir()
            cls._plugin_cache_dir = get_plugin_cache_dir()
            cls._plugin_config_dir = get_plugin_config_dir()

    # =================================
    # datastore 相关
    # =================================

    _Model: Optional[Type[DeclarativeBase]] = None
    _get_session: Optional[Any] = None

    @classmethod
    def get_model(cls) -> Type[DeclarativeBase]:
        if cls._Model is None:
            cls.get_datastore()
        if cls._Model:
            return cls._Model
        class LocalModel(DeclarativeBase):
            """本地模型（当 NoneBot 不可用时使用）"""
            __abstract__ = True
        return LocalModel

    @classmethod
    def get_session(cls) -> AsyncSession:
        if cls._get_session is None:
            cls.get_datastore()
        if cls._get_session:
            return cls._get_session()
        return AsyncSession()

    @classmethod
    def get_datastore(cls):
        if not get_nb2_driver():
            return
        with suppress(ImportError, RuntimeError, AttributeError):
            from nonebot import require
            require("nonebot_plugin_datastore")
            from nonebot_plugin_datastore import get_plugin_data, create_session
            cls._Model = get_plugin_data().Model
            cls._get_session = create_session
